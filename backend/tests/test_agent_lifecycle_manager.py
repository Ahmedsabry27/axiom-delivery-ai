import pytest

from app.agents.default_agent import (
    DefaultAgent,
)
from app.agents.registry import AgentRegistry
from app.agents.services.agent_lifecycle_manager import (
    AgentLifecycleManager,
)


@pytest.mark.asyncio
async def test_initialize_agent():

    registry = AgentRegistry()

    agent = DefaultAgent()

    registry.register(agent)

    manager = AgentLifecycleManager(registry)

    await manager.initialize_agent("default-agent")

    assert agent.definition.status.value == "READY"


@pytest.mark.asyncio
async def test_stop_agent():

    registry = AgentRegistry()

    agent = DefaultAgent()

    registry.register(agent)

    manager = AgentLifecycleManager(registry)

    await manager.initialize_agent("default-agent")

    await manager.stop_agent("default-agent")

    assert agent.definition.status.value == "STOPPED"


@pytest.mark.asyncio
async def test_health_check():

    registry = AgentRegistry()

    agent = DefaultAgent()

    registry.register(agent)

    manager = AgentLifecycleManager(registry)

    await manager.initialize_agent("default-agent")

    health = await manager.health_check("default-agent")

    assert health.status == "READY"
