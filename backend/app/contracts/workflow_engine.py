from abc import ABC, abstractmethod

from app.contracts.results import WorkflowResult
from app.runtime.context import RuntimeContext
from app.runtime.workflow import Workflow


class WorkflowEngine(ABC):
    """
    Executes workflows.

    Implementations are responsible for:
    - Executing workflow tasks
    - Resolving the appropriate agent for each task
    - Delegating task execution to the agent
    - Returning the aggregated workflow result
    """

    @abstractmethod
    async def execute(
        self,
        workflow: Workflow,
        context: RuntimeContext,
    ) -> WorkflowResult:
        """
        Execute the supplied workflow within the given runtime context.

        Args:
            workflow: The workflow to execute.
            context: The runtime context shared across the workflow execution.

        Returns:
            The final workflow execution result.
        """
        ...
