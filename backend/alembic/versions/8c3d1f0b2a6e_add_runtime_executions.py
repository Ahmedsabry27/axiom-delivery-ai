"""add runtime executions

Revision ID: 8c3d1f0b2a6e
Revises: 57d2ef723b0b
Create Date: 2026-07-31
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "8c3d1f0b2a6e"
down_revision: str | Sequence[str] | None = "57d2ef723b0b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "runtime_executions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("workflow_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("agent", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("duration_ms", sa.Float(), nullable=True),
        sa.Column("steps", sa.JSON(), nullable=False),
        sa.Column("result_message", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workflow_id"),
    )
    op.create_index("ix_runtime_executions_conversation_id", "runtime_executions", ["conversation_id"])
    op.create_index("ix_runtime_executions_user_id", "runtime_executions", ["user_id"])
    op.create_index("ix_runtime_executions_workflow_id", "runtime_executions", ["workflow_id"])
    op.create_index("ix_runtime_executions_status", "runtime_executions", ["status"])


def downgrade() -> None:
    op.drop_index("ix_runtime_executions_status", table_name="runtime_executions")
    op.drop_index("ix_runtime_executions_workflow_id", table_name="runtime_executions")
    op.drop_index("ix_runtime_executions_user_id", table_name="runtime_executions")
    op.drop_index("ix_runtime_executions_conversation_id", table_name="runtime_executions")
    op.drop_table("runtime_executions")
