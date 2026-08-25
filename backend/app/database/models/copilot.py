from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


def _id() -> str:
    return str(uuid4())


class CopilotSavedInsight(Base):
    __tablename__ = "copilot_saved_insights"
    __table_args__ = (UniqueConstraint("tenant_id", "id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True)
    title: Mapped[str] = mapped_column(String(255))
    summary: Mapped[str] = mapped_column(Text)
    insight_type: Mapped[str] = mapped_column(String(60), index=True)
    conversation_id: Mapped[str | None] = mapped_column(String(36), index=True)
    execution_id: Mapped[str | None] = mapped_column(String(36), index=True)
    response_reference: Mapped[str | None] = mapped_column(String(120))
    delivery_context: Mapped[dict] = mapped_column(JSON, default=dict)
    confidence: Mapped[str] = mapped_column(String(30))
    evidence_snapshots: Mapped[list] = mapped_column(JSON, default=list)
    evidence_freshness: Mapped[str | None] = mapped_column(String(40))
    owner_id: Mapped[str] = mapped_column(String(255), index=True)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    review_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(30), default="SAVED", index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[str] = mapped_column(String(255))
    updated_by: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CopilotPromptTemplate(Base):
    __tablename__ = "copilot_prompt_templates"
    __table_args__ = (UniqueConstraint("tenant_id", "template_key", "version"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True)
    template_key: Mapped[str] = mapped_column(String(120), index=True)
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str] = mapped_column(String(60), index=True)
    prompt_body: Mapped[str] = mapped_column(Text)
    required_context_types: Mapped[list] = mapped_column(JSON, default=list)
    expected_response_type: Mapped[str] = mapped_column(String(80))
    evidence_requirement: Mapped[str] = mapped_column(String(40))
    may_propose_action: Mapped[bool] = mapped_column(Boolean, default=False)
    owner_id: Mapped[str] = mapped_column(String(255), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(30), default="DRAFT", index=True)
    supersedes_id: Mapped[str | None] = mapped_column(String(36))
    created_by: Mapped[str] = mapped_column(String(255))
    updated_by: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CopilotPromptFavorite(Base):
    __tablename__ = "copilot_prompt_favorites"
    __table_args__ = (UniqueConstraint("tenant_id", "user_id", "template_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True)
    user_id: Mapped[str] = mapped_column(String(255), index=True)
    template_id: Mapped[str] = mapped_column(String(36), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
