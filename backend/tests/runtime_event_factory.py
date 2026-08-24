from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.runtime_execution import RuntimeExecution, RuntimeExecutionEvent
from app.services.runtime_execution_service import RuntimeExecutionService


def create_execution_without_events(
    db: Session, *, status: str = "RUNNING"
) -> RuntimeExecution:
    execution = RuntimeExecution(
        id=uuid4(),
        conversation_id=uuid4(),
        workflow_id=uuid4(),
        user_id="runtime-event-factory-user",
        tenant_id="runtime-event-factory-tenant",
        status=status,
        started_at=datetime.now(UTC).replace(tzinfo=None),
        steps=[],
        runtime_metadata={},
        token_usage={},
    )
    db.add(execution)
    db.commit()
    return execution


def append_runtime_event(
    db: Session,
    execution: RuntimeExecution,
    *,
    event_type: str = "step",
    name: str = "Factory Event",
) -> dict:
    service = object.__new__(RuntimeExecutionService)
    event = service._append_runtime_event_locked(
        db,
        execution,
        {"type": event_type, "name": name, "status": "completed"},
    )
    db.commit()
    return event


def create_execution_with_events(db: Session, *, event_count: int) -> RuntimeExecution:
    execution = create_execution_without_events(db)
    for index in range(event_count):
        append_runtime_event(db, execution, name=f"Historical Event {index + 1}")
    assert_execution_event_consistency(db, execution.id)
    return execution


def assert_execution_event_consistency(db: Session, execution_id) -> None:
    counter = db.get(RuntimeExecution, execution_id).last_event_sequence
    maximum = db.execute(
        select(func.coalesce(func.max(RuntimeExecutionEvent.sequence), 0)).where(
            RuntimeExecutionEvent.execution_id == execution_id
        )
    ).scalar_one()
    assert counter == maximum
