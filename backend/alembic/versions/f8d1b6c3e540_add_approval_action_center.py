"""Add durable Approval and Action Center.

Revision ID: f8d1b6c3e540
Revises: e7c0a5f2b438
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f8d1b6c3e540"
down_revision: str | None = "e7c0a5f2b438"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("delivery_proposed_actions") as batch:
        batch.add_column(sa.Column("title", sa.String(255)))
        batch.add_column(sa.Column("description", sa.Text()))
        batch.add_column(
            sa.Column("origin", sa.String(30), nullable=False, server_default="USER")
        )
        batch.add_column(sa.Column("requester_id", sa.String(255)))
        batch.add_column(sa.Column("agent_id", sa.String(160)))
        batch.add_column(sa.Column("target_entity_type", sa.String(50)))
        batch.add_column(sa.Column("target_entity_id", sa.String(36)))
        batch.add_column(
            sa.Column(
                "target_system",
                sa.String(80),
                nullable=False,
                server_default="INTERNAL",
            )
        )
        batch.add_column(
            sa.Column("payload", sa.JSON(), nullable=False, server_default="{}")
        )
        batch.add_column(
            sa.Column(
                "original_payload", sa.JSON(), nullable=False, server_default="{}"
            )
        )
        batch.add_column(
            sa.Column(
                "risk_level", sa.String(20), nullable=False, server_default="HIGH"
            )
        )
        batch.add_column(sa.Column("policy_id", sa.String(36)))
        batch.add_column(sa.Column("policy_version", sa.Integer()))
        batch.add_column(
            sa.Column(
                "required_approval_count",
                sa.Integer(),
                nullable=False,
                server_default="1",
            )
        )
        batch.add_column(sa.Column("expires_at", sa.DateTime(timezone=True)))
        batch.add_column(sa.Column("idempotency_key", sa.String(120)))
        batch.add_column(sa.Column("submitted_at", sa.DateTime(timezone=True)))
        batch.add_column(sa.Column("approved_at", sa.DateTime(timezone=True)))
        batch.add_column(sa.Column("executed_at", sa.DateTime(timezone=True)))
        batch.add_column(sa.Column("verified_at", sa.DateTime(timezone=True)))
        batch.add_column(sa.Column("cancelled_at", sa.DateTime(timezone=True)))
        batch.add_column(sa.Column("failure_code", sa.String(80)))
        batch.add_column(sa.Column("failure_message", sa.String(500)))
    op.execute(
        "UPDATE delivery_proposed_actions SET "
        "title = action_type, description = content, requester_id = created_by, "
        "risk_level = CASE WHEN risk_classification IN ('LOW','MEDIUM','HIGH','RESTRICTED') "
        "THEN risk_classification ELSE 'HIGH' END "
        "WHERE title IS NULL"
    )
    with op.batch_alter_table("delivery_proposed_actions") as batch:
        batch.create_unique_constraint(
            "uq_action_tenant_idempotency", ["tenant_id", "idempotency_key"]
        )
        batch.create_index("ix_action_tenant_requester", ["tenant_id", "requester_id"])
        batch.create_index(
            "ix_action_tenant_risk_status", ["tenant_id", "risk_level", "status"]
        )
        batch.create_index("ix_action_tenant_expiration", ["tenant_id", "expires_at"])
        batch.create_index(
            "ix_action_tenant_target",
            ["tenant_id", "target_entity_type", "target_entity_id"],
        )

    with op.batch_alter_table("approval_requests") as batch:
        batch.add_column(sa.Column("proposed_action_id", sa.String(36)))
        batch.add_column(sa.Column("action_version", sa.Integer()))
        batch.add_column(sa.Column("assigned_approver_id", sa.String(160)))
        batch.add_column(sa.Column("assigned_role", sa.String(160)))
        batch.add_column(
            sa.Column(
                "required_approval_count",
                sa.Integer(),
                nullable=False,
                server_default="1",
            )
        )
        batch.add_column(sa.Column("delegated_from", sa.String(160)))
        batch.add_column(sa.Column("delegated_to", sa.String(160)))
        batch.create_unique_constraint("uq_approval_tenant_id", ["tenant_id", "id"])
        batch.create_foreign_key(
            "fk_approval_proposed_action",
            "delivery_proposed_actions",
            ["tenant_id", "proposed_action_id"],
            ["tenant_id", "id"],
            ondelete="CASCADE",
        )
        batch.create_index(
            "ix_action_approval_assignee",
            ["tenant_id", "assigned_approver_id", "status"],
        )
        batch.create_index(
            "ix_action_approval_action",
            ["tenant_id", "proposed_action_id", "action_version"],
        )

    op.create_table(
        "action_approval_decisions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("approval_request_id", sa.String(36), nullable=False),
        sa.Column("proposed_action_id", sa.String(36), nullable=False),
        sa.Column("action_version", sa.Integer(), nullable=False),
        sa.Column("decision", sa.String(30), nullable=False),
        sa.Column("actor_id", sa.String(160), nullable=False),
        sa.Column("comment", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("evidence_snapshot", sa.JSON(), nullable=False),
        sa.Column("policy_snapshot", sa.JSON(), nullable=False),
        sa.CheckConstraint(
            "decision IN ('APPROVED','REJECTED','CHANGES_REQUESTED')",
            name="ck_action_decision_value",
        ),
        sa.UniqueConstraint("tenant_id", "id"),
        sa.UniqueConstraint(
            "tenant_id",
            "approval_request_id",
            "action_version",
            "actor_id",
            name="uq_action_decision_actor_version",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "approval_request_id"],
            ["approval_requests.tenant_id", "approval_requests.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "proposed_action_id"],
            ["delivery_proposed_actions.tenant_id", "delivery_proposed_actions.id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_action_decision_tenant_action",
        "action_approval_decisions",
        ["tenant_id", "proposed_action_id", "created_at"],
    )
    op.create_table(
        "action_policy_definitions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("action_type", sa.String(80), nullable=False),
        sa.Column("conditions", sa.JSON(), nullable=False),
        sa.Column("risk_level", sa.String(20), nullable=False),
        sa.Column("approval_rules", sa.JSON(), nullable=False),
        sa.Column("verification_rules", sa.JSON(), nullable=False),
        sa.Column("execution_rules", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True)),
        sa.Column("retired_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "status IN ('DRAFT','ACTIVE','RETIRED')",
            name="ck_action_policy_status",
        ),
        sa.UniqueConstraint("tenant_id", "id"),
        sa.UniqueConstraint("tenant_id", "action_type", "version"),
    )
    op.create_index(
        "ix_policy_tenant_active",
        "action_policy_definitions",
        ["tenant_id", "action_type", "status"],
    )
    op.create_table(
        "action_executions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("proposed_action_id", sa.String(36), nullable=False),
        sa.Column("action_version", sa.Integer(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("adapter", sa.String(100), nullable=False),
        sa.Column("idempotency_key", sa.String(120), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("request_snapshot", sa.JSON(), nullable=False),
        sa.Column("result_summary", sa.JSON(), nullable=False),
        sa.Column("external_reference", sa.String(255)),
        sa.Column("failure_code", sa.String(80)),
        sa.Column("failure_message", sa.String(500)),
        sa.Column("retryable", sa.Boolean(), nullable=False),
        sa.Column("trace_id", sa.String(80), nullable=False),
        sa.Column("executed_by", sa.String(160), nullable=False),
        sa.CheckConstraint(
            "status IN ('EXECUTING','EXECUTED','FAILED','PARTIALLY_EXECUTED')",
            name="ck_action_execution_status",
        ),
        sa.UniqueConstraint("tenant_id", "id"),
        sa.UniqueConstraint(
            "tenant_id",
            "proposed_action_id",
            "idempotency_key",
            name="uq_execution_idempotency",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "proposed_action_id"],
            ["delivery_proposed_actions.tenant_id", "delivery_proposed_actions.id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_execution_tenant_status",
        "action_executions",
        ["tenant_id", "status", "started_at"],
    )
    op.create_index(
        "ix_execution_tenant_trace",
        "action_executions",
        ["tenant_id", "trace_id"],
    )
    op.create_table(
        "action_verifications",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("execution_id", sa.String(36), nullable=False),
        sa.Column("verification_type", sa.String(50), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("assigned_verifier_id", sa.String(160)),
        sa.Column("verified_by", sa.String(160)),
        sa.Column("verified_at", sa.DateTime(timezone=True)),
        sa.Column("expected_result", sa.JSON(), nullable=False),
        sa.Column("observed_result", sa.JSON(), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("comment", sa.Text()),
        sa.CheckConstraint(
            "status IN ('PENDING','VERIFIED','VERIFICATION_FAILED')",
            name="ck_action_verification_status",
        ),
        sa.UniqueConstraint("tenant_id", "id"),
        sa.UniqueConstraint("tenant_id", "execution_id"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "execution_id"],
            ["action_executions.tenant_id", "action_executions.id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_verification_tenant_status",
        "action_verifications",
        ["tenant_id", "status"],
    )
    op.create_table(
        "action_notifications",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("user_id", sa.String(160), nullable=False),
        sa.Column("proposed_action_id", sa.String(36)),
        sa.Column("approval_request_id", sa.String(36)),
        sa.Column("notification_type", sa.String(50), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("message", sa.String(500), nullable=False),
        sa.Column("route", sa.String(500), nullable=False),
        sa.Column("read", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("tenant_id", "id"),
        sa.ForeignKeyConstraint(
            ["tenant_id", "proposed_action_id"],
            ["delivery_proposed_actions.tenant_id", "delivery_proposed_actions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id", "approval_request_id"],
            ["approval_requests.tenant_id", "approval_requests.id"],
            ondelete="CASCADE",
        ),
    )
    op.create_index(
        "ix_notification_tenant_user_read",
        "action_notifications",
        ["tenant_id", "user_id", "read"],
    )


def downgrade() -> None:
    op.drop_index("ix_notification_tenant_user_read", table_name="action_notifications")
    op.drop_table("action_notifications")
    op.drop_index("ix_verification_tenant_status", table_name="action_verifications")
    op.drop_table("action_verifications")
    op.drop_index("ix_execution_tenant_trace", table_name="action_executions")
    op.drop_index("ix_execution_tenant_status", table_name="action_executions")
    op.drop_table("action_executions")
    op.drop_index("ix_policy_tenant_active", table_name="action_policy_definitions")
    op.drop_table("action_policy_definitions")
    op.drop_index(
        "ix_action_decision_tenant_action", table_name="action_approval_decisions"
    )
    op.drop_table("action_approval_decisions")
    with op.batch_alter_table("approval_requests") as batch:
        batch.drop_index("ix_action_approval_action")
        batch.drop_index("ix_action_approval_assignee")
        batch.drop_constraint("fk_approval_proposed_action", type_="foreignkey")
        batch.drop_constraint("uq_approval_tenant_id", type_="unique")
        for column in (
            "delegated_to",
            "delegated_from",
            "required_approval_count",
            "assigned_role",
            "assigned_approver_id",
            "action_version",
            "proposed_action_id",
        ):
            batch.drop_column(column)
    with op.batch_alter_table("delivery_proposed_actions") as batch:
        batch.drop_index("ix_action_tenant_target")
        batch.drop_index("ix_action_tenant_expiration")
        batch.drop_index("ix_action_tenant_risk_status")
        batch.drop_index("ix_action_tenant_requester")
        batch.drop_constraint("uq_action_tenant_idempotency", type_="unique")
        for column in (
            "failure_message",
            "failure_code",
            "cancelled_at",
            "verified_at",
            "executed_at",
            "approved_at",
            "submitted_at",
            "idempotency_key",
            "expires_at",
            "required_approval_count",
            "policy_version",
            "policy_id",
            "risk_level",
            "original_payload",
            "payload",
            "target_system",
            "target_entity_id",
            "target_entity_type",
            "agent_id",
            "requester_id",
            "origin",
            "description",
            "title",
        ):
            batch.drop_column(column)
