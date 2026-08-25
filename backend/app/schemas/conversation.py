from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# --------------------------------------------------
# Create Conversation
# --------------------------------------------------


class ConversationCreate(BaseModel):
    title: str


# --------------------------------------------------
# Update Conversation
# --------------------------------------------------


class ConversationUpdate(BaseModel):
    title: str | None = None
    is_pinned: bool | None = None
    is_archived: bool | None = None
    context_summary: dict | None = None


# --------------------------------------------------
# Response
# --------------------------------------------------


class ConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    created_at: datetime
    updated_at: datetime
    tenant_id: str
    agent_uuid: str | None = None
    agent_version: int | None = None
    is_pinned: bool = False
    is_archived: bool = False
    context_summary: dict = Field(default_factory=dict)
