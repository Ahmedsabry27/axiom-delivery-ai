from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.base import Base
from app.models.runtime_execution import RuntimeExecution, RuntimeExecutionEvent
from app.runtime.execution_tracker import ExecutionTracker
from app.runtime.leases import claim_execution
from app.services.runtime_execution_service import RuntimeExecutionService


def test_twenty_five_concurrent_runtime_lifecycles(tmp_path) -> None:
    engine = create_engine(
        f"sqlite+pysqlite:///{tmp_path / 'runtime-load.db'}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.create_all(engine)
    service = RuntimeExecutionService()

    def execute(index: int) -> str:
        with sessions() as db:
            runtime = RuntimeExecution(
                id=uuid4(),
                workflow_id=uuid4(),
                conversation_id=uuid4(),
                user_id=f"load-user-{index}",
                tenant_id="load-test",
                goal="load smoke",
                status="PENDING",
                runtime_metadata={},
                steps=[],
            )
            db.add(runtime)
            db.commit()
            execution_id = runtime.id
            claimed = claim_execution(
                db,
                execution_id,
                worker_id=f"load-worker-{index}",
                expected_status="PENDING",
            )
            assert claimed is not None
            service.transition_execution(
                execution_id,
                "RUNNING",
                worker_id=f"load-worker-{index}",
                ownership_attempt=claimed.attempt,
                db=db,
            )
            service.transition_execution(
                execution_id,
                "COMPLETED",
                worker_id=f"load-worker-{index}",
                ownership_attempt=claimed.attempt,
                result_message="ok",
                db=db,
            )
            return str(execution_id)

    with ThreadPoolExecutor(max_workers=10) as pool:
        execution_ids = list(pool.map(execute, range(25)))

    with sessions() as db:
        runtimes = db.query(RuntimeExecution).all()
        events = db.query(RuntimeExecutionEvent).all()
        assert len(execution_ids) == len(runtimes) == 25
        assert all(row.status == "COMPLETED" for row in runtimes)
        assert all(row.lease_owner is None for row in runtimes)
        assert len(events) == 50
        assert len([event for event in events if event.final]) == 25
        assert len({(event.execution_id, event.sequence) for event in events}) == 50


@pytest.mark.asyncio
async def test_twenty_five_terminal_sse_streams_close_cleanly() -> None:
    writer = object.__new__(RuntimeExecutionService)
    writer._tracker = ExecutionTracker()
    reader = object.__new__(RuntimeExecutionService)
    reader._tracker = ExecutionTracker()
    execution_ids = []

    from app.database.session import SessionLocal

    with SessionLocal() as db:
        for index in range(25):
            runtime = RuntimeExecution(
                id=uuid4(),
                workflow_id=uuid4(),
                conversation_id=uuid4(),
                user_id=f"sse-user-{index}",
                tenant_id="sse-load",
                status="PENDING",
                runtime_metadata={},
                steps=[],
            )
            db.add(runtime)
            db.commit()
            writer.transition_execution(runtime.id, "RUNNING", db=db)
            writer.transition_execution(runtime.id, "COMPLETED", db=db)
            execution_ids.append(str(runtime.id))

    async def consume(execution_id: str) -> list[int]:
        return [event["sequence"] async for event in reader.stream(execution_id)]

    sequences = await asyncio.gather(*(consume(item) for item in execution_ids))
    assert sequences == [[1, 2]] * 25
    assert reader._tracker.listeners == {}
