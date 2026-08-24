"""add workflow management fields

Revision ID: a2c5e7d9f1b3
Revises: 9f4b2a1c6d8e
"""

import sqlalchemy as sa

from alembic import op

revision = "a2c5e7d9f1b3"
down_revision = "9f4b2a1c6d8e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("workflows", sa.Column("description", sa.String(), nullable=True))
    op.add_column("workflows", sa.Column("assigned_agent", sa.String(), nullable=True))
    op.add_column("workflows", sa.Column("trigger_type", sa.String(), nullable=False, server_default="MANUAL"))
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("workflows") as batch_op:
            batch_op.alter_column("trigger_type", server_default=None)
    else:
        op.alter_column("workflows", "trigger_type", server_default=None)


def downgrade() -> None:
    op.drop_column("workflows", "trigger_type")
    op.drop_column("workflows", "assigned_agent")
    op.drop_column("workflows", "description")
