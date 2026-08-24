from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ActionRequest:
    """
    Request submitted for action execution.
    """

    action_name: str

    user_id: str

    roles: list[str]

    input_data: dict[str, Any] = field(default_factory=dict)
