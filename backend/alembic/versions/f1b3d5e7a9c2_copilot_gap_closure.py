"""copilot saved insights and prompt templates

Revision ID: f1b3d5e7a9c2
Revises: e9a1c3d5f7b2
"""

import sqlalchemy as sa

from alembic import op

revision = "f1b3d5e7a9c2"
down_revision = "e9a1c3d5f7b2"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "conversations",
        sa.Column(
            "is_archived", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    op.add_column(
        "conversations",
        sa.Column("context_summary", sa.JSON(), nullable=False, server_default="{}"),
    )
    op.create_table(
        "copilot_saved_insights",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("insight_type", sa.String(60), nullable=False),
        sa.Column("conversation_id", sa.String(36)),
        sa.Column("execution_id", sa.String(36)),
        sa.Column("response_reference", sa.String(120)),
        sa.Column("delivery_context", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.String(30), nullable=False),
        sa.Column("evidence_snapshots", sa.JSON(), nullable=False),
        sa.Column("evidence_freshness", sa.String(40)),
        sa.Column("owner_id", sa.String(255), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("review_date", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.String(255), nullable=False),
        sa.Column("updated_by", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "id"),
    )
    for name, columns in (
        ("ix_copilot_insight_tenant_status", ["tenant_id", "status", "updated_at"]),
        ("ix_copilot_insight_owner", ["tenant_id", "owner_id"]),
    ):
        op.create_index(name, "copilot_saved_insights", columns)
    op.create_table(
        "copilot_prompt_templates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("template_key", sa.String(120), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.String(60), nullable=False),
        sa.Column("prompt_body", sa.Text(), nullable=False),
        sa.Column("required_context_types", sa.JSON(), nullable=False),
        sa.Column("expected_response_type", sa.String(80), nullable=False),
        sa.Column("evidence_requirement", sa.String(40), nullable=False),
        sa.Column("may_propose_action", sa.Boolean(), nullable=False),
        sa.Column("owner_id", sa.String(255), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("supersedes_id", sa.String(36)),
        sa.Column("created_by", sa.String(255), nullable=False),
        sa.Column("updated_by", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "template_key", "version"),
    )
    op.create_index(
        "ix_copilot_template_catalog",
        "copilot_prompt_templates",
        ["tenant_id", "category", "status", "updated_at"],
    )
    op.create_table(
        "copilot_prompt_favorites",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("user_id", sa.String(255), nullable=False),
        sa.Column("template_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["template_id"], ["copilot_prompt_templates.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint("tenant_id", "user_id", "template_id"),
    )
    op.create_index(
        "ix_copilot_favorite_user", "copilot_prompt_favorites", ["tenant_id", "user_id"]
    )


def downgrade():
    op.drop_table("copilot_prompt_favorites")
    op.drop_table("copilot_prompt_templates")
    op.drop_table("copilot_saved_insights")
    op.drop_column("conversations", "context_summary")
    op.drop_column("conversations", "is_archived")
