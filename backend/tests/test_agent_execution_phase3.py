from __future__ import annotations

from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.agents.application_service import AgentApplicationService, AgentIdentity
from app.agents.execution_service import AgentExecutionService, ExecutionRequest
from app.ai.models import AIResponse, AIUsage
from app.database.models.agent_execution import AgentContinuation, AgentExecution
from app.database.models.knowledge_source import KnowledgeSource
from app.database.models.tool import ToolDefinition, ToolExecution
from app.database.models.tool_discovery import ToolDiscoveryEvent
from app.models.conversation import Conversation
from app.services.runtime_execution_service import RuntimeExecutionService


def actor(actor_id="operator", tenant="tenant-a", extra=()):
    return AgentIdentity(
        actor_id,
        tenant,
        frozenset(
            {
                "agents.list",
                "agents.read",
                "agents.create",
                "agents.update",
                "agents.publish",
                "agents.enable",
                "agents.execute",
                "agents.tools.manage",
                "agents.knowledge.manage",
                "agents.executions.read",
                "deployment.reports.create",
                *extra,
            }
        ),
        frozenset(),
    )


def configured(name="Runtime Agent"):
    return {
        "name": name,
        "instructions": "UNIQUE_SAFE_GUIDANCE: finish with verified evidence.",
        "model_configuration": {
            "provider": "openai",
            "model": "gpt-4.1-mini",
            "temperature": 0.1,
        },
        "planner_configuration": {"name": "default"},
        "execution_limits": {"max_steps": 4, "timeout_seconds": 20, "cost_limit": 2.0},
    }


def catalog_tool():
    return ToolDefinition(
        tenant_id="tenant-a",
        name="deployment_report",
        display_name="Deployment Report",
        description="Generate deployment report",
        category="operations",
        provider="native",
        version="1.0.0",
        input_schema={},
        permissions=["deployment.reports.create"],
        risk_level="write",
        enabled=True,
        active=True,
        configuration_state="ready",
    )


def enabled_agent(db, *, with_tool=False, with_knowledge=False, approval=False):
    service = AgentApplicationService()
    identity = actor()
    row = service.create(db, identity, configured())
    if with_tool:
        db.add(catalog_tool())
        db.commit()
        service.set_tools(
            db,
            identity,
            row.uuid,
            [
                {
                    "tool_name": "deployment_report",
                    "version_restriction": "1.0.0",
                    "assignment_action": "execute",
                    "enabled": True,
                    "risk_mode": "write",
                    "approval_required": approval,
                }
            ],
        )
    source = None
    if with_knowledge:
        source = KnowledgeSource(
            tenant_id="tenant-a",
            owner_id="operator",
            name="Release Runbook",
            source_type="DOCUMENT",
            readiness_status="ready",
        )
        db.add(source)
        db.commit()
        service.set_knowledge(
            db,
            identity,
            row.uuid,
            [
                {
                    "knowledge_source_id": source.id,
                    "access_mode": "retrieve",
                    "readiness_required": True,
                    "enabled": True,
                }
            ],
        )
    row = service.publish(
        db, identity, row.uuid, row.lock_version, "Published for execution"
    )
    row = service.lifecycle(db, identity, row.uuid, "enable", row.lock_version)
    return row, source


def test_low_confidence_auto_routing_uses_default_fallback(db_session):
    row, _ = enabled_agent(db_session)
    selected, candidates = RuntimeExecutionService._select_agent(
        db_session,
        tenant_id="tenant-a",
        goal="Generate Deployment Report",
        requested_agent_id=None,
        identity=actor(),
    )
    assert candidates
    assert candidates[0]["confidence"] < 0.55
    assert selected is None
    explicit, _ = RuntimeExecutionService._select_agent(
        db_session,
        tenant_id="tenant-a",
        goal="Generate Deployment Report",
        requested_agent_id=row.uuid,
        identity=actor(),
    )
    assert explicit["agent_id"] == row.uuid
    assert explicit["confidence"] == 1.0


