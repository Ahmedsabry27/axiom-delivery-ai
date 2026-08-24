from __future__ import annotations

from datetime import UTC, datetime

from app.contracts.workflow_engine import Workflow
from app.contracts.workflow_repository import WorkflowRepository
from app.events.base import Event
from app.events.runtime_events import (
    TaskCompleted,
    TaskFailed,
    TaskStarted,
    WorkflowApprovalPending,
    WorkflowCancelled,
    WorkflowCompleted,
    WorkflowFailed,
    WorkflowPaused,
    WorkflowRecovering,
    WorkflowResumed,
    WorkflowStarted,
)
from app.runtime.event_bus import EventBus
from app.runtime.runtime_state import RuntimeState
from app.runtime.task import Task
from app.runtime.task_state import TaskState


class WorkflowStateManager:
    """
    Manages workflow and task lifecycle transitions.

    Responsibilities
    ----------------
    • Workflow state transitions
    • Task state transitions
    • Timestamp management
    • Duration calculation
    • Repository persistence
    • Runtime event publishing

    This class intentionally does NOT perform orchestration,
    retries, scheduling, timeout handling or dependency
    resolution. Those responsibilities belong to
    DefaultWorkflowEngine.
    """

    EVENT_SOURCE = "WorkflowStateManager"

    def __init__(
        self,
        repository: WorkflowRepository,
        event_bus: EventBus,
    ) -> None:
        self._repository = repository
        self._event_bus = event_bus

    # ------------------------------------------------------------------
    # Workflow Lifecycle
    # ------------------------------------------------------------------

    async def start_workflow(
        self,
        workflow: Workflow,
    ) -> None:
        """
        Transition a workflow into the RUNNING state.
        """

        workflow.state = RuntimeState.RUNNING

        # Preserve the original start time when resuming
        workflow.started_at = workflow.started_at or datetime.now(UTC)

        workflow.completed_at = None

        await self._persist_and_publish(
            workflow,
            WorkflowStarted(
                source=self.EVENT_SOURCE,
                payload={
                    "workflow_id": str(workflow.id),
                    "goal": workflow.goal,
                    "state": workflow.state.value,
                    "started_at": workflow.started_at.isoformat(),
                },
            ),
        )

    async def pause_workflow(
        self,
        workflow: Workflow,
    ) -> None:
        """
        Pause workflow execution.
        """

        workflow.state = RuntimeState.PAUSED

        await self._persist_and_publish(
            workflow,
            WorkflowPaused(
                source=self.EVENT_SOURCE,
                payload={
                    "workflow_id": str(workflow.id),
                    "goal": workflow.goal,
                    "state": workflow.state.value,
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            ),
        )

    async def resume_workflow(
        self,
        workflow: Workflow,
    ) -> None:
        """
        Resume execution of a paused workflow.
        """

        workflow.state = RuntimeState.RUNNING

        await self._persist_and_publish(
            workflow,
            WorkflowResumed(
                source=self.EVENT_SOURCE,
                payload={
                    "workflow_id": str(workflow.id),
                    "goal": workflow.goal,
                    "state": workflow.state.value,
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            ),
        )

    async def approval_pending(
        self,
        workflow: Workflow,
    ) -> None:
        """
        Transition a workflow to the APPROVAL_PENDING state.
        """

        workflow.state = RuntimeState.APPROVAL_PENDING

        await self._persist_and_publish(
            workflow,
            WorkflowApprovalPending(
                source=self.EVENT_SOURCE,
                payload={
                    "workflow_id": str(workflow.id),
                    "goal": workflow.goal,
                    "state": workflow.state.value,
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            ),
        )

    async def recover_workflow(
        self,
        workflow: Workflow,
    ) -> None:
        """
        Transition a workflow to the RECOVERING state.
        """

        workflow.state = RuntimeState.RECOVERING

        await self._persist_and_publish(
            workflow,
            WorkflowRecovering(
                source=self.EVENT_SOURCE,
                payload={
                    "workflow_id": str(workflow.id),
                    "goal": workflow.goal,
                    "state": workflow.state.value,
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            ),
        )

    async def complete_workflow(
        self,
        workflow: Workflow,
    ) -> None:
        """
        Transition a workflow to the COMPLETED state.
        """

        workflow.state = RuntimeState.COMPLETED
        workflow.completed_at = datetime.now(UTC)

        if workflow.started_at is not None:
            workflow.duration_ms = round(
                (workflow.completed_at - workflow.started_at).total_seconds() * 1000,
                2,
            )

        await self._persist_and_publish(
            workflow,
            WorkflowCompleted(
                source=self.EVENT_SOURCE,
                payload={
                    "workflow_id": str(workflow.id),
                    "goal": workflow.goal,
                    "state": workflow.state.value,
                    "duration_ms": getattr(
                        workflow,
                        "duration_ms",
                        None,
                    ),
                    "completed_at": workflow.completed_at.isoformat(),
                },
            ),
        )

    async def fail_workflow(
        self,
        workflow: Workflow,
        error: str | None = None,
    ) -> None:
        """
        Transition a workflow to the FAILED state.
        """

        workflow.state = RuntimeState.FAILED
        workflow.completed_at = datetime.now(UTC)

        if workflow.started_at is not None:
            workflow.duration_ms = round(
                (workflow.completed_at - workflow.started_at).total_seconds() * 1000,
                2,
            )

        await self._persist_and_publish(
            workflow,
            WorkflowFailed(
                source=self.EVENT_SOURCE,
                payload={
                    "workflow_id": str(workflow.id),
                    "goal": workflow.goal,
                    "state": workflow.state.value,
                    "duration_ms": getattr(
                        workflow,
                        "duration_ms",
                        None,
                    ),
                    "completed_at": workflow.completed_at.isoformat(),
                    "error": error,
                },
            ),
        )

    async def cancel_workflow(
        self,
        workflow: Workflow,
    ) -> None:
        """
        Transition a workflow to the CANCELLED state.
        """

        workflow.state = RuntimeState.CANCELLED
        workflow.completed_at = datetime.now(UTC)

        if workflow.started_at is not None:
            workflow.duration_ms = round(
                (workflow.completed_at - workflow.started_at).total_seconds() * 1000,
                2,
            )

        await self._persist_and_publish(
            workflow,
            WorkflowCancelled(
                source=self.EVENT_SOURCE,
                payload={
                    "workflow_id": str(workflow.id),
                    "goal": workflow.goal,
                    "state": workflow.state.value,
                    "duration_ms": getattr(
                        workflow,
                        "duration_ms",
                        None,
                    ),
                    "completed_at": workflow.completed_at.isoformat(),
                },
            ),
        )

    # ------------------------------------------------------------------
    # Task Lifecycle
    # ------------------------------------------------------------------

    async def start_task(
        self,
        workflow: Workflow,
        task: Task,
    ) -> None:
        """
        Transition a task to the RUNNING state.
        """

        task.state = TaskState.RUNNING
        task.started_at = datetime.now(UTC)
        task.completed_at = None
        task.duration_ms = None

        await self._persist_and_publish(
            workflow,
            TaskStarted(
                source=self.EVENT_SOURCE,
                payload={
                    "workflow_id": str(workflow.id),
                    "task_id": str(task.id),
                    "task": task.name,
                    "description": task.description,
                    "agent": task.agent,
                    "attempt": task.attempt,
                    "started_at": task.started_at.isoformat(),
                },
            ),
        )

    async def complete_task(
        self,
        workflow: Workflow,
        task: Task,
    ) -> None:
        """
        Transition a task to the COMPLETED state.
        """

        task.state = TaskState.COMPLETED
        task.completed_at = datetime.now(UTC)
        task.duration_ms = self._calculate_duration(task)

        await self._persist_and_publish(
            workflow,
            TaskCompleted(
                source=self.EVENT_SOURCE,
                payload={
                    "workflow_id": str(workflow.id),
                    "task_id": str(task.id),
                    "task": task.name,
                    "description": task.description,
                    "agent": task.agent,
                    "attempt": task.attempt,
                    "duration_ms": task.duration_ms,
                    "completed_at": task.completed_at.isoformat(),
                },
            ),
        )

    async def fail_task(
        self,
        workflow: Workflow,
        task: Task,
        error: str,
        state: TaskState = TaskState.FAILED,
    ) -> None:
        """
        Transition a task to a terminal failure state.

        The supplied state allows the engine to preserve
        FAILED, TIMED_OUT or CANCELLED.
        """

        task.state = state
        task.completed_at = datetime.now(UTC)
        task.duration_ms = self._calculate_duration(task)

        await self._persist_and_publish(
            workflow,
            TaskFailed(
                source=self.EVENT_SOURCE,
                payload={
                    "workflow_id": str(workflow.id),
                    "task_id": str(task.id),
                    "task": task.name,
                    "description": task.description,
                    "agent": task.agent,
                    "attempt": task.attempt,
                    "state": task.state.value,
                    "duration_ms": task.duration_ms,
                    "completed_at": task.completed_at.isoformat(),
                    "error": error,
                },
            ),
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _persist_and_publish(
        self,
        workflow: Workflow,
        event: Event,
    ) -> None:
        """
        Persist the workflow and publish a runtime event.
        """

        await self._repository.save(workflow)

        await self._event_bus.publish(
            event,
        )

    @staticmethod
    def _calculate_duration(
        task: Task,
    ) -> float | None:
        """
        Calculate task execution duration in milliseconds.

        Returns
        -------
        float | None
            Rounded execution duration in milliseconds,
            or None if the task has not both started
            and completed.
        """

        if task.started_at is None or task.completed_at is None:
            return None

        return round(
            (task.completed_at - task.started_at).total_seconds() * 1000,
            2,
        )

    @staticmethod
    def is_terminal_state(
        task: Task,
    ) -> bool:
        """
        Returns True when the task has reached
        a terminal state.
        """

        return task.state in {
            TaskState.COMPLETED,
            TaskState.FAILED,
            TaskState.TIMED_OUT,
            TaskState.CANCELLED,
        }

    @staticmethod
    def is_terminal_workflow_state(
        workflow: Workflow,
    ) -> bool:
        """
        Returns True when the workflow has reached
        a terminal state.
        """

        return workflow.state in {
            RuntimeState.COMPLETED,
            RuntimeState.FAILED,
            RuntimeState.CANCELLED,
        }
