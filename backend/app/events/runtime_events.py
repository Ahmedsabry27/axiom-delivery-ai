from dataclasses import dataclass

from app.events.base import Event

# ---------------------------------------------------------------------
# Planning Events
# ---------------------------------------------------------------------


@dataclass(slots=True)
class PlanningStarted(Event):
    """
    Published when workflow planning begins.
    """


@dataclass(slots=True)
class PlanningCompleted(Event):
    """
    Published when workflow planning completes successfully.
    """


@dataclass(slots=True)
class PlanningFailed(Event):
    """
    Published when workflow planning fails.
    """


# ---------------------------------------------------------------------
# Workflow Lifecycle Events
# ---------------------------------------------------------------------


@dataclass(slots=True)
class WorkflowStarted(Event):
    """
    Published when workflow execution begins.
    """


@dataclass(slots=True)
class WorkflowPaused(Event):
    """
    Published when workflow execution is paused.
    """


@dataclass(slots=True)
class WorkflowResumed(Event):
    """
    Published when a paused workflow resumes execution.
    """


@dataclass(slots=True)
class WorkflowApprovalPending(Event):
    """
    Published when workflow execution is waiting
    for human approval.
    """


@dataclass(slots=True)
class WorkflowRecovering(Event):
    """
    Published when a workflow is restoring
    from a checkpoint.
    """


@dataclass(slots=True)
class WorkflowCompleted(Event):
    """
    Published when workflow execution completes successfully.
    """


@dataclass(slots=True)
class WorkflowFailed(Event):
    """
    Published when workflow execution fails.
    """


@dataclass(slots=True)
class WorkflowCancelling(Event):
    """
    Published when workflow cancellation begins.
    """


@dataclass(slots=True)
class WorkflowCancelled(Event):
    """
    Published when workflow execution has been cancelled.
    """


# ---------------------------------------------------------------------
# Task Lifecycle Events
# ---------------------------------------------------------------------


@dataclass(slots=True)
class TaskStarted(Event):
    """
    Published when a task starts execution.
    """


@dataclass(slots=True)
class TaskCompleted(Event):
    """
    Published when a task completes successfully.
    """


@dataclass(slots=True)
class TaskFailed(Event):
    """
    Published when a task fails.
    """


@dataclass(slots=True)
class TaskRetrying(Event):
    """
    Published before retrying a failed task.
    """


@dataclass(slots=True)
class TaskTimedOut(Event):
    """
    Published when a task exceeds its timeout.
    """


@dataclass(slots=True)
class TaskCancelled(Event):
    """
    Published when a task is cancelled.
    """


@dataclass(slots=True)
class TaskApprovalRequested(Event):
    """
    Published when a task requires human approval.
    """


@dataclass(slots=True)
class TaskApproved(Event):
    """
    Published when a task receives approval.
    """


@dataclass(slots=True)
class TaskRejected(Event):
    """
    Published when a task is rejected.
    """


# ---------------------------------------------------------------------
# Checkpoint Events
# ---------------------------------------------------------------------


@dataclass(slots=True)
class CheckpointCreated(Event):
    """
    Published after a workflow checkpoint is persisted.
    """


@dataclass(slots=True)
class CheckpointRestored(Event):
    """
    Published after a workflow checkpoint is restored.
    """


@dataclass(slots=True)
class CheckpointDeleted(Event):
    """
    Published after a checkpoint is removed.
    """


# ---------------------------------------------------------------------
# Audit Events
# ---------------------------------------------------------------------


@dataclass(slots=True)
class AuditRecorded(Event):
    """
    Published whenever an audit record is written.
    """
