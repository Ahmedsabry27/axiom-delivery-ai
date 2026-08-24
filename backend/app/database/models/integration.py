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


def now() -> datetime:
    return datetime.now(UTC)


class IntegrationConnection(Base):
    __tablename__ = "integration_connections"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "name", name="uq_integration_connection_tenant_name"
        ),
        Index(
            "ix_integration_connections_status",
            "tenant_id",
            "connector_type",
            "status",
            "health_status",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    connector_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    auth_type: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft")
    health_status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="not_configured"
    )
    base_url: Mapped[str] = mapped_column(String(500), nullable=False)
    secret_ref: Mapped[str | None] = mapped_column(String(500))
    configuration: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    safe_metadata: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error_code: Mapped[str | None] = mapped_column(String(80))
    last_error_message_safe: Mapped[str | None] = mapped_column(String(500))
    created_by: Mapped[str] = mapped_column(String(160), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=now, onupdate=now
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    lock_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class IntegrationCapability(Base):
    __tablename__ = "integration_capabilities"
    __table_args__ = (
        UniqueConstraint(
            "connection_id",
            "external_name",
            name="uq_integration_capability_connection_name",
        ),
        Index(
            "ix_integration_capabilities_catalog",
            "tenant_id",
            "capability_type",
            "enabled",
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    connection_id: Mapped[str] = mapped_column(
        ForeignKey("integration_connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tenant_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    external_name: Mapped[str] = mapped_column(String(160), nullable=False)
    display_name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    capability_type: Mapped[str] = mapped_column(String(20), nullable=False)
    version: Mapped[str] = mapped_column(String(40), nullable=False, default="1.0.0")
    input_schema: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    output_schema: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False, default="low")
    approval_required: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    governance: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    provisioned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=now, onupdate=now
    )


class IntegrationAgentAssignment(Base):
    __tablename__ = "integration_agent_assignments"
    __table_args__ = (
        UniqueConstraint(
            "connection_id", "agent_id", name="uq_integration_connection_agent"
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    connection_id: Mapped[str] = mapped_column(
        ForeignKey("integration_connections.id", ondelete="CASCADE"), nullable=False
    )
    agent_id: Mapped[int] = mapped_column(
        ForeignKey("agents.id", ondelete="CASCADE"), nullable=False
    )
    tenant_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    capability_names: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    created_by: Mapped[str] = mapped_column(String(160), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=now
    )


class IntegrationUsage(Base):
    __tablename__ = "integration_usage"
    __table_args__ = (
        Index(
            "ix_integration_usage_history", "tenant_id", "connection_id", "created_at"
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    connection_id: Mapped[str] = mapped_column(
        ForeignKey("integration_connections.id", ondelete="CASCADE"), nullable=False
    )
    tenant_id: Mapped[str] = mapped_column(String(120), nullable=False)
    capability_name: Mapped[str] = mapped_column(String(160), nullable=False)
    capability_type: Mapped[str] = mapped_column(String(20), nullable=False)
    agent_id: Mapped[str | None] = mapped_column(String(160))
    actor_id: Mapped[str] = mapped_column(String(160), nullable=False)
    execution_id: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    latency_ms: Mapped[float | None] = mapped_column()
    error_code: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=now
    )


class ProviderAuthorization(Base):
    __tablename__ = "integration_provider_authorizations"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "provider",
            "provider_tenant_id",
            name="uq_provider_authorization_tenant",
        ),
    )
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    provider_tenant_id: Mapped[str] = mapped_column(String(160), nullable=False)
    account_label: Mapped[str] = mapped_column(String(200), nullable=False)
    granted_scopes: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    secret_ref: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(
        String(40), nullable=False, default="CONSENT_REQUIRED"
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_refreshed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    safe_metadata: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=now
    )


class IntegrationOAuthState(Base):
    __tablename__ = "integration_oauth_states"
    state_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    actor_id: Mapped[str] = mapped_column(String(160), nullable=False)
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    redirect_uri: Mapped[str] = mapped_column(String(500), nullable=False)
    code_verifier_ref: Mapped[str | None] = mapped_column(String(500))
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=now
    )


class IntegrationMapping(Base):
    __tablename__ = "integration_mappings"
    __table_args__ = (
        UniqueConstraint(
            "connection_id",
            "external_entity_type",
            name="uq_integration_mapping_entity",
        ),
    )
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    connection_id: Mapped[str] = mapped_column(
        ForeignKey("integration_connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tenant_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    external_entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    canonical_entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    mapping_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    field_mappings: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    authority_policy: Mapped[str] = mapped_column(
        String(40), nullable=False, default="SOURCE_PRIORITY"
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=now, onupdate=now
    )


class IntegrationSyncRun(Base):
    __tablename__ = "integration_sync_runs"
    __table_args__ = (
        Index(
            "ix_integration_sync_run_history",
            "tenant_id",
            "connection_id",
            "started_at",
        ),
    )
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    connection_id: Mapped[str] = mapped_column(
        ForeignKey("integration_connections.id", ondelete="CASCADE"), nullable=False
    )
    tenant_id: Mapped[str] = mapped_column(String(120), nullable=False)
    mode: Mapped[str] = mapped_column(String(30), nullable=False)
    trigger: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    configuration_version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1
    )
    mapping_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    cursor_start: Mapped[str | None] = mapped_column(String(500))
    cursor_end: Mapped[str | None] = mapped_column(String(500))
    counters: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    rate_limit_events: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    correlation_ref: Mapped[str] = mapped_column(String(100), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=now
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class IntegrationSourceRecord(Base):
    __tablename__ = "integration_source_records"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "provider_tenant_id",
            "external_entity_type",
            "external_entity_id",
            name="uq_integration_source_external",
        ),
        Index(
            "ix_integration_source_connection",
            "tenant_id",
            "connection_id",
            "external_entity_type",
        ),
    )
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    connection_id: Mapped[str] = mapped_column(
        ForeignKey("integration_connections.id", ondelete="CASCADE"), nullable=False
    )
    tenant_id: Mapped[str] = mapped_column(String(120), nullable=False)
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    provider_tenant_id: Mapped[str] = mapped_column(String(160), nullable=False)
    external_entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    external_entity_id: Mapped[str] = mapped_column(String(240), nullable=False)
    canonical_entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    canonical_entity_id: Mapped[str | None] = mapped_column(String(160))
    source_version: Mapped[str] = mapped_column(String(100), nullable=False)
    source_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    content_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(1000))
    classification: Mapped[str] = mapped_column(
        String(40), nullable=False, default="INTERNAL"
    )
    data_status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="CURRENT"
    )
    safe_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    first_synchronized_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=now
    )
    last_synchronized_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=now
    )
    last_successful_run_id: Mapped[str | None] = mapped_column(String(36))


class IntegrationQuarantine(Base):
    __tablename__ = "integration_quarantine"
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    connection_id: Mapped[str] = mapped_column(
        ForeignKey("integration_connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tenant_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    external_entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    external_entity_id: Mapped[str] = mapped_column(String(240), nullable=False)
    rule_code: Mapped[str] = mapped_column(String(100), nullable=False)
    safe_reason: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="OPEN")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=now
    )


class IntegrationWebhookSubscription(Base):
    __tablename__ = "integration_webhook_subscriptions"
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    connection_id: Mapped[str] = mapped_column(
        ForeignKey("integration_connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tenant_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    provider_subscription_id: Mapped[str] = mapped_column(String(240), nullable=False)
    resource: Mapped[str] = mapped_column(String(300), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_renewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    safe_metadata: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
