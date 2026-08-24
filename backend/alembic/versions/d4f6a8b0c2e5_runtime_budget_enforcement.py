"""Add durable runtime budget enforcement.

Revision ID: d4f6a8b0c2e5
Revises: c3e5f7a9b1d4
"""

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op
from app.database.models.governance import (
    BudgetAlert,
    BudgetOverride,
    BudgetReservation,
)

revision = "d4f6a8b0c2e5"
down_revision = "c3e5f7a9b1d4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("ai_budgets")}
    if "state_version" not in columns:
        op.add_column(
            "ai_budgets",
            sa.Column(
                "state_version", sa.Integer(), nullable=False, server_default="1"
            ),
        )
    tables = set(inspector.get_table_names())
    for table in (
        BudgetReservation.__table__,
        BudgetAlert.__table__,
        BudgetOverride.__table__,
    ):
        if table.name not in tables:
            table.create(bind=bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    for table in (
        BudgetOverride.__table__,
        BudgetAlert.__table__,
        BudgetReservation.__table__,
    ):
        table.drop(bind=bind, checkfirst=True)
    columns = {column["name"] for column in inspect(bind).get_columns("ai_budgets")}
    if "state_version" in columns:
        op.drop_column("ai_budgets", "state_version")
