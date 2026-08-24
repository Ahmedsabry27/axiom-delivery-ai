"""Add durable tenant-scoped RAID Intelligence.

Revision ID: d6b9f4e1a327
Revises: c5a8e3d0f216
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d6b9f4e1a327"
down_revision: str | None = "c5a8e3d0f216"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


RAID_COLUMNS = (
    sa.Column("reference", sa.String(40)),
    sa.Column("description", sa.Text()),
    sa.Column("priority", sa.String(30)),
    sa.Column("residual_impact", sa.String(30)),
    sa.Column("residual_probability", sa.String(30)),
    sa.Column("exposure_score", sa.Integer()),
    sa.Column("exposure_band", sa.String(30)),
    sa.Column("residual_exposure_score", sa.Integer()),
    sa.Column("residual_exposure_band", sa.String(30)),
    sa.Column("attention_score", sa.Integer()),
    sa.Column("attention_reasons", sa.JSON(), nullable=False, server_default="[]"),
    sa.Column(
        "identified_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
    ),
    sa.Column("review_date", sa.Date()),
    sa.Column("last_reviewed_at", sa.DateTime(timezone=True)),
    sa.Column("closed_at", sa.DateTime(timezone=True)),
    sa.Column("closure_reason", sa.Text()),
    sa.Column("escalated", sa.Boolean(), nullable=False, server_default=sa.false()),
    sa.Column("programme_id", sa.String(36)),
    sa.Column("team_id", sa.String(36)),
    sa.Column("work_item_id", sa.String(36)),
    sa.Column("defect_id", sa.String(36)),
    sa.Column("dependency_id", sa.String(36)),
    sa.Column("trigger", sa.Text()),
    sa.Column("mitigation_plan", sa.Text()),
    sa.Column("contingency_plan", sa.Text()),
    sa.Column("risk_response", sa.String(30)),
    sa.Column("validation_owner_id", sa.String(255)),
    sa.Column("validation_due_date", sa.Date()),
    sa.Column("validation_method", sa.Text()),
    sa.Column("validation_status", sa.String(30)),
    sa.Column("severity", sa.String(30)),
    sa.Column("containment_plan", sa.Text()),
    sa.Column("resolution_plan", sa.Text()),
    sa.Column("root_cause", sa.Text()),
    sa.Column("critical_path", sa.Boolean(), nullable=False, server_default=sa.false()),
    sa.Column("blocked_since", sa.DateTime(timezone=True)),
    sa.Column("decision_owner_id", sa.String(255)),
    sa.Column("rationale", sa.Text()),
    sa.Column(
        "completion_evidence_required",
        sa.Boolean(),
        nullable=False,
        server_default=sa.false(),
    ),
)


def upgrade() -> None:
    with op.batch_alter_table("delivery_copilot_responses") as batch:
        batch.alter_column("sprint_id", existing_type=sa.String(36), nullable=True)
        batch.add_column(sa.Column("raid_id", sa.String(36)))
        batch.add_column(
            sa.Column(
                "response_type",
                sa.String(30),
                nullable=False,
                server_default="SPRINT_INTELLIGENCE",
            )
        )
        batch.create_foreign_key(
            "fk_copilot_response_raid",
            "delivery_raid_items",
            ["tenant_id", "raid_id"],
            ["tenant_id", "id"],
            ondelete="RESTRICT",
        )

    with op.batch_alter_table("delivery_raid_items") as batch:
        for column in RAID_COLUMNS:
            batch.add_column(column)
        for name, table, column in (
            ("fk_raid_programme", "delivery_programmes", "programme_id"),
            ("fk_raid_team", "delivery_teams", "team_id"),
            ("fk_raid_work_item", "delivery_work_items", "work_item_id"),
            ("fk_raid_defect", "delivery_defects", "defect_id"),
            ("fk_raid_dependency", "delivery_dependencies", "dependency_id"),
        ):
            batch.create_foreign_key(
                name,
                table,
                ["tenant_id", column],
                ["tenant_id", "id"],
                ondelete="RESTRICT",
            )
        batch.create_unique_constraint(
            "uq_raid_tenant_reference", ["tenant_id", "reference"]
        )
        batch.create_index(
            "ix_delivery_raid_tenant_attention", ["tenant_id", "attention_score"]
        )
        batch.create_index("ix_delivery_raid_tenant_owner", ["tenant_id", "owner_id"])
        batch.create_index(
            "ix_delivery_raid_tenant_release", ["tenant_id", "release_id"]
        )

    for table in ("delivery_recommendations", "delivery_proposed_actions"):
        with op.batch_alter_table(table) as batch:
            batch.add_column(sa.Column("raid_id", sa.String(36)))
            batch.create_foreign_key(
                f"fk_{table}_raid",
                "delivery_raid_items",
                ["tenant_id", "raid_id"],
                ["tenant_id", "id"],
                ondelete="RESTRICT",
            )
            if table == "delivery_proposed_actions":
                batch.create_index(
                    "ix_proposed_action_tenant_raid", ["tenant_id", "raid_id"]
                )

    op.create_table(
        "delivery_raid_evidence",
        sa.Column("tenant_id", sa.String(120), primary_key=True),
        sa.Column("raid_id", sa.String(36), primary_key=True),
        sa.Column("evidence_id", sa.String(36), primary_key=True),
        sa.Column("linked_by", sa.String(255), nullable=False),
        sa.Column("linked_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["tenant_id", "raid_id"],
            ["delivery_raid_items.tenant_id", "delivery_raid_items.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "evidence_id"],
            ["delivery_evidence.tenant_id", "delivery_evidence.id"],
            ondelete="RESTRICT",
        ),
    )
    op.create_index(
        "ix_raid_evidence_tenant_evidence",
        "delivery_raid_evidence",
        ["tenant_id", "evidence_id"],
    )
    op.create_table(
        "delivery_raid_relationships",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("raid_id", sa.String(36), nullable=False),
        sa.Column("entity_type", sa.String(30), nullable=False),
        sa.Column("entity_id", sa.String(36), nullable=False),
        sa.Column("relationship_type", sa.String(40), nullable=False),
        sa.Column("created_by", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "id"),
        sa.UniqueConstraint(
            "tenant_id", "raid_id", "entity_type", "entity_id", "relationship_type"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "raid_id"],
            ["delivery_raid_items.tenant_id", "delivery_raid_items.id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_raid_relationship_entity",
        "delivery_raid_relationships",
        ["tenant_id", "entity_type", "entity_id"],
    )
    op.create_table(
        "delivery_raid_related_items",
        sa.Column("tenant_id", sa.String(120), primary_key=True),
        sa.Column("raid_id", sa.String(36), primary_key=True),
        sa.Column("related_raid_id", sa.String(36), primary_key=True),
        sa.Column("relationship_type", sa.String(40), nullable=False),
        sa.Column("created_by", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "raid_id <> related_raid_id", name="ck_raid_not_self_related"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "raid_id"],
            ["delivery_raid_items.tenant_id", "delivery_raid_items.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "related_raid_id"],
            ["delivery_raid_items.tenant_id", "delivery_raid_items.id"],
            ondelete="CASCADE",
        ),
    )
    op.create_table(
        "delivery_raid_history",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("raid_id", sa.String(36), nullable=False),
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
            ["tenant_id", "raid_id"],
            ["delivery_raid_items.tenant_id", "delivery_raid_items.id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_raid_history_tenant_item",
        "delivery_raid_history",
        ["tenant_id", "raid_id", "changed_at"],
    )
    op.create_table(
        "delivery_raid_reviews",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("raid_id", sa.String(36), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("reviewed_by", sa.String(255), nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("next_review_date", sa.Date()),
        sa.UniqueConstraint("tenant_id", "id"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "raid_id"],
            ["delivery_raid_items.tenant_id", "delivery_raid_items.id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_raid_review_tenant_item",
        "delivery_raid_reviews",
        ["tenant_id", "raid_id", "reviewed_at"],
    )
    op.create_table(
        "delivery_raid_candidates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("candidate_type", sa.String(30), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("affected_entities", sa.JSON(), nullable=False),
        sa.Column("suggested_owner", sa.String(255)),
        sa.Column("suggested_due_date", sa.Date()),
        sa.Column("suggested_probability", sa.String(30)),
        sa.Column("suggested_impact", sa.String(30)),
        sa.Column("possible_duplicates", sa.JSON(), nullable=False),
        sa.Column("limitations", sa.JSON(), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("detected_by_agent", sa.String(120), nullable=False),
        sa.Column("model", sa.String(120), nullable=False),
        sa.Column("trace_id", sa.String(80), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("reviewed_by", sa.String(255)),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("dismissal_reason", sa.Text()),
        sa.Column("accepted_raid_id", sa.String(36)),
        sa.Column("merged_raid_id", sa.String(36)),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.UniqueConstraint("tenant_id", "id"),
        sa.UniqueConstraint("tenant_id", "trace_id"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "accepted_raid_id"],
            ["delivery_raid_items.tenant_id", "delivery_raid_items.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "merged_raid_id"],
            ["delivery_raid_items.tenant_id", "delivery_raid_items.id"],
            ondelete="RESTRICT",
        ),
    )
    op.create_index(
        "ix_raid_candidate_tenant_status",
        "delivery_raid_candidates",
        ["tenant_id", "status", "detected_at"],
    )
    op.create_table(
        "delivery_raid_candidate_evidence",
        sa.Column("tenant_id", sa.String(120), primary_key=True),
        sa.Column("candidate_id", sa.String(36), primary_key=True),
        sa.Column("evidence_id", sa.String(36), primary_key=True),
        sa.ForeignKeyConstraint(
            ["tenant_id", "candidate_id"],
            ["delivery_raid_candidates.tenant_id", "delivery_raid_candidates.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "evidence_id"],
            ["delivery_evidence.tenant_id", "delivery_evidence.id"],
            ondelete="RESTRICT",
        ),
    )

    op.execute(
        sa.text(
            "UPDATE delivery_raid_items SET reference = 'LEGACY-' || id WHERE reference IS NULL"
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM delivery_copilot_responses "
            "WHERE response_type = 'RAID_INTELLIGENCE'"
        )
    )
    op.drop_table("delivery_raid_candidate_evidence")
    op.drop_index(
        "ix_raid_candidate_tenant_status", table_name="delivery_raid_candidates"
    )
    op.drop_table("delivery_raid_candidates")
    op.drop_index("ix_raid_review_tenant_item", table_name="delivery_raid_reviews")
    op.drop_table("delivery_raid_reviews")
    op.drop_index("ix_raid_history_tenant_item", table_name="delivery_raid_history")
    op.drop_table("delivery_raid_history")
    op.drop_table("delivery_raid_related_items")
    op.drop_index(
        "ix_raid_relationship_entity", table_name="delivery_raid_relationships"
    )
    op.drop_table("delivery_raid_relationships")
    op.drop_index(
        "ix_raid_evidence_tenant_evidence", table_name="delivery_raid_evidence"
    )
    op.drop_table("delivery_raid_evidence")
    for table in ("delivery_proposed_actions", "delivery_recommendations"):
        with op.batch_alter_table(table) as batch:
            if table == "delivery_proposed_actions":
                batch.drop_index("ix_proposed_action_tenant_raid")
            batch.drop_constraint(f"fk_{table}_raid", type_="foreignkey")
            batch.drop_column("raid_id")
    with op.batch_alter_table("delivery_raid_items") as batch:
        for index in (
            "ix_delivery_raid_tenant_release",
            "ix_delivery_raid_tenant_owner",
            "ix_delivery_raid_tenant_attention",
        ):
            batch.drop_index(index)
        batch.drop_constraint("uq_raid_tenant_reference", type_="unique")
        for name in (
            "fk_raid_dependency",
            "fk_raid_defect",
            "fk_raid_work_item",
            "fk_raid_team",
            "fk_raid_programme",
        ):
            batch.drop_constraint(name, type_="foreignkey")
        for column in reversed(RAID_COLUMNS):
            batch.drop_column(column.name)
    with op.batch_alter_table("delivery_copilot_responses") as batch:
        batch.drop_constraint("fk_copilot_response_raid", type_="foreignkey")
        batch.drop_column("response_type")
        batch.drop_column("raid_id")
        batch.alter_column("sprint_id", existing_type=sa.String(36), nullable=False)