@pytest.mark.asyncio
async def test_published_instructions_model_planner_and_knowledge_affect_result(
    db_session,
    monkeypatch,
):
    class Provider:
        def ask(self, *, messages):
            instructions = messages[0].content.split("Published agent instructions:\n")[
                -1
            ]
            return AIResponse(
                text=f"Verified result. {instructions}",
                response_id="response-1",
                model="gpt-4.1-mini",
                usage=AIUsage(10, 5, 15),
            )

    monkeypatch.setattr(
        "app.agents.execution_service.AIProviderFactory.get_provider",
        lambda **_: Provider(),
    )
    row, source = enabled_agent(db_session, with_knowledge=True)
    result = await AgentExecutionService().start(
        db_session,
        agent_id=row.uuid,
        request=ExecutionRequest(message="Summarize release readiness", inputs={}),
        identity=actor(),
    )
    assert result["status"] == "succeeded"
    assert "UNIQUE_SAFE_GUIDANCE" in result["result"]["message"]
    assert result["agent_version"] == row.published_version == 1
    assert result["knowledge_source_ids"] == [source.id]
    assert result["result"]["citations"][0]["trust"] == "untrusted_data"
    persisted = db_session.get(AgentExecution, result["execution_id"])
    assert (persisted.model_provider, persisted.model_name, persisted.planner) == (
        "openai",
        "gpt-4.1-mini",
        "default",
    )
    assert persisted.runtime_metadata["prompt_precedence"][0] == "platform_security"


@pytest.mark.asyncio
async def test_deployment_report_input_resume_links_discovery_and_tool_execution(
    db_session,
):
    row, _ = enabled_agent(db_session, with_tool=True)
    service = AgentExecutionService()
    result = await service.start(
        db_session,
        agent_id=row.uuid,
        request=ExecutionRequest(message="Generate a deployment report", inputs={}),
        identity=actor(),
    )
    assert result["status"] == "waiting_for_input"
    assert set(result["continuation"]["missing_fields"]) == {
        "project_name",
        "release_version",
        "environment",
        "status",
    }
    token = result["continuation"]["resume_token"]
    assert token not in db_session.query(AgentContinuation).one().resume_token_hash
    completed = await service.resume(
        db_session,
        execution_id=result["execution_id"],
        token=token,
        response={
            "project_name": "Copilot",
            "release_version": "3.0.0",
            "environment": "production",
            "status": "succeeded",
        },
        identity=actor(),
        action="input",
    )
    assert completed["status"] == "succeeded"
    assert "Deployment Report: Copilot" in completed["result"]["message"]
    assert db_session.query(ToolExecution).filter_by(agent_id=row.uuid).count() == 1
    discovery = db_session.query(ToolDiscoveryEvent).one()
    assert discovery.execution_id == completed["execution_id"]
    with pytest.raises(HTTPException) as replay:
        await service.resume(
            db_session,
            execution_id=result["execution_id"],
            token=token,
            response={},
            identity=actor(),
            action="input",
        )
    assert replay.value.detail["code"] == "CONTINUATION_ALREADY_USED"


@pytest.mark.asyncio
async def test_runtime_accepts_string_conversation_id_and_global_native_tool(
    db_session,
):
    row, _ = enabled_agent(db_session, with_tool=True)
    catalog = (
        db_session.query(ToolDefinition)
        .filter_by(tenant_id="tenant-a", name="deployment_report")
        .one()
    )
    catalog.tenant_id = "default"
    catalog.registration_source = "native"
    conversation = Conversation(
        id=uuid4(),
        title="Governed runtime",
        user_id="operator",
        tenant_id="tenant-a",
    )
    db_session.add(conversation)
    db_session.commit()

    result = await AgentExecutionService().start(
        db_session,
        agent_id=row.uuid,
        request=ExecutionRequest(
            message="Generate a deployment report",
            inputs={
                "project_name": "Atlas",
                "release_version": "1.2",
                "environment": "staging",
                "status": "succeeded",
            },
            conversation_id=str(conversation.id),
            selected_tool="deployment_report",
        ),
        identity=actor(),
    )

    assert result["status"] == "succeeded"
    assert result["conversation_id"] == str(conversation.id)
    assert "Deployment Report: Atlas" in result["result"]["message"]


