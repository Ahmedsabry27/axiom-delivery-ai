from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.api.runtime import runtime_events_stream
from app.database.session import SessionLocal
from app.models.runtime_execution import RuntimeExecution
from app.services.runtime_execution_service import runtime_execution_service


def create_runtime() -> RuntimeExecution:
    with SessionLocal() as db:
        runtime = RuntimeExecution(
            id=uuid4(),
            workflow_id=uuid4(),
            conversation_id=uuid4(),
            user_id="shared-subject",
            tenant_id="tenant-a",
            status="PENDING",
            runtime_metadata={},
            steps=[],
        )
        db.add(runtime)
        db.commit()
        db.refresh(runtime)
        db.expunge(runtime)
        return runtime


def test_runtime_lookup_requires_matching_tenant() -> None:
    runtime = create_runtime()
    with SessionLocal() as db:
        assert (
            runtime_execution_service.get_for_user(
                db, runtime.id, "shared-subject", "tenant-a"
            )
            is not None
        )
        assert (
            runtime_execution_service.get_for_user(
                db, runtime.id, "shared-subject", "tenant-b"
            )
            is None
        )


@pytest.mark.asyncio
async def test_sse_rejects_same_subject_from_another_tenant() -> None:
    runtime = create_runtime()
    with SessionLocal() as db, pytest.raises(HTTPException) as error:
        await runtime_events_stream(
            execution_id=runtime.id,
            after_sequence=0,
            last_event_id=None,
            db=db,
            user={"sub": "shared-subject", "custom:tenant_id": "tenant-b"},
        )
    assert error.value.status_code == 404
