from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ActionDefinition:
    """
    Metadata describing an executable business action.

    Contains:

    - Identity
    - Description
    - Category
    - Permissions
    - Supported agents
    - Runtime metadata
    """

    name: str

    description: str

    category: str = "general"

    required_permissions: list[str] = field(default_factory=list)

    supported_agents: list[str] = field(default_factory=list)

    metadata: dict[str, Any] = field(default_factory=dict)
