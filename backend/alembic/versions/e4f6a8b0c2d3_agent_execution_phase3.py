"""Durable agent executions and replay-safe continuations.

Revision ID: e4f6a8b0c2d3
Revises: d3e5f7a9b1c2
"""

import sqlalchemy as sa

from alembic import op

revision = "e4f6a8b0c2d3"
down_revision = "d3e5f7a9b1c2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("conversations") as batch:
        batch.add_column(
            sa.Column(
                "tenant_id", sa.String(120), nullable=False, server_default="default"
            )
        )
        batch.add_column(sa.Column("agent_uuid", sa.String(36)))
        batch.add_column(sa.Column("agent_version", sa.Integer()))
        batch.create_index("ix_conversations_tenant_id", ["tenant_id"])
    op.create_table(
        "agent_executions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column(
            "agent_id",
            sa.Integer(),
            sa.ForeignKey("agents.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("agent_uuid", sa.String(36), nullable=False),
        sa.Column("agent_version", sa.Integer(), nullable=False),
        sa.Column("actor_id", sa.String(160), nullable=False),
        sa.Column("service_identity", sa.String(160)),
        sa.Column("conversation_id", sa.String(36)),
        sa.Column("workflow_id", sa.String(36)),
        sa.Column("discovery_id", sa.String(36)),
        sa.Column(
            "parent_execution_id", sa.String(36), sa.ForeignKey("agent_executions.id")
        ),
        sa.Column("status", sa.String(40), nullable=False, server_default="queued"),
        sa.Column(
            "current_phase", sa.String(60), nullable=False, server_default="queued"
        ),
        sa.Column("request_summary", sa.String(500), nullable=False),
        sa.Column("input_summary", sa.JSON(), nullable=False),
        sa.Column("output_summary", sa.JSON(), nullable=False),
        sa.Column("model_provider", sa.String(80), nullable=False),
        sa.Column("model_name", sa.String(160), nullable=False),
        sa.Column("planner", sa.String(120), nullable=False),
        sa.Column("selected_tools", sa.JSON(), nullable=False),
        sa.Column("tool_execution_ids", sa.JSON(), nullable=False),
        sa.Column("knowledge_source_ids", sa.JSON(), nullable=False),
        sa.Column("runtime_metadata", sa.JSON(), nullable=False),
        sa.Column("token_usage", sa.JSON(), nullable=False),
        sa.Column("estimated_cost", sa.Float()),
        sa.Column("actual_cost", sa.Float()),
        sa.Column("currency", sa.String(8), nullable=False, server_default="USD"),
        sa.Column("error_code", sa.String(80)),
        sa.Column("safe_error_message", sa.String(500)),
        sa.Column("correlation_id", sa.String(100), nullable=False, unique=True),
        sa.Column("trace_id", sa.String(100), nullable=False),
        sa.Column("test_mode", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("cancelled_at", sa.DateTime(timezone=True)),
        sa.Column("duration_ms", sa.Float()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_agent_execution_tenant_status",
        "agent_executions",
        ["tenant_id", "status", "created_at"],
    )
    op.create_index(
        "ix_agent_execution_agent_time",
        "agent_executions",
        ["tenant_id", "agent_id", "created_at"],
    )
    op.create_index(
        "ix_agent_execution_correlation", "agent_executions", ["correlation_id"]
    )
    op.create_table(
        "agent_continuations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column(
            "execution_id",
            sa.String(36),
            sa.ForeignKey("agent_executions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("conversation_id", sa.String(36)),
        sa.Column("workflow_id", sa.String(36)),
        sa.Column(
            "agent_id",
            sa.Integer(),
            sa.ForeignKey("agents.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("agent_version", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("tool_name", sa.String(100)),
        sa.Column("tool_version", sa.String(40)),
        sa.Column("schema", sa.JSON(), nullable=False),
        sa.Column("known_values", sa.JSON(), nullable=False),
        sa.Column("missing_fields", sa.JSON(), nullable=False),
        sa.Column("safe_question", sa.String(500)),
        sa.Column("alternatives", sa.JSON(), nullable=False),
        sa.Column("required_approver", sa.String(160)),
        sa.Column("input_fingerprint", sa.String(64)),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("resume_token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("response", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
        sa.Column("cancelled_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint(
            "execution_id", "kind", "status", name="uq_agent_continuation_state"
        ),
    )
    op.create_index(
        "ix_agent_continuation_tenant_execution",
        "agent_continuations",
        ["tenant_id", "execution_id"],
    )
    op.create_index(
        "ix_agent_continuation_expiration",
        "agent_continuations",
        ["status", "expires_at"],
    )


def downgrade() -> None:
    op.drop_table("agent_continuations")
    op.drop_table("agent_executions")
    with op.batch_alter_table("conversations") as batch:
        batch.drop_index("ix_conversations_tenant_id")
        batch.drop_column("agent_version")
        batch.drop_column("agent_uuid")
        batch.drop_column("tenant_id")
