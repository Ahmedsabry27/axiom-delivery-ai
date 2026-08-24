from __future__ import annotations

import pytest

from app.agents.default_agent import DefaultAgent
from app.agents.models.agent import (
    AgentDefinition,
    AgentStatus,
)
from app.agents.models.capability import (
    AgentCapability,
)
from app.agents.models.metadata import (
    AgentMetadata,
)
from app.agents.registry import AgentRegistry


class ReportingAgent(DefaultAgent):
    name = "reporting-agent"

    def __init__(self):

        self.definition = AgentDefinition(
            metadata=AgentMetadata(
                name=self.name,
                description="Reporting agent",
            ),
            capabilities=[
                AgentCapability(
                    name="report-generation",
                    description="Generate reports",
                    supported_tasks=[
                        "generate-report",
                    ],
                    supported_tools=[
                        "powerbi",
                    ],
                ),
                AgentCapability(
                    name="analytics",
                    description="Data analytics",
                    supported_tasks=[
                        "analyze-data",
                    ],
                ),
            ],
        )

        self.definition.status = AgentStatus.READY


class SimpleAgent(DefaultAgent):
    name = "simple-agent"

    def __init__(self):

        self.definition = AgentDefinition(
            metadata=AgentMetadata(
                name=self.name,
                description="Simple reporting agent",
            ),
            capabilities=[
                AgentCapability(
                    name="report-generation",
                    description="Basic reports",
                ),
            ],
        )

        self.definition.status = AgentStatus.READY


@pytest.fixture
def registry():

    registry = AgentRegistry()

    registry.register(ReportingAgent())

    registry.register(SimpleAgent())

    return registry


def test_search_agent_by_capability(
    registry,
):

    agents = registry.search(
        capability="report-generation",
    )

    names = [agent.name for agent in agents]

    assert "reporting-agent" in names

    assert "simple-agent" in names


def test_search_agent_by_task(
    registry,
):

    agents = registry.search(
        task="generate-report",
    )

    assert len(agents) == 1

    assert agents[0].name == "reporting-agent"


def test_search_agent_by_tool(
    registry,
):

    agents = registry.search(
        tool="powerbi",
    )

    assert len(agents) == 1

    assert agents[0].name == "reporting-agent"


def test_select_best_agent_by_capability_score(
    registry,
):

    agent = registry.select_agent(
        required_capabilities=[
            "report-generation",
            "analytics",
        ],
    )

    assert agent.name == "reporting-agent"


def test_select_agent_with_no_match(
    registry,
):

    with pytest.raises(ValueError):
        registry.select_agent(
            required_capabilities=[
                "medical-diagnosis",
            ]
        )


def test_unavailable_agent_is_not_selected(
    registry,
):

    reporting = registry.get("reporting-agent")

    reporting.definition.status = AgentStatus.FAILED

    agent = registry.select_agent(
        required_capabilities=[
            "report-generation",
        ]
    )

    assert agent.name == "simple-agent"
