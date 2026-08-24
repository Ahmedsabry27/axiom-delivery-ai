"""Canonical tenant-scoped agents and immutable versions.

Revision ID: c2d4e6f8a0b1
Revises: b1c3d5e7f9a2
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from uuid import uuid4

import sqlalchemy as sa

from alembic import op

revision = "c2d4e6f8a0b1"
down_revision = "b1c3d5e7f9a2"
branch_labels = None
depends_on = None


def _slug(value: str, fallback: int) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return (normalized or f"agent-{fallback}")[:100]


def upgrade() -> None:
    additions = [
        sa.Column("uuid", sa.String(36), nullable=True),
        sa.Column(
            "tenant_id", sa.String(120), nullable=False, server_default="default"
        ),
        sa.Column("slug", sa.String(120), nullable=True),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("owner_id", sa.String(160), nullable=False, server_default="system"),
        sa.Column(
            "lifecycle_status", sa.String(20), nullable=False, server_default="draft"
        ),
        sa.Column(
            "operational_health",
            sa.String(30),
            nullable=False,
            server_default="unknown",
        ),
        sa.Column("current_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("published_version", sa.Integer(), nullable=True),
        sa.Column("model_configuration_ref", sa.String(200), nullable=True),
        sa.Column(
            "planner_configuration", sa.JSON(), nullable=False, server_default="{}"
        ),
        sa.Column(
            "instruction_version", sa.Integer(), nullable=False, server_default="1"
        ),
        sa.Column(
            "tool_discovery_mode",
            sa.String(30),
            nullable=False,
            server_default="assigned_only",
        ),
        sa.Column(
            "memory_configuration", sa.JSON(), nullable=False, server_default="{}"
        ),
        sa.Column(
            "max_execution_steps", sa.Integer(), nullable=False, server_default="20"
        ),
        sa.Column(
            "execution_timeout_seconds",
            sa.Integer(),
            nullable=False,
            server_default="120",
        ),
        sa.Column("cost_limit", sa.Float(), nullable=True),
        sa.Column("risk_limit", sa.String(20), nullable=False, server_default="read"),
        sa.Column(
            "environment_restrictions", sa.JSON(), nullable=False, server_default="[]"
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_by", sa.String(160), nullable=False, server_default="system"
        ),
        sa.Column(
            "updated_by", sa.String(160), nullable=False, server_default="system"
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lock_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.String(160), nullable=True),
    ]
    with op.batch_alter_table("agents") as batch:
        for column in additions:
            batch.add_column(column)

    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT id, name, status, health, configuration, created_at FROM agents ORDER BY id"
        )
    ).mappings()
    used: set[str] = set()
    migrated: list[dict] = []
    for row in rows:
        base = _slug(row["name"], row["id"])
        slug = base
        suffix = 2
        while slug in used:
            slug = f"{base[:110]}-{suffix}"
            suffix += 1
        used.add(slug)
        try:
            config = json.loads(row["configuration"] or "{}")
        except (TypeError, json.JSONDecodeError):
            config = {
                "legacy_configuration": row["configuration"],
                "migration_warning": "invalid JSON preserved",
            }
        legacy_status = str(row["status"] or "").lower()
        lifecycle = (
            "enabled" if legacy_status in {"online", "ready", "enabled"} else "draft"
        )
        now = datetime.now(UTC)
        public_id = str(uuid4())
        bind.execute(
            sa.text("""UPDATE agents SET uuid=:uuid, slug=:slug, description=:description,
                owner_id='system', lifecycle_status=:lifecycle, operational_health=:health,
                updated_at=:updated_at WHERE id=:id"""),
            {
                "uuid": public_id,
                "slug": slug,
                "description": str(config.get("description", "")),
                "lifecycle": lifecycle,
                "health": str(row["health"] or "unknown").lower(),
                "updated_at": row["created_at"] or now,
                "id": row["id"],
            },
        )
        migrated.append(
            {
                "id": row["id"],
                "tenant": "default",
                "config": config,
                "created_at": row["created_at"] or now,
                "published": lifecycle == "enabled",
            }
        )

    with op.batch_alter_table("agents") as batch:
        batch.alter_column("uuid", nullable=False)
        batch.alter_column("slug", nullable=False)
        batch.create_unique_constraint("uq_agents_uuid", ["uuid"])
        batch.create_unique_constraint("uq_agent_tenant_slug", ["tenant_id", "slug"])
        batch.create_check_constraint(
            "ck_agent_lifecycle_status",
            "lifecycle_status IN ('draft','published','enabled','disabled','archived','error')",
        )
        batch.create_index("ix_agents_tenant_status", ["tenant_id", "lifecycle_status"])
        batch.create_index("ix_agents_tenant_owner", ["tenant_id", "owner_id"])
        batch.create_index("ix_agents_tenant_updated", ["tenant_id", "updated_at"])

    op.create_table(
        "agent_versions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "agent_id",
            sa.Integer(),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("instructions", sa.Text(), nullable=False),
        sa.Column("model_configuration", sa.JSON(), nullable=False),
        sa.Column("planner_configuration", sa.JSON(), nullable=False),
        sa.Column("memory_configuration", sa.JSON(), nullable=False),
        sa.Column("execution_limits", sa.JSON(), nullable=False),
        sa.Column("tool_discovery_configuration", sa.JSON(), nullable=False),
        sa.Column("configuration_snapshot", sa.JSON(), nullable=False),
        sa.Column("change_note", sa.String(500), nullable=False),
        sa.Column("created_by", sa.String(160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.UniqueConstraint("agent_id", "version", name="uq_agent_version"),
    )
    op.create_index(
        "ix_agent_versions_tenant_agent",
        "agent_versions",
        ["tenant_id", "agent_id", "version"],
    )
    op.create_table(
        "agent_activity_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "agent_id",
            sa.Integer(),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("actor_id", sa.String(160), nullable=False),
        sa.Column("agent_version", sa.Integer(), nullable=True),
        sa.Column("summary", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_agent_activity_tenant_agent",
        "agent_activity_events",
        ["tenant_id", "agent_id", "created_at"],
    )

    versions = sa.table(
        "agent_versions",
        sa.column("id"),
        sa.column("agent_id"),
        sa.column("tenant_id"),
        sa.column("version"),
        sa.column("instructions"),
        sa.column("model_configuration"),
        sa.column("planner_configuration"),
        sa.column("memory_configuration"),
        sa.column("execution_limits"),
        sa.column("tool_discovery_configuration"),
        sa.column("configuration_snapshot"),
        sa.column("change_note"),
        sa.column("created_by"),
        sa.column("created_at"),
        sa.column("published"),
    )
    for item in migrated:
        config = item["config"]
        op.bulk_insert(
            versions,
            [
                {
                    "id": str(uuid4()),
                    "agent_id": item["id"],
                    "tenant_id": item["tenant"],
                    "version": 1,
                    "instructions": str(config.get("instructions", "")),
                    "model_configuration": {"model": config.get("model", "")},
                    "planner_configuration": {},
                    "memory_configuration": {
                        "enabled": bool(config.get("memory_enabled", True))
                    },
                    "execution_limits": {"max_steps": 20, "timeout_seconds": 120},
                    "tool_discovery_configuration": {
                        "mode": "assigned_only",
                        "legacy_tools": config.get("tools", []),
                    },
                    "configuration_snapshot": config,
                    "change_note": "Migrated from legacy agent configuration",
                    "created_by": "system:migration",
                    "created_at": item["created_at"],
                    "published": item["published"],
                }
            ],
        )


def downgrade() -> None:
    op.drop_index("ix_agent_activity_tenant_agent", table_name="agent_activity_events")
    op.drop_table("agent_activity_events")
    op.drop_index("ix_agent_versions_tenant_agent", table_name="agent_versions")
    op.drop_table("agent_versions")
    names = [
        "uuid",
        "tenant_id",
        "slug",
        "description",
        "owner_id",
        "lifecycle_status",
        "operational_health",
        "current_version",
        "published_version",
        "model_configuration_ref",
        "planner_configuration",
        "instruction_version",
        "tool_discovery_mode",
        "memory_configuration",
        "max_execution_steps",
        "execution_timeout_seconds",
        "cost_limit",
        "risk_limit",
        "environment_restrictions",
        "updated_at",
        "created_by",
        "updated_by",
        "published_at",
        "archived_at",
        "lock_version",
        "deleted_at",
        "deleted_by",
    ]
    with op.batch_alter_table("agents") as batch:
        batch.drop_index("ix_agents_tenant_updated")
        batch.drop_index("ix_agents_tenant_owner")
        batch.drop_index("ix_agents_tenant_status")
        batch.drop_constraint("ck_agent_lifecycle_status", type_="check")
        batch.drop_constraint("uq_agent_tenant_slug", type_="unique")
        batch.drop_constraint("uq_agents_uuid", type_="unique")
        for name in names:
            batch.drop_column(name)
