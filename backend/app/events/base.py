from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4


@dataclass(slots=True)
class Event:
    """
    Base class for all runtime events.
    """

    id: UUID = field(default_factory=uuid4)

    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    source: str = ""

    payload: dict[str, Any] = field(default_factory=dict)
