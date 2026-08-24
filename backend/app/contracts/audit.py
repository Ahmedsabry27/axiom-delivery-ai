from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from uuid import uuid4


class AuditLevel(str, Enum):
    """
    Audit severity.
    """

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


@dataclass(slots=True)
class AuditEntry:
    """
    Immutable workflow audit record.
    """

    id: str = field(default_factory=lambda: str(uuid4()))

    workflow_id: str = ""

    task_id: str | None = None

    event: str = ""

    message: str = ""

    level: AuditLevel = AuditLevel.INFO

    metadata: dict[str, object] = field(default_factory=dict)

    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
