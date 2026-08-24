from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.database.base import Base
from app.models.runtime_execution import RuntimeExecution
from app.services.runtime_execution_service import RuntimeExecutionService
from tests.runtime_event_factory import (
    append_runtime_event,
    assert_execution_event_consistency,
    create_execution_with_events,
)


def test_drifted_counter_self_heals_on_append(db_session) -> None:
    execution = create_execution_with_events(db_session, event_count=3)
    execution.last_event_sequence = 1
    db_session.commit()

    event = append_runtime_event(db_session, execution, name="After Drift")

    assert event["sequence"] == 4
    assert db_session.get(RuntimeExecution, execution.id).last_event_sequence == 4
    assert_execution_event_consistency(db_session, execution.id)


def test_factory_keeps_counter_equal_to_maximum(db_session) -> None:
    execution = create_execution_with_events(db_session, event_count=3)
    summary = RuntimeExecutionService.check_execution_event_sequence(
        db_session, execution.id
    )
    assert summary == {
        "execution_id": str(execution.id),
        "counter": 3,
        "max_sequence": 3,
        "event_count": 3,
        "duplicate_count": 0,
        "consistent": True,
    }


def test_existing_execution_reuse_does_not_reset_counter(db_session) -> None:
    execution = create_execution_with_events(db_session, event_count=2)
    reused = db_session.merge(
        RuntimeExecution(
            id=execution.id,
            conversation_id=execution.conversation_id,
            workflow_id=execution.workflow_id,
            user_id=execution.user_id,
            tenant_id=execution.tenant_id,
            status=execution.status,
            last_event_sequence=execution.last_event_sequence,
        )
    )
    db_session.commit()

    event = append_runtime_event(db_session, reused, name="After Reuse")

    assert event["sequence"] == 3
    assert_execution_event_consistency(db_session, execution.id)


def test_concurrent_writers_self_heal_drift(tmp_path) -> None:
    engine = create_engine(
        f"sqlite+pysqlite:///{tmp_path / 'drift-concurrency.db'}",
        connect_args={"check_same_thread": False, "timeout": 20},
        poolclass=NullPool,
    )
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.create_all(engine)
    with sessions() as db:
        execution = create_execution_with_events(db, event_count=3)
        execution.last_event_sequence = 1
        db.commit()
        execution_id = execution.id

    def append(index: int) -> int:
        service = object.__new__(RuntimeExecutionService)
        with sessions() as db:
            record = db.get(RuntimeExecution, execution_id)
            event = service._append_runtime_event_locked(
                db,
                record,
                {"type": "step", "name": f"Concurrent {index}", "status": "completed"},
            )
            db.commit()
            return event["sequence"]

    with ThreadPoolExecutor(max_workers=8) as pool:
        allocated = list(pool.map(append, range(8)))

    assert sorted(allocated) == list(range(4, 12))
    with sessions() as db:
        summary = RuntimeExecutionService.check_execution_event_sequence(
            db, execution_id
        )
        assert summary["consistent"] is True
        assert summary["counter"] == summary["max_sequence"] == 11


def test_all_production_runtime_event_construction_is_canonical() -> None:
    app_root = Path(__file__).resolve().parents[1] / "app"
    writers = []
    for source in app_root.rglob("*.py"):
        if (
            source.name != "runtime_execution.py"
            and "RuntimeExecutionEvent(" in source.read_text()
        ):
            writers.append(source.relative_to(app_root).as_posix())
    assert writers == ["services/runtime_execution_service.py"]


def test_consistency_checker_detects_drift_without_mutation(db_session) -> None:
    execution = create_execution_with_events(db_session, event_count=2)
    execution.last_event_sequence = 1
    db_session.commit()

    summary = RuntimeExecutionService.check_execution_event_sequence(
        db_session, execution.id
    )

    assert summary["consistent"] is False
    assert summary["counter"] == 1
    assert summary["max_sequence"] == 2
    assert db_session.get(RuntimeExecution, execution.id).last_event_sequence == 1


def test_unknown_execution_consistency_check_fails_closed(db_session) -> None:
    with pytest.raises(LookupError, match="was not found"):
        RuntimeExecutionService.check_execution_event_sequence(
            db_session, "00000000-0000-0000-0000-000000000001"
        )
