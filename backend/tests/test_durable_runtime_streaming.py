from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

from app.core.config import settings
from app.database.session import SessionLocal
from app.models.runtime_execution import RuntimeExecution, RuntimeExecutionEvent
from app.runtime.execution_tracker import ExecutionTracker
from app.services.runtime_execution_service import RuntimeExecutionService


def create_execution() -> RuntimeExecution:
    with SessionLocal() as db:
        execution = RuntimeExecution(
            id=uuid4(),
            conversation_id=uuid4(),
            workflow_id=uuid4(),
            user_id="durable-stream-user",
            tenant_id="durable-stream-tenant",
            status="PENDING",
            started_at=None,
            steps=[],
            runtime_metadata={},
            token_usage={},
        )
        db.add(execution)
        db.commit()
        db.refresh(execution)
        db.expunge(execution)
        return execution


def service() -> RuntimeExecutionService:
    instance = object.__new__(RuntimeExecutionService)
    instance._tracker = ExecutionTracker()
    return instance


async def collect(stream, count: int) -> list[dict]:
    events = []
    async for event in stream:
        if event.get("type") != "heartbeat":
            events.append(event)
        if len(events) == count:
            await stream.aclose()
            break
    return events


@pytest.mark.asyncio
async def test_initial_replay_is_ordered_and_terminal_closes() -> None:
    writer = service()
    reader = service()
    execution = create_execution()
    writer.transition_execution(execution.id, "RUNNING")
    writer.append_runtime_event(
        execution.id,
        {"type": "intent.completed", "name": "Intent", "status": "completed"},
    )
    writer.transition_execution(execution.id, "COMPLETED")

    events = [event async for event in reader.stream(str(execution.id))]

    assert [event["sequence"] for event in events] == [1, 2, 3]
    assert [event["type"] for event in events] == [
        "runtime.started",
        "intent.completed",
        "runtime.completed",
    ]


@pytest.mark.asyncio
async def test_cursor_replay_excludes_already_delivered_events() -> None:
    writer = service()
    reader = service()
    execution = create_execution()
    writer.transition_execution(execution.id, "RUNNING")
    for index in range(4):
        writer.append_runtime_event(
            execution.id,
            {"type": "step", "name": f"Step {index}", "status": "completed"},
        )
    writer.transition_execution(execution.id, "COMPLETED")

    events = [
        event async for event in reader.stream(str(execution.id), after_sequence=3)
    ]
    assert [event["sequence"] for event in events] == [4, 5, 6]


@pytest.mark.asyncio
async def test_cross_instance_poll_discovers_event_without_tracker_signal(
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "RUNTIME_EVENT_POLL_INTERVAL_SECONDS", 0.05)
    writer = service()
    reader = service()
    execution = create_execution()
    writer.transition_execution(execution.id, "RUNNING")
    stream = reader.stream(str(execution.id), after_sequence=1)

    async def persist_on_other_instance() -> None:
        await asyncio.sleep(0.08)
        writer.append_runtime_event(
            execution.id,
            {"type": "tool_started", "name": "jira.create_issue", "status": "running"},
        )
        writer.append_runtime_event(
            execution.id,
            {
                "type": "tool_completed",
                "name": "jira.create_issue",
                "status": "completed",
            },
        )
        writer.transition_execution(execution.id, "COMPLETED")

    task = asyncio.create_task(persist_on_other_instance())
    events = await asyncio.wait_for(collect(stream, 3), timeout=2)
    await task

    assert [event["type"] for event in events] == [
        "tool_started",
        "tool_completed",
        "runtime.completed",
    ]
    assert reader._tracker.listeners.get(str(execution.id)) is None


@pytest.mark.asyncio
async def test_waiting_event_is_nonterminal_and_resume_is_delivered(
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "RUNTIME_EVENT_POLL_INTERVAL_SECONDS", 0.05)
    writer = service()
    reader = service()
    execution = create_execution()
    writer.transition_execution(execution.id, "RUNNING")
    writer.transition_execution(execution.id, "WAITING_FOR_INPUT")
    stream = reader.stream(str(execution.id))

    async def resume() -> None:
        await asyncio.sleep(0.08)
        writer.transition_execution(execution.id, "RUNNING")
        writer.transition_execution(execution.id, "COMPLETED")

    task = asyncio.create_task(resume())
    events = await asyncio.wait_for(collect(stream, 4), timeout=2)
    await task
    assert [event["type"] for event in events] == [
        "runtime.started",
        "runtime.waiting_for_input",
        "runtime.resumed",
        "runtime.completed",
    ]


@pytest.mark.asyncio
async def test_batch_pagination_delivers_all_events(monkeypatch) -> None:
    monkeypatch.setattr(settings, "RUNTIME_EVENT_BATCH_SIZE", 2)
    writer = service()
    reader = service()
    execution = create_execution()
    writer.transition_execution(execution.id, "RUNNING")
    for index in range(5):
        writer.append_runtime_event(
            execution.id,
            {"type": "step", "name": f"Batch {index}", "status": "completed"},
        )
    writer.transition_execution(execution.id, "COMPLETED")

    events = [event async for event in reader.stream(str(execution.id))]
    assert [event["sequence"] for event in events] == list(range(1, 8))


@pytest.mark.asyncio
async def test_timeout_and_cancellation_histories_close_in_order() -> None:
    for terminal, child_type in (
        ("TIMED_OUT", "tool_timed_out"),
        ("CANCELLED", "tool_cancelled"),
    ):
        writer = service()
        reader = service()
        execution = create_execution()
        writer.transition_execution(execution.id, "RUNNING")
        writer.append_runtime_event(
            execution.id,
            {
                "type": "tool_started",
                "name": "jira.get_create_metadata",
                "status": "running",
            },
        )
        writer.append_runtime_event(
            execution.id,
            {
                "type": child_type,
                "name": "jira.get_create_metadata",
                "status": terminal.lower(),
            },
        )
        writer.transition_execution(execution.id, terminal)

        events = [event async for event in reader.stream(str(execution.id))]
        assert [event["type"] for event in events][-3:] == [
            "tool_started",
            child_type,
            f"runtime.{terminal.lower()}",
        ]


@pytest.mark.asyncio
async def test_heartbeat_is_transport_only_and_cleanup_removes_listener(
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "RUNTIME_EVENT_POLL_INTERVAL_SECONDS", 0.05)
    monkeypatch.setattr(settings, "RUNTIME_SSE_HEARTBEAT_SECONDS", 0.05)
    writer = service()
    reader = service()
    execution = create_execution()
    writer.transition_execution(execution.id, "RUNNING")
    stream = reader.stream(str(execution.id), after_sequence=1)

    heartbeat = await asyncio.wait_for(anext(stream), timeout=1)
    await stream.aclose()

    assert heartbeat == {"type": "heartbeat"}
    with SessionLocal() as db:
        assert (
            db.query(RuntimeExecutionEvent).filter_by(execution_id=execution.id).count()
            == 1
        )
    assert reader._tracker.listeners.get(str(execution.id)) is None


@pytest.mark.asyncio
async def test_terminal_reconnect_after_final_sequence_closes_without_duplicate() -> (
    None
):
    writer = service()
    reader = service()
    execution = create_execution()
    writer.transition_execution(execution.id, "RUNNING")
    writer.transition_execution(execution.id, "COMPLETED")

    events = [
        event async for event in reader.stream(str(execution.id), after_sequence=2)
    ]
    assert events == []
