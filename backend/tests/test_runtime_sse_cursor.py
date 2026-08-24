from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.runtime import _runtime_event_cursor, runtime_events_stream
from app.database.session import SessionLocal
from app.models.runtime_execution import RuntimeExecution
from app.runtime.execution_tracker import ExecutionTracker
from app.services.runtime_execution_service import (
    RuntimeExecutionService,
    runtime_execution_service,
)


def test_query_cursor_takes_precedence_over_header() -> None:
    assert _runtime_event_cursor(7, "5") == 7


@pytest.mark.parametrize("value", ["abc", "-1"])
def test_invalid_last_event_id_is_rejected(value: str) -> None:
    with pytest.raises(HTTPException) as exc:
        _runtime_event_cursor(None, value)
    assert exc.value.status_code == 400


def test_empty_cursor_starts_at_zero() -> None:
    assert _runtime_event_cursor(None, None) == 0
    assert _runtime_event_cursor(None, "") == 0


@pytest.mark.asyncio
async def test_endpoint_frames_sequence_as_sse_id(monkeypatch) -> None:
    service = object.__new__(RuntimeExecutionService)
    service._tracker = ExecutionTracker()
    with SessionLocal() as db:
        execution = RuntimeExecution(
            id=uuid4(),
            conversation_id=uuid4(),
            workflow_id=uuid4(),
            user_id="sse-user",
            tenant_id="sse-tenant",
            status="PENDING",
            steps=[],
            runtime_metadata={},
            token_usage={},
        )
        db.add(execution)
        db.commit()
        service.transition_execution(execution.id, "RUNNING", db=db)
        service.transition_execution(execution.id, "COMPLETED", db=db)
        execution_id = execution.id

    monkeypatch.setattr(runtime_execution_service, "_tracker", ExecutionTracker())
    with SessionLocal() as db:
        response = await runtime_events_stream(
            execution_id=execution_id,
            after_sequence=1,
            last_event_id=None,
            db=db,
            user={"sub": "sse-user", "custom:tenant_id": "sse-tenant"},
        )
        chunks = [chunk async for chunk in response.body_iterator]

    body = b"".join(
        chunk if isinstance(chunk, bytes) else chunk.encode() for chunk in chunks
    ).decode()
    assert body.startswith("id: 2\nevent: runtime_event\n")
    assert '"type": "runtime.completed"' in body
