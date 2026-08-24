from abc import ABC, abstractmethod

from app.runtime.context import RuntimeContext
from app.runtime.execution_plan import ExecutionPlan


class Planner(ABC):
    """
    Responsible for producing an execution plan.
    """

    @abstractmethod
    async def plan(
        self,
        context: RuntimeContext,
    ) -> ExecutionPlan: ...
