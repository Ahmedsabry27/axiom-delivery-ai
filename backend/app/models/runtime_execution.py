from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


class RuntimeExecution(Base):
    """Durable record for a user-visible runtime execution."""

    __tablename__ = "runtime_executions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    workflow_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, unique=True, index=True
    )
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    goal: Mapped[str | None] = mapped_column(Text, nullable=True)
    agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    selected_agent_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True, index=True
    )
    tenant_id: Mapped[str] = mapped_column(
        String(120), nullable=False, default="default", index=True
    )
    provider_name: Mapped[str | None] = mapped_column(String(40), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    workspace_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    current_step: Mapped[str | None] = mapped_column(String(120), nullable=True)
    runtime_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    token_usage: Mapped[dict] = mapped_column(JSON, default=dict)
    estimated_cost: Mapped[float | None] = mapped_column(nullable=True)
    actual_cost: Mapped[float | None] = mapped_column(nullable=True)
    waiting_reason: Mapped[str | None] = mapped_column(String(80), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="PENDING", index=True)
    state_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Highest sequence allocated by a committed event append. Allocation uses one
    # database UPDATE ... RETURNING in the same transaction as the event insert.
    last_event_sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Retained for schema compatibility; new writers use last_event_sequence.
    next_event_sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    deadline_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    lease_owner: Mapped[str | None] = mapped_column(String(255), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration_ms: Mapped[float | None] = mapped_column(nullable=True)
    steps: Mapped[list] = mapped_column(JSON, default=list)
    result_message: Mapped[str | None] = mapped_column(nullable=True)
    error: Mapped[str | None] = mapped_column(nullable=True)


class RuntimeExecutionEvent(Base):
    """Append-only, reconnect-safe runtime event stream."""

    __tablename__ = "runtime_execution_events"
    __table_args__ = (
        UniqueConstraint("execution_id", "sequence", name="uq_runtime_event_sequence"),
        Index(
            "uq_runtime_events_terminal",
            "execution_id",
            unique=True,
            postgresql_where=text("final = true AND component_type = 'runtime'"),
            sqlite_where=text("final = 1 AND component_type = 'runtime'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    execution_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("runtime_executions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    state_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    aggregate_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    component_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    component_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    component_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    final: Mapped[bool] = mapped_column(nullable=False, default=False)
    name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )


class RuntimeContinuation(Base):
    """One-time input or approval gate for a RuntimeExecution."""

    __tablename__ = "runtime_continuations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    execution_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("runtime_executions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tenant_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    schema: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    known_values: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    response: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    required_role: Mapped[str | None] = mapped_column(String(120), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
