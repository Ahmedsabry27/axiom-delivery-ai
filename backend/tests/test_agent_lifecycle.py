from __future__ import annotations

from uuid import uuid4

import pytest

from app.agents.default_agent import DefaultAgent
from app.agents.models.agent import AgentStatus
from app.runtime.context import RuntimeContext
from app.runtime.task import Task


@pytest.fixture
def agent():
    return DefaultAgent()


@pytest.fixture
def context():
    return RuntimeContext(
        request_id=uuid4(),
        workflow_id=uuid4(),
        session_id=uuid4(),
        conversation_id=uuid4(),
        tenant_id="demo",
        user_id="ahmed",
        goal="Test agent lifecycle",
        trace_id=str(uuid4()),
        metadata={},
        available_agents=["default-agent"],
        available_tools=[],
    )


@pytest.fixture
def task():
    return Task(
        name="Lifecycle Test Task",
        agent="default-agent",
    )


def test_agent_initial_state(agent):
    """
    Agent should start in CREATED state.
    """

    assert agent.definition.status == (AgentStatus.CREATED)

    assert agent.name == "default-agent"


@pytest.mark.asyncio
async def test_agent_initialize(agent):
    """
    Initialize should move agent to READY state.
    """

    await agent.initialize()

    assert agent.definition.status == (AgentStatus.READY)


@pytest.mark.asyncio
async def test_agent_execute_updates_telemetry(
    agent,
    context,
    task,
):
    """
    Execution should:
    - return successful result
    - update execution metrics
    """

    await agent.initialize()

    result = await agent.execute(
        context=context,
        task=task,
    )

    assert result.success is True

    assert result.output["workflow_id"] == (str(context.workflow_id))

    assert result.output["request_id"] == (str(context.request_id))

    assert agent.definition.executions == 1

    assert agent.definition.successful_executions == 1

    assert agent.definition.failed_executions == 0


@pytest.mark.asyncio
async def test_agent_health_check(
    agent,
):
    """
    Health check should return
    agent telemetry.
    """

    await agent.initialize()

    health = await agent.health_check()

    assert health.healthy is True

    assert health.status == (AgentStatus.READY.value)

    assert health.executions == 0


@pytest.mark.asyncio
async def test_agent_health_after_execution(
    agent,
    context,
    task,
):
    """
    Health should expose execution metrics.
    """

    await agent.initialize()

    await agent.execute(
        context=context,
        task=task,
    )

    health = await agent.health_check()

    assert health.executions == 1

    assert health.successful_executions == 1

    assert health.failed_executions == 0

    assert health.success_rate() == 100.0


@pytest.mark.asyncio
async def test_agent_shutdown(
    agent,
):
    """
    Shutdown should stop the agent.
    """

    await agent.initialize()

    await agent.shutdown()

    assert agent.definition.status == (AgentStatus.STOPPED)
