"""Add durable dependencies and milestones.

Revision ID: b4f7d2c9e105
Revises: aae403476012
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b4f7d2c9e105"
down_revision: str | None = "aae403476012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "delivery_milestones",
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("release_id", sa.String(36)),
        sa.Column("sprint_id", sa.String(36)),
        sa.Column("description", sa.Text()),
        sa.Column("planned_date", sa.Date(), nullable=False),
        sa.Column("forecast_date", sa.Date()),
        sa.Column("actual_date", sa.Date()),
        sa.Column("critical", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("source_system", sa.String(40), nullable=False),
        sa.Column("external_id", sa.String(255)),
        sa.Column("source_url", sa.String(1000)),
        sa.Column("owner_id", sa.String(255)),
        sa.Column("created_by", sa.String(255)),
        sa.Column("updated_by", sa.String(255)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("record_metadata", sa.JSON(), nullable=False),
        sa.UniqueConstraint("tenant_id", "id"),
        sa.CheckConstraint("actual_date IS NULL OR status IN ('COMPLETED', 'CANCELLED')", name="ck_milestone_actual_status"),
        sa.CheckConstraint("forecast_date IS NULL OR forecast_date >= planned_date", name="ck_milestone_forecast_date"),
        sa.ForeignKeyConstraint(["tenant_id", "project_id"], ["delivery_projects.tenant_id", "delivery_projects.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id", "release_id"], ["delivery_releases.tenant_id", "delivery_releases.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id", "sprint_id"], ["delivery_sprints.tenant_id", "delivery_sprints.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_milestone_tenant_project_status", "delivery_milestones", ["tenant_id", "project_id", "status"])
    op.create_index("ix_milestone_tenant_critical_date", "delivery_milestones", ["tenant_id", "critical", "planned_date"])

    op.create_table(
        "delivery_dependencies",
        sa.Column("project_id", sa.String(36), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("dependency_type", sa.String(40), nullable=False),
        sa.Column("impact", sa.String(30)),
        sa.Column("priority", sa.String(30)),
        sa.Column("required_by_date", sa.Date()),
        sa.Column("identified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("blocked_since", sa.DateTime(timezone=True)),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("critical_path", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("source_system", sa.String(40), nullable=False),
        sa.Column("external_id", sa.String(255)),
        sa.Column("source_url", sa.String(1000)),
        sa.Column("owner_id", sa.String(255)),
        sa.Column("created_by", sa.String(255)),
        sa.Column("updated_by", sa.String(255)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("record_metadata", sa.JSON(), nullable=False),
        sa.UniqueConstraint("tenant_id", "id"),
        sa.CheckConstraint("resolved_at IS NULL OR status IN ('RESOLVED', 'CLOSED')", name="ck_dependency_resolved_status"),
        sa.ForeignKeyConstraint(["tenant_id", "project_id"], ["delivery_projects.tenant_id", "delivery_projects.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_dependency_tenant_project_status", "delivery_dependencies", ["tenant_id", "project_id", "status"])
    op.create_index("ix_dependency_tenant_critical_due", "delivery_dependencies", ["tenant_id", "critical_path", "required_by_date"])
    op.create_index("ix_dependency_tenant_owner", "delivery_dependencies", ["tenant_id", "owner_id"])

    op.create_table(
        "delivery_dependency_endpoints",
        sa.Column("dependency_id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(120), primary_key=True),
        sa.Column("direction", sa.String(10), primary_key=True),
        sa.Column("entity_type", sa.String(30), nullable=False),
        sa.Column("entity_id", sa.String(255), nullable=False),
        sa.CheckConstraint("direction IN ('SOURCE', 'TARGET')", name="ck_dependency_endpoint_direction"),
        sa.CheckConstraint("entity_type IN ('PROGRAMME','PROJECT','TEAM','SPRINT','RELEASE','MILESTONE','WORK_ITEM','SYSTEM','EXTERNAL_PARTY')", name="ck_dependency_endpoint_type"),
        sa.ForeignKeyConstraint(["tenant_id", "dependency_id"], ["delivery_dependencies.tenant_id", "delivery_dependencies.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("tenant_id", "dependency_id", "direction"),
    )
    op.create_index("ix_dependency_endpoint_entity", "delivery_dependency_endpoints", ["tenant_id", "entity_type", "entity_id"])


def downgrade() -> None:
    # Forward-fix policy: downgrade exists for local rehearsal only.
    op.drop_table("delivery_dependency_endpoints")
    op.drop_table("delivery_dependencies")
    op.drop_table("delivery_milestones")
