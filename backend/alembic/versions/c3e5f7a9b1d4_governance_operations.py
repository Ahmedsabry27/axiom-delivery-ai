"""Add governance and AI operations persistence.

Revision ID: c3e5f7a9b1d4
Revises: b2d4f6a8c0e1
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from app.database.models.governance import (
    AIIncident,
    AccessReview,
    Budget,
    EvaluationDataset,
    EvaluationResult,
    EvaluationRun,
    GovernancePolicy,
    GovernedModel,
    ModelPrice,
    RetentionPolicy,
    UsageRecord,
)

revision: str = "c3e5f7a9b1d4"
down_revision: str | Sequence[str] | None = "b2d4f6a8c0e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

AUDIT_COLUMNS = (
    sa.Column("event_id", sa.String(36), nullable=True),
    sa.Column("trace_id", sa.String(80), nullable=True),
    sa.Column("actor_type", sa.String(20), nullable=True),
    sa.Column("result", sa.String(30), nullable=True),
    sa.Column("policy_id", sa.String(36), nullable=True),
    sa.Column("policy_version", sa.Integer(), nullable=True),
    sa.Column("agent_id", sa.String(36), nullable=True),
    sa.Column("model_id", sa.String(36), nullable=True),
    sa.Column("provider", sa.String(80), nullable=True),
    sa.Column("tool_id", sa.String(120), nullable=True),
    sa.Column("execution_id", sa.String(36), nullable=True),
    sa.Column("approval_id", sa.String(36), nullable=True),
    sa.Column("severity", sa.String(20), nullable=True),
    sa.Column("previous_hash", sa.String(64), nullable=True),
    sa.Column("integrity_hash", sa.String(64), nullable=True),
    sa.Column("canonical_payload", sa.Text(), nullable=True),
)


def upgrade() -> None:
    bind = op.get_bind()
    for table in (
        GovernancePolicy.__table__,
        AccessReview.__table__,
        GovernedModel.__table__,
        ModelPrice.__table__,
        UsageRecord.__table__,
        Budget.__table__,
        EvaluationDataset.__table__,
        EvaluationRun.__table__,
        EvaluationResult.__table__,
        AIIncident.__table__,
        RetentionPolicy.__table__,
    ):
        table.create(bind, checkfirst=True)
    with op.batch_alter_table("audit_logs") as batch:
        for column in AUDIT_COLUMNS:
            batch.add_column(column)
        batch.create_unique_constraint("uq_audit_event_id", ["event_id"])
        batch.create_index("ix_audit_event_id", ["event_id"])
        batch.create_index("ix_audit_trace_id", ["trace_id"])
        batch.create_index("ix_audit_execution_id", ["execution_id"])
        batch.create_index("ix_audit_integrity_hash", ["integrity_hash"])


def downgrade() -> None:
    bind = op.get_bind()
    with op.batch_alter_table("audit_logs") as batch:
        for index in (
            "ix_audit_integrity_hash",
            "ix_audit_execution_id",
            "ix_audit_trace_id",
            "ix_audit_event_id",
        ):
            batch.drop_index(index)
        batch.drop_constraint("uq_audit_event_id", type_="unique")
        for column in reversed(AUDIT_COLUMNS):
            batch.drop_column(column.name)
    for table in (
        RetentionPolicy.__table__,
        AIIncident.__table__,
        EvaluationResult.__table__,
        EvaluationRun.__table__,
        EvaluationDataset.__table__,
        Budget.__table__,
        UsageRecord.__table__,
        ModelPrice.__table__,
        GovernedModel.__table__,
        AccessReview.__table__,
        GovernancePolicy.__table__,
    ):
        table.drop(bind, checkfirst=True)
