import pytest

from app.agents.default_agent import DefaultAgent
from app.agents.registry import AgentRegistry
from app.agents.services.agent_lifecycle_manager import (
    AgentLifecycleManager,
)
from app.events.agent_events import (
    AgentExecutionFailed,
    AgentReady,
    AgentRegistered,
    AgentStarted,
    AgentStopped,
)
from app.runtime.event_bus import EventBus


class EventCollector:
    """
    Simple event subscriber for tests.
    """

    def __init__(self):
        self.events = []

    async def handle(
        self,
        event,
    ):
        self.events.append(event)


@pytest.fixture
def registry():

    return AgentRegistry()


@pytest.fixture
def event_bus():

    return EventBus()


@pytest.fixture
def collector(
    event_bus,
):

    collector = EventCollector()

    event_bus.subscribe(
        AgentRegistered,
        collector.handle,
    )

    event_bus.subscribe(
        AgentStarted,
        collector.handle,
    )

    event_bus.subscribe(
        AgentReady,
        collector.handle,
    )

    event_bus.subscribe(
        AgentStopped,
        collector.handle,
    )

    event_bus.subscribe(
        AgentExecutionFailed,
        collector.handle,
    )

    return collector


@pytest.mark.asyncio
async def test_agent_registered_event(
    registry,
    event_bus,
    collector,
):

    manager = AgentLifecycleManager(
        registry,
        event_bus,
    )

    agent = DefaultAgent()

    await manager.register_agent(agent)

    assert len(collector.events) == 1

    event = collector.events[0]

    assert isinstance(
        event,
        AgentRegistered,
    )

    assert event.agent_name == ("default-agent")


@pytest.mark.asyncio
async def test_agent_start_and_ready_events(
    registry,
    event_bus,
    collector,
):

    agent = DefaultAgent()

    registry.register(agent)

    manager = AgentLifecycleManager(
        registry,
        event_bus,
    )

    await manager.initialize_agent("default-agent")

    assert len(collector.events) == 2

    assert isinstance(
        collector.events[0],
        AgentStarted,
    )

    assert isinstance(
        collector.events[1],
        AgentReady,
    )

    assert agent.definition.status.value == "READY"


@pytest.mark.asyncio
async def test_agent_stopped_event(
    registry,
    event_bus,
    collector,
):

    agent = DefaultAgent()

    registry.register(agent)

    manager = AgentLifecycleManager(
        registry,
        event_bus,
    )

    await manager.stop_agent("default-agent")

    assert len(collector.events) == 1

    event = collector.events[0]

    assert isinstance(
        event,
        AgentStopped,
    )

    assert event.agent_name == ("default-agent")

    assert agent.definition.status.value == "STOPPED"


@pytest.mark.asyncio
async def test_agent_initialization_failure_event(
    registry,
    event_bus,
    collector,
):

    class FailingAgent(DefaultAgent):
        name = "failing-agent"

        async def initialize(
            self,
        ):

            raise RuntimeError("Initialization failed")

    agent = FailingAgent()

    registry.register(agent)

    manager = AgentLifecycleManager(
        registry,
        event_bus,
    )

    with pytest.raises(RuntimeError):
        await manager.initialize_agent("failing-agent")

    assert len(collector.events) == 2

    assert isinstance(
        collector.events[0],
        AgentStarted,
    )

    assert isinstance(
        collector.events[1],
        AgentExecutionFailed,
    )

    assert collector.events[1].error == "Initialization failed"
