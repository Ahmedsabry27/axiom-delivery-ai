"""conversation runtime metadata

Revision ID: a6c8e0f2b4d6
Revises: f5a7c9e1b3d5
"""
import sqlalchemy as sa

from alembic import op

revision = "a6c8e0f2b4d6"
down_revision = "f5a7c9e1b3d5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("conversations", sa.Column("is_pinned", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column("conversations", "is_pinned")
