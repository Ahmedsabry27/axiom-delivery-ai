"""add RuntimeExecution deadline

Revision ID: e1a3c5d7f9b2
Revises: d0f2a4c6e8b1
Create Date: 2026-08-12
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e1a3c5d7f9b2"
down_revision: str | Sequence[str] | None = "d0f2a4c6e8b1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "runtime_executions", sa.Column("deadline_at", sa.DateTime(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("runtime_executions", "deadline_at")
