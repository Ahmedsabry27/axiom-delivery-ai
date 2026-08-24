from __future__ import annotations

from uuid import uuid4

import pytest

from app.agents.default_agent import DefaultAgent
from app.agents.models.agent import (
    AgentDefinition,
)
from app.agents.models.capability import (
    AgentCapability,
)
from app.agents.models.metadata import (
    AgentMetadata,
)
from app.agents.registry import AgentRegistry
from app.contracts.results import AgentResult
from app.runtime.context import RuntimeContext
from app.runtime.task import Task


class ReportAgent(DefaultAgent):
    """
    Test agent that supports report generation.
    """

    name = "report-agent"

    def __init__(self):

        self.definition = AgentDefinition(
            metadata=AgentMetadata(
                name=self.name,
                description=("Agent specialized in report generation"),
            ),
            capabilities=[
                AgentCapability(
                    name="report-generation",
                    description=("Generate business reports"),
                    supported_tasks=[
                        "Generate Report",
                    ],
                )
            ],
        )

    async def execute(
        self,
        context: RuntimeContext,
        task: Task,
    ) -> AgentResult:

        return AgentResult(
            success=True,
            output={
                "agent_used": self.name,
                "goal": context.goal,
                "task": task.name,
            },
            metadata={
                "agent": self.name,
            },
        )


@pytest.mark.asyncio
async def test_dynamic_agent_selection_by_task_requirement():
    """
    Verify:

    Goal
      |
    Task requirements
      |
    Agent Registry
      |
    Capability Matching
      |
    Correct Agent Selected
    """

    registry = AgentRegistry()

    default_agent = DefaultAgent()
    report_agent = ReportAgent()

    registry.register(default_agent)

    registry.register(report_agent)

    selected_agent = registry.select_agent(["report-generation"])

    assert selected_agent.name == ("report-agent")


@pytest.mark.asyncio
async def test_selected_agent_executes_task():

    registry = AgentRegistry()

    report_agent = ReportAgent()

    registry.register(report_agent)

    agent = registry.select_agent(["report-generation"])

    context = RuntimeContext(
        request_id=uuid4(),
        workflow_id=uuid4(),
        session_id=uuid4(),
        conversation_id=uuid4(),
        tenant_id="demo",
        user_id="ahmed",
        goal="Generate customer report",
        trace_id=str(uuid4()),
        metadata={},
        available_agents=["report-agent"],
        available_tools=[],
    )

    task = Task(
        name="Generate Report",
        description=("Generate customer report"),
        required_capabilities=["report-generation"],
    )

    result = await agent.execute(
        context=context,
        task=task,
    )

    assert result.success is True

    assert result.output["agent_used"] == "report-agent"

    assert result.output["goal"] == "Generate customer report"


@pytest.mark.asyncio
async def test_dynamic_selection_fails_when_capability_missing():

    registry = AgentRegistry()

    registry.register(ReportAgent())

    with pytest.raises(
        ValueError,
        match="No agent found matching required capabilities",
    ):
        registry.select_agent(["data-analysis"])
