from abc import ABC, abstractmethod

from app.runtime.task import Task
from app.runtime.workflow import Workflow


class WorkflowRepository(ABC):
    """
    Persistence contract for workflow execution state.
    """

    @abstractmethod
    async def save_workflow(
        self,
        workflow: Workflow,
    ) -> None:
        """
        Persist a newly created workflow.
        """
        ...

    @abstractmethod
    async def update_workflow(
        self,
        workflow: Workflow,
    ) -> None:
        """
        Persist workflow state changes.
        """
        ...

    @abstractmethod
    async def save_task(
        self,
        workflow: Workflow,
        task: Task,
    ) -> None:
        """
        Persist a newly started task.
        """
        ...

    @abstractmethod
    async def update_task(
        self,
        workflow: Workflow,
        task: Task,
    ) -> None:
        """
        Persist task state changes.
        """
        ...
