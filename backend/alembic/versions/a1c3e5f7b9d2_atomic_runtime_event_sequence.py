"""Add authoritative runtime event sequence counter.

Revision ID: a1c3e5f7b9d2
Revises: f8d1b6c3e540
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a1c3e5f7b9d2"
down_revision: str | Sequence[str] | None = "f8d1b6c3e540"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add nullable first so existing rows can be derived from durable history.
    with op.batch_alter_table("runtime_executions") as batch:
        batch.add_column(sa.Column("last_event_sequence", sa.Integer(), nullable=True))

    op.execute(
        "UPDATE runtime_executions AS execution "
        "SET last_event_sequence = COALESCE(("
        "SELECT MAX(event.sequence) FROM runtime_execution_events AS event "
        "WHERE event.execution_id = execution.id), 0)"
    )

    with op.batch_alter_table("runtime_executions") as batch:
        batch.alter_column(
            "last_event_sequence",
            existing_type=sa.Integer(),
            nullable=False,
            server_default="0",
        )


def downgrade() -> None:
    with op.batch_alter_table("runtime_executions") as batch:
        batch.drop_column("last_event_sequence")
