from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.agents.application_service import AgentIdentity
from app.database.session import SessionLocal
from app.integrations.jira import CAPABILITIES
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.runtime_execution import RuntimeContinuation, RuntimeExecution
from app.runtime.continuation_interpreter import (
    ContinuationFieldValue,
    ContinuationInterpretationResult,
)
from app.runtime.input_requirements import (
    MissingFieldResolver,
    RequirementSchemaProvider,
)
from app.runtime.parameter_reconciler import CanonicalParameter, ParameterState
from app.services.runtime_execution_service import RuntimeExecutionService

JIRA_CREATE = next(item for item in CAPABILITIES if item.name == "jira.create_issue")


def _parameter(name, value):
    return CanonicalParameter(
        name=name,
        value=value,
        value_type="string",
        source="user_prompt",
        confidence=1,
        explicit=True,
        status="RESOLVED",
    )


def _waiting_runtime(db, *, state_version=1, parameters=None):
    state = ParameterState(
        intent="jira.issue.create",
        parameters=(
            {"project_key": _parameter("project_key", "KAN")}
            if parameters is None
            else parameters
        ),
        version=state_version,
    )
    definition = [
        {
            "type": "function",
            "function": {
                "name": JIRA_CREATE.name,
                "description": JIRA_CREATE.description,
                "parameters": JIRA_CREATE.input_schema,
            },
        }
    ]
    schema = RequirementSchemaProvider().get("jira.issue.create", definition)
    requirements = MissingFieldResolver().evaluate(state, schema)
    requirement_payload = requirements.model_dump(mode="json")
    requirement_payload["parameter_state_version"] = state_version
    execution = RuntimeExecution(
        id=uuid4(),
        conversation_id=uuid4(),
        workflow_id=uuid4(),
        user_id="user-1",
        tenant_id="tenant-1",
        goal="Create a Jira ticket",
        status="WAITING_FOR_INPUT",
        state_version=2,
        provider_name="openai",
        model_name="test-model",
        started_at=datetime.now(UTC).replace(tzinfo=None),
        runtime_metadata={
            "intent_analysis": {
                "intent": "jira.issue.create",
                "domain": "jira",
                "operation": "create",
                "resource": "issue",
                "confidence": 1,
                "ambiguous": False,
                "ambiguity_reason": None,
                "entities": {},
                "semantic_hints": [],
                "source": "deterministic",
                "error_code": None,
            },
            "parameter_state": state.model_dump(mode="json"),
            "input_requirements": requirement_payload,
            "permissions": [],
        },
    )
    service = RuntimeExecutionService()
    fields = service._requirement_fields(requirement_payload)
    known_values = {
        name: item.value
        for name, item in state.parameters.items()
        if item.status == "RESOLVED"
    }
    continuation = service._build_input_continuation(
        execution,
        fields,
        known_values,
        parameter_state_version=state_version,
        input_requirements=requirement_payload,
    )
    db.add_all([execution, continuation])
    db.commit()
    return service, execution, continuation


@pytest.fixture
def quiet_service(monkeypatch):
    async def publish(*_args, **_kwargs):
        return None

    async def execute(*_args, **_kwargs):
        return None

    monkeypatch.setattr(RuntimeExecutionService, "publish_event", publish)
    monkeypatch.setattr(RuntimeExecutionService, "_execute_with_deadline", execute)


@pytest.mark.asyncio
async def test_structured_reply_completes_same_execution(db_session, quiet_service):
    service, execution, continuation = _waiting_runtime(db_session)
    original_id = execution.id
    resumed = await service.continue_execution(
        db_session,
        execution_id=execution.id,
        user_id="user-1",
        tenant_id="tenant-1",
        continuation_id=continuation.id,
        values={"issue_type": "Task", "summary": "Payment timeout"},
    )
    db_session.refresh(resumed)
    assert resumed.id == original_id
    assert resumed.status == "RUNNING"
    assert resumed.runtime_metadata["parameter_state"]["version"] == 2
    assert resumed.runtime_metadata["inputs"] == {
        "issue_type": "Task",
        "project_key": "KAN",
        "summary": "Payment timeout",
    }
    assert db_session.query(RuntimeExecution).count() == 1
    assert continuation.status == "consumed"


