from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Barrier
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.ai.exceptions import AITimeoutError
from app.database.base import Base
from app.database.session import SessionLocal
from app.events.base import Event
from app.models.runtime_execution import RuntimeExecution, RuntimeExecutionEvent
from app.runtime.event_bus import EventBus
from app.runtime.execution_tracker import ExecutionTracker
from app.services import runtime_execution_service as runtime_service_module
from app.services.runtime_execution_service import RuntimeExecutionService


def make_execution(db, status: str = "RUNNING") -> RuntimeExecution:
    execution = RuntimeExecution(
        id=uuid4(),
        conversation_id=uuid4(),
        workflow_id=uuid4(),
        user_id="atomic-events-user",
        tenant_id="atomic-events-tenant",
        status=status,
        started_at=datetime.now(UTC).replace(tzinfo=None),
        steps=[],
        runtime_metadata={},
        token_usage={},
    )
    db.add(execution)
    db.commit()
    return execution


@pytest.mark.parametrize(
    ("target", "event_type"),
    [
        ("COMPLETED", "runtime.completed"),
        ("FAILED", "runtime.failed"),
        ("CANCELLED", "runtime.cancelled"),
        ("TIMED_OUT", "runtime.timed_out"),
    ],
)
def test_terminal_transition_commits_exactly_one_matching_event(
    db_session, target: str, event_type: str
) -> None:
    service = object.__new__(RuntimeExecutionService)
    execution = make_execution(db_session)

    first = service.transition_execution(
        execution.id,
        target,
        error_message="safe failure" if target != "COMPLETED" else None,
        result_message="done" if target == "COMPLETED" else None,
        db=db_session,
    )
    service.transition_execution(execution.id, target, db=db_session)

    events = (
        db_session.query(RuntimeExecutionEvent)
        .filter_by(execution_id=execution.id, final=True)
        .all()
    )
    assert first.status == target
    assert [event.event_type for event in events] == [event_type]
    assert events[0].aggregate_status == target
    assert events[0].state_version == first.state_version == 1
    assert events[0].payload["final"] is True


def test_post_terminal_informational_event_is_not_persisted() -> None:
    service = object.__new__(RuntimeExecutionService)
    with SessionLocal() as db:
        execution = make_execution(db)
        execution_id = execution.id
    service.transition_execution(execution_id, "COMPLETED")

    service.append_runtime_event(
        execution_id,
        {"type": "late_step", "name": "Late callback", "status": "completed"},
    )

    with SessionLocal() as db:
        events = (
            db.query(RuntimeExecutionEvent).filter_by(execution_id=execution_id).all()
        )
        assert len(events) == 1
        assert events[0].event_type == "runtime.completed"


def test_event_insert_failure_rolls_back_state_transition(
    db_session, monkeypatch
) -> None:
    service = object.__new__(RuntimeExecutionService)
    execution = make_execution(db_session)

    def fail_insert(*_args, **_kwargs):
        raise RuntimeError("simulated event insert failure")

    monkeypatch.setattr(service, "_append_runtime_event_locked", fail_insert)
    with pytest.raises(RuntimeError, match="simulated event insert failure"):
        service.transition_execution(execution.id, "COMPLETED", db=db_session)

    db_session.expire_all()
    persisted = db_session.get(RuntimeExecution, execution.id)
    assert persisted.status == "RUNNING"
    assert persisted.state_version == 0
    assert (
        db_session.query(RuntimeExecutionEvent)
        .filter_by(execution_id=execution.id)
        .count()
        == 0
    )


def test_wait_resume_and_informational_events_share_monotonic_sequence(
    db_session,
) -> None:
    service = object.__new__(RuntimeExecutionService)
    execution = make_execution(db_session)

    service.transition_execution(execution.id, "WAITING_FOR_INPUT", db=db_session)
    service.transition_execution(execution.id, "RUNNING", db=db_session)

    # Exercise the same locked append implementation without its application SessionLocal.
    record = db_session.get(RuntimeExecution, execution.id)
    service._append_runtime_event_locked(
        db_session,
        record,
        {"type": "tool_started", "name": "jira.create_issue", "status": "running"},
    )
    db_session.commit()
    service.transition_execution(execution.id, "COMPLETED", db=db_session)

    events = (
        db_session.query(RuntimeExecutionEvent)
        .filter_by(execution_id=execution.id)
        .order_by(RuntimeExecutionEvent.sequence)
        .all()
    )
    assert [event.sequence for event in events] == [1, 2, 3, 4]
    assert [event.event_type for event in events] == [
        "runtime.waiting_for_input",
        "runtime.resumed",
        "tool_started",
        "runtime.completed",
    ]
    assert events[0].state_version == 1
    assert events[1].state_version == 2
    assert events[2].state_version == 2
    assert events[3].state_version == 3


