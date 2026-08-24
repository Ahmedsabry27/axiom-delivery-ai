from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from app.logging.logger import logger
from app.runtime.task import Task
from app.runtime.task_graph import TaskGraph


class ParallelExecutor:
    """
    Executes workflow tasks concurrently while respecting dependency constraints.

    Responsibilities
    ----------------
    - Schedule independent tasks concurrently
    - Respect dependency ordering through TaskGraph
    - Limit concurrency using semaphore

    Does NOT:
    - Publish events
    - Persist state
    - Execute agents directly
    - Handle retries

    Those responsibilities belong to DefaultWorkflowEngine.
    """

    def __init__(
        self,
        *,
        max_parallel_tasks: int = 10,
        fail_fast: bool = True,
    ) -> None:

        self._semaphore = asyncio.Semaphore(max_parallel_tasks)

        self._fail_fast = fail_fast

    async def execute(
        self,
        graph: TaskGraph,
        execute_task: Callable[[Task], Awaitable[dict[str, Any]]],
    ) -> list[dict[str, Any]]:
        """
        Execute workflow tasks respecting dependencies.

        Independent tasks run in parallel.
        """

        results: list[dict[str, Any]] = []

        ready = graph.get_ready_tasks()

        while ready:
            logger.info(
                "Executing %d ready task(s).",
                len(ready),
            )

            batch_results = await self._execute_batch(
                ready,
                execute_task,
            )

            newly_ready: list[Task] = []

            for task, result, error in batch_results:
                if error is None:
                    results.append(result)

                    unlocked = graph.mark_completed(
                        task.id,
                    )

                    newly_ready.extend(unlocked)

                else:
                    logger.exception(
                        "Task '%s' failed.",
                        task.name,
                        exc_info=error,
                    )

                    graph.mark_failed(
                        task.id,
                    )

                    if self._fail_fast:
                        raise error

            ready = newly_ready

        if not graph.is_complete():
            raise RuntimeError(
                "Workflow terminated before all tasks reached a terminal state."
            )

        return results

    async def _execute_batch(
        self,
        tasks: list[Task],
        execute_task: Callable[[Task], Awaitable[dict[str, Any]]],
    ) -> list[
        tuple[
            Task,
            dict[str, Any] | None,
            Exception | None,
        ]
    ]:
        """
        Execute one batch of independent tasks.

        Uses task.id instead of Task object as dictionary key
        because Task is mutable and therefore unhashable.
        """

        futures: dict[str, asyncio.Task] = {}

        async with asyncio.TaskGroup() as tg:
            for task in tasks:
                futures[str(task.id)] = tg.create_task(
                    self._execute_single(
                        task,
                        execute_task,
                    )
                )

        results: list[
            tuple[
                Task,
                dict[str, Any] | None,
                Exception | None,
            ]
        ] = []

        for task in tasks:
            future = futures[str(task.id)]

            try:
                results.append(
                    (
                        task,
                        future.result(),
                        None,
                    )
                )

            # Each future is an isolation boundary; failures are returned with its task.
            except Exception as ex:  # noqa: BLE001
                results.append(
                    (
                        task,
                        None,
                        ex,
                    )
                )

        return results

    async def _execute_single(
        self,
        task: Task,
        execute_task: Callable[[Task], Awaitable[dict[str, Any]]],
    ) -> dict[str, Any]:
        """
        Execute a single task under concurrency limit.
        """

        async with self._semaphore:
            logger.debug(
                "Starting task '%s'",
                task.name,
            )

            result = await execute_task(
                task,
            )

            logger.debug(
                "Finished task '%s'",
                task.name,
            )

            return result
