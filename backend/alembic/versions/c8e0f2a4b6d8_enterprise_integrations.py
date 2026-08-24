"""generic enterprise integration connections

Revision ID: c8e0f2a4b6d8
Revises: b7d9f1a3c5e7
"""

import sqlalchemy as sa

from alembic import op

revision = "c8e0f2a4b6d8"
down_revision = "b7d9f1a3c5e7"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "integration_connections",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("connector_type", sa.String(80), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("display_name", sa.String(160), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("auth_type", sa.String(40), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("health_status", sa.String(30), nullable=False),
        sa.Column("base_url", sa.String(500), nullable=False),
        sa.Column("secret_ref", sa.String(500)),
        sa.Column("configuration", sa.JSON, nullable=False),
        sa.Column("safe_metadata", sa.JSON, nullable=False),
        sa.Column("last_verified_at", sa.DateTime(timezone=True)),
        sa.Column("last_error_code", sa.String(80)),
        sa.Column("last_error_message_safe", sa.String(500)),
        sa.Column("created_by", sa.String(160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("enabled", sa.Boolean, nullable=False),
        sa.Column("lock_version", sa.Integer, nullable=False),
        sa.UniqueConstraint(
            "tenant_id", "name", name="uq_integration_connection_tenant_name"
        ),
    )
    op.create_index(
        "ix_integration_connections_tenant_id", "integration_connections", ["tenant_id"]
    )
    op.create_index(
        "ix_integration_connections_connector_type",
        "integration_connections",
        ["connector_type"],
    )
    op.create_index(
        "ix_integration_connections_status",
        "integration_connections",
        ["tenant_id", "connector_type", "status", "health_status"],
    )
    op.create_table(
        "integration_capabilities",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "connection_id",
            sa.String(36),
            sa.ForeignKey("integration_connections.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("external_name", sa.String(160), nullable=False),
        sa.Column("display_name", sa.String(160), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("capability_type", sa.String(20), nullable=False),
        sa.Column("version", sa.String(40), nullable=False),
        sa.Column("input_schema", sa.JSON, nullable=False),
        sa.Column("output_schema", sa.JSON, nullable=False),
        sa.Column("risk_level", sa.String(20), nullable=False),
        sa.Column("approval_required", sa.Boolean, nullable=False),
        sa.Column("governance", sa.JSON, nullable=False),
        sa.Column("enabled", sa.Boolean, nullable=False),
        sa.Column("provisioned", sa.Boolean, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "connection_id",
            "external_name",
            name="uq_integration_capability_connection_name",
        ),
    )
    op.create_index(
        "ix_integration_capabilities_connection_id",
        "integration_capabilities",
        ["connection_id"],
    )
    op.create_index(
        "ix_integration_capabilities_tenant_id",
        "integration_capabilities",
        ["tenant_id"],
    )
    op.create_index(
        "ix_integration_capabilities_catalog",
        "integration_capabilities",
        ["tenant_id", "capability_type", "enabled"],
    )
    op.create_table(
        "integration_agent_assignments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "connection_id",
            sa.String(36),
            sa.ForeignKey("integration_connections.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "agent_id",
            sa.Integer,
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("capability_names", sa.JSON, nullable=False),
        sa.Column("created_by", sa.String(160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "connection_id", "agent_id", name="uq_integration_connection_agent"
        ),
    )
    op.create_index(
        "ix_integration_agent_assignments_tenant_id",
        "integration_agent_assignments",
        ["tenant_id"],
    )
    op.create_table(
        "integration_usage",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "connection_id",
            sa.String(36),
            sa.ForeignKey("integration_connections.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("capability_name", sa.String(160), nullable=False),
        sa.Column("capability_type", sa.String(20), nullable=False),
        sa.Column("agent_id", sa.String(160)),
        sa.Column("actor_id", sa.String(160), nullable=False),
        sa.Column("execution_id", sa.String(100)),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("latency_ms", sa.Float),
        sa.Column("error_code", sa.String(80)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_integration_usage_history",
        "integration_usage",
        ["tenant_id", "connection_id", "created_at"],
    )


def downgrade():
    op.drop_table("integration_usage")
    op.drop_table("integration_agent_assignments")
    op.drop_table("integration_capabilities")
    op.drop_table("integration_connections")
