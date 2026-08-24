from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ActionPermission:
    """
    Defines who can execute an action.
    """

    action_name: str

    allowed_roles: list[str] = field(default_factory=list)

    requires_approval: bool = False
