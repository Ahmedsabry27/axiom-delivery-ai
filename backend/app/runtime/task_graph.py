from __future__ import annotations

from collections import defaultdict
from uuid import UUID

from app.runtime.task import Task


class TaskGraph:
    """
    Represents a directed acyclic graph (DAG) of workflow tasks.

    Responsibilities
    ----------------
    - Track task dependencies.
    - Identify runnable tasks.
    - Unlock downstream tasks.
    - Detect workflow completion.
    - Block downstream tasks when a dependency fails.
    """

    def __init__(self, tasks: list[Task]) -> None:
        self._tasks: dict[UUID, Task] = {task.id: task for task in tasks}

        # Parent -> Children
        self._children: dict[UUID, list[UUID]] = defaultdict(list)

        # Task -> Remaining unresolved dependencies
        self._remaining_dependencies: dict[UUID, int] = {}

        # Completed tasks
        self._completed: set[UUID] = set()

        # Failed tasks
        self._failed: set[UUID] = set()

        # Tasks blocked because an upstream dependency failed
        self._blocked: set[UUID] = set()

        for task in tasks:
            self._remaining_dependencies[task.id] = len(task.depends_on)

            for dependency in task.depends_on:
                self._children[dependency].append(task.id)

    # ------------------------------------------------------------------
    # Scheduling
    # ------------------------------------------------------------------

    def get_ready_tasks(self) -> list[Task]:
        """
        Return all tasks whose dependencies have been satisfied.
        """

        ready: list[Task] = []

        for task_id, remaining in self._remaining_dependencies.items():
            if remaining != 0:
                continue

            if task_id in self._completed:
                continue

            if task_id in self._failed:
                continue

            if task_id in self._blocked:
                continue

            ready.append(self._tasks[task_id])

        return ready

    def mark_completed(
        self,
        task_id: UUID,
    ) -> list[Task]:
        """
        Mark a task as completed and unlock newly-runnable tasks.
        """

        if task_id in self._completed:
            return []

        self._completed.add(task_id)

        newly_ready: list[Task] = []

        for child in self._children.get(task_id, []):
            self._remaining_dependencies[child] -= 1

            if (
                self._remaining_dependencies[child] == 0
                and child not in self._blocked
                and child not in self._failed
            ):
                newly_ready.append(self._tasks[child])

        return newly_ready

    def mark_failed(
        self,
        task_id: UUID,
    ) -> None:
        """
        Mark a task as failed.

        All downstream tasks become blocked because their
        dependencies can never be satisfied.
        """

        if task_id in self._failed:
            return

        self._failed.add(task_id)

        self._block_descendants(task_id)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def is_complete(self) -> bool:
        """
        Returns True when every executable task has finished.

        Blocked tasks are considered terminal.
        """

        terminal = len(self._completed) + len(self._failed) + len(self._blocked)

        return terminal == len(self._tasks)

    def task(
        self,
        task_id: UUID,
    ) -> Task:
        """
        Retrieve a task by id.
        """

        return self._tasks[task_id]

    def tasks(self) -> list[Task]:
        """
        Return all workflow tasks.
        """

        return list(self._tasks.values())

    @property
    def completed_tasks(self) -> set[UUID]:
        return self._completed.copy()

    @property
    def failed_tasks(self) -> set[UUID]:
        return self._failed.copy()

    @property
    def blocked_tasks(self) -> set[UUID]:
        return self._blocked.copy()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _block_descendants(
        self,
        task_id: UUID,
    ) -> None:
        """
        Recursively block every downstream task.
        """

        for child in self._children.get(task_id, []):
            if child in self._blocked:
                continue

            self._blocked.add(child)

            self._block_descendants(child)
