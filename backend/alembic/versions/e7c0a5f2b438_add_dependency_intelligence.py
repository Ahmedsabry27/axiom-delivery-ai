"""Add durable Dependency Intelligence.

Revision ID: e7c0a5f2b438
Revises: d6b9f4e1a327
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e7c0a5f2b438"
down_revision: str | None = "d6b9f4e1a327"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("delivery_dependencies") as batch:
        batch.add_column(sa.Column("reference", sa.String(40)))
        batch.add_column(
            sa.Column(
                "relationship_type",
                sa.String(40),
                nullable=False,
                server_default="DEPENDS_ON",
            )
        )
        batch.add_column(sa.Column("provider_owner_id", sa.String(255)))
        batch.add_column(sa.Column("consumer_owner_id", sa.String(255)))
        batch.add_column(sa.Column("acknowledged_at", sa.DateTime(timezone=True)))
        batch.add_column(sa.Column("committed_resolution_date", sa.Date()))
        batch.add_column(sa.Column("forecast_resolution_date", sa.Date()))
        batch.add_column(sa.Column("actual_resolution_date", sa.Date()))
        batch.add_column(sa.Column("last_reviewed_at", sa.DateTime(timezone=True)))
        batch.add_column(sa.Column("next_review_date", sa.Date()))
        batch.add_column(
            sa.Column(
                "external", sa.Boolean(), nullable=False, server_default=sa.false()
            )
        )
    op.execute(
        "UPDATE delivery_dependencies "
        "SET reference = 'D-' || substr(id, 1, 8) WHERE reference IS NULL"
    )
    with op.batch_alter_table("delivery_dependencies") as batch:
        batch.alter_column("reference", existing_type=sa.String(40), nullable=False)
        batch.create_unique_constraint(
            "uq_dependency_tenant_reference", ["tenant_id", "reference"]
        )
        batch.create_index(
            "ix_dependency_tenant_status_required",
            ["tenant_id", "status", "required_by_date"],
        )
        batch.create_index(
            "ix_dependency_tenant_forecast",
            ["tenant_id", "forecast_resolution_date"],
        )

    with op.batch_alter_table("delivery_dependency_endpoints") as batch:
        batch.drop_constraint("ck_dependency_endpoint_type", type_="check")
        batch.create_check_constraint(
            "ck_dependency_endpoint_type",
            "entity_type IN ('PORTFOLIO','PROGRAMME','PROJECT','TEAM','SPRINT','RELEASE','MILESTONE','EPIC','WORK_ITEM','DEFECT','SYSTEM','SERVICE','ENVIRONMENT','VENDOR','EXTERNAL_PARTY')",
        )
        batch.create_index(
            "ix_dependency_endpoint_direction_entity",
            ["tenant_id", "direction", "entity_type", "entity_id"],
        )

    op.create_table(
        "delivery_dependency_history",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("dependency_id", sa.String(36), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("previous_status", sa.String(30)),
        sa.Column("new_status", sa.String(30)),
        sa.Column("note", sa.Text()),
        sa.Column("actor_id", sa.String(255), nullable=False),
        sa.Column("trace_id", sa.String(80), nullable=False),
        sa.Column("record_version", sa.Integer(), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("change_data", sa.JSON(), nullable=False),
        sa.UniqueConstraint("tenant_id", "id"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "dependency_id"],
            ["delivery_dependencies.tenant_id", "delivery_dependencies.id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_dependency_history_tenant_item",
        "delivery_dependency_history",
        ["tenant_id", "dependency_id", "changed_at"],
    )

    op.create_table(
        "delivery_dependency_scenarios",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("dependency_id", sa.String(36), nullable=False),
        sa.Column("change_type", sa.String(40), nullable=False),
        sa.Column("change_value", sa.JSON(), nullable=False),
        sa.Column("assumptions", sa.JSON(), nullable=False),
        sa.Column("baseline_result", sa.JSON(), nullable=False),
        sa.Column("scenario_result", sa.JSON(), nullable=False),
        sa.Column("difference", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("limitations", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_by", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "id"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "dependency_id"],
            ["delivery_dependencies.tenant_id", "delivery_dependencies.id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_dependency_scenario_tenant_item",
        "delivery_dependency_scenarios",
        ["tenant_id", "dependency_id", "created_at"],
    )

    op.create_table(
        "delivery_dependency_candidates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("candidate_type", sa.String(40), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("provider_entity_type", sa.String(30), nullable=False),
        sa.Column("provider_entity_id", sa.String(255), nullable=False),
        sa.Column("consumer_entity_type", sa.String(30), nullable=False),
        sa.Column("consumer_entity_id", sa.String(255), nullable=False),
        sa.Column("relationship_type", sa.String(40), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("affected_entities", sa.JSON(), nullable=False),
        sa.Column("possible_duplicates", sa.JSON(), nullable=False),
        sa.Column("possible_cycle", sa.JSON(), nullable=False),
        sa.Column("suggested_owner", sa.String(255)),
        sa.Column("suggested_required_by_date", sa.Date()),
        sa.Column("suggested_priority", sa.String(20)),
        sa.Column("limitations", sa.JSON(), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("detected_by_agent", sa.String(120), nullable=False),
        sa.Column("model", sa.String(120), nullable=False),
        sa.Column("trace_id", sa.String(80), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("reviewed_by", sa.String(255)),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("dismissal_reason", sa.Text()),
        sa.Column("accepted_dependency_id", sa.String(36)),
        sa.Column("merged_dependency_id", sa.String(36)),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.UniqueConstraint("tenant_id", "id"),
        sa.UniqueConstraint("tenant_id", "trace_id"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "accepted_dependency_id"],
            ["delivery_dependencies.tenant_id", "delivery_dependencies.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "merged_dependency_id"],
            ["delivery_dependencies.tenant_id", "delivery_dependencies.id"],
            ondelete="RESTRICT",
        ),
    )
    op.create_index(
        "ix_dependency_candidate_tenant_status",
        "delivery_dependency_candidates",
        ["tenant_id", "status", "detected_at"],
    )
    op.create_table(
        "delivery_dependency_candidate_evidence",
        sa.Column("tenant_id", sa.String(120), primary_key=True),
        sa.Column("candidate_id", sa.String(36), primary_key=True),
        sa.Column("evidence_id", sa.String(36), primary_key=True),
        sa.ForeignKeyConstraint(
            ["tenant_id", "candidate_id"],
            [
                "delivery_dependency_candidates.tenant_id",
                "delivery_dependency_candidates.id",
            ],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "evidence_id"],
            ["delivery_evidence.tenant_id", "delivery_evidence.id"],
            ondelete="RESTRICT",
        ),
    )

    with op.batch_alter_table("delivery_copilot_responses") as batch:
        batch.add_column(sa.Column("dependency_id", sa.String(36)))
        batch.create_foreign_key(
            "fk_copilot_response_dependency",
            "delivery_dependencies",
            ["tenant_id", "dependency_id"],
            ["tenant_id", "id"],
            ondelete="RESTRICT",
        )


def downgrade() -> None:
    with op.batch_alter_table("delivery_copilot_responses") as batch:
        batch.drop_constraint("fk_copilot_response_dependency", type_="foreignkey")
        batch.drop_column("dependency_id")

    op.drop_table("delivery_dependency_candidate_evidence")
    op.drop_index(
        "ix_dependency_candidate_tenant_status",
        table_name="delivery_dependency_candidates",
    )
    op.drop_table("delivery_dependency_candidates")
    op.drop_index(
        "ix_dependency_scenario_tenant_item",
        table_name="delivery_dependency_scenarios",
    )
    op.drop_table("delivery_dependency_scenarios")
    op.drop_index(
        "ix_dependency_history_tenant_item",
        table_name="delivery_dependency_history",
    )
    op.drop_table("delivery_dependency_history")

    with op.batch_alter_table("delivery_dependency_endpoints") as batch:
        batch.drop_index("ix_dependency_endpoint_direction_entity")
        batch.drop_constraint("ck_dependency_endpoint_type", type_="check")
        batch.create_check_constraint(
            "ck_dependency_endpoint_type",
            "entity_type IN ('PROGRAMME','PROJECT','TEAM','SPRINT','RELEASE','MILESTONE','WORK_ITEM','SYSTEM','EXTERNAL_PARTY')",
        )

    with op.batch_alter_table("delivery_dependencies") as batch:
        batch.drop_index("ix_dependency_tenant_forecast")
        batch.drop_index("ix_dependency_tenant_status_required")
        batch.drop_constraint("uq_dependency_tenant_reference", type_="unique")
        for column in (
            "external",
            "next_review_date",
            "last_reviewed_at",
            "actual_resolution_date",
            "forecast_resolution_date",
            "committed_resolution_date",
            "acknowledged_at",
            "consumer_owner_id",
            "provider_owner_id",
            "relationship_type",
            "reference",
        ):
            batch.drop_column(column)
