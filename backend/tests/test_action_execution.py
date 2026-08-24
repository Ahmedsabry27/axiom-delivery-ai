from __future__ import annotations

import pytest

from app.actions.contracts.action import Action
from app.actions.models.action_result import ActionResult


class SuccessfulAction(Action):
    name = "successful-action"

    async def execute(
        self,
        input_data: dict,
    ) -> ActionResult:

        return ActionResult(
            success=True,
            action_name=self.name,
            output={"status": "completed"},
        )


class FailedAction(Action):
    name = "failed-action"

    async def execute(
        self,
        input_data: dict,
    ) -> ActionResult:

        return ActionResult(
            success=False,
            action_name=self.name,
            output={"error": "execution failed"},
        )


@pytest.mark.asyncio
async def test_successful_action_execution():

    action = SuccessfulAction()

    result = await action.execute({})

    assert result.success is True

    assert result.output["status"] == "completed"


@pytest.mark.asyncio
async def test_failed_action_execution():

    action = FailedAction()

    result = await action.execute({})

    assert result.success is False

    assert result.output["error"] == "execution failed"
