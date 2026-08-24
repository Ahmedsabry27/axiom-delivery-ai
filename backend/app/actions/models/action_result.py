from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ActionResult:
    """
    Result returned from action execution.

    Contains:
    - execution status
    - action output
    - errors
    - execution metadata
    """

    success: bool

    action_name: str

    output: dict[str, Any]

    error: str | None = None

    metadata: dict[str, Any] = field(default_factory=dict)
