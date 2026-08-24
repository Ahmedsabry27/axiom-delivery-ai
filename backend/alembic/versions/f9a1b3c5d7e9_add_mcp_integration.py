"""add Sprint 13 MCP integration
Revision ID: f9a1b3c5d7e9
Revises: e8f0a2b4c6d8
"""

import sqlalchemy as sa

from alembic import op

revision = "f9a1b3c5d7e9"
down_revision = "e8f0a2b4c6d8"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "mcp_servers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("display_name", sa.String(120), nullable=False),
        sa.Column("slug", sa.String(80), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("environment", sa.String(40), nullable=False),
        sa.Column("server_url", sa.String(500), nullable=False),
        sa.Column("transport", sa.String(40), nullable=False),
        sa.Column("auth_type", sa.String(40), nullable=False),
        sa.Column("secret_reference", sa.String(500)),
        sa.Column("auth_config", sa.JSON, nullable=False),
        sa.Column("requested_scopes", sa.JSON, nullable=False),
        sa.Column("granted_scopes", sa.JSON, nullable=False),
        sa.Column("policy", sa.JSON, nullable=False),
        sa.Column("requested_protocol_version", sa.String(40)),
        sa.Column("negotiated_protocol_version", sa.String(40)),
        sa.Column("sdk_version", sa.String(20), nullable=False),
        sa.Column("server_name", sa.String(120)),
        sa.Column("server_version", sa.String(80)),
        sa.Column("capabilities", sa.JSON, nullable=False),
        sa.Column("enabled", sa.Boolean, nullable=False),
        sa.Column("health_status", sa.String(40), nullable=False),
        sa.Column("sync_status", sa.String(40), nullable=False),
        sa.Column("last_health_check", sa.DateTime(timezone=True)),
        sa.Column("last_connected_at", sa.DateTime(timezone=True)),
        sa.Column("last_synced_at", sa.DateTime(timezone=True)),
        sa.Column("configuration_version", sa.Integer, nullable=False),
        sa.Column("created_by", sa.String(160), nullable=False),
        sa.Column("updated_by", sa.String(160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("tenant_id", "slug", name="uq_mcp_server_tenant_slug"),
    )
    op.create_index(
        "ix_mcp_server_health", "mcp_servers", ["tenant_id", "enabled", "health_status"]
    )
    op.create_table(
        "mcp_capabilities",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("server_id", sa.String(36), nullable=False),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("capability_type", sa.String(30), nullable=False),
        sa.Column("remote_name", sa.String(500), nullable=False),
        sa.Column("internal_name", sa.String(180), nullable=False),
        sa.Column("display_name", sa.String(160), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("uri", sa.String(2000)),
        sa.Column("mime_type", sa.String(160)),
        sa.Column("schema_json", sa.JSON, nullable=False),
        sa.Column("safe_metadata", sa.JSON, nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False),
        sa.Column("previous_fingerprint", sa.String(64)),
        sa.Column("change_status", sa.String(40), nullable=False),
        sa.Column("risk_level", sa.String(30), nullable=False),
        sa.Column("permission", sa.String(200), nullable=False),
        sa.Column("approval_policy", sa.String(40), nullable=False),
        sa.Column("enabled", sa.Boolean, nullable=False),
        sa.Column("approved", sa.Boolean, nullable=False),
        sa.Column("missing", sa.Boolean, nullable=False),
        sa.Column("first_discovered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_discovered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "server_id",
            "capability_type",
            "remote_name",
            name="uq_mcp_capability_remote",
        ),
        sa.UniqueConstraint("internal_name", name="uq_mcp_capability_internal"),
    )
    op.create_index(
        "ix_mcp_capability_catalog",
        "mcp_capabilities",
        ["tenant_id", "capability_type", "enabled", "missing"],
    )
    op.create_index(
        "ix_mcp_capability_fingerprint", "mcp_capabilities", ["fingerprint"]
    )
    op.create_table(
        "mcp_sync_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("server_id", sa.String(36), nullable=False),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("added_count", sa.Integer, nullable=False),
        sa.Column("changed_count", sa.Integer, nullable=False),
        sa.Column("removed_count", sa.Integer, nullable=False),
        sa.Column("warning_count", sa.Integer, nullable=False),
        sa.Column("error_code", sa.String(80)),
        sa.Column("safe_error", sa.String(500)),
        sa.Column("correlation_id", sa.String(100), nullable=False),
    )
    op.create_index(
        "ix_mcp_sync_history", "mcp_sync_runs", ["tenant_id", "started_at", "status"]
    )


def downgrade():
    op.drop_table("mcp_sync_runs")
    op.drop_table("mcp_capabilities")
    op.drop_table("mcp_servers")
