from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# --------------------------------------------------
# Chat Request
# --------------------------------------------------
class ChatRequest(BaseModel):
    """
    Request payload for both synchronous and streaming chat endpoints.
    """

    message: str = Field(
        ...,
        min_length=1,
        description="User message to send to the AI.",
    )

    conversation_id: UUID | None = Field(
        default=None,
        description="Conversation identifier.",
    )


# --------------------------------------------------
# Chat Response
# --------------------------------------------------
class ChatResponse(BaseModel):
    """
    Response returned by the synchronous chat endpoint.
    """

    model_config = ConfigDict(from_attributes=True)

    response: str

    response_id: str | None = None


# --------------------------------------------------
# Stream Event (Documentation Only)
# --------------------------------------------------
class StreamEvent(BaseModel):
    """
    Documents the structure of the Server-Sent Events (SSE)
    returned by the streaming endpoint.
    """

    type: str

    text: str = ""

    response_id: str | None = None

    model: str = ""

    usage: dict | None = None

    metadata: dict = Field(default_factory=dict)
