import pytest

from app.events.runtime_events import (
    WorkflowStarted,
)


@pytest.mark.asyncio
async def test_event_publish(event_bus):

    received = []

    async def handler(event):

        received.append(event)

    event_bus.subscribe(
        WorkflowStarted,
        handler,
    )

    await event_bus.publish(
        WorkflowStarted(
            source="test",
            payload={"id": "123"},
        )
    )

    assert len(received) == 1
