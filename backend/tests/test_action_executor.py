from app.actions.contracts.action import Action
from app.actions.models.action_result import (
    ActionResult,
)
from app.actions.registry import ActionRegistry
from app.actions.services.action_executor import (
    ActionExecutor,
)


class EmailAction(Action):
    name = "send-email"

    async def execute(
        self,
        input_data: dict,
    ):

        return ActionResult(
            success=True,
            action_name=self.name,
            output={"sent": True},
        )


class FailureAction(Action):
    name = "failed-action"

    async def execute(
        self,
        input_data: dict,
    ):

        raise Exception("Execution failed")


async def test_execute_registered_action():

    registry = ActionRegistry()

    registry.register(EmailAction())

    executor = ActionExecutor(registry)

    result = await executor.execute("send-email", {"to": "user@test.com"})

    assert result.success is True

    assert result.action_name == "send-email"


async def test_execute_unknown_action():

    registry = ActionRegistry()

    executor = ActionExecutor(registry)

    try:
        await executor.execute("unknown", {})

        raise AssertionError()

    except ValueError:
        assert True


async def test_failed_action_execution():

    registry = ActionRegistry()

    registry.register(FailureAction())

    executor = ActionExecutor(registry)

    result = await executor.execute("failed-action", {})

    assert result.success is False

    assert result.metadata["status"] == "FAILED"
