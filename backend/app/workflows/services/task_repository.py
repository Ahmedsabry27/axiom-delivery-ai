from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.database.models.task import Task


class TaskRepository:
    """
    Persistence layer for workflow tasks.

    Responsibilities:

    - Create task records
    - Retrieve workflow tasks
    - Assign agents
    - Update task status
    - Complete tasks
    """

    def __init__(
        self,
        db: Session,
    ) -> None:

        self._db = db

    def create_task(
        self,
        workflow_id: int,
        name: str,
        agent: str | None = None,
    ) -> Task:
        """
        Create a workflow task.
        """

        task = Task(
            workflow_id=workflow_id,
            name=name,
            status="PENDING",
            agent=agent,
        )

        self._db.add(task)

        self._db.commit()

        self._db.refresh(task)

        return task

    def get_tasks_by_workflow(
        self,
        workflow_id: int,
    ) -> list[Task]:

        return self._db.query(Task).filter(Task.workflow_id == workflow_id).all()

    def assign_agent(
        self,
        task_id: int,
        agent: str,
    ) -> Task | None:

        task = self._db.get(
            Task,
            task_id,
        )

        if task is None:
            return None

        task.agent = agent

        self._db.commit()

        self._db.refresh(task)

        return task

    def update_status(
        self,
        task_id: int,
        status: str,
    ) -> Task | None:

        task = self._db.get(
            Task,
            task_id,
        )

        if task is None:
            return None

        task.status = status

        if status == "RUNNING":
            task.started_at = datetime.now(UTC)

        self._db.commit()

        self._db.refresh(task)

        return task

    def complete_task(
        self,
        task_id: int,
    ) -> Task | None:

        task = self._db.get(
            Task,
            task_id,
        )

        if task is None:
            return None

        task.status = "COMPLETED"

        task.completed_at = datetime.now(UTC)

        self._db.commit()

        self._db.refresh(task)

        return task
