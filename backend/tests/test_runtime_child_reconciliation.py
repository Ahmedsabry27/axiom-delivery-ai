from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.agents.execution_service import AgentExecutionService
from app.database.models.agent import Agent
from app.database.models.agent_execution import AgentExecution
from app.database.models.tool import ToolExecution
from app.models.runtime_execution import RuntimeContinuation, RuntimeExecution
from app.runtime.child_reconciliation import (
    ChildOutcome,
    RequiredChildStateError,
    map_agent_execution_status,
    map_tool_execution_status,
)
from app.services.runtime_execution_service import RuntimeExecutionService


def runtime(db, status="RUNNING"):
    row = RuntimeExecution(
        id=uuid4(),
        conversation_id=uuid4(),
        workflow_id=uuid4(),
        user_id="owner",
        tenant_id="tenant-a",
        status=status,
        started_at=datetime.now(UTC).replace(tzinfo=None),
        steps=[],
        runtime_metadata={},
        token_usage={},
    )
    db.add(row)
    db.commit()
    return row


def agent(db, parent, status="running"):
    definition = Agent(
        tenant_id="tenant-a",
        slug=f"agent-{uuid4()}",
        name="Runtime Agent",
        owner_id="owner",
        lifecycle_status="enabled",
    )
    db.add(definition)
    db.flush()
    row = AgentExecution(
        runtime_execution_id=str(parent.id),
        tenant_id="tenant-a",
        agent_id=definition.id,
        agent_uuid=definition.uuid,
        agent_version=1,
        actor_id="owner",
        status=status,
        current_phase=status,
        request_summary="test",
        model_provider="openai",
        model_name="test-model",
        planner="default",
        correlation_id=str(uuid4()),
        trace_id=str(uuid4()),
    )
    db.add(row)
    db.commit()
    return row


def tool(
    db, parent, status="running", correlation_id=None, name="jira.get_create_metadata"
):
    row = ToolExecution(
        tenant_id="tenant-a",
        tool_name=name,
        tool_version="1.0.0",
        actor_id="owner",
        status=status,
        correlation_id=correlation_id or str(parent.workflow_id),
        input_summary={},
    )
    db.add(row)
    db.commit()
    return row


def test_child_status_mapping_is_deterministic():
    assert map_agent_execution_status("running") == ChildOutcome.ACTIVE
    assert (
        map_agent_execution_status("waiting_for_clarification")
        == ChildOutcome.WAITING_FOR_INPUT
    )
    assert (
        map_agent_execution_status("waiting_for_approval")
        == ChildOutcome.WAITING_FOR_APPROVAL
    )
    assert map_agent_execution_status("expired") == ChildOutcome.TIMED_OUT
    assert map_tool_execution_status("succeeded") == ChildOutcome.SUCCEEDED
    assert map_tool_execution_status("timed_out") == ChildOutcome.TIMED_OUT


@pytest.mark.parametrize(
    "child_status", ["running", "failed", "timed_out", "cancelled"]
)
def test_required_tool_prevents_false_parent_completion(db_session, child_status):
    service = object.__new__(RuntimeExecutionService)
    parent = runtime(db_session)
    tool(db_session, parent, child_status)

    with pytest.raises(RequiredChildStateError):
        service.transition_execution(parent.id, "COMPLETED", db=db_session)

    db_session.expire_all()
    assert db_session.get(RuntimeExecution, parent.id).status == "RUNNING"


def test_required_tool_timeout_rolls_up_to_parent_timeout(db_session):
    service = object.__new__(RuntimeExecutionService)
    parent = runtime(db_session)
    child = tool(db_session, parent, "timed_out")

    updated = service.transition_execution(
        parent.id, "TIMED_OUT", error_code="TOOL_TIMEOUT", db=db_session
    )

    assert updated.status == "TIMED_OUT"
    assert db_session.get(ToolExecution, child.id).status == "timed_out"


def test_required_agent_failure_prevents_parent_completion(db_session):
    service = object.__new__(RuntimeExecutionService)
    parent = runtime(db_session)
    agent(db_session, parent, "failed")

    with pytest.raises(RequiredChildStateError):
        service.transition_execution(parent.id, "COMPLETED", db=db_session)


@pytest.mark.parametrize(
    ("parent_status", "child_status"),
    [("FAILED", "failed"), ("CANCELLED", "cancelled"), ("TIMED_OUT", "timed_out")],
)
def test_terminal_parent_reconciles_owned_active_children(
    db_session, parent_status, child_status
):
    service = object.__new__(RuntimeExecutionService)
    parent = runtime(db_session)
    child_agent = agent(db_session, parent)
    child_tool = tool(db_session, parent, correlation_id=child_agent.correlation_id)

    service.transition_execution(parent.id, parent_status, db=db_session)

    db_session.expire_all()
    assert db_session.get(RuntimeExecution, parent.id).status == parent_status
    assert db_session.get(AgentExecution, child_agent.id).status == child_status
    assert db_session.get(ToolExecution, child_tool.id).status == child_status