@pytest.mark.asyncio
async def test_partial_reply_creates_next_round_on_same_execution(
    db_session, quiet_service
):
    service, execution, continuation = _waiting_runtime(db_session)
    resumed = await service.continue_execution(
        db_session,
        execution_id=execution.id,
        user_id="user-1",
        tenant_id="tenant-1",
        continuation_id=continuation.id,
        values={"issue_type": "Task"},
    )
    db_session.refresh(resumed)
    pending = db_session.query(RuntimeContinuation).filter_by(status="pending").one()
    assert resumed.status == "WAITING_FOR_INPUT"
    assert pending.id != continuation.id
    assert pending.schema["parameter_state_version"] == 2
    assert [field["name"] for field in pending.schema["fields"]] == ["summary"]
    assert db_session.query(RuntimeExecution).count() == 1


@pytest.mark.asyncio
async def test_three_round_jira_continuation_retains_all_prior_values(
    db_session, quiet_service
):
    service, execution, continuation = _waiting_runtime(db_session, parameters={})
    original_id = execution.id
    expected_remaining = [
        ["issue_type", "summary"],
        ["summary"],
        [],
    ]
    for values, remaining in zip(
        ({"project_key": "KAN"}, {"issue_type": "Task"}, {"summary": "Login failure"}),
        expected_remaining,
        strict=True,
    ):
        resumed = await service.continue_execution(
            db_session,
            execution_id=original_id,
            user_id="user-1",
            tenant_id="tenant-1",
            continuation_id=continuation.id,
            values=values,
        )
        db_session.refresh(resumed)
        assert resumed.id == original_id
        assert (
            resumed.runtime_metadata["parameter_state"]["intent"] == "jira.issue.create"
        )
        resolved = {
            name: item["value"]
            for name, item in resumed.runtime_metadata["parameter_state"][
                "parameters"
            ].items()
        }
        for name, value in values.items():
            assert resolved[name] == value
        pending = (
            db_session.query(RuntimeContinuation).filter_by(status="pending").all()
        )
        assert len(pending) == (1 if remaining else 0)
        if remaining:
            continuation = pending[0]
            assert [
                field["name"] for field in continuation.schema["fields"]
            ] == remaining
    assert resolved == {
        "project_key": "KAN",
        "issue_type": "Task",
        "summary": "Login failure",
    }
    assert resumed.runtime_metadata["parameter_state"]["version"] == 4
    assert resumed.status == "RUNNING"
    assert db_session.query(RuntimeExecution).count() == 1


@pytest.mark.asyncio
async def test_invalid_reply_is_nonterminal_and_preserves_continuation(
    db_session, quiet_service
):
    service, execution, continuation = _waiting_runtime(db_session)
    continuation.schema = {
        **continuation.schema,
        "fields": [
            {
                "name": "issue_type",
                "label": "Issue Type",
                "type": "select",
                "required": True,
                "options": ["Task", "Bug"],
                "validation": {"type": "string", "enum": ["Task", "Bug"]},
            }
        ],
    }
    db_session.commit()
    resumed = await service.continue_execution(
        db_session,
        execution_id=execution.id,
        user_id="user-1",
        tenant_id="tenant-1",
        continuation_id=continuation.id,
        values={"issue_type": "Incident"},
    )
    db_session.refresh(continuation)
    assert resumed.status == "WAITING_FOR_INPUT"
    assert continuation.status == "pending"
    assert continuation.schema["validation_feedback"]["invalid_fields"] == [
        "issue_type"
    ]


@pytest.mark.asyncio
async def test_cancel_is_terminal_and_duplicate_submission_is_rejected(
    db_session, quiet_service
):
    service, execution, continuation = _waiting_runtime(db_session)
    cancelled = await service.continue_execution(
        db_session,
        execution_id=execution.id,
        user_id="user-1",
        tenant_id="tenant-1",
        continuation_id=continuation.id,
        values={},
        message="never mind",
    )
    assert cancelled.status == "CANCELLED"
    assert continuation.status == "cancelled"
    with pytest.raises(ValueError, match="WAITING_FOR_INPUT"):
        await service.continue_execution(
            db_session,
            execution_id=execution.id,
            user_id="user-1",
            tenant_id="tenant-1",
            continuation_id=continuation.id,
            values={},
            message="Task",
        )


