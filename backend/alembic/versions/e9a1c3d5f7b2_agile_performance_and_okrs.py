"""agile performance and okrs

Revision ID: e9a1c3d5f7b2
Revises: d2f4a6c8e0b3
"""

import sqlalchemy as sa

from alembic import op

revision = "e9a1c3d5f7b2"
down_revision = "d2f4a6c8e0b3"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "agile_metric_observations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("metric_key", sa.String(120), nullable=False),
        sa.Column("metric_version", sa.String(30), nullable=False),
        sa.Column("context_type", sa.String(30), nullable=False),
        sa.Column("context_id", sa.String(36), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("value", sa.Float()),
        sa.Column("unit", sa.String(40), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("source_system", sa.String(80), nullable=False),
        sa.Column("source_timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("numerator", sa.Float()),
        sa.Column("denominator", sa.Float()),
        sa.Column("missing_inputs", sa.JSON(), nullable=False),
        sa.Column("evidence_refs", sa.JSON(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "id"),
        sa.UniqueConstraint(
            "tenant_id",
            "metric_key",
            "context_type",
            "context_id",
            "period_start",
            "period_end",
            name="uq_agile_metric_period",
        ),
    )
    op.create_index(
        "ix_agile_metric_context_period",
        "agile_metric_observations",
        ["tenant_id", "context_type", "context_id", "period_end"],
    )
    op.create_table(
        "agile_objectives",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("level", sa.String(30), nullable=False),
        sa.Column("owner_id", sa.String(160), nullable=False),
        sa.Column("contributors", sa.JSON(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("target_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("confidence", sa.Float()),
        sa.Column("baseline", sa.Float()),
        sa.Column("target", sa.Float()),
        sa.Column("current_value", sa.Float()),
        sa.Column("unit", sa.String(40), nullable=False),
        sa.Column("related_metrics", sa.JSON(), nullable=False),
        sa.Column("related_entities", sa.JSON(), nullable=False),
        sa.Column("evidence_refs", sa.JSON(), nullable=False),
        sa.Column("risks", sa.JSON(), nullable=False),
        sa.Column("dependencies", sa.JSON(), nullable=False),
        sa.Column("suggested_target", sa.Boolean(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "id"),
    )
    op.create_index(
        "ix_agile_objective_level_status",
        "agile_objectives",
        ["tenant_id", "level", "status"],
    )
    op.create_table(
        "agile_key_results",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("objective_id", sa.String(36), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("baseline", sa.Float()),
        sa.Column("target", sa.Float()),
        sa.Column("current_value", sa.Float()),
        sa.Column("unit", sa.String(40), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("confidence", sa.Float()),
        sa.Column("metric_key", sa.String(120)),
        sa.Column("evidence_refs", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.UniqueConstraint("tenant_id", "id"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "objective_id"],
            ["agile_objectives.tenant_id", "agile_objectives.id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_agile_key_result_objective",
        "agile_key_results",
        ["tenant_id", "objective_id"],
    )
    op.create_table(
        "agile_objective_check_ins",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("objective_id", sa.String(36), nullable=False),
        sa.Column("actor_id", sa.String(160), nullable=False),
        sa.Column("current_value", sa.Float()),
        sa.Column("confidence", sa.Float()),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("evidence_refs", sa.JSON(), nullable=False),
        sa.Column("limitations", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id", "objective_id"],
            ["agile_objectives.tenant_id", "agile_objectives.id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_agile_check_in_objective",
        "agile_objective_check_ins",
        ["tenant_id", "objective_id", "created_at"],
    )


def downgrade():
    op.drop_index("ix_agile_check_in_objective", table_name="agile_objective_check_ins")
    op.drop_table("agile_objective_check_ins")
    op.drop_index("ix_agile_key_result_objective", table_name="agile_key_results")
    op.drop_table("agile_key_results")
    op.drop_index("ix_agile_objective_level_status", table_name="agile_objectives")
    op.drop_table("agile_objectives")
    op.drop_index(
        "ix_agile_metric_context_period", table_name="agile_metric_observations"
    )
    op.drop_table("agile_metric_observations")