@pytest.mark.parametrize(
    ("parent_status", "child_status"),
    [("FAILED", "failed"), ("CANCELLED", "cancelled"), ("TIMED_OUT", "timed_out")],
)
def test_existing_terminal_parent_repairs_leaked_active_children(
    db_session, parent_status, child_status
):
    service = object.__new__(RuntimeExecutionService)
    parent = runtime(db_session, parent_status)
    child_agent = agent(db_session, parent)
    child_tool = tool(db_session, parent, correlation_id=child_agent.correlation_id)

    service.transition_execution(parent.id, parent_status, db=db_session)

    db_session.expire_all()
    assert db_session.get(AgentExecution, child_agent.id).status == child_status
    assert db_session.get(ToolExecution, child_tool.id).status == child_status


def test_successful_required_children_allow_parent_completion(db_session):
    service = object.__new__(RuntimeExecutionService)
    parent = runtime(db_session)
    child_agent = agent(db_session, parent, "succeeded")
    tool(db_session, parent, "succeeded", correlation_id=child_agent.correlation_id)

    updated = service.transition_execution(parent.id, "COMPLETED", db=db_session)

    assert updated.status == "COMPLETED"


def test_jira_metadata_failure_cannot_remain_running_when_parent_fails(db_session):
    service = object.__new__(RuntimeExecutionService)
    parent = runtime(db_session)
    jira = tool(db_session, parent, "running")

    service.transition_execution(
        parent.id, "FAILED", error_message="Runtime execution failed", db=db_session
    )

    db_session.expire_all()
    assert db_session.get(ToolExecution, jira.id).status == "failed"
    assert db_session.get(RuntimeExecution, parent.id).status == "FAILED"


@pytest.mark.asyncio
async def test_unexpected_managed_agent_exception_terminalizes_child(
    db_session, monkeypatch
):
    parent = runtime(db_session)
    child = agent(db_session, parent)
    service = AgentExecutionService()

    async def explode(*_args, **_kwargs):
        raise RuntimeError("provider payload that must not be persisted")

    monkeypatch.setattr(service, "_run", explode)
    with pytest.raises(RuntimeError):
        await service._run_with_timeout(
            db_session,
            child,
            type("Identity", (), {"actor_id": "owner"})(),
            "test",
            {},
            "production",
        )

    db_session.expire_all()
    persisted = db_session.get(AgentExecution, child.id)
    assert persisted.status == "failed"
    assert persisted.safe_error_message == "Managed agent execution failed unexpectedly"


@pytest.mark.asyncio
async def test_managed_agent_timeout_preserves_timed_out_status(
    db_session, monkeypatch
):
    parent = runtime(db_session)
    child = agent(db_session, parent)
    child.runtime_metadata = {"limits": {"timeout_seconds": 1}}
    db_session.commit()
    service = AgentExecutionService()

    async def hang(*_args, **_kwargs):
        import asyncio

        await asyncio.sleep(2)

    monkeypatch.setattr(service, "_run", hang)
    result = await service._run_with_timeout(
        db_session,
        child,
        type("Identity", (), {"actor_id": "owner"})(),
        "test",
        {},
        "production",
    )

    assert result["status"] == "timed_out"
    assert db_session.get(AgentExecution, child.id).status == "timed_out"


@pytest.mark.parametrize(
    ("runtime_status", "kind", "error_code"),
    [
        ("WAITING_FOR_INPUT", "input", "CONTINUATION_EXPIRED"),
        ("WAITING_FOR_APPROVAL", "approval", "APPROVAL_EXPIRED"),
    ],
)
def test_expired_continuation_times_out_parent(
    db_session, runtime_status, kind, error_code
):
    from datetime import timedelta

    service = object.__new__(RuntimeExecutionService)
    parent = runtime(db_session, runtime_status)
    continuation = RuntimeContinuation(
        execution_id=parent.id,
        tenant_id=parent.tenant_id,
        kind=kind,
        status="pending",
        schema={},
        known_values={},
        response={},
        expires_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(seconds=1),
    )
    db_session.add(continuation)
    db_session.commit()

    updated = service.expire_continuations(db_session, parent)

    assert updated.status == "TIMED_OUT"
    assert updated.runtime_metadata["error_code"] == error_code
    assert db_session.get(RuntimeContinuation, continuation.id).status == "expired"
