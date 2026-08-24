"""link runtime and managed agent executions

Revision ID: b7d9f1a3c5e7
Revises: a6c8e0f2b4d6
"""
import sqlalchemy as sa

from alembic import op

revision = "b7d9f1a3c5e7"
down_revision = "a6c8e0f2b4d6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("agent_executions", sa.Column("runtime_execution_id", sa.String(length=36), nullable=True))
    op.create_index("ix_agent_executions_runtime_execution_id", "agent_executions", ["runtime_execution_id"])


def downgrade() -> None:
    op.drop_index("ix_agent_executions_runtime_execution_id", table_name="agent_executions")
    op.drop_column("agent_executions", "runtime_execution_id")