@pytest.mark.asyncio
async def test_new_request_abandons_legacy_continuation_and_starts_one_replacement(
    db_session, quiet_service
):
    conversation_id = uuid4()
    execution = RuntimeExecution(
        id=uuid4(),
        conversation_id=conversation_id,
        workflow_id=uuid4(),
        user_id="user-1",
        tenant_id="tenant-1",
        goal="Generate Jira report",
        status="WAITING_FOR_INPUT",
        state_version=2,
        provider_name="openai",
        model_name="test-model",
        started_at=datetime.now(UTC).replace(tzinfo=None),
        runtime_metadata={
            # Deliberately inconsistent legacy semantic state: abandonment must
            # remain available even though applying an answer would fail closed.
            "intent_analysis": {"intent": "jira.report.generate"},
            "parameter_state": {
                "intent": "legacy.report.intent",
                "parameters": {},
                "version": 1,
            },
            "input_requirements": {"intent": "jira.report.generate"},
            "permissions": ["runtime.execute"],
        },
    )
    continuation = RuntimeContinuation(
        execution_id=execution.id,
        tenant_id="tenant-1",
        kind="input",
        schema={
            "intent": "jira.report.generate",
            "parameter_state_version": 1,
            "fields": [
                {
                    "name": "jira_report_scope",
                    "label": "Jira report scope",
                    "type": "text",
                    "required": True,
                }
            ],
        },
        known_values={},
        expires_at=datetime.now(UTC).replace(tzinfo=None) + timedelta(hours=1),
    )
    db_session.add_all(
        [
            Conversation(
                id=conversation_id,
                user_id="user-1",
                tenant_id="tenant-1",
                title="Jira report",
            ),
            execution,
            continuation,
        ]
    )
    db_session.commit()

    service = RuntimeExecutionService()
    replacement = await service.continue_execution(
        db_session,
        execution_id=execution.id,
        user_id="user-1",
        tenant_id="tenant-1",
        continuation_id=continuation.id,
        values={},
        message="Create a Jira ticket",
        resume_identity=AgentIdentity(
            actor_id="user-1",
            tenant_id="tenant-1",
            permissions=frozenset({"runtime.execute"}),
            groups=frozenset(),
        ),
    )

    db_session.refresh(execution)
    db_session.refresh(continuation)
    assert execution.status == "CANCELLED"
    assert continuation.status == "cancelled"
    assert replacement.id != execution.id
    assert replacement.conversation_id == conversation_id
    assert replacement.goal == "Create a Jira ticket"
    assert replacement.runtime_metadata["continuation_handoff"] == {
        "cancelled_execution_id": str(execution.id),
        "old_intent": "jira.report.generate",
    }
    assert db_session.query(RuntimeExecution).count() == 2
    assert (
        db_session.query(Message)
        .filter_by(conversation_id=conversation_id, content="Create a Jira ticket")
        .count()
        == 1
    )

    with pytest.raises(ValueError, match="WAITING_FOR_INPUT"):
        await service.continue_execution(
            db_session,
            execution_id=execution.id,
            user_id="user-1",
            tenant_id="tenant-1",
            continuation_id=continuation.id,
            values={},
            message="Create a Jira ticket",
        )
    assert db_session.query(RuntimeExecution).count() == 2


@pytest.mark.asyncio
async def test_stale_parameter_version_is_rejected(db_session, quiet_service):
    service, execution, continuation = _waiting_runtime(db_session, state_version=2)
    continuation.schema = {**continuation.schema, "parameter_state_version": 1}
    db_session.commit()
    with pytest.raises(ValueError, match="stale"):
        await service.continue_execution(
            db_session,
            execution_id=execution.id,
            user_id="user-1",
            tenant_id="tenant-1",
            continuation_id=continuation.id,
            values={"issue_type": "Task"},
        )
    assert continuation.status == "pending"


