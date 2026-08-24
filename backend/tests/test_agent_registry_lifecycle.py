import pytest

from app.agents.default_agent import DefaultAgent
from app.agents.models.agent import AgentStatus
from app.agents.registry import AgentRegistry


@pytest.mark.asyncio
async def test_initialize_registered_agents():

    registry = AgentRegistry()

    agent = DefaultAgent()

    registry.register(agent)

    await registry.initialize_all()

    assert agent.definition.status == AgentStatus.READY


@pytest.mark.asyncio
async def test_shutdown_registered_agents():

    registry = AgentRegistry()

    agent = DefaultAgent()

    registry.register(agent)

    await registry.initialize_all()

    await registry.shutdown_all()

    assert agent.definition.status == AgentStatus.STOPPED


@pytest.mark.asyncio
async def test_health_check_all_agents():

    registry = AgentRegistry()

    agent = DefaultAgent()

    registry.register(agent)

    await registry.initialize_all()

    health = await registry.health_check_all()

    assert agent.name in health

    assert health[agent.name].status == AgentStatus.READY.value


def test_find_agent_by_capability():

    registry = AgentRegistry()

    agent = DefaultAgent()

    registry.register(agent)

    result = registry.find_by_capability("report-generation")

    assert isinstance(result, list)


def test_available_agents_only_returns_ready_agents():

    registry = AgentRegistry()

    agent = DefaultAgent()

    registry.register(agent)

    # CREATED state initially
    available = registry.available_agents()

    assert len(available) == 0


@pytest.mark.asyncio
async def test_available_agents_after_initialization():

    registry = AgentRegistry()

    agent = DefaultAgent()

    registry.register(agent)

    await registry.initialize_all()

    available = registry.available_agents()

    assert len(available) == 1

    assert available[0] == agent
