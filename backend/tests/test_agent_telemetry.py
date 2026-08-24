from uuid import uuid4

import pytest

from app.agents.default_agent import DefaultAgent
from app.runtime.context import RuntimeContext
from app.runtime.task import Task


@pytest.mark.asyncio
async def test_agent_execution_metadata():

    agent = DefaultAgent()

    await agent.initialize()

    context = RuntimeContext(
        request_id=uuid4(),
        workflow_id=uuid4(),
        session_id=uuid4(),
        conversation_id=uuid4(),
        tenant_id="demo",
        user_id="ahmed",
        goal="Telemetry test",
        trace_id="trace",
        metadata={},
        available_agents=["default-agent"],
        available_tools=[],
    )

    task = Task(
        name="Telemetry Task",
        agent="default-agent",
    )

    result = await agent.execute(
        context,
        task,
    )

    assert result.success is True

    assert result.execution_metadata["agent"] == "default-agent"

    assert result.execution_metadata["task"] == "Telemetry Task"

    assert result.execution_metadata["status"] == "SUCCESS"

    assert result.execution_metadata["duration_ms"] >= 0
