from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from app.core.config import settings
from app.database.models.audit import AuditLog
from app.database.models.tool import ToolDefinition, ToolExecution
from app.database.session import SessionLocal
from app.models.runtime_execution import RuntimeExecution, RuntimeExecutionEvent
from app.runtime.leases import claim_execution, renew_execution_lease
from app.runtime.recovery import RuntimeRecoveryService
from app.services.runtime_execution_service import (
    RuntimeExecutionService,
    RuntimeLeaseLostError,
)


def make_execution(db, *, status="PENDING", owner=None, expired=False, attempt=1):
    now = datetime.now(UTC).replace(tzinfo=None)
    row = RuntimeExecution(
        id=uuid4(),
        workflow_id=uuid4(),
        conversation_id=uuid4(),
        user_id="user-1",
        tenant_id="default",
        goal="recover me",
        status=status,
        runtime_metadata={},
        lease_owner=owner,
        lease_expires_at=now - timedelta(seconds=1) if expired else None,
        heartbeat_at=now - timedelta(seconds=40) if owner else None,
        attempt=attempt,
        started_at=now - timedelta(seconds=10),
        deadline_at=now + timedelta(minutes=5),
        steps=[],
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def add_tool(db, runtime, *, name, status, risk, output=None):
    db.add(
        ToolDefinition(
            tenant_id="default",
            name=name,
            display_name=name,
            description=name,
            category="test",
            provider="test",
            version="1",
            input_schema={},
            permissions=[],
            tags=[],
            risk_level=risk,
        )
    )
    tool = ToolExecution(
        tenant_id="default",
        tool_name=name,
        tool_version="1",
        actor_id="user-1",
        status=status,
        correlation_id=str(runtime.workflow_id),
        input_summary={},
        output_summary=output,
    )
    db.add(tool)
    db.commit()
    return tool


def test_claim_is_exclusive_and_wrong_owner_cannot_heartbeat():
    with SessionLocal() as db:
        row = make_execution(db)
        execution_id = row.id
    with SessionLocal() as first:
        claimed = claim_execution(
            first, execution_id, worker_id="worker-a", expected_status="PENDING"
        )
        assert claimed is not None
        attempt = claimed.attempt
    with SessionLocal() as second:
        assert (
            claim_execution(
                second, execution_id, worker_id="worker-b", expected_status="PENDING"
            )
            is None
        )
        assert not renew_execution_lease(
            second, execution_id, worker_id="worker-b", attempt=attempt
        )


def test_heartbeat_renews_without_event():
    with SessionLocal() as db:
        row = make_execution(db)
        execution_id = row.id
        row = claim_execution(
            db, execution_id, worker_id="worker-a", expected_status="PENDING"
        )
        assert row is not None
        RuntimeExecutionService().transition_execution(
            execution_id,
            "RUNNING",
            worker_id="worker-a",
            ownership_attempt=row.attempt,
        )
    with SessionLocal() as db:
        before = db.get(RuntimeExecution, execution_id).lease_expires_at
        event_count = (
            db.query(RuntimeExecutionEvent).filter_by(execution_id=execution_id).count()
        )
        assert renew_execution_lease(db, execution_id, worker_id="worker-a", attempt=1)
        after = db.get(RuntimeExecution, execution_id).lease_expires_at
        assert after >= before
        assert (
            db.query(RuntimeExecutionEvent).filter_by(execution_id=execution_id).count()
            == event_count
        )


@pytest.mark.asyncio
async def test_stale_deadline_wins_over_recovery(monkeypatch):
    service = RuntimeExecutionService()
    recovery = RuntimeRecoveryService(service)
    monkeypatch.setattr(
        service,
        "launch_recovered_execution",
        lambda _row: pytest.fail("must not launch"),
    )
    with SessionLocal() as db:
        row = make_execution(db, status="RUNNING", owner="dead", expired=True)
        row.deadline_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(seconds=1)
        db.commit()
        execution_id = str(row.id)
    assert await recovery.reconcile_execution(execution_id)
    with SessionLocal() as db:
        row = db.get(RuntimeExecution, UUID(execution_id))
        assert row.status == "TIMED_OUT"
        assert row.lease_owner is None


@pytest.mark.asyncio
async def test_safe_stale_execution_reclaimed_once(monkeypatch):
    service = RuntimeExecutionService()
    recovery = RuntimeRecoveryService(service)
    launched = []
    monkeypatch.setattr(
        service, "launch_recovered_execution", lambda row: launched.append(row.id)
    )
    with SessionLocal() as db:
        row = make_execution(db, status="RUNNING", owner="dead", expired=True)
        tool = add_tool(
            db, row, name="jira.search_issues", status="running", risk="read"
        )
        tool_id = tool.id
        execution_id = str(row.id)
    assert await recovery.reconcile_execution(execution_id)
    assert not await recovery.reconcile_execution(execution_id)
    with SessionLocal() as db:
        row = db.get(RuntimeExecution, UUID(execution_id))
        assert row.status == "RUNNING"
        assert row.lease_owner == service.worker_id
        assert row.attempt == 2
        events = (
            db.query(RuntimeExecutionEvent)
            .filter_by(execution_id=row.id, event_type="runtime.recovered")
            .all()
        )
        assert len(events) == 1
        audit = (
            db.query(AuditLog)
            .filter_by(target_id=str(row.id), action="runtime.recovered")
            .one()
        )
        assert audit.actor_id == "runtime-recovery"
        abandoned = db.get(ToolExecution, tool_id)
        assert abandoned.status == "failed"
        assert abandoned.error_code == "WORKER_LOSS_RETRY"
    assert len(launched) == 1


@pytest.mark.asyncio
async def test_legacy_running_execution_without_lease_is_reconciled(monkeypatch):
    service = RuntimeExecutionService()
    recovery = RuntimeRecoveryService(service)
    launched = []
    monkeypatch.setattr(
        service, "launch_recovered_execution", lambda row: launched.append(row.id)
    )
    with SessionLocal() as db:
        row = make_execution(db, status="RUNNING")
        execution_id = str(row.id)
    assert execution_id in recovery.find_stale_execution_ids()
    assert await recovery.reconcile_execution(execution_id)
    assert len(launched) == 1


@pytest.mark.asyncio
async def test_uncertain_jira_write_is_never_replayed(monkeypatch):
    service = RuntimeExecutionService()
    recovery = RuntimeRecoveryService(service)
    monkeypatch.setattr(
        service,
        "launch_recovered_execution",
        lambda _row: pytest.fail("unsafe action replayed"),
    )
    with SessionLocal() as db:
        row = make_execution(db, status="RUNNING", owner="dead", expired=True)
        add_tool(db, row, name="jira.create_issue", status="running", risk="write")
        execution_id = str(row.id)
    assert await recovery.reconcile_execution(execution_id)
    with SessionLocal() as db:
        row = db.get(RuntimeExecution, UUID(execution_id))
        assert row.status == "FAILED"
        assert (
            row.runtime_metadata["error_code"] == "RECOVERY_UNCERTAIN_EXTERNAL_ACTION"
        )
        assert row.lease_owner is None


@pytest.mark.asyncio
async def test_successful_jira_write_is_not_replayed(monkeypatch):
    service = RuntimeExecutionService()
    recovery = RuntimeRecoveryService(service)
    monkeypatch.setattr(
        service,
        "launch_recovered_execution",
        lambda _row: pytest.fail("successful action replayed"),
    )
    with SessionLocal() as db:
        row = make_execution(db, status="RUNNING", owner="dead", expired=True)
        add_tool(
            db,
            row,
            name="jira.create_issue",
            status="succeeded",
            risk="write",
            output={"key": "KAN-123"},
        )
        execution_id = str(row.id)
    assert await recovery.reconcile_execution(execution_id)
    with SessionLocal() as db:
        row = db.get(RuntimeExecution, UUID(execution_id))
        assert row.status == "COMPLETED"
        assert "KAN-123" in row.result_message


def test_terminal_and_waiting_states_release_lease():
    service = RuntimeExecutionService()
    for target in (
        "WAITING_FOR_INPUT",
        "WAITING_FOR_APPROVAL",
        "COMPLETED",
        "FAILED",
        "CANCELLED",
        "TIMED_OUT",
    ):
        with SessionLocal() as db:
            row = make_execution(db, status="RUNNING", owner="worker-a")
            row.lease_expires_at = datetime.now(UTC).replace(tzinfo=None) + timedelta(
                seconds=30
            )
            db.commit()
            execution_id = row.id
        service.transition_execution(execution_id, target)
        with SessionLocal() as db:
            row = db.get(RuntimeExecution, execution_id)
            assert row.lease_owner is None
            assert row.lease_expires_at is None
            assert row.heartbeat_at is None


def test_different_worker_can_claim_waiting_execution_without_incrementing_attempt():
    service = RuntimeExecutionService()
    with SessionLocal() as db:
        row = make_execution(db, status="WAITING_FOR_INPUT")
        execution_id = row.id
        claimed = claim_execution(
            db,
            execution_id,
            worker_id="worker-b",
            expected_status="WAITING_FOR_INPUT",
        )
        assert claimed is not None
        assert claimed.attempt == 1
    service.transition_execution(
        execution_id,
        "RUNNING",
        worker_id="worker-b",
        ownership_attempt=1,
    )
    with SessionLocal() as db:
        row = db.get(RuntimeExecution, execution_id)
        assert row.status == "RUNNING"
        assert row.lease_owner == "worker-b"


def test_stale_worker_is_fenced_after_reclaim(monkeypatch):
    service = RuntimeExecutionService()
    with SessionLocal() as db:
        row = make_execution(db, status="RUNNING", owner="worker-a", expired=True)
        execution_id = row.id
    with SessionLocal() as db:
        reclaimed = claim_execution(
            db,
            execution_id,
            worker_id="worker-b",
            expected_status="RUNNING",
            recovery=True,
        )
        assert reclaimed is not None
    with pytest.raises(RuntimeLeaseLostError):
        service.transition_execution(
            execution_id, "COMPLETED", worker_id="worker-a", ownership_attempt=1
        )


@pytest.mark.asyncio
async def test_recovery_attempts_are_bounded(monkeypatch):
    service = RuntimeExecutionService()
    recovery = RuntimeRecoveryService(service)
    monkeypatch.setattr(
        service,
        "launch_recovered_execution",
        lambda _row: pytest.fail("exhausted runtime launched"),
    )
    with SessionLocal() as db:
        row = make_execution(
            db,
            status="RUNNING",
            owner="dead",
            expired=True,
            attempt=settings.RUNTIME_MAX_RECOVERY_ATTEMPTS,
        )
        execution_id = str(row.id)
    assert await recovery.reconcile_execution(execution_id)
    with SessionLocal() as db:
        row = db.get(RuntimeExecution, UUID(execution_id))
        assert row.status == "FAILED"
        assert row.runtime_metadata["error_code"] == "RECOVERY_ATTEMPTS_EXHAUSTED"
