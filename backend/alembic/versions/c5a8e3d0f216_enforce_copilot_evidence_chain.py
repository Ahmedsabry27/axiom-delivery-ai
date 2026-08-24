"""Enforce the Copilot evidence-to-proposal chain.

Revision ID: c5a8e3d0f216
Revises: b4f7d2c9e105
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c5a8e3d0f216"
down_revision: str | None = "b4f7d2c9e105"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "delivery_copilot_responses",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("conversation_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("user_message_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("assistant_message_id", sa.Uuid(as_uuid=False), nullable=False),
        sa.Column("sprint_id", sa.String(36), nullable=False),
        sa.Column("trace_id", sa.String(80), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("response_payload", sa.JSON(), nullable=False),
        sa.Column("created_by", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "id"),
        sa.UniqueConstraint("tenant_id", "trace_id"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "sprint_id"],
            ["delivery_sprints.tenant_id", "delivery_sprints.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["conversations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["user_message_id"], ["messages.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["assistant_message_id"], ["messages.id"], ondelete="RESTRICT"
        ),
    )
    op.create_index(
        "ix_copilot_response_tenant_conversation",
        "delivery_copilot_responses",
        ["tenant_id", "conversation_id"],
    )
    op.create_table(
        "delivery_copilot_response_evidence",
        sa.Column("tenant_id", sa.String(120), primary_key=True),
        sa.Column("response_id", sa.String(36), primary_key=True),
        sa.Column("evidence_id", sa.String(36), primary_key=True),
        sa.ForeignKeyConstraint(
            ["tenant_id", "response_id"],
            ["delivery_copilot_responses.tenant_id", "delivery_copilot_responses.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "evidence_id"],
            ["delivery_evidence.tenant_id", "delivery_evidence.id"],
            ondelete="RESTRICT",
        ),
    )

    with op.batch_alter_table("delivery_proposed_actions") as batch:
        for column, length in (
            ("response_id", 36),
            ("sprint_id", 36),
            ("work_item_id", 36),
            ("dependency_id", 36),
            ("recommendation_id", 36),
            ("trace_id", 80),
        ):
            batch.add_column(sa.Column(column, sa.String(length), nullable=True))
        batch.add_column(sa.Column("message_id", sa.Uuid(as_uuid=False), nullable=True))
        batch.create_foreign_key(
            "fk_action_message",
            "messages",
            ["message_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch.create_foreign_key(
            "fk_action_copilot_response",
            "delivery_copilot_responses",
            ["tenant_id", "response_id"],
            ["tenant_id", "id"],
            ondelete="RESTRICT",
        )
        for suffix, table, column in (
            ("sprint", "delivery_sprints", "sprint_id"),
            ("work_item", "delivery_work_items", "work_item_id"),
            ("dependency", "delivery_dependencies", "dependency_id"),
            ("recommendation", "delivery_recommendations", "recommendation_id"),
        ):
            batch.create_foreign_key(
                f"fk_action_{suffix}",
                table,
                ["tenant_id", column],
                ["tenant_id", "id"],
                ondelete="RESTRICT",
            )
        batch.create_index(
            "ix_proposed_action_tenant_response",
            ["tenant_id", "response_id"],
        )

    for table in ("delivery_evidence", "delivery_recommendations"):
        with op.batch_alter_table(table) as batch:
            batch.add_column(sa.Column("dependency_id", sa.String(36)))
            batch.add_column(sa.Column("milestone_id", sa.String(36)))
            batch.create_foreign_key(
                f"fk_{table}_dependency",
                "delivery_dependencies",
                ["tenant_id", "dependency_id"],
                ["tenant_id", "id"],
                ondelete="RESTRICT",
            )
            batch.create_foreign_key(
                f"fk_{table}_milestone",
                "delivery_milestones",
                ["tenant_id", "milestone_id"],
                ["tenant_id", "id"],
                ondelete="RESTRICT",
            )
        op.execute(
            sa.text(
                f"UPDATE {table} SET dependency_id = entity_id "
                "WHERE entity_type = 'DEPENDENCY'"
            )
        )
        op.execute(
            sa.text(
                f"UPDATE {table} SET milestone_id = entity_id "
                "WHERE entity_type = 'MILESTONE'"
            )
        )

    with op.batch_alter_table("delivery_raid_items") as batch:
        batch.add_column(sa.Column("milestone_id", sa.String(36)))
        batch.create_foreign_key(
            "fk_raid_milestone",
            "delivery_milestones",
            ["tenant_id", "milestone_id"],
            ["tenant_id", "id"],
            ondelete="RESTRICT",
        )


def downgrade() -> None:
    with op.batch_alter_table("delivery_raid_items") as batch:
        batch.drop_constraint("fk_raid_milestone", type_="foreignkey")
        batch.drop_column("milestone_id")
    for table in ("delivery_recommendations", "delivery_evidence"):
        with op.batch_alter_table(table) as batch:
            batch.drop_constraint(f"fk_{table}_milestone", type_="foreignkey")
            batch.drop_constraint(f"fk_{table}_dependency", type_="foreignkey")
            batch.drop_column("milestone_id")
            batch.drop_column("dependency_id")
    with op.batch_alter_table("delivery_proposed_actions") as batch:
        batch.drop_index("ix_proposed_action_tenant_response")
        for name in (
            "fk_action_recommendation",
            "fk_action_dependency",
            "fk_action_work_item",
            "fk_action_sprint",
            "fk_action_copilot_response",
            "fk_action_message",
        ):
            batch.drop_constraint(name, type_="foreignkey")
        for column in (
            "trace_id",
            "recommendation_id",
            "dependency_id",
            "work_item_id",
            "sprint_id",
            "response_id",
            "message_id",
        ):
            batch.drop_column(column)
    op.drop_table("delivery_copilot_response_evidence")
    op.drop_index(
        "ix_copilot_response_tenant_conversation",
        table_name="delivery_copilot_responses",
    )
    op.drop_table("delivery_copilot_responses")
