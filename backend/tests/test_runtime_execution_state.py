from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.database.models.audit import AuditLog
from app.models.runtime_execution import RuntimeExecution
from app.services.runtime_execution_service import (
    InvalidRuntimeTransitionError,
    RuntimeExecutionService,
)


def make_execution(db, status: str = "PENDING") -> RuntimeExecution:
    now = datetime.now(UTC).replace(tzinfo=None) if status != "PENDING" else None
    execution = RuntimeExecution(
        id=uuid4(),
        conversation_id=uuid4(),
        workflow_id=uuid4(),
        user_id="runtime-state-user",
        tenant_id="runtime-state-tenant",
        status=status,
        started_at=now,
        steps=[],
        runtime_metadata={},
        token_usage={},
    )
    db.add(execution)
    db.commit()
    return execution


@pytest.mark.parametrize(
    ("source", "target"),
    [
        ("PENDING", "RUNNING"),
        ("PENDING", "CANCELLED"),
        ("RUNNING", "COMPLETED"),
        ("RUNNING", "FAILED"),
        ("RUNNING", "CANCELLED"),
        ("RUNNING", "TIMED_OUT"),
        ("RUNNING", "WAITING_FOR_INPUT"),
        ("WAITING_FOR_INPUT", "RUNNING"),
        ("RUNNING", "WAITING_FOR_APPROVAL"),
        ("WAITING_FOR_APPROVAL", "RUNNING"),
        ("WAITING_FOR_APPROVAL", "FAILED"),
    ],
)
def test_valid_runtime_transitions(db_session, source: str, target: str) -> None:
    service = object.__new__(RuntimeExecutionService)
    execution = make_execution(db_session, source)

    updated = service.transition_execution(execution.id, target, db=db_session)

    assert updated.status == target
    if source == "PENDING" and target == "RUNNING":
        assert updated.started_at is not None
        assert updated.deadline_at is not None
    if target in service._TERMINAL_STATUSES:
        assert updated.completed_at is not None
        assert updated.duration_ms is None or updated.duration_ms >= 0
    else:
        assert updated.completed_at is None


@pytest.mark.parametrize(
    ("source", "target"),
    [
        ("COMPLETED", "RUNNING"),
        ("FAILED", "RUNNING"),
        ("CANCELLED", "RUNNING"),
        ("TIMED_OUT", "RUNNING"),
        ("COMPLETED", "FAILED"),
        ("FAILED", "COMPLETED"),
        ("CANCELLED", "COMPLETED"),
        ("TIMED_OUT", "COMPLETED"),
    ],
)
def test_invalid_terminal_runtime_transitions_are_rejected(
    db_session, source: str, target: str
) -> None:
    service = object.__new__(RuntimeExecutionService)
    execution = make_execution(db_session, source)

    with pytest.raises(InvalidRuntimeTransitionError):
        service.transition_execution(execution.id, target, db=db_session)

    db_session.expire_all()
    assert db_session.get(RuntimeExecution, execution.id).status == source


def test_repeated_terminal_transition_is_idempotent(db_session) -> None:
    service = object.__new__(RuntimeExecutionService)
    execution = make_execution(db_session, "RUNNING")
    first = service.transition_execution(
        execution.id, "COMPLETED", result_message="done", db=db_session
    )
    finished_at = first.completed_at
    duration_ms = first.duration_ms
    audit_count = (
        db_session.query(AuditLog)
        .filter_by(target_type="runtime_execution", target_id=str(execution.id))
        .count()
    )

    second = service.transition_execution(
        execution.id, "COMPLETED", result_message="different", db=db_session
    )

    assert second.completed_at == finished_at
    assert second.duration_ms == duration_ms
    assert second.result_message == "done"
    assert (
        db_session.query(AuditLog)
        .filter_by(target_type="runtime_execution", target_id=str(execution.id))
        .count()
        == audit_count
    )


def test_wait_and_resume_preserve_original_start_time(db_session) -> None:
    service = object.__new__(RuntimeExecutionService)
    execution = make_execution(db_session)

    running = service.transition_execution(execution.id, "RUNNING", db=db_session)
    original_started_at = running.started_at
    service.transition_execution(
        execution.id,
        "WAITING_FOR_INPUT",
        reason="required_input",
        db=db_session,
    )
    resumed = service.transition_execution(execution.id, "RUNNING", db=db_session)
    completed = service.transition_execution(execution.id, "COMPLETED", db=db_session)

    assert resumed.started_at == original_started_at
    assert completed.started_at == original_started_at
    assert completed.completed_at is not None
    assert completed.duration_ms == round(
        (completed.completed_at - original_started_at).total_seconds() * 1000, 2
    )


def test_first_terminal_transition_wins(db_session) -> None:
    service = object.__new__(RuntimeExecutionService)
    execution = make_execution(db_session, "RUNNING")

    service.transition_execution(execution.id, "COMPLETED", db=db_session)
    with pytest.raises(InvalidRuntimeTransitionError):
        service.transition_execution(execution.id, "FAILED", db=db_session)

    db_session.expire_all()
    assert db_session.get(RuntimeExecution, execution.id).status == "COMPLETED"
