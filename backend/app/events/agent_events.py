from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4


@dataclass
class AgentEvent:
    """
    Base class for all agent lifecycle events.
    """

    agent_name: str

    timestamp: datetime

    source: str

    event_id: UUID = field(default_factory=uuid4)

    agent_id: str | None = None

    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentRegistered(AgentEvent):
    """
    Published when an agent is registered
    in the agent registry.
    """

    event_type: str = "AGENT_REGISTERED"

    source: str = "AgentRegistry"


@dataclass
class AgentStarted(AgentEvent):
    """
    Published when agent initialization starts.
    """

    event_type: str = "AGENT_STARTED"

    source: str = "AgentLifecycleManager"


@dataclass
class AgentReady(AgentEvent):
    """
    Published when agent initialization
    completes and agent becomes READY.
    """

    event_type: str = "AGENT_READY"

    source: str = "AgentLifecycleManager"


@dataclass
class AgentExecutionCompleted(AgentEvent):
    """
    Published after successful agent execution.
    """

    execution_id: str = ""

    task_name: str = ""

    duration_ms: float = 0.0

    event_type: str = "AGENT_EXECUTION_COMPLETED"

    source: str = "AgentRuntime"


@dataclass
class AgentExecutionFailed(AgentEvent):
    """
    Published when agent execution fails.
    """

    execution_id: str = ""

    task_name: str = ""

    error: str = ""

    event_type: str = "AGENT_EXECUTION_FAILED"

    source: str = "AgentRuntime"


@dataclass
class AgentStopped(AgentEvent):
    """
    Published when agent shutdown completes.
    """

    event_type: str = "AGENT_STOPPED"

    source: str = "AgentLifecycleManager"