def test_child_terminal_event_precedes_parent_terminal_event(db_session) -> None:
    service = object.__new__(RuntimeExecutionService)
    execution = make_execution(db_session)
    record = db_session.get(RuntimeExecution, execution.id)
    service._append_runtime_event_locked(
        db_session,
        record,
        {
            "type": "tool_completed",
            "name": "jira.create_issue",
            "status": "completed",
            "component_type": "tool",
            "component_id": "tool-execution-1",
            "component_status": "COMPLETED",
        },
    )
    db_session.commit()

    service.transition_execution(execution.id, "COMPLETED", db=db_session)

    events = (
        db_session.query(RuntimeExecutionEvent)
        .filter_by(execution_id=execution.id)
        .order_by(RuntimeExecutionEvent.sequence)
        .all()
    )
    assert [event.event_type for event in events] == [
        "tool_completed",
        "runtime.completed",
    ]


def test_concurrent_event_writers_allocate_unique_sequences(tmp_path) -> None:
    engine = create_engine(
        f"sqlite+pysqlite:///{tmp_path / 'runtime-events.db'}",
        connect_args={"check_same_thread": False, "timeout": 10},
    )
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.create_all(engine)
    service = object.__new__(RuntimeExecutionService)
    with sessions() as db:
        execution = make_execution(db)
        execution_id = execution.id
    barrier = Barrier(6)

    def append(index: int) -> None:
        with sessions() as db:
            record = (
                db.query(RuntimeExecution)
                .filter_by(id=execution_id)
                .with_for_update()
                .one()
            )
            barrier.wait()
            service._append_runtime_event_locked(
                db,
                record,
                {"type": "step", "name": f"Concurrent {index}", "status": "completed"},
            )
            db.commit()

    with ThreadPoolExecutor(max_workers=6) as pool:
        list(pool.map(append, range(6)))

    with sessions() as db:
        events = (
            db.query(RuntimeExecutionEvent)
            .filter_by(execution_id=execution_id)
            .order_by(RuntimeExecutionEvent.sequence)
            .all()
        )
        assert [event.sequence for event in events] == [1, 2, 3, 4, 5, 6]
        assert db.get(RuntimeExecution, execution_id).last_event_sequence == 6


def test_high_contention_event_writers_allocate_unique_sequences(tmp_path) -> None:
    engine = create_engine(
        f"sqlite+pysqlite:///{tmp_path / 'runtime-events-contention.db'}",
        connect_args={"check_same_thread": False, "timeout": 20},
        poolclass=NullPool,
    )
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.create_all(engine)
    service = object.__new__(RuntimeExecutionService)
    with sessions() as db:
        execution_id = make_execution(db).id
    barrier = Barrier(20)

    def append(index: int) -> int:
        with sessions() as db:
            record = db.get(RuntimeExecution, execution_id)
            barrier.wait()
            event = service._append_runtime_event_locked(
                db,
                record,
                {"type": "step", "name": f"Writer {index}", "status": "completed"},
            )
            db.commit()
            return event["sequence"]

    with ThreadPoolExecutor(max_workers=20) as pool:
        allocated = list(pool.map(append, range(20)))

    assert sorted(allocated) == list(range(1, 21))
    with sessions() as db:
        events = (
            db.query(RuntimeExecutionEvent)
            .filter_by(execution_id=execution_id)
            .order_by(RuntimeExecutionEvent.sequence)
            .all()
        )
        assert [event.sequence for event in events] == list(range(1, 21))
        assert db.get(RuntimeExecution, execution_id).last_event_sequence == 20


def test_failed_insert_rolls_back_allocated_sequence(tmp_path, monkeypatch) -> None:
    engine = create_engine(f"sqlite+pysqlite:///{tmp_path / 'runtime-rollback.db'}")
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.create_all(engine)
    service = object.__new__(RuntimeExecutionService)
    with sessions() as db:
        execution_id = make_execution(db).id

    with sessions() as db:
        record = db.get(RuntimeExecution, execution_id)
        original_flush = db.flush
        flushes = 0

        def fail_event_flush(*args, **kwargs):
            nonlocal flushes
            flushes += 1
            if flushes == 2:
                raise RuntimeError("forced event insert failure")
            return original_flush(*args, **kwargs)

        monkeypatch.setattr(db, "flush", fail_event_flush)
        with pytest.raises(RuntimeError, match="forced event insert failure"):
            service._append_runtime_event_locked(
                db, record, {"type": "step", "name": "Fails", "status": "failed"}
            )
        db.rollback()

    with sessions() as db:
        record = db.get(RuntimeExecution, execution_id)
        assert record.last_event_sequence == 0
        assert (
            db.query(RuntimeExecutionEvent).filter_by(execution_id=execution_id).count()
            == 0
        )
        event = service._append_runtime_event_locked(
            db, record, {"type": "step", "name": "Works", "status": "completed"}
        )
        db.commit()
        assert event["sequence"] == 1