@pytest.mark.asyncio
async def test_runtime_revocation_and_cross_tenant_access_fail_closed(db_session):
    row, _ = enabled_agent(db_session, with_tool=True)
    service = AgentExecutionService()
    pending = await service.start(
        db_session,
        agent_id=row.uuid,
        request=ExecutionRequest(message="Generate a deployment report", inputs={}),
        identity=actor(),
    )
    catalog = db_session.query(ToolDefinition).filter_by(name="deployment_report").one()
    catalog.enabled = False
    db_session.commit()
    with pytest.raises(HTTPException) as revoked:
        await service.resume(
            db_session,
            execution_id=pending["execution_id"],
            token=pending["continuation"]["resume_token"],
            response={
                "project_name": "X",
                "release_version": "1",
                "environment": "staging",
                "status": "succeeded",
            },
            identity=actor(),
            action="input",
        )
    assert revoked.value.detail["code"] == "ASSIGNED_TOOL_UNAVAILABLE"
    with pytest.raises(HTTPException) as isolated:
        service.get(db_session, actor(tenant="tenant-b"), pending["execution_id"])
    assert isolated.value.status_code == 404


@pytest.mark.asyncio
async def test_cancellation_is_durable_idempotent_and_blocks_resume(db_session):
    row, _ = enabled_agent(db_session, with_tool=True)
    service = AgentExecutionService()
    pending = await service.start(
        db_session,
        agent_id=row.uuid,
        request=ExecutionRequest(message="Generate a deployment report", inputs={}),
        identity=actor(),
    )
    first = service.cancel(db_session, actor(), pending["execution_id"])
    second = service.cancel(db_session, actor(), pending["execution_id"])
    assert first["status"] == second["status"] == "cancelled"
    assert db_session.query(AgentContinuation).one().status == "cancelled"
    with pytest.raises(HTTPException) as denied:
        service.cancel(db_session, actor("other"), pending["execution_id"])
    assert denied.value.status_code == 403


@pytest.mark.asyncio
async def test_clarification_is_authorized_validated_and_resumes_same_execution(
    db_session,
):
    row, _ = enabled_agent(db_session, with_tool=True)
    service = AgentExecutionService()
    pending = await service.start(
        db_session,
        agent_id=row.uuid,
        request=ExecutionRequest(
            message="Which tool should create this report?", inputs={}
        ),
        identity=actor(),
    )
    assert pending["status"] == "waiting_for_clarification"
    with pytest.raises(HTTPException) as invalid:
        await service.resume(
            db_session,
            execution_id=pending["execution_id"],
            token=pending["continuation"]["resume_token"],
            response={"selected_tool": "unauthorized_tool"},
            identity=actor(),
            action="clarification",
        )
    assert invalid.value.detail["code"] == "INVALID_CLARIFICATION"
    resumed = await service.resume(
        db_session,
        execution_id=pending["execution_id"],
        token=pending["continuation"]["resume_token"],
        response={"selected_tool": "deployment_report"},
        identity=actor(),
        action="clarification",
    )
    assert resumed["execution_id"] == pending["execution_id"]
    assert resumed["status"] == "waiting_for_input"


@pytest.mark.asyncio
async def test_approval_requires_separation_permission_and_is_one_time(db_session):
    row, _ = enabled_agent(db_session, with_tool=True, approval=True)
    service = AgentExecutionService()
    inputs = {
        "project_name": "Copilot",
        "release_version": "3",
        "environment": "production",
        "status": "succeeded",
    }
    pending = await service.start(
        db_session,
        agent_id=row.uuid,
        request=ExecutionRequest(message="Generate a deployment report", inputs=inputs),
        identity=actor(),
    )
    assert pending["status"] == "waiting_for_approval"
    with pytest.raises(HTTPException) as self_approval:
        await service.resume(
            db_session,
            execution_id=pending["execution_id"],
            token=pending["continuation"]["resume_token"],
            response={},
            identity=actor(),
            action="approve",
        )
    assert self_approval.value.detail["code"] == "APPROVER_SEPARATION_REQUIRED"
    approver = actor("approver", extra={"agents.approve"})
    completed = await service.resume(
        db_session,
        execution_id=pending["execution_id"],
        token=pending["continuation"]["resume_token"],
        response={"reason": "Change approved"},
        identity=approver,
        action="approve",
    )
    assert completed["status"] == "succeeded"
    with pytest.raises(HTTPException) as replay:
        await service.resume(
            db_session,
            execution_id=pending["execution_id"],
            token=pending["continuation"]["resume_token"],
            response={},
            identity=approver,
            action="approve",
        )
    assert replay.value.detail["code"] == "CONTINUATION_ALREADY_USED"
