from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID, uuid4

from app.runtime.task_state import TaskState


@dataclass(slots=True)
class Task:
    """
    Represents a unit of work within a workflow.

    A task defines:
    - What work should be performed
    - Agent routing requirements
    - Execution dependencies
    - Runtime execution state and metrics
    """

    # ------------------------------------------------------------------
    # Task Definition
    # ------------------------------------------------------------------

    id: UUID = field(default_factory=uuid4)

    name: str = ""

    description: str = ""

    # Explicit agent assignment (optional)
    #
    # If provided:
    #   Execute using this agent
    #
    # If empty:
    #   AgentRegistry will dynamically select
    #   the best matching agent
    agent: str | None = None

    # ------------------------------------------------------------------
    # Dynamic Agent Selection
    # ------------------------------------------------------------------

    required_capabilities: list[str] = field(default_factory=list)

    required_tools: list[str] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Tool Execution
    # ------------------------------------------------------------------

    tool: str | None = None

    task_type: str = "AGENT"
    capability_id: str | None = None
    semantic_capability: str | None = None
    implementation_name: str | None = None
    agent_id: str | None = None
    agent_version: int | None = None
    integration_connection_id: str | None = None
    parameters: dict[str, object] = field(default_factory=dict)
    required: bool = True
    retry_policy: dict[str, object] = field(default_factory=dict)
    side_effect_class: str = "UNKNOWN"
    expected_output_schema: dict[str, object] | None = None

    # ------------------------------------------------------------------
    # Dependencies
    # ------------------------------------------------------------------

    depends_on: list[UUID] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------

    metadata: dict[str, object] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Execution Policy
    # ------------------------------------------------------------------

    timeout_seconds: int = 30

    retry_count: int = 0

    # ------------------------------------------------------------------
    # Human Approval
    # ------------------------------------------------------------------

    requires_approval: bool = False

    approval_title: str | None = None

    approval_description: str | None = None

    approval_requested_by: str | None = None

    approval_assigned_to: str | None = None

    approval_timeout_seconds: int | None = None

    # ------------------------------------------------------------------
    # Runtime State
    # ------------------------------------------------------------------

    state: TaskState = TaskState.PENDING

    attempt: int = 0

    started_at: datetime | None = None

    completed_at: datetime | None = None

    duration_ms: float | None = None

    last_error: str | None = None

    # ------------------------------------------------------------------
    # Routing Helpers
    # ------------------------------------------------------------------

    def requires_agent_selection(self) -> bool:
        """
        Determines whether this task requires
        dynamic agent routing.
        """

        return self.agent is None and len(self.required_capabilities) > 0
