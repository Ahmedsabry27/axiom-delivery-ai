from dataclasses import dataclass, field
from typing import Any
from uuid import UUID


@dataclass(frozen=True, slots=True)
class RuntimeContext:
    """
    Immutable execution context shared across the runtime.
    """

    request_id: UUID

    workflow_id: UUID

    session_id: UUID

    conversation_id: UUID

    tenant_id: str

    user_id: str

    goal: str

    trace_id: str

    metadata: dict[str, Any] = field(default_factory=dict)

    available_agents: list[str] = field(default_factory=list)

    available_tools: list[str] = field(default_factory=list)
