from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


def now() -> datetime:
    return datetime.now(UTC)


class AgentExecution(Base):
    __tablename__ = "agent_executions"
    __table_args__ = (
        Index("ix_agent_execution_tenant_status", "tenant_id", "status", "created_at"),
        Index("ix_agent_execution_agent_time", "tenant_id", "agent_id", "created_at"),
        Index("ix_agent_execution_correlation", "correlation_id"),
    )
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    runtime_execution_id: Mapped[str | None] = mapped_column(String(36), index=True)
    tenant_id: Mapped[str] = mapped_column(String(120), nullable=False)
    agent_id: Mapped[int] = mapped_column(
        ForeignKey("agents.id", ondelete="RESTRICT"), nullable=False
    )
    agent_uuid: Mapped[str] = mapped_column(String(36), nullable=False)
    agent_version: Mapped[int] = mapped_column(Integer, nullable=False)
    actor_id: Mapped[str] = mapped_column(String(160), nullable=False)
    service_identity: Mapped[str | None] = mapped_column(String(160))
    conversation_id: Mapped[str | None] = mapped_column(String(36))
    workflow_id: Mapped[str | None] = mapped_column(String(36))
    discovery_id: Mapped[str | None] = mapped_column(String(36))
    parent_execution_id: Mapped[str | None] = mapped_column(
        ForeignKey("agent_executions.id")
    )
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="queued")
    current_phase: Mapped[str] = mapped_column(
        String(60), nullable=False, default="queued"
    )
    request_summary: Mapped[str] = mapped_column(String(500), nullable=False)
    input_summary: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    output_summary: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    model_provider: Mapped[str] = mapped_column(String(80), nullable=False)
    model_name: Mapped[str] = mapped_column(String(160), nullable=False)
    planner: Mapped[str] = mapped_column(String(120), nullable=False)
    selected_tools: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    tool_execution_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    knowledge_source_ids: Mapped[list] = mapped_column(
        JSON, nullable=False, default=list
    )
    runtime_metadata: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    token_usage: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    estimated_cost: Mapped[float | None] = mapped_column()
    actual_cost: Mapped[float | None] = mapped_column()
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="USD")
    error_code: Mapped[str | None] = mapped_column(String(80))
    safe_error_message: Mapped[str | None] = mapped_column(String(500))
    correlation_id: Mapped[str] = mapped_column(
        String(100), nullable=False, unique=True
    )
    trace_id: Mapped[str] = mapped_column(String(100), nullable=False)
    test_mode: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=now
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[float | None] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=now, onupdate=now
    )


class AgentContinuation(Base):
    __tablename__ = "agent_continuations"
    __table_args__ = (
        UniqueConstraint(
            "execution_id", "kind", "status", name="uq_agent_continuation_state"
        ),
        Index("ix_agent_continuation_tenant_execution", "tenant_id", "execution_id"),
        Index("ix_agent_continuation_expiration", "status", "expires_at"),
    )
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(String(120), nullable=False)
    execution_id: Mapped[str] = mapped_column(
        ForeignKey("agent_executions.id", ondelete="CASCADE"), nullable=False
    )
    conversation_id: Mapped[str | None] = mapped_column(String(36))
    workflow_id: Mapped[str | None] = mapped_column(String(36))
    agent_id: Mapped[int] = mapped_column(
        ForeignKey("agents.id", ondelete="RESTRICT"), nullable=False
    )
    agent_version: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    tool_name: Mapped[str | None] = mapped_column(String(100))
    tool_version: Mapped[str | None] = mapped_column(String(40))
    schema: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    known_values: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    missing_fields: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    safe_question: Mapped[str | None] = mapped_column(String(500))
    alternatives: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    required_approver: Mapped[str | None] = mapped_column(String(160))
    input_fingerprint: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    resume_token_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True
    )
    response: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=now
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
