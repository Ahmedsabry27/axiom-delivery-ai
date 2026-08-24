from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass
class AgentExecutionMetadata:
    """
    Represents a single agent execution instance.
    """

    execution_id: UUID

    agent_name: str

    task_name: str

    started_at: datetime

    completed_at: datetime | None = None

    duration_ms: int | None = None

    success: bool | None = None