@pytest.mark.asyncio
async def test_event_bus_isolates_subscriber_failure(caplog) -> None:
    bus = EventBus()
    delivered = []

    class TestEvent(Event):
        pass

    def broken(_event):
        raise RuntimeError("telemetry unavailable")

    def healthy(event):
        delivered.append(event)

    bus.subscribe(TestEvent, broken)
    bus.subscribe(TestEvent, healthy)
    event = TestEvent()

    await bus.publish(event)

    assert delivered == [event]
    assert "Runtime EventBus subscriber failed" in caplog.text


@pytest.mark.asyncio
async def test_jira_success_has_child_terminal_before_runtime_terminal(
    monkeypatch,
) -> None:
    service = object.__new__(RuntimeExecutionService)
    service._tracker = ExecutionTracker()
    with SessionLocal() as db:
        execution = make_execution(db, "PENDING")
        service.transition_execution(execution.id, "RUNNING", db=db)

    monkeypatch.setattr(
        runtime_service_module.tool_registry,
        "get",
        lambda _name: SimpleNamespace(metadata=SimpleNamespace(risk_level="write")),
    )

    async def succeed(*_args, **_kwargs):
        return SimpleNamespace(
            status="succeeded",
            execution_id="jira-create-1",
            data={"key": "OPS-1"},
            error=None,
            meta={"duration_ms": 5},
        )

    monkeypatch.setattr(runtime_service_module.tool_executor, "execute", succeed)
    await service._execute_runtime_tool(
        str(execution.id),
        execution,
        SimpleNamespace(trace_id="trace-1"),
        {"tools.execute"},
        execution.tenant_id,
        "jira.create_issue",
        {"project_key": "OPS", "summary": "Atomic event test"},
        stage="create",
    )
    service.transition_execution(execution.id, "COMPLETED", result_message="OPS-1")

    with SessionLocal() as db:
        event_types = [
            item.event_type
            for item in db.query(RuntimeExecutionEvent)
            .filter_by(execution_id=execution.id)
            .order_by(RuntimeExecutionEvent.sequence)
        ]
    assert event_types == [
        "runtime.started",
        "action_started",
        "action_completed",
        "runtime.completed",
    ]


@pytest.mark.asyncio
async def test_jira_timeout_has_child_timeout_before_runtime_timeout(
    monkeypatch,
) -> None:
    service = object.__new__(RuntimeExecutionService)
    service._tracker = ExecutionTracker()
    with SessionLocal() as db:
        execution = make_execution(db, "PENDING")
        service.transition_execution(execution.id, "RUNNING", db=db)

    monkeypatch.setattr(
        runtime_service_module.tool_registry,
        "get",
        lambda _name: SimpleNamespace(metadata=SimpleNamespace(risk_level="read")),
    )

    async def time_out(*_args, **_kwargs):
        return SimpleNamespace(
            status="timed_out",
            execution_id="jira-metadata-1",
            data=None,
            error=SimpleNamespace(
                code="TOOL_TIMEOUT", message="Jira metadata timed out"
            ),
            meta={"duration_ms": 1000},
        )

    monkeypatch.setattr(runtime_service_module.tool_executor, "execute", time_out)
    with pytest.raises(AITimeoutError):
        await service._execute_runtime_tool(
            str(execution.id),
            execution,
            SimpleNamespace(trace_id="trace-2"),
            {"tools.execute"},
            execution.tenant_id,
            "jira.get_create_metadata",
            {"project_key": "OPS"},
            stage="issue-types",
        )
    service.transition_execution(
        execution.id,
        "TIMED_OUT",
        error_code="TOOL_TIMEOUT",
        error_message="Jira metadata timed out",
    )

    with SessionLocal() as db:
        event_types = [
            item.event_type
            for item in db.query(RuntimeExecutionEvent)
            .filter_by(execution_id=execution.id)
            .order_by(RuntimeExecutionEvent.sequence)
        ]
    assert event_types == [
        "runtime.started",
        "tool_started",
        "tool_timed_out",
        "runtime.timed_out",
    ]
