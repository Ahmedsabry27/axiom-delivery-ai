"""Add enterprise settings persistence.

Revision ID: a7c9e1f3b5d8
Revises: f6a8c0e2b4d7
"""

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

revision: str = "a7c9e1f3b5d8"
down_revision: str | Sequence[str] | None = "f6a8c0e2b4d7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "setting_values",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("user_id", sa.String(160), nullable=False, server_default=""),
        sa.Column("scope", sa.String(20), nullable=False),
        sa.Column("key", sa.String(120), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("effective_from", sa.DateTime(timezone=True)),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_by", sa.String(160), nullable=False),
        sa.UniqueConstraint(
            "tenant_id", "user_id", "scope", "key", name="uq_setting_scope_key"
        ),
    )
    op.create_index("ix_setting_tenant_scope", "setting_values", ["tenant_id", "scope"])
    op.create_table(
        "setting_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("setting_id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("user_id", sa.String(160), nullable=False, server_default=""),
        sa.Column("scope", sa.String(20), nullable=False),
        sa.Column("key", sa.String(120), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True)),
        sa.Column("reason", sa.String(500)),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("changed_by", sa.String(160), nullable=False),
    )
    op.create_index(
        "ix_setting_versions_setting_id", "setting_versions", ["setting_id"]
    )
    op.create_index("ix_setting_versions_tenant_id", "setting_versions", ["tenant_id"])
    settings_table = sa.table(
        "setting_values",
        sa.column("tenant_id", sa.String),
        sa.column("user_id", sa.String),
        sa.column("scope", sa.String),
        sa.column("key", sa.String),
        sa.column("value", sa.JSON),
        sa.column("version", sa.Integer),
        sa.column("updated_at", sa.DateTime(timezone=True)),
        sa.column("updated_by", sa.String),
    )
    now = datetime.now(UTC)
    demo = {
        "workspace.display_name": "Axiom Demo Enterprise",
        "workspace.primary_timezone": "Europe/London",
        "workspace.locale": "en-GB",
        "workspace.base_currency": "GBP",
        "delivery.sprint_length_days": 14,
        "delivery.estimation_unit": "Story points",
        "delivery.evidence_fresh_days": 7,
        "delivery.blocker_critical_days": 5,
        "reporting.fiscal_year_start": "2027-04-01",
        "reporting.cadence": "Weekly",
        "reporting.trend_weeks": 4,
        "reporting.percentage_precision": 1,
    }
    op.bulk_insert(
        settings_table,
        [
            {
                "tenant_id": "axiom-demo",
                "user_id": "",
                "scope": "tenant",
                "key": key,
                "value": value,
                "version": 1,
                "updated_at": now,
                "updated_by": "AX-DEMO-01",
            }
            for key, value in demo.items()
        ],
    )


def downgrade() -> None:
    op.drop_table("setting_versions")
    op.drop_table("setting_values")
