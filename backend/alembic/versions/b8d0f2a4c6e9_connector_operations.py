"""Add provider authorization and connector synchronization records.

Revision ID: b8d0f2a4c6e9
Revises: a7c9e1f3b5d8
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b8d0f2a4c6e9"
down_revision: str | Sequence[str] | None = "a7c9e1f3b5d8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "integration_provider_authorizations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("provider", sa.String(30), nullable=False),
        sa.Column("provider_tenant_id", sa.String(160), nullable=False),
        sa.Column("account_label", sa.String(200), nullable=False),
        sa.Column("granted_scopes", sa.JSON(), nullable=False),
        sa.Column("secret_ref", sa.String(500)),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("last_refreshed_at", sa.DateTime(timezone=True)),
        sa.Column("last_verified_at", sa.DateTime(timezone=True)),
        sa.Column("safe_metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "tenant_id",
            "provider",
            "provider_tenant_id",
            name="uq_provider_authorization_tenant",
        ),
    )
    op.create_index(
        "ix_integration_provider_authorizations_tenant_id",
        "integration_provider_authorizations",
        ["tenant_id"],
    )
    op.create_table(
        "integration_oauth_states",
        sa.Column("state_hash", sa.String(64), primary_key=True),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("actor_id", sa.String(160), nullable=False),
        sa.Column("provider", sa.String(30), nullable=False),
        sa.Column("redirect_uri", sa.String(500), nullable=False),
        sa.Column("code_verifier_ref", sa.String(500)),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_integration_oauth_states_tenant_id",
        "integration_oauth_states",
        ["tenant_id"],
    )
    op.create_table(
        "integration_mappings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "connection_id",
            sa.String(36),
            sa.ForeignKey("integration_connections.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("external_entity_type", sa.String(100), nullable=False),
        sa.Column("canonical_entity_type", sa.String(100), nullable=False),
        sa.Column("mapping_version", sa.Integer(), nullable=False),
        sa.Column("field_mappings", sa.JSON(), nullable=False),
        sa.Column("authority_policy", sa.String(40), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "connection_id",
            "external_entity_type",
            name="uq_integration_mapping_entity",
        ),
    )
    op.create_index(
        "ix_integration_mappings_connection_id",
        "integration_mappings",
        ["connection_id"],
    )
    op.create_index(
        "ix_integration_mappings_tenant_id", "integration_mappings", ["tenant_id"]
    )
    op.create_table(
        "integration_sync_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "connection_id",
            sa.String(36),
            sa.ForeignKey("integration_connections.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("mode", sa.String(30), nullable=False),
        sa.Column("trigger", sa.String(30), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("configuration_version", sa.Integer(), nullable=False),
        sa.Column("mapping_version", sa.Integer(), nullable=False),
        sa.Column("cursor_start", sa.String(500)),
        sa.Column("cursor_end", sa.String(500)),
        sa.Column("counters", sa.JSON(), nullable=False),
        sa.Column("rate_limit_events", sa.Integer(), nullable=False),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("correlation_ref", sa.String(100), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "ix_integration_sync_run_history",
        "integration_sync_runs",
        ["tenant_id", "connection_id", "started_at"],
    )
    op.create_table(
        "integration_source_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "connection_id",
            sa.String(36),
            sa.ForeignKey("integration_connections.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("provider", sa.String(30), nullable=False),
        sa.Column("provider_tenant_id", sa.String(160), nullable=False),
        sa.Column("external_entity_type", sa.String(100), nullable=False),
        sa.Column("external_entity_id", sa.String(240), nullable=False),
        sa.Column("canonical_entity_type", sa.String(100), nullable=False),
        sa.Column("canonical_entity_id", sa.String(160)),
        sa.Column("source_version", sa.String(100), nullable=False),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("content_fingerprint", sa.String(64), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("source_url", sa.String(1000)),
        sa.Column("classification", sa.String(40), nullable=False),
        sa.Column("data_status", sa.String(30), nullable=False),
        sa.Column("safe_payload", sa.JSON(), nullable=False),
        sa.Column("first_synchronized_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_synchronized_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_successful_run_id", sa.String(36)),
        sa.UniqueConstraint(
            "tenant_id",
            "provider_tenant_id",
            "external_entity_type",
            "external_entity_id",
            name="uq_integration_source_external",
        ),
    )
    op.create_index(
        "ix_integration_source_connection",
        "integration_source_records",
        ["tenant_id", "connection_id", "external_entity_type"],
    )
    op.create_table(
        "integration_quarantine",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "connection_id",
            sa.String(36),
            sa.ForeignKey("integration_connections.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("external_entity_type", sa.String(100), nullable=False),
        sa.Column("external_entity_id", sa.String(240), nullable=False),
        sa.Column("rule_code", sa.String(100), nullable=False),
        sa.Column("safe_reason", sa.String(500), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_integration_quarantine_connection_id",
        "integration_quarantine",
        ["connection_id"],
    )
    op.create_index(
        "ix_integration_quarantine_tenant_id", "integration_quarantine", ["tenant_id"]
    )
    op.create_table(
        "integration_webhook_subscriptions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "connection_id",
            sa.String(36),
            sa.ForeignKey("integration_connections.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("provider_subscription_id", sa.String(240), nullable=False),
        sa.Column("resource", sa.String(300), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("last_renewed_at", sa.DateTime(timezone=True)),
        sa.Column("safe_metadata", sa.JSON(), nullable=False),
    )
    op.create_index(
        "ix_integration_webhook_subscriptions_connection_id",
        "integration_webhook_subscriptions",
        ["connection_id"],
    )
    op.create_index(
        "ix_integration_webhook_subscriptions_tenant_id",
        "integration_webhook_subscriptions",
        ["tenant_id"],
    )


def downgrade() -> None:
    for table in [
        "integration_webhook_subscriptions",
        "integration_quarantine",
        "integration_source_records",
        "integration_sync_runs",
        "integration_mappings",
        "integration_oauth_states",
        "integration_provider_authorizations",
    ]:
        op.drop_table(table)
