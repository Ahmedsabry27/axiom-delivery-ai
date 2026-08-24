from __future__ import annotations

import asyncio
import inspect
import json
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.ai.models import AIResponse
from app.auth.dependencies import get_current_user
from app.database.session import SessionLocal
from app.main import app
from app.models.conversation import Conversation
from app.models.runtime_execution import (
    RuntimeContinuation,
    RuntimeExecution,
    RuntimeExecutionEvent,
)
from app.services.runtime_execution_service import RuntimeExecutionService


class _SemanticProvider:
    def ask(self, messages):
        system = messages[0].content
        if "Classify the user's semantic intent" in system:
            payload = {
                "intent": "jira.issue.create",
                "domain": "jira",
                "operation": "create",
                "resource": "issue",
                "confidence": 1,
                "ambiguous": False,
                "ambiguity_reason": None,
                "entities": {},
                "semantic_hints": [],
                "source": "llm",
                "error_code": None,
            }
        else:
            payload = {
                "intent": "jira.issue.create",
                "parameters": {},
                "unresolved_mentions": [],
                "warnings": [],
                "source": "llm",
                "error_code": None,
            }
        return AIResponse(text=json.dumps(payload), model="production-path-test")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "prompt",
    [
        "Create Jira ticket",
        "Create a Jira ticket",
        "Create JIRA ticket",
        "Create a JIRA ticket",
        "create a jira ticket",
        "Please create a JIRA ticket",
        "Can you create a Jira issue?",
    ],
)
async def test_real_chat_api_persists_and_projects_only_canonical_jira_create_fields(
    monkeypatch,
    prompt,
):
    case_id = str(uuid4())
    runtime_service = RuntimeExecutionService()
    monkeypatch.setattr("app.api.chat.runtime_execution_service", runtime_service)
    monkeypatch.setattr("app.api.runtime.runtime_execution_service", runtime_service)
    user = {
        "sub": f"chat-path-user-{case_id}",
        "custom:tenant_id": f"chat-path-tenant-{case_id}",
        "permissions": ["runtime.execute"],
    }
    app.dependency_overrides[get_current_user] = lambda: user
    monkeypatch.setattr(
        "app.ai.factory.AIProviderFactory.get_provider",
        lambda **_: _SemanticProvider(),
    )
    downstream_calls = {
        "capability": 0,
        "agent": 0,
        "planner": 0,
        "tool": 0,
    }

    def forbidden(name):
        async def call(*_args, **_kwargs):
            downstream_calls[name] += 1
            raise AssertionError(f"{name} ran before requirements were complete")

        return call

    monkeypatch.setattr(
        runtime_service, "_resolve_capability_once", forbidden("capability")
    )
    monkeypatch.setattr(runtime_service, "_route_agent_once", forbidden("agent"))
    monkeypatch.setattr(runtime_service, "_plan_execution_once", forbidden("planner"))
    monkeypatch.setattr(runtime_service, "_execute_runtime_tool", forbidden("tool"))

    with SessionLocal() as db:
        conversation = Conversation(
            user_id=user["sub"],
            tenant_id=user["custom:tenant_id"],
            title="Fresh Jira create",
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
        conversation_id = conversation.id

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            started = await client.post(
                "/api/chat/start",
                json={
                    "message": prompt,
                    "conversation_id": str(conversation_id),
                },
            )
            assert started.status_code == 202
            execution_id = UUID(started.json()["execution_id"])

            for _ in range(100):
                await asyncio.sleep(0.01)
                with SessionLocal() as db:
                    execution = db.get(RuntimeExecution, execution_id)
                    if (
                        execution is not None
                        and execution.status == "WAITING_FOR_INPUT"
                    ):
                        break
            else:
                pytest.fail("fresh Chat runtime did not reach WAITING_FOR_INPUT")

            snapshot_response = await client.get(f"/api/runtime/{execution_id}")
            assert snapshot_response.status_code == 200
            snapshot = snapshot_response.json()
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    with SessionLocal() as db:
        execution = db.get(RuntimeExecution, execution_id)
        metadata = execution.runtime_metadata
        continuation = (
            db.query(RuntimeContinuation)
            .filter_by(execution_id=execution.id, status="pending")
            .one()
        )
        events = (
            db.query(RuntimeExecutionEvent)
            .filter_by(execution_id=execution.id)
            .order_by(RuntimeExecutionEvent.sequence)
            .all()
        )

        assert execution.status == "WAITING_FOR_INPUT"
        assert metadata["intent_analysis"]["intent"] == "jira.issue.create"
        assert metadata["parameter_extraction"]["intent"] == "jira.issue.create"
        assert metadata["parameter_state"]["intent"] == "jira.issue.create"
        assert metadata["parameter_state"]["parameters"] == {}
        assert metadata["input_requirements"]["intent"] == "jira.issue.create"
        assert metadata["input_requirements"]["schema_available"] is True
        assert metadata["input_requirements"]["complete"] is False
        assert [item["name"] for item in metadata["input_requirements"]["missing"]] == [
            "project_key",
            "issue_type",
            "summary",
        ]
        assert "capability_resolution" not in metadata
        assert "agent_routing" not in metadata

        assert continuation.schema["intent"] == "jira.issue.create"
        assert continuation.schema["requested_fields"] == [
            "project_key",
            "issue_type",
            "summary",
        ]
        assert [field["name"] for field in continuation.schema["fields"]] == [
            "project_key",
            "issue_type",
            "summary",
        ]
        assert continuation.known_values == {}

        serialized = json.dumps(
            {
                "metadata": metadata,
                "continuation": continuation.schema,
                "events": [event.payload for event in events],
                "snapshot": snapshot,
            }
        )
        assert "report_scope" not in serialized
        assert "Jira report scope" not in serialized
        assert not any(event.name == "Agent Selection" for event in events)
        assert not any(event.event_type == "runtime.failed" for event in events)
        assert [event.event_type for event in events] == [
            "runtime.started",
            "step",
            "step",
            "intent_analysis.completed",
            "parameter_extraction.completed",
            "parameter_reconciliation.completed",
            "input_requirements.evaluated",
            "runtime.waiting_for_input",
            "required_input",
        ]

    assert snapshot["continuation"]["requested_fields"] == [
        "project_key",
        "issue_type",
        "summary",
    ]
    assert [field["name"] for field in snapshot["continuation"]["fields"]] == [
        "project_key",
        "issue_type",
        "summary",
    ]
    assert downstream_calls == {"capability": 0, "agent": 0, "planner": 0, "tool": 0}
    assert Path(inspect.getfile(type(runtime_service))).resolve() == (
        Path(__file__).resolve().parents[1]
        / "app/services/runtime_execution_service.py"
    )
