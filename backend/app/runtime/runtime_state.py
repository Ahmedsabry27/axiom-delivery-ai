from enum import Enum


class RuntimeState(str, Enum):
    """
       Represents the lifecycle state of a workflow execution.

       State Transitions
       -----------------
       CREATED
           ↓
       PLANNING
           ↓
       READY
           ↓
       RUNNING
          ↙ ↓ ↘
    WAITING PAUSED CANCELLING
          ↓      ↓
       RUNNING   CANCELLED
          ↓
    COMPLETED / FAILED
    """

    # ------------------------------------------------------------------
    # Initial States
    # ------------------------------------------------------------------

    CREATED = "CREATED"
    """Workflow has been created but not yet initialized."""

    PLANNING = "PLANNING"
    """Planner is generating the execution plan."""

    READY = "READY"
    """Workflow has been validated and is ready for execution."""

    # ------------------------------------------------------------------
    # Active Execution
    # ------------------------------------------------------------------

    RUNNING = "RUNNING"
    """Workflow is actively executing tasks."""

    WAITING = "WAITING"
    """Workflow is waiting for an external dependency."""

    PAUSED = "PAUSED"
    """Workflow execution has been paused."""

    # ------------------------------------------------------------------
    # Optional Enterprise States
    # ------------------------------------------------------------------

    APPROVAL_PENDING = "APPROVAL_PENDING"
    """Workflow is waiting for human approval."""

    RECOVERING = "RECOVERING"
    """Workflow is restoring from a checkpoint."""

    CANCELLING = "CANCELLING"
    """Cancellation has been requested but tasks are still stopping."""

    # ------------------------------------------------------------------
    # Terminal States
    # ------------------------------------------------------------------

    COMPLETED = "COMPLETED"
    """Workflow finished successfully."""

    FAILED = "FAILED"
    """Workflow terminated due to an unrecoverable error."""

    CANCELLED = "CANCELLED"
    """Workflow was cancelled before completion."""
