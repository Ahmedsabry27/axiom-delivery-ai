"""Governed agent assignments and tenant-scoped knowledge.

Revision ID: d3e5f7a9b1c2
Revises: c2d4e6f8a0b1
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "d3e5f7a9b1c2"
down_revision = "c2d4e6f8a0b1"
branch_labels = None
depends_on = None


def _identity_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "agent_id",
            sa.Integer(),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tenant_id", sa.String(120), nullable=False),
    ]


def upgrade() -> None:
    with op.batch_alter_table("knowledge_sources") as batch:
        batch.add_column(
            sa.Column(
                "tenant_id", sa.String(120), nullable=False, server_default="default"
            )
        )
        batch.add_column(
            sa.Column(
                "owner_id", sa.String(160), nullable=False, server_default="system"
            )
        )
        batch.add_column(
            sa.Column(
                "readiness_status",
                sa.String(30),
                nullable=False,
                server_default="pending",
            )
        )
        batch.add_column(
            sa.Column(
                "health_status",
                sa.String(30),
                nullable=False,
                server_default="unknown",
            )
        )
        batch.add_column(sa.Column("last_synchronized_at", sa.DateTime(timezone=True)))
        batch.create_index(
            "ix_knowledge_tenant_readiness",
            ["tenant_id", "readiness_status", "health_status"],
        )

    op.create_table(
        "agent_tool_assignments",
        *_identity_columns(),
        sa.Column("agent_version", sa.Integer()),
        sa.Column("tool_name", sa.String(100), nullable=False),
        sa.Column("version_restriction", sa.String(80)),
        sa.Column(
            "assignment_action", sa.String(20), nullable=False, server_default="execute"
        ),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("risk_mode", sa.String(20), nullable=False, server_default="read"),
        sa.Column(
            "approval_required", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("added_by", sa.String(160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "agent_id", "tool_name", "assignment_action", name="uq_agent_tool_action"
        ),
        sa.CheckConstraint(
            "assignment_action IN ('execute','discover')", name="ck_agent_tool_action"
        ),
        sa.CheckConstraint(
            "risk_mode IN ('read','write','destructive')", name="ck_agent_tool_risk"
        ),
    )
    op.create_index(
        "ix_agent_tools_tenant_agent",
        "agent_tool_assignments",
        ["tenant_id", "agent_id", "enabled"],
    )
    op.create_table(
        "agent_knowledge_assignments",
        *_identity_columns(),
        sa.Column(
            "knowledge_source_id",
            sa.Integer(),
            sa.ForeignKey("knowledge_sources.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("source_type", sa.String(80), nullable=False),
        sa.Column("access_mode", sa.String(20), nullable=False, server_default="read"),
        sa.Column(
            "readiness_required", sa.Boolean(), nullable=False, server_default=sa.true()
        ),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("added_by", sa.String(160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "agent_id", "knowledge_source_id", name="uq_agent_knowledge_source"
        ),
        sa.CheckConstraint(
            "access_mode IN ('read','search','retrieve')",
            name="ck_agent_knowledge_access",
        ),
    )
    op.create_index(
        "ix_agent_knowledge_tenant_agent",
        "agent_knowledge_assignments",
        ["tenant_id", "agent_id", "enabled"],
    )
    op.create_table(
        "agent_access_assignments",
        *_identity_columns(),
        sa.Column("subject_type", sa.String(20), nullable=False),
        sa.Column("subject_id", sa.String(160), nullable=False),
        sa.Column("action", sa.String(30), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("added_by", sa.String(160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "agent_id",
            "subject_type",
            "subject_id",
            "action",
            name="uq_agent_access_subject_action",
        ),
        sa.CheckConstraint(
            "subject_type IN ('user','group','role','service')",
            name="ck_agent_access_subject_type",
        ),
        sa.CheckConstraint(
            "action IN ('view','edit','publish','execute','manage_tools','manage_knowledge','manage_access','view_executions','view_analytics')",
            name="ck_agent_access_action",
        ),
    )
    op.create_index(
        "ix_agent_access_lookup",
        "agent_access_assignments",
        ["tenant_id", "agent_id", "subject_type"],
    )
    op.create_table(
        "agent_execution_settings",
        *_identity_columns(),
        sa.Column("max_steps", sa.Integer(), nullable=False, server_default="20"),
        sa.Column(
            "timeout_seconds", sa.Integer(), nullable=False, server_default="120"
        ),
        sa.Column("cost_limit", sa.Float()),
        sa.Column("risk_limit", sa.String(20), nullable=False, server_default="read"),
        sa.Column("updated_by", sa.String(160), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("agent_id", name="uq_agent_execution_setting"),
    )
    op.create_index(
        "ix_agent_execution_settings_tenant",
        "agent_execution_settings",
        ["tenant_id", "agent_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_agent_execution_settings_tenant", table_name="agent_execution_settings"
    )
    op.drop_table("agent_execution_settings")
    op.drop_index("ix_agent_access_lookup", table_name="agent_access_assignments")
    op.drop_table("agent_access_assignments")
    op.drop_index(
        "ix_agent_knowledge_tenant_agent",
        table_name="agent_knowledge_assignments",
    )
    op.drop_table("agent_knowledge_assignments")
    op.drop_index("ix_agent_tools_tenant_agent", table_name="agent_tool_assignments")
    op.drop_table("agent_tool_assignments")
    with op.batch_alter_table("knowledge_sources") as batch:
        batch.drop_index("ix_knowledge_tenant_readiness")
        batch.drop_column("last_synchronized_at")
        batch.drop_column("health_status")
        batch.drop_column("readiness_status")
        batch.drop_column("owner_id")
        batch.drop_column("tenant_id")
