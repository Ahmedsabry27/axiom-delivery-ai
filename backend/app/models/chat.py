from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """
    Incoming chat request.

    If provider/model are omitted, the backend will use the defaults
    configured in Settings.
    """

    message: str = Field(
        min_length=1,
        description="User message",
    )

    conversation_id: UUID | None = None

    agent_id: str | None = None

    provider: Literal["openai", "bedrock"] | None = Field(
        default=None,
        description="AI provider to use",
    )

    model: str | None = Field(
        default=None,
        max_length=200,
        description="Model identifier",
    )

    workspace_id: str | None = Field(default=None, max_length=120)
    metadata: dict[str, Any] | None = None


class ChatResponse(BaseModel):
    """
    Chat response returned by the backend.
    """

    response: str

    response_id: str | None = None

    provider: str

    model: str
