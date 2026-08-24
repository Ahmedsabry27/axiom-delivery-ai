from app.agents.models.agent import (
    AgentDefinition,
)
from app.agents.models.metadata import (
    AgentMetadata,
)


def test_agent_execution_metrics():

    agent = AgentDefinition(
        metadata=AgentMetadata(
            name="test-agent",
            description="test",
        )
    )

    agent.record_execution(
        success=True,
        duration_ms=100,
    )

    agent.record_execution(
        success=False,
        duration_ms=300,
        error="timeout",
    )

    assert agent.executions == 2

    assert agent.successful_executions == 1

    assert agent.failed_executions == 1

    assert agent.success_rate() == 50

    assert agent.average_duration() == 200

    assert agent.last_error == "timeout"
