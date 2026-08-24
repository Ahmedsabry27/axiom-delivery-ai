from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4


@dataclass
class AgentCapability:
    """
    Defines a capability provided by an agent.

    A capability describes:
    - What an agent can do
    - Which tasks it supports
    - Which tools it can use
    - Additional discovery metadata
    """

    name: str

    description: str

    supported_tasks: list[str] = field(default_factory=list)

    supported_tools: list[str] = field(default_factory=list)

    category: str = "general"

    version: str = "1.0"

    id: UUID = field(default_factory=uuid4)

    metadata: dict[str, Any] = field(default_factory=dict)

    def supports_task(
        self,
        task_name: str,
    ) -> bool:
        """
        Check whether this capability
        supports a specific task.
        """

        return task_name in self.supported_tasks

    def supports_tool(
        self,
        tool_name: str,
    ) -> bool:
        """
        Check whether this capability
        supports a specific tool.
        """

        return tool_name in self.supported_tools
