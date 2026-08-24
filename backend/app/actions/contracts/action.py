from __future__ import annotations

from abc import ABC, abstractmethod

from app.actions.models.action_definition import (
    ActionDefinition,
)
from app.actions.models.action_result import (
    ActionResult,
)


class Action(ABC):
    """
    Enterprise Action Contract.
    """

    name: str

    definition: ActionDefinition

    @abstractmethod
    async def execute(
        self,
        input_data: dict,
    ) -> ActionResult:
        """
        Execute action.
        """
