from __future__ import annotations

import pytest

from app.actions.contracts.action import Action
from app.actions.models.action_result import ActionResult
from app.actions.registry import ActionRegistry


class DummyAction(Action):
    name = "test-action"

    async def execute(
        self,
        input_data: dict,
    ) -> ActionResult:

        return ActionResult(
            success=True,
            action_name=self.name,
            output={},
        )


def test_register_action():

    registry = ActionRegistry()

    action = DummyAction()

    registry.register(action)

    retrieved = registry.get("test-action")

    assert retrieved is action


def test_duplicate_action_registration():

    registry = ActionRegistry()

    action = DummyAction()

    registry.register(action)

    with pytest.raises(ValueError):
        registry.register(action)


def test_list_actions():

    registry = ActionRegistry()

    registry.register(DummyAction())

    actions = registry.list_actions()

    assert "test-action" in actions
