import pytest

from app.actions.contracts.action import Action
from app.actions.models.action_permission import (
    ActionPermission,
)
from app.actions.models.action_request import (
    ActionRequest,
)
from app.actions.models.action_result import (
    ActionResult,
)
from app.actions.registry import (
    ActionRegistry,
)
from app.actions.services.action_executor import (
    ActionExecutor,
)
from app.actions.services.action_permission_validator import (
    ActionPermissionValidator,
)
from app.actions.services.agent_action_runner import (
    AgentActionRunner,
)


class DeployAction(Action):
    name = "deploy"

    async def execute(
        self,
        input_data,
    ):

        return ActionResult(
            success=True,
            action_name=self.name,
            output={"deployment": "completed"},
        )


@pytest.mark.asyncio
async def test_agent_to_action_flow():

    registry = ActionRegistry()

    registry.register(DeployAction())

    executor = ActionExecutor(registry)

    validator = ActionPermissionValidator()

    validator.register_permission(
        ActionPermission(
            action_name="deploy",
            allowed_roles=["release-manager"],
        )
    )

    runner = AgentActionRunner(
        executor,
        validator,
    )

    result = await runner.run(
        ActionRequest(
            action_name="deploy",
            user_id="user1",
            roles=["release-manager"],
            input_data={"environment": "production"},
        )
    )

    assert result.success is True
