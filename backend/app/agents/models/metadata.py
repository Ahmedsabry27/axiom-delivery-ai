from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class AgentMetadata:
    """
    Enterprise metadata describing an agent.
    """

    name: str

    version: str = "1.0.0"

    description: str = ""

    owner: str = "AI Platform"

    tags: list[str] = field(default_factory=list)

    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    metadata: dict[str, Any] = field(default_factory=dict)
