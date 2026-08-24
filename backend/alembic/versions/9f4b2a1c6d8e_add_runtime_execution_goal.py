"""add runtime execution goal

Revision ID: 9f4b2a1c6d8e
Revises: 8c3d1f0b2a6e
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "9f4b2a1c6d8e"
down_revision: str | Sequence[str] | None = "8c3d1f0b2a6e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("runtime_executions", sa.Column("goal", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("runtime_executions", "goal")
