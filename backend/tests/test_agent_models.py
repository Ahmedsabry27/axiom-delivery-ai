from app.agents.models import (
    AgentCapability,
    AgentDefinition,
    AgentMetadata,
    AgentStatus,
)


def test_agent_capability_creation():

    capability = AgentCapability(
        name="reporting",
        description="Generate reports",
        supported_tasks=["summarize"],
    )

    assert capability.name == "reporting"
    assert "summarize" in capability.supported_tasks


def test_agent_metadata_creation():

    metadata = AgentMetadata(
        name="report-agent",
        version="1.0.0",
    )

    assert metadata.name == "report-agent"
    assert metadata.version == "1.0.0"


def test_agent_definition_capability_matching():

    capability = AgentCapability(
        name="reporting",
        description="Generate reports",
    )

    agent = AgentDefinition(
        metadata=AgentMetadata(name="report-agent"),
        capabilities=[capability],
    )

    assert agent.status == AgentStatus.CREATED

    assert agent.has_capability("reporting")

    assert not agent.has_capability("email")
