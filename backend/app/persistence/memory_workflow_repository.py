from uuid import UUID

from app.contracts.workflow_repository import WorkflowRepository
from app.runtime.task import Task
from app.runtime.workflow import Workflow


class InMemoryWorkflowRepository(WorkflowRepository):
    """
    Simple in-memory implementation used for development
    and unit testing.
    """

    def __init__(self) -> None:

        self._workflows: dict[UUID, Workflow] = {}

        self._tasks: dict[UUID, Task] = {}

    # --------------------------------------------------
    # Generic Repository Interface
    # --------------------------------------------------

    async def save(
        self,
        workflow: Workflow,
    ) -> None:

        self._workflows[workflow.id] = workflow

    async def get(
        self,
        workflow_id: UUID,
    ) -> Workflow | None:

        return self._workflows.get(
            workflow_id,
        )

    async def delete(
        self,
        workflow_id: UUID,
    ) -> None:

        self._workflows.pop(
            workflow_id,
            None,
        )

    # --------------------------------------------------
    # Explicit Workflow Methods
    # --------------------------------------------------

    async def save_workflow(
        self,
        workflow: Workflow,
    ) -> None:

        await self.save(
            workflow,
        )

    async def update_workflow(
        self,
        workflow: Workflow,
    ) -> None:

        await self.save(
            workflow,
        )

    async def get_workflow(
        self,
        workflow_id: UUID,
    ) -> Workflow | None:

        return await self.get(
            workflow_id,
        )

    # --------------------------------------------------
    # Task Methods
    # --------------------------------------------------

    async def save_task(
        self,
        workflow: Workflow,
        task: Task,
    ) -> None:

        self._tasks[task.id] = task

    async def update_task(
        self,
        workflow: Workflow,
        task: Task,
    ) -> None:

        self._tasks[task.id] = task

    async def get_task(
        self,
        task_id: UUID,
    ) -> Task | None:

        return self._tasks.get(
            task_id,
        )
