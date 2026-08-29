"""canonical RuntimeExecution start semantics

Revision ID: d0f2a4c6e8b1
Revises: c9e1f3a5b7d9
Create Date: 2026-08-12
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d0f2a4c6e8b1"
down_revision: str | Sequence[str] | None = "c9e1f3a5b7d9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Existing executions already have a start timestamp. New PENDING rows remain
    # null until the canonical PENDING -> RUNNING transition claims them.
    with op.batch_alter_table("runtime_executions") as batch:
        batch.alter_column(
            "started_at",
            existing_type=sa.DateTime(),
            nullable=True,
        )


def downgrade() -> None:
    # Preserve downgrade safety for any PENDING rows created after this migration.
    op.execute(
        "UPDATE runtime_executions "
        "SET started_at = CURRENT_TIMESTAMP WHERE started_at IS NULL"
    )
    with op.batch_alter_table("runtime_executions") as batch:
        batch.alter_column(
            "started_at",
            existing_type=sa.DateTime(),
            nullable=False,
        )