@pytest.mark.asyncio
async def test_production_continuation_preserves_jira_create_semantics(
    db_session, quiet_service, monkeypatch
):
    state = ParameterState(
        intent="jira.issue.create",
        parameters={"project_key": _parameter("project_key", "KAN")},
    )
    definition = [
        {
            "type": "function",
            "function": {
                "name": JIRA_CREATE.name,
                "description": JIRA_CREATE.description,
                "parameters": JIRA_CREATE.input_schema,
            },
        }
    ]
    schema = RequirementSchemaProvider().get("jira.issue.create", definition)
    requirements = MissingFieldResolver().evaluate(state, schema)
    requirement_payload = requirements.model_dump(mode="json")
    requirement_payload["parameter_state_version"] = state.version
    execution = RuntimeExecution(
        id=uuid4(),
        conversation_id=uuid4(),
        workflow_id=uuid4(),
        user_id="user-1",
        tenant_id="tenant-1",
        goal="Create Jira ticket in KAN",
        status="WAITING_FOR_INPUT",
        state_version=2,
        provider_name="openai",
        model_name="test-model",
        started_at=datetime.now(UTC).replace(tzinfo=None),
        runtime_metadata={
            "intent_analysis": {
                "intent": "jira.issue.create",
                "domain": "jira",
                "operation": "create",
                "resource": "issue",
                "confidence": 1,
                "ambiguous": False,
                "ambiguity_reason": None,
                "entities": {},
                "semantic_hints": [],
                "source": "deterministic",
                "error_code": None,
            },
            "parameter_state": state.model_dump(mode="json"),
            "input_requirements": requirement_payload,
            "intent": {"intent": "jira.report.generate", "domain": "jira"},
            "permissions": [],
        },
    )
    continuation = RuntimeExecutionService._build_input_continuation(
        execution,
        RuntimeExecutionService._requirement_fields(requirement_payload),
        {"project_key": "KAN"},
        parameter_state_version=state.version,
        input_requirements=requirement_payload,
    )
    db_session.add_all([execution, continuation])
    db_session.commit()
    assert continuation.schema["intent"] == "jira.issue.create"
    assert continuation.schema["title"] == "Jira Issue details required"
    assert [item["name"] for item in continuation.schema["fields"]] == [
        "issue_type",
        "summary",
    ]
    monkeypatch.setattr(
        "app.services.runtime_execution_service.continuation_interpreter.interpret_natural_language",
        lambda *_args, **_kwargs: ContinuationInterpretationResult(
            values={
                "issue_type": ContinuationFieldValue(
                    name="issue_type", value="Task", value_type="string", confidence=1
                ),
                "summary": ContinuationFieldValue(
                    name="summary",
                    value="Login failure",
                    value_type="string",
                    confidence=1,
                ),
            }
        ),
    )
    resumed = await RuntimeExecutionService().continue_execution(
        db_session,
        execution_id=execution.id,
        user_id="user-1",
        tenant_id="tenant-1",
        continuation_id=continuation.id,
        values={},
        message="Task, summary is Login failure",
    )
    db_session.refresh(resumed)
    next_state = resumed.runtime_metadata["parameter_state"]
    assert resumed.id == execution.id and resumed.status == "RUNNING"
    assert next_state["intent"] == "jira.issue.create" and next_state["version"] == 2
    assert {name: item["value"] for name, item in next_state["parameters"].items()} == {
        "project_key": "KAN",
        "issue_type": "Task",
        "summary": "Login failure",
    }
    assert resumed.runtime_metadata["input_requirements"]["complete"] is True
    assert (
        db_session.query(RuntimeContinuation).filter_by(status="pending").count() == 0
    )


@pytest.mark.asyncio
async def test_incomplete_production_pipeline_stops_before_capability_and_agent(
    monkeypatch,
):
    service = RuntimeExecutionService()
    execution_id = uuid4()
    with SessionLocal() as db:
        execution = RuntimeExecution(
            id=execution_id,
            conversation_id=uuid4(),
            workflow_id=uuid4(),
            user_id="user-gate",
            tenant_id="tenant-gate",
            goal="Create Jira ticket",
            status="RUNNING",
            state_version=1,
            provider_name="openai",
            model_name="test-model",
            started_at=datetime.now(UTC).replace(tzinfo=None),
            lease_owner=service.worker_id,
            attempt=1,
            lease_expires_at=(datetime.now(UTC) + timedelta(minutes=5)).replace(
                tzinfo=None
            ),
            heartbeat_at=datetime.now(UTC).replace(tzinfo=None),
            runtime_metadata={"permissions": []},
            steps=[],
            token_usage={},
        )
        db.add(execution)
        db.commit()
        db.refresh(execution)
    service._owned_attempts[str(execution_id)] = 1
    intent = {
        "intent": "jira.issue.create",
        "domain": "jira",
        "operation": "create",
        "resource": "issue",
        "confidence": 1,
        "ambiguous": False,
        "ambiguity_reason": None,
        "entities": {},
        "semantic_hints": [],
        "source": "deterministic",
        "error_code": None,
    }
    extraction = {
        "intent": "jira.issue.create",
        "parameters": {},
        "unresolved_mentions": [],
        "warnings": [],
        "source": "llm",
        "error_code": None,
    }
    canonical = ParameterState(intent="jira.issue.create", parameters={}).model_dump(
        mode="json"
    )

    async def classify(*_args, **_kwargs):
        return intent

    async def extract(*_args, **_kwargs):
        return extraction

    async def reconcile(*_args, **_kwargs):
        return canonical

    async def forbidden(*_args, **_kwargs):
        pytest.fail("downstream stage ran early")

    events = []

    async def capture_event(_execution_id, event):
        events.append(event)

    async def capture_step(_execution_id, name, *_args, **_kwargs):
        events.append({"name": name})

    monkeypatch.setattr(service, "_load_conversation_context", lambda *_: [])
    monkeypatch.setattr(service, "_classify_intent_once", classify)
    monkeypatch.setattr(service, "_extract_parameters_once", extract)
    monkeypatch.setattr(service, "_reconcile_parameters_once", reconcile)
    monkeypatch.setattr(service, "_resolve_capability_once", forbidden)
    monkeypatch.setattr(service, "_route_agent_once", forbidden)
    monkeypatch.setattr(service, "_plan_execution_once", forbidden)
    monkeypatch.setattr(service, "_execute_runtime_tool", forbidden)
    monkeypatch.setattr(service, "publish_event", capture_event)
    monkeypatch.setattr(service, "publish_step", capture_step)
    await service._execute(
        execution,
        "Create Jira ticket",
        set(),
        "tenant-gate",
        "openai",
        "test-model",
        None,
        {},
    )
    with SessionLocal() as db:
        stored = db.get(RuntimeExecution, execution_id)
        continuation = (
            db.query(RuntimeContinuation)
            .filter_by(execution_id=execution_id, status="pending")
            .one()
        )
        assert stored.status == "WAITING_FOR_INPUT"
        assert stored.runtime_metadata["input_requirements"]["complete"] is False
        assert continuation.schema["intent"] == "jira.issue.create"
        assert [field["name"] for field in continuation.schema["fields"]] == [
            "project_key",
            "issue_type",
            "summary",
        ]
        assert continuation.known_values == {}
        assert "capability_resolution" not in stored.runtime_metadata
        assert "agent_routing" not in stored.runtime_metadata
        assert "execution_plan" not in stored.runtime_metadata
    assert not any(event.get("name") == "Agent Selection" for event in events)


