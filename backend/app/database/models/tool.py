from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


def now():
    return datetime.now(UTC)


class ToolDefinition(Base):
    __tablename__ = "tool_definitions"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "name", "version", name="uq_tool_tenant_name_version"
        ),
        Index("ix_tools_catalog", "tenant_id", "provider", "category", "enabled"),
    )
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(String(120), default="default", index=True)
    name: Mapped[str] = mapped_column(String(100), index=True)
    display_name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(80), index=True)
    provider: Mapped[str] = mapped_column(String(80), index=True)
    version: Mapped[str] = mapped_column(String(40))
    input_schema: Mapped[dict] = mapped_column(JSON)
    output_schema: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    permissions: Mapped[list] = mapped_column(JSON, default=list)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    risk_level: Mapped[str] = mapped_column(String(20), default="read")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    deprecated: Mapped[bool] = mapped_column(Boolean, default=False)
    registration_source: Mapped[str] = mapped_column(String(120), default="application")
    integration_connection_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True, index=True
    )
    configuration_state: Mapped[str] = mapped_column(String(30), default="not_required")
    created_by: Mapped[str] = mapped_column(String(120), default="system")
    updated_by: Mapped[str] = mapped_column(String(120), default="system")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, onupdate=now
    )


class ToolExecution(Base):
    __tablename__ = "tool_executions"
    __table_args__ = (
        Index("ix_tool_execution_history", "tenant_id", "started_at", "status"),
        Index("ix_tool_execution_correlation", "correlation_id"),
        UniqueConstraint(
            "tenant_id", "tool_name", "idempotency_key", name="uq_tool_idempotency"
        ),
    )
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(String(120), index=True)
    tool_name: Mapped[str] = mapped_column(String(100), index=True)
    tool_version: Mapped[str] = mapped_column(String(40))
    actor_id: Mapped[str] = mapped_column(String(160), index=True)
    agent_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    status: Mapped[str] = mapped_column(String(30), index=True)
    correlation_id: Mapped[str] = mapped_column(String(100))
    trace_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    input_summary: Mapped[dict] = mapped_column(JSON, default=dict)
    output_summary: Mapped[dict | list | str | None] = mapped_column(
        JSON, nullable=True
    )
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    idempotency_key: Mapped[str | None] = mapped_column(String(160), nullable=True)
    provider_request_id: Mapped[str | None] = mapped_column(String(160), nullable=True)


class IntegrationConfiguration(Base):
    __tablename__ = "integration_configurations"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "provider", name="uq_integration_tenant_provider"
        ),
        Index("ix_integration_status", "tenant_id", "enabled", "health_status"),
    )
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(String(120), default="default", index=True)
    provider: Mapped[str] = mapped_column(String(80))
    display_name: Mapped[str] = mapped_column(String(120))
    base_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    account_identifier: Mapped[str | None] = mapped_column(String(255), nullable=True)
    auth_method: Mapped[str | None] = mapped_column(String(80), nullable=True)
    secret_reference: Mapped[str | None] = mapped_column(String(500), nullable=True)
    safe_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    health_status: Mapped[str] = mapped_column(String(30), default="not_configured")
    health_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    last_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, onupdate=now
    )
