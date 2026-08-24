"""Add governed workflow management persistence.

Revision ID: f6a8c0e2b4d7
Revises: e5a7c9d1f3b6
"""

import json
from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import uuid4

import sqlalchemy as sa

from alembic import op

revision: str = "f6a8c0e2b4d7"
down_revision: str | Sequence[str] | None = "e5a7c9d1f3b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("workflows") as batch:
        batch.add_column(sa.Column("public_id", sa.String(36), nullable=True))
        batch.add_column(
            sa.Column(
                "tenant_id", sa.String(120), nullable=False, server_default="default"
            )
        )
        batch.add_column(
            sa.Column(
                "lifecycle_status",
                sa.String(30),
                nullable=False,
                server_default="DRAFT",
            )
        )
        batch.add_column(
            sa.Column(
                "owner_id", sa.String(160), nullable=False, server_default="system"
            )
        )
        batch.add_column(
            sa.Column(
                "current_version", sa.Integer(), nullable=False, server_default="1"
            )
        )
        batch.add_column(sa.Column("published_version", sa.Integer(), nullable=True))
        batch.add_column(
            sa.Column("lock_version", sa.Integer(), nullable=False, server_default="1")
        )
        batch.add_column(
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch.add_column(
            sa.Column(
                "updated_by", sa.String(160), nullable=False, server_default="system"
            )
        )
        batch.add_column(
            sa.Column("published_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch.add_column(
            sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True)
        )

    bind = op.get_bind()
    now = datetime.now(UTC)
    rows = (
        bind.execute(
            sa.text("SELECT id, created_by, created_at, status FROM workflows")
        )
        .mappings()
        .all()
    )
    for row in rows:
        legacy_status = str(row["status"] or "CREATED").upper()
        lifecycle = "PUBLISHED" if legacy_status in {"ACTIVE", "COMPLETED"} else "DRAFT"
        bind.execute(
            sa.text(
                "UPDATE workflows SET public_id=:public_id, tenant_id='default', lifecycle_status=:lifecycle, owner_id=:owner, current_version=1, published_version=:published_version, lock_version=1, updated_at=:updated_at, updated_by=:owner WHERE id=:id"
            ),
            {
                "public_id": str(uuid4()),
                "lifecycle": lifecycle,
                "owner": row["created_by"] or "system",
                "published_version": 1 if lifecycle == "PUBLISHED" else None,
                "updated_at": row["created_at"] or now,
                "id": row["id"],
            },
        )
    with op.batch_alter_table("workflows") as batch:
        batch.alter_column("public_id", nullable=False)
        batch.alter_column("updated_at", nullable=False)
        batch.create_unique_constraint(
            "uq_workflow_tenant_public", ["tenant_id", "public_id"]
        )
        batch.create_index(
            "ix_workflows_tenant_status", ["tenant_id", "lifecycle_status"]
        )
        batch.create_index("ix_workflows_tenant_owner", ["tenant_id", "owner_id"])
        batch.create_index("ix_workflows_tenant_updated", ["tenant_id", "updated_at"])

    op.create_table(
        "workflow_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "workflow_id",
            sa.Integer(),
            sa.ForeignKey("workflows.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("definition", sa.JSON(), nullable=False),
        sa.Column("trigger_type", sa.String(40), nullable=False),
        sa.Column("validation_result", sa.JSON(), nullable=False),
        sa.Column("change_summary", sa.String(500), nullable=False),
        sa.Column("created_by", sa.String(160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("workflow_id", "version", name="uq_workflow_version"),
    )
    op.create_index(
        "ix_workflow_versions_tenant_workflow",
        "workflow_versions",
        ["tenant_id", "workflow_id", "version"],
    )
    op.create_table(
        "workflow_activity_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "workflow_id",
            sa.Integer(),
            sa.ForeignKey("workflows.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("actor_id", sa.String(160), nullable=False),
        sa.Column("workflow_version", sa.Integer()),
        sa.Column("summary", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_workflow_activity_tenant_workflow",
        "workflow_activity_events",
        ["tenant_id", "workflow_id", "created_at"],
    )
    op.create_table(
        "workflow_access_grants",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "workflow_id",
            sa.Integer(),
            sa.ForeignKey("workflows.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("subject_type", sa.String(30), nullable=False),
        sa.Column("subject_id", sa.String(160), nullable=False),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.String(160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "tenant_id",
            "workflow_id",
            "subject_type",
            "subject_id",
            "action",
            name="uq_workflow_access_grant",
        ),
    )
    op.create_index(
        "ix_workflow_access_subject",
        "workflow_access_grants",
        ["tenant_id", "subject_type", "subject_id", "action"],
    )

    workflow_rows = (
        bind.execute(
            sa.text(
                "SELECT id, tenant_id, definition, trigger_type, created_by, created_at, published_version FROM workflows"
            )
        )
        .mappings()
        .all()
    )
    for row in workflow_rows:
        definition = row["definition"]
        if not isinstance(definition, str):
            definition = json.dumps(definition or {})
        bind.execute(
            sa.text(
                "INSERT INTO workflow_versions (id, workflow_id, tenant_id, version, definition, trigger_type, validation_result, change_summary, created_by, created_at, published) VALUES (:id, :workflow_id, :tenant_id, 1, :definition, :trigger_type, :validation_result, :change_summary, :created_by, :created_at, :published)"
            ),
            {
                "id": str(uuid4()),
                "workflow_id": row["id"],
                "tenant_id": row["tenant_id"],
                "definition": definition,
                "trigger_type": row["trigger_type"] or "MANUAL",
                "validation_result": "{}",
                "change_summary": "Backfilled existing workflow",
                "created_by": row["created_by"] or "system",
                "created_at": row["created_at"] or now,
                "published": bool(row["published_version"]),
            },
        )


def downgrade() -> None:
    op.drop_index("ix_workflow_access_subject", table_name="workflow_access_grants")
    op.drop_table("workflow_access_grants")
    op.drop_index(
        "ix_workflow_activity_tenant_workflow", table_name="workflow_activity_events"
    )
    op.drop_table("workflow_activity_events")
    op.drop_index(
        "ix_workflow_versions_tenant_workflow", table_name="workflow_versions"
    )
    op.drop_table("workflow_versions")
    with op.batch_alter_table("workflows") as batch:
        batch.drop_index("ix_workflows_tenant_updated")
        batch.drop_index("ix_workflows_tenant_owner")
        batch.drop_index("ix_workflows_tenant_status")
        batch.drop_constraint("uq_workflow_tenant_public", type_="unique")
        for column in (
            "retired_at",
            "published_at",
            "updated_by",
            "updated_at",
            "lock_version",
            "published_version",
            "current_version",
            "owner_id",
            "lifecycle_status",
            "tenant_id",
            "public_id",
        ):
            batch.drop_column(column)
