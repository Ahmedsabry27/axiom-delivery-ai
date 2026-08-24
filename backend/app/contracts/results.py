from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentResult:
    success: bool

    output: dict

    metadata: dict = field(default_factory=dict)

    execution_metadata: dict = field(default_factory=dict)


@dataclass(slots=True)
class ToolResult:
    success: bool
    output: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class WorkflowResult:
    success: bool
    output: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)