@pytest.mark.asyncio
async def test_unknown_requirement_schema_fails_closed_before_capability(monkeypatch):
    service = RuntimeExecutionService()
    execution_id = uuid4()
    with SessionLocal() as db:
        execution = RuntimeExecution(
            id=execution_id,
            conversation_id=uuid4(),
            workflow_id=uuid4(),
            user_id="user-unknown-schema",
            tenant_id="tenant-gate",
            goal="Unsupported migrated request",
            status="RUNNING",
            state_version=1,
            provider_name="openai",
            model_name="test-model",
            started_at=datetime.now(UTC).replace(tzinfo=None),
            lease_owner=service.worker_id,
            attempt=1,
            lease_expires_at=(datetime.now(UTC) + timedelta(minutes=5)).replace(
                tzinfo=None
            ),
            heartbeat_at=datetime.now(UTC).replace(tzinfo=None),
            runtime_metadata={"permissions": []},
            steps=[],
            token_usage={},
        )
        db.add(execution)
        db.commit()
        db.refresh(execution)
    service._owned_attempts[str(execution_id)] = 1
    intent = {
        "intent": "unknown.request",
        "domain": "unknown",
        "operation": "request",
        "resource": None,
        "confidence": 1,
        "ambiguous": False,
        "ambiguity_reason": None,
        "entities": {},
        "semantic_hints": [],
        "source": "deterministic",
        "error_code": None,
    }
    extraction = {
        "intent": "unknown.request",
        "parameters": {},
        "unresolved_mentions": [],
        "warnings": [],
        "source": "llm",
        "error_code": None,
    }
    canonical = ParameterState(intent="unknown.request", parameters={}).model_dump(
        mode="json"
    )

    async def classify(*_args, **_kwargs):
        return intent

    async def extract(*_args, **_kwargs):
        return extraction

    async def reconcile(*_args, **_kwargs):
        return canonical

    async def forbidden(*_args, **_kwargs):
        pytest.fail("capability ran with unknown completeness")

    async def quiet(*_args, **_kwargs):
        return None

    monkeypatch.setattr(service, "_load_conversation_context", lambda *_: [])
    monkeypatch.setattr(service, "_classify_intent_once", classify)
    monkeypatch.setattr(service, "_extract_parameters_once", extract)
    monkeypatch.setattr(service, "_reconcile_parameters_once", reconcile)
    monkeypatch.setattr(service, "_resolve_capability_once", forbidden)
    monkeypatch.setattr(service, "publish_event", quiet)
    monkeypatch.setattr(service, "publish_step", quiet)

    await service._execute(
        execution,
        "Unsupported migrated request",
        set(),
        "tenant-gate",
        "openai",
        "test-model",
        None,
        {},
    )

    with SessionLocal() as db:
        stored = db.get(RuntimeExecution, execution_id)
        assert stored.status == "FAILED"
        assert stored.runtime_metadata["input_requirements"]["complete"] is None
        assert (
            stored.runtime_metadata["error_code"]
            == "INPUT_REQUIREMENT_SCHEMA_UNAVAILABLE"
        )
        assert "capability_resolution" not in stored.runtime_metadata
