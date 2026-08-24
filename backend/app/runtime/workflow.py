from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4

from app.runtime.runtime_state import RuntimeState
from app.runtime.task import Task


@dataclass(slots=True)
class Workflow:
    """
    Represents a workflow execution.

    A workflow contains:
    - Business goal
    - Tasks to execute
    - Runtime lifecycle state
    - Execution metrics
    """

    # --------------------------------------------------
    # Identity
    # --------------------------------------------------

    id: UUID = field(default_factory=uuid4)

    # --------------------------------------------------
    # Definition
    # --------------------------------------------------

    goal: str = ""

    tasks: list[Task] = field(default_factory=list)

    # --------------------------------------------------
    # Runtime State
    # --------------------------------------------------

    state: RuntimeState = RuntimeState.CREATED

    # --------------------------------------------------
    # Lifecycle Tracking
    # --------------------------------------------------

    started_at: datetime | None = None

    completed_at: datetime | None = None

    duration_ms: float | None = None

    last_checkpoint_at: datetime | None = None

    # --------------------------------------------------
    # Metadata
    # --------------------------------------------------

    metadata: dict[str, object] = field(default_factory=dict)

    created_at: datetime | None = None

    updated_at: datetime | None = None
