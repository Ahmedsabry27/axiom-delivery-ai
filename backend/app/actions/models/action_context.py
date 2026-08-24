from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ActionContext:
    """
    Runtime context passed to actions.
    """

    user_id: str

    agent_name: str

    workflow_id: str

    metadata: dict[str, Any] = field(default_factory=dict)
