from __future__ import annotations

import pytest

from app.actions.contracts.action import Action
from app.actions.models.action_result import ActionResult


class DummyAction(Action):
    name = "dummy-action"

    async def execute(
        self,
        input_data: dict,
    ) -> ActionResult:

        return ActionResult(
            success=True,
            action_name=self.name,
            output={"message": "Action executed"},
        )


@pytest.mark.asyncio
async def test_action_contract_execution():

    action = DummyAction()

    result = await action.execute({"request": "test"})

    assert isinstance(
        result,
        ActionResult,
    )

    assert result.success is True

    assert result.action_name == "dummy-action"

    assert result.output["message"] == "Action executed"
