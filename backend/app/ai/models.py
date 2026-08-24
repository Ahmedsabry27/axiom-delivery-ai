from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# --------------------------------------------------
# AI Message Role
# --------------------------------------------------
class AIMessageRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


# --------------------------------------------------
# AI Conversation Message
# --------------------------------------------------
@dataclass(slots=True)
class AIMessage:
    """
    Standardized conversation message shared by all providers.
    """

    role: AIMessageRole
    content: str


# --------------------------------------------------
# AI Token Usage
# --------------------------------------------------
@dataclass(slots=True)
class AIUsage:
    """
    Standardized token usage across all AI providers.
    """

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


# --------------------------------------------------
# AI Response
# --------------------------------------------------
@dataclass(slots=True)
class AIResponse:
    """
    Standardized AI response returned by every provider.
    """

    text: str
    response_id: str | None = None
    model: str = ""
    latency_seconds: float = 0.0
    usage: AIUsage | None = None


# --------------------------------------------------
# AI Stream Event
# --------------------------------------------------
@dataclass(slots=True)
class AIStreamEvent:
    """
    Standardized streaming event emitted by every provider.
    """

    event_type: str

    text: str = ""

    response_id: str | None = None

    model: str = ""

    usage: AIUsage | None = None

    metadata: dict[str, Any] = field(default_factory=dict)
