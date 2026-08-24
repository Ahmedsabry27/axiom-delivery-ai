from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from app.actions.models.action_result import ActionResult
from app.actions.registry import ActionRegistry


class ActionExecutor:
    """
    Executes registered actions.

    Responsibilities:

    - Discover action
    - Validate existence
    - Execute action
    - Capture execution metadata
    """

    def __init__(
        self,
        registry: ActionRegistry,
    ) -> None:

        self._registry = registry

    async def execute(
        self,
        action_name: str,
        input_data: dict,
    ) -> ActionResult:
        """
        Execute action by name.
        """

        action = self._registry.get(action_name)

        if action is None:
            raise ValueError(f"Action '{action_name}' not found.")

        execution_id = str(uuid4())

        started_at = datetime.now(UTC)

        try:
            result = await action.execute(input_data)

            result.metadata.update(
                {
                    "execution_id": execution_id,
                    "started_at": started_at.isoformat(),
                    "completed_at": datetime.now(UTC).isoformat(),
                    "status": "SUCCESS",
                }
            )

            return result

        # Executor boundaries must convert arbitrary action failures into ActionResult.
        except Exception as ex:  # noqa: BLE001
            return ActionResult(
                success=False,
                action_name=action_name,
                output={},
                error=str(ex),
                metadata={
                    "execution_id": execution_id,
                    "status": "FAILED",
                },
            )
