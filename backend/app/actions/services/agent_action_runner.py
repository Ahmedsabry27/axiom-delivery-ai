from __future__ import annotations

from app.actions.models.action_request import (
    ActionRequest,
)
from app.actions.services.action_executor import (
    ActionExecutor,
)
from app.actions.services.action_permission_validator import (
    ActionPermissionValidator,
)


class AgentActionRunner:
    """
    Connects Agent execution with Actions.

    Flow:

    Agent
      |
      v
    Permission
      |
      v
    Action Executor
      |
      v
    Result
    """

    def __init__(
        self,
        executor: ActionExecutor,
        permission_validator: ActionPermissionValidator,
    ):

        self._executor = executor

        self._permission_validator = permission_validator

    async def run(
        self,
        request: ActionRequest,
    ):

        allowed = self._permission_validator.validate(request)

        if not allowed:
            raise PermissionError("Action execution denied.")

        return await self._executor.execute(
            request.action_name,
            request.input_data,
        )
