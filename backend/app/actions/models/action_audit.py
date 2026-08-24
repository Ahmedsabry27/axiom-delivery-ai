from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class ActionAuditRecord:
    """
    Audit record for action execution.
    """

    action_name: str

    user_id: str

    execution_id: str

    status: str

    timestamp: datetime

    input_data: dict[str, Any] = field(default_factory=dict)

    metadata: dict[str, Any] = field(default_factory=dict)

    error: str | None = None
