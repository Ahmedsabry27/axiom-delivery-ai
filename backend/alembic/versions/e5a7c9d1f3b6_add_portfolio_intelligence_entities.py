"""Add durable Portfolio Intelligence entities.

Revision ID: e5a7c9d1f3b6
Revises: d4f6a8b0c2e5
"""

from sqlalchemy import inspect

from alembic import op
from app.database.models.delivery import (
    PortfolioInvestmentSnapshot,
    PortfolioOutcomeLink,
    PortfolioStrategicOutcome,
)

revision = "e5a7c9d1f3b6"
down_revision = "d4f6a8b0c2e5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(inspect(bind).get_table_names())
    for table in (
        PortfolioStrategicOutcome.__table__,
        PortfolioOutcomeLink.__table__,
        PortfolioInvestmentSnapshot.__table__,
    ):
        if table.name not in tables:
            table.create(bind=bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    for table in (
        PortfolioInvestmentSnapshot.__table__,
        PortfolioOutcomeLink.__table__,
        PortfolioStrategicOutcome.__table__,
    ):
        table.drop(bind=bind, checkfirst=True)
