"""store action permissions as JSON

Revision ID: a3c5e7f9b1d6
Revises: f1b3d5e7a9c2
Create Date: 2026-08-27 18:47:00

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a3c5e7f9b1d6"
down_revision: str | Sequence[str] | None = "f1b3d5e7a9c2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Align the persisted column with the Action ORM JSON contract."""
    if op.get_bind().dialect.name == "postgresql":
        op.alter_column(
            "actions",
            "permissions",
            existing_type=sa.String(),
            type_=sa.JSON(),
            existing_nullable=False,
            postgresql_using="permissions::json",
        )
        return

    with op.batch_alter_table("actions") as batch_op:
        batch_op.alter_column(
            "permissions",
            existing_type=sa.String(),
            type_=sa.JSON(),
            existing_nullable=False,
        )


def downgrade() -> None:
    """Restore the legacy text representation without discarding values."""
    if op.get_bind().dialect.name == "postgresql":
        op.alter_column(
            "actions",
            "permissions",
            existing_type=sa.JSON(),
            type_=sa.String(),
            existing_nullable=False,
            postgresql_using="permissions::text",
        )
        return

    with op.batch_alter_table("actions") as batch_op:
        batch_op.alter_column(
            "permissions",
            existing_type=sa.JSON(),
            type_=sa.String(),
            existing_nullable=False,
        )
