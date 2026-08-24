"""link provisioned integrations to tool and action catalogs

Revision ID: c9e1f3a5b7d9
Revises: c8e0f2a4b6d8
"""

import sqlalchemy as sa

from alembic import op

revision = "c9e1f3a5b7d9"
down_revision = "c8e0f2a4b6d8"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "tool_definitions", sa.Column("integration_connection_id", sa.String(36))
    )
    op.create_index(
        "ix_tool_definitions_integration_connection_id",
        "tool_definitions",
        ["integration_connection_id"],
    )
    op.add_column(
        "actions",
        sa.Column(
            "tenant_id", sa.String(120), nullable=False, server_default="default"
        ),
    )
    op.add_column("actions", sa.Column("display_name", sa.String(160)))
    op.add_column("actions", sa.Column("provider", sa.String(80)))
    op.add_column("actions", sa.Column("category", sa.String(80)))
    op.add_column("actions", sa.Column("integration_connection_id", sa.String(36)))
    op.add_column("actions", sa.Column("risk_level", sa.String(20)))
    op.add_column(
        "actions",
        sa.Column(
            "approval_required", sa.Boolean, nullable=False, server_default=sa.false()
        ),
    )
    op.create_index("ix_actions_tenant_id", "actions", ["tenant_id"])
    op.create_index(
        "ix_actions_integration_connection_id", "actions", ["integration_connection_id"]
    )
    op.create_index(
        "uq_action_tenant_connection_name",
        "actions",
        ["tenant_id", "integration_connection_id", "name"],
        unique=True,
    )


def downgrade():
    op.drop_index("uq_action_tenant_connection_name", table_name="actions")
    op.drop_index("ix_actions_integration_connection_id", table_name="actions")
    op.drop_index("ix_actions_tenant_id", table_name="actions")
    for column in (
        "approval_required",
        "risk_level",
        "integration_connection_id",
        "category",
        "provider",
        "display_name",
        "tenant_id",
    ):
        op.drop_column("actions", column)
    op.drop_index(
        "ix_tool_definitions_integration_connection_id", table_name="tool_definitions"
    )
    op.drop_column("tool_definitions", "integration_connection_id")
