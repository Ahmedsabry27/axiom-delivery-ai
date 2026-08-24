"""unified runtime console persistence

Revision ID: f5a7c9e1b3d5
Revises: e4f6a8b0c2d3
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "f5a7c9e1b3d5"
down_revision = "e4f6a8b0c2d3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for name, column in (
        ("selected_agent_id", sa.Column("selected_agent_id", sa.String(36))),
        ("tenant_id", sa.Column("tenant_id", sa.String(120), nullable=False, server_default="default")),
        ("provider_name", sa.Column("provider_name", sa.String(40))),
        ("model_name", sa.Column("model_name", sa.String(200))),
        ("workspace_id", sa.Column("workspace_id", sa.String(120))),
        ("current_step", sa.Column("current_step", sa.String(120))),
        ("runtime_metadata", sa.Column("runtime_metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'"))),
        ("token_usage", sa.Column("token_usage", sa.JSON(), nullable=False, server_default=sa.text("'{}'"))),
        ("estimated_cost", sa.Column("estimated_cost", sa.Float())),
        ("actual_cost", sa.Column("actual_cost", sa.Float())),
        ("waiting_reason", sa.Column("waiting_reason", sa.String(80))),
    ):
        op.add_column("runtime_executions", column)
    op.create_index("ix_runtime_executions_selected_agent_id", "runtime_executions", ["selected_agent_id"])
    op.create_index("ix_runtime_executions_tenant_id", "runtime_executions", ["tenant_id"])

    op.create_table(
        "runtime_execution_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("execution_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("runtime_executions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("name", sa.String(160)),
        sa.Column("status", sa.String(32)),
        sa.Column("description", sa.Text()),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("execution_id", "sequence", name="uq_runtime_event_sequence"),
    )
    op.create_index("ix_runtime_execution_events_execution_id", "runtime_execution_events", ["execution_id"])
    op.create_table(
        "runtime_continuations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("execution_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("runtime_executions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("schema", sa.JSON(), nullable=False),
        sa.Column("known_values", sa.JSON(), nullable=False),
        sa.Column("response", sa.JSON(), nullable=False),
        sa.Column("required_role", sa.String(120)),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("consumed_at", sa.DateTime()),
    )
    op.create_index("ix_runtime_continuations_execution_id", "runtime_continuations", ["execution_id"])
    op.create_index("ix_runtime_continuations_tenant_id", "runtime_continuations", ["tenant_id"])


def downgrade() -> None:
    op.drop_table("runtime_continuations")
    op.drop_table("runtime_execution_events")
    op.drop_index("ix_runtime_executions_tenant_id", table_name="runtime_executions")
    op.drop_index("ix_runtime_executions_selected_agent_id", table_name="runtime_executions")
    for name in ("waiting_reason", "actual_cost", "estimated_cost", "token_usage", "runtime_metadata", "current_step", "workspace_id", "model_name", "provider_name", "tenant_id", "selected_agent_id"):
        op.drop_column("runtime_executions", name)
