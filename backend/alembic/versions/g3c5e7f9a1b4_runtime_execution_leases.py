"""Add durable runtime execution leases.

Revision ID: g3c5e7f9a1b4
Revises: f2b4d6e8a0c3
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "g3c5e7f9a1b4"
down_revision: str | None = "f2b4d6e8a0c3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("runtime_executions", sa.Column("lease_owner", sa.String(255), nullable=True))
    op.add_column("runtime_executions", sa.Column("lease_expires_at", sa.DateTime(), nullable=True))
    op.add_column("runtime_executions", sa.Column("heartbeat_at", sa.DateTime(), nullable=True))
    op.add_column(
        "runtime_executions",
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_index(
        "ix_runtime_executions_stale_lease",
        "runtime_executions",
        ["status", "lease_expires_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_runtime_executions_stale_lease", table_name="runtime_executions")
    op.drop_column("runtime_executions", "attempt")
    op.drop_column("runtime_executions", "heartbeat_at")
    op.drop_column("runtime_executions", "lease_expires_at")
    op.drop_column("runtime_executions", "lease_owner")
