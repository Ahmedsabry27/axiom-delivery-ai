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
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


def now():
    return datetime.now(UTC)


class MCPServer(Base):
    __tablename__ = "mcp_servers"
    __table_args__ = (
        UniqueConstraint("tenant_id", "slug", name="uq_mcp_server_tenant_slug"),
        Index("ix_mcp_server_health", "tenant_id", "enabled", "health_status"),
    )
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(String(120), index=True)
    display_name: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(80))
    description: Mapped[str] = mapped_column(Text, default="")
    environment: Mapped[str] = mapped_column(String(40), default="production")
    server_url: Mapped[str] = mapped_column(String(500))
    transport: Mapped[str] = mapped_column(String(40), default="streamable_http")
    auth_type: Mapped[str] = mapped_column(String(40), default="none")
    secret_reference: Mapped[str | None] = mapped_column(String(500), nullable=True)
    auth_config: Mapped[dict] = mapped_column(JSON, default=dict)
    requested_scopes: Mapped[list] = mapped_column(JSON, default=list)
    granted_scopes: Mapped[list] = mapped_column(JSON, default=list)
    policy: Mapped[dict] = mapped_column(JSON, default=dict)
    requested_protocol_version: Mapped[str | None] = mapped_column(
        String(40), nullable=True
    )
    negotiated_protocol_version: Mapped[str | None] = mapped_column(
        String(40), nullable=True
    )
    sdk_version: Mapped[str] = mapped_column(String(20), default="1.28.1")
    server_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    server_version: Mapped[str | None] = mapped_column(String(80), nullable=True)
    capabilities: Mapped[dict] = mapped_column(JSON, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    health_status: Mapped[str] = mapped_column(String(40), default="unconfigured")
    sync_status: Mapped[str] = mapped_column(String(40), default="never")
    last_health_check: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_connected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_synced_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    configuration_version: Mapped[int] = mapped_column(Integer, default=1)
    created_by: Mapped[str] = mapped_column(String(160))
    updated_by: Mapped[str] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, onupdate=now
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class MCPCapability(Base):
    __tablename__ = "mcp_capabilities"
    __table_args__ = (
        UniqueConstraint(
            "server_id",
            "capability_type",
            "remote_name",
            name="uq_mcp_capability_remote",
        ),
        UniqueConstraint(
            "tenant_id", "internal_name", name="uq_mcp_capability_tenant_internal"
        ),
        Index(
            "ix_mcp_capability_catalog",
            "tenant_id",
            "capability_type",
            "enabled",
            "missing",
        ),
        Index("ix_mcp_capability_fingerprint", "fingerprint"),
    )
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    server_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("mcp_servers.id", ondelete="CASCADE"), index=True
    )
    tenant_id: Mapped[str] = mapped_column(String(120), index=True)
    capability_type: Mapped[str] = mapped_column(String(30))
    remote_name: Mapped[str] = mapped_column(String(500))
    internal_name: Mapped[str] = mapped_column(String(180))
    display_name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, default="")
    uri: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    mime_type: Mapped[str | None] = mapped_column(String(160), nullable=True)
    schema_json: Mapped[dict] = mapped_column(JSON, default=dict)
    safe_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    previous_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    change_status: Mapped[str] = mapped_column(String(40), default="unchanged")
    risk_level: Mapped[str] = mapped_column(String(30), default="read")
    permission: Mapped[str] = mapped_column(String(200))
    approval_policy: Mapped[str] = mapped_column(String(40), default="none")
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    missing: Mapped[bool] = mapped_column(Boolean, default=False)
    first_discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now
    )
    last_discovered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now
    )
    last_synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now
    )


class MCPSyncRun(Base):
    __tablename__ = "mcp_sync_runs"
    __table_args__ = (
        Index("ix_mcp_sync_history", "tenant_id", "started_at", "status"),
    )
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    server_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("mcp_servers.id", ondelete="CASCADE"), index=True
    )
    tenant_id: Mapped[str] = mapped_column(String(120), index=True)
    status: Mapped[str] = mapped_column(String(30))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    added_count: Mapped[int] = mapped_column(Integer, default=0)
    changed_count: Mapped[int] = mapped_column(Integer, default=0)
    removed_count: Mapped[int] = mapped_column(Integer, default=0)
    warning_count: Mapped[int] = mapped_column(Integer, default=0)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    safe_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    correlation_id: Mapped[str] = mapped_column(String(100))
