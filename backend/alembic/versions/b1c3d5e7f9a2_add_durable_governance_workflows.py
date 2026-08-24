"""Add durable governance workflows and relational integrity.

Revision ID: b1c3d5e7f9a2
Revises: a0b2c4d6e8f1
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "b1c3d5e7f9a2"
down_revision = "a0b2c4d6e8f1"
branch_labels = None
depends_on = None


def _assert_no_rows(sql: str, diagnostic: str) -> None:
    rows = op.get_bind().execute(sa.text(sql)).fetchmany(5)
    if rows:
        sample = ", ".join(str(tuple(row)) for row in rows)
        raise RuntimeError(
            f"{diagnostic}. Reconcile these rows before upgrading. Sample: {sample}"
        )


def upgrade() -> None:
    _assert_no_rows(
        """SELECT tenant_id, tool_name, COALESCE(tool_version, ''), subject_type,
                  subject_id, action, COUNT(*)
             FROM tool_assignments
         GROUP BY tenant_id, tool_name, COALESCE(tool_version, ''), subject_type,
                  subject_id, action HAVING COUNT(*) > 1""",
        "Duplicate tool assignments prevent the required uniqueness constraint",
    )
    _assert_no_rows(
        """SELECT tenant_id, name, version, COUNT(*) FROM tool_governance_policies
         GROUP BY tenant_id, name, version HAVING COUNT(*) > 1""",
        "Duplicate governance policy versions prevent the required uniqueness constraint",
    )
    _assert_no_rows(
        """SELECT tenant_id, internal_name, COUNT(*) FROM mcp_capabilities
         GROUP BY tenant_id, internal_name HAVING COUNT(*) > 1""",
        "Duplicate tenant MCP internal names prevent the required uniqueness constraint",
    )
    _assert_no_rows(
        """SELECT file_id, sequence, COUNT(*) FROM native_file_contents
         GROUP BY file_id, sequence HAVING COUNT(*) > 1""",
        "Duplicate native file-content sequences prevent the required uniqueness constraint",
    )
    _assert_no_rows(
        """SELECT c.id, c.server_id FROM mcp_capabilities c
        LEFT JOIN mcp_servers s ON s.id=c.server_id WHERE s.id IS NULL""",
        "Orphan MCP capabilities prevent the server foreign key",
    )
    _assert_no_rows(
        """SELECT r.id, r.server_id FROM mcp_sync_runs r
        LEFT JOIN mcp_servers s ON s.id=r.server_id WHERE s.id IS NULL""",
        "Orphan MCP sync runs prevent the server foreign key",
    )
    _assert_no_rows(
        """SELECT c.id, c.file_id FROM native_file_contents c
        LEFT JOIN native_files f ON f.id=c.file_id WHERE f.id IS NULL""",
        "Orphan native file content prevents the file foreign key",
    )
    _assert_no_rows(
        """SELECT c.id, c.discovery_id FROM tool_candidate_decisions c
        LEFT JOIN tool_discovery_events d ON d.id=c.discovery_id WHERE d.id IS NULL""",
        "Orphan discovery candidate decisions prevent the discovery foreign key",
    )
    _assert_no_rows(
        """SELECT f.id, f.discovery_id FROM tool_discovery_feedback f
        LEFT JOIN tool_discovery_events d ON d.id=f.discovery_id WHERE d.id IS NULL""",
        "Orphan discovery feedback prevents the discovery foreign key",
    )

    with op.batch_alter_table("tool_assignments") as batch:
        batch.create_unique_constraint(
            "uq_tool_assignment_subject_action",
            [
                "tenant_id",
                "tool_name",
                "tool_version",
                "subject_type",
                "subject_id",
                "action",
            ],
        )
    with op.batch_alter_table("tool_governance_policies") as batch:
        batch.create_unique_constraint(
            "uq_governance_policy_version", ["tenant_id", "name", "version"]
        )
    with op.batch_alter_table("mcp_capabilities") as batch:
        batch.drop_constraint("uq_mcp_capability_internal", type_="unique")
        batch.create_unique_constraint(
            "uq_mcp_capability_tenant_internal", ["tenant_id", "internal_name"]
        )
        batch.create_foreign_key(
            "fk_mcp_capability_server",
            "mcp_servers",
            ["server_id"],
            ["id"],
            ondelete="CASCADE",
        )
    with op.batch_alter_table("mcp_sync_runs") as batch:
        batch.create_foreign_key(
            "fk_mcp_sync_server",
            "mcp_servers",
            ["server_id"],
            ["id"],
            ondelete="CASCADE",
        )
    with op.batch_alter_table("native_file_contents") as batch:
        batch.create_unique_constraint(
            "uq_native_file_content_sequence", ["file_id", "sequence"]
        )
        batch.create_foreign_key(
            "fk_native_content_file",
            "native_files",
            ["file_id"],
            ["id"],
            ondelete="CASCADE",
        )
    with op.batch_alter_table("tool_candidate_decisions") as batch:
        batch.create_foreign_key(
            "fk_candidate_discovery",
            "tool_discovery_events",
            ["discovery_id"],
            ["id"],
            ondelete="CASCADE",
        )
    with op.batch_alter_table("tool_discovery_feedback") as batch:
        batch.create_foreign_key(
            "fk_feedback_discovery",
            "tool_discovery_events",
            ["discovery_id"],
            ["id"],
            ondelete="CASCADE",
        )

    op.create_table(
        "approval_requests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("tool_name", sa.String(100), nullable=False),
        sa.Column("tool_version", sa.String(40), nullable=False),
        sa.Column("discovery_id", sa.String(36)),
        sa.Column("execution_id", sa.String(36)),
        sa.Column("conversation_id", sa.String(160)),
        sa.Column("requester_id", sa.String(160), nullable=False),
        sa.Column("requester_agent_id", sa.String(160)),
        sa.Column("policy_id", sa.String(36)),
        sa.Column("policy_version", sa.Integer),
        sa.Column("required_approver_role", sa.String(160)),
        sa.Column("required_approver_group", sa.String(160)),
        sa.Column("separation_of_duties", sa.Boolean, nullable=False),
        sa.Column("risk_level", sa.String(30), nullable=False),
        sa.Column("environment", sa.String(40), nullable=False),
        sa.Column("safe_action_summary", sa.JSON, nullable=False),
        sa.Column("input_fingerprint", sa.String(64), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approver_id", sa.String(160)),
        sa.Column("decision", sa.String(30)),
        sa.Column("decision_reason", sa.String(500)),
        sa.Column("decided_at", sa.DateTime(timezone=True)),
        sa.Column("resume_token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("audit_metadata", sa.JSON, nullable=False),
        sa.Column("state_version", sa.Integer, nullable=False),
    )
    op.create_index(
        "ix_approval_tenant_status",
        "approval_requests",
        ["tenant_id", "status", "created_at"],
    )
    op.create_index(
        "ix_approval_binding",
        "approval_requests",
        ["tenant_id", "tool_name", "tool_version"],
    )
    op.create_table(
        "clarification_requests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("conversation_id", sa.String(160)),
        sa.Column("discovery_id", sa.String(36)),
        sa.Column("tool_name", sa.String(100), nullable=False),
        sa.Column("tool_version", sa.String(40), nullable=False),
        sa.Column("candidate_alternatives", sa.JSON, nullable=False),
        sa.Column("question", sa.Text, nullable=False),
        sa.Column("input_schema", sa.JSON, nullable=False),
        sa.Column("known_values", sa.JSON, nullable=False),
        sa.Column("missing_fields", sa.JSON, nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("user_response", sa.JSON),
        sa.Column("resume_token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("consumed_at", sa.DateTime(timezone=True)),
        sa.Column("requester_id", sa.String(160), nullable=False),
        sa.Column("audit_metadata", sa.JSON, nullable=False),
        sa.Column("state_version", sa.Integer, nullable=False),
    )
    op.create_index(
        "ix_clarification_tenant_status",
        "clarification_requests",
        ["tenant_id", "status", "created_at"],
    )

    for column in (
        sa.Column("actor_id", sa.String, nullable=True),
        sa.Column("action", sa.String, nullable=True),
        sa.Column("target_type", sa.String, nullable=True),
        sa.Column("target_id", sa.String, nullable=True),
        sa.Column("correlation_id", sa.String, nullable=True),
        sa.Column("before_summary", sa.JSON, nullable=True),
        sa.Column("after_summary", sa.JSON, nullable=True),
        sa.Column("metadata_json", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    ):
        op.add_column("audit_logs", column)
    op.create_index(
        "ix_audit_tenant_created", "audit_logs", ["tenant_id", "created_at"]
    )
    op.create_index("ix_audit_correlation", "audit_logs", ["correlation_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_correlation", table_name="audit_logs")
    op.drop_index("ix_audit_tenant_created", table_name="audit_logs")
    for name in (
        "created_at",
        "metadata_json",
        "after_summary",
        "before_summary",
        "correlation_id",
        "target_id",
        "target_type",
        "action",
        "actor_id",
    ):
        op.drop_column("audit_logs", name)
    op.drop_table("clarification_requests")
    op.drop_table("approval_requests")
    with op.batch_alter_table("tool_discovery_feedback") as batch:
        batch.drop_constraint("fk_feedback_discovery", type_="foreignkey")
    with op.batch_alter_table("tool_candidate_decisions") as batch:
        batch.drop_constraint("fk_candidate_discovery", type_="foreignkey")
    with op.batch_alter_table("native_file_contents") as batch:
        batch.drop_constraint("fk_native_content_file", type_="foreignkey")
        batch.drop_constraint("uq_native_file_content_sequence", type_="unique")
    with op.batch_alter_table("mcp_sync_runs") as batch:
        batch.drop_constraint("fk_mcp_sync_server", type_="foreignkey")
    with op.batch_alter_table("mcp_capabilities") as batch:
        batch.drop_constraint("fk_mcp_capability_server", type_="foreignkey")
        batch.drop_constraint("uq_mcp_capability_tenant_internal", type_="unique")
        batch.create_unique_constraint("uq_mcp_capability_internal", ["internal_name"])
    with op.batch_alter_table("tool_governance_policies") as batch:
        batch.drop_constraint("uq_governance_policy_version", type_="unique")
    with op.batch_alter_table("tool_assignments") as batch:
        batch.drop_constraint("uq_tool_assignment_subject_action", type_="unique")
