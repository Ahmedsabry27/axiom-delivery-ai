"""make task agent nullable

Revision ID: 57d2ef723b0b
Revises: 4c798e1da4ad
Create Date: 2026-07-27 18:29:44.346084

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '57d2ef723b0b'
down_revision: str | Sequence[str] | None = '4c798e1da4ad'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.alter_column(
            "agent",
            existing_type=sa.String(),
            nullable=True,
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table("tasks") as batch_op:
        batch_op.alter_column(
            "agent",
            existing_type=sa.String(),
            nullable=False,
        )
