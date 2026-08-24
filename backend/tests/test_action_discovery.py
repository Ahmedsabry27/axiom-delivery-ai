from __future__ import annotations

from app.actions.contracts.action import Action
from app.actions.models.action_definition import (
    ActionDefinition,
)
from app.actions.models.action_result import ActionResult
from app.actions.registry import ActionRegistry


class ReportAction(Action):
    name = "report-action"

    definition = ActionDefinition(
        name=name,
        description="Generate reports",
        category="reporting",
        required_permissions=["report.read"],
        supported_agents=["default-agent"],
    )

    async def execute(
        self,
        input_data: dict,
    ) -> ActionResult:

        return ActionResult(
            success=True,
            action_name=self.name,
            output={},
        )


class DeploymentAction(Action):
    name = "deployment-action"

    definition = ActionDefinition(
        name=name,
        description="Deploy application",
        category="deployment",
        required_permissions=["deployment.execute"],
        supported_agents=["deployment-agent"],
    )

    async def execute(
        self,
        input_data: dict,
    ) -> ActionResult:

        return ActionResult(
            success=True,
            action_name=self.name,
            output={},
        )


def test_find_action_by_category():

    registry = ActionRegistry()

    registry.register(ReportAction())

    registry.register(DeploymentAction())

    actions = registry.find_by_category("reporting")

    assert len(actions) == 1

    assert actions[0].name == "report-action"


def test_find_action_by_permission():

    registry = ActionRegistry()

    registry.register(DeploymentAction())

    actions = registry.find_by_permission("deployment.execute")

    assert actions[0].name == "deployment-action"


def test_find_action_by_agent():

    registry = ActionRegistry()

    registry.register(ReportAction())

    actions = registry.find_by_agent("default-agent")

    assert actions[0].name == "report-action"


def test_action_search():

    registry = ActionRegistry()

    registry.register(ReportAction())

    result = registry.search(
        category="reporting",
        permission="report.read",
    )

    assert len(result) == 1
