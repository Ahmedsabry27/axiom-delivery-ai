from enum import StrEnum


class TaskState(StrEnum):
    """
    Lifecycle state of an individual workflow task.
    """

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
