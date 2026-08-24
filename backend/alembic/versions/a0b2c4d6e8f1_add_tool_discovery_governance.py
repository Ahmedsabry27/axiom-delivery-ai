"""add Sprint 14 tool discovery and governance
Revision ID: a0b2c4d6e8f1
Revises: f9a1b3c5d7e9
"""

import sqlalchemy as sa

from alembic import op

revision = "a0b2c4d6e8f1"
down_revision = "f9a1b3c5d7e9"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "tool_search_index",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("tool_name", sa.String(100), nullable=False),
        sa.Column("tool_version", sa.String(40), nullable=False),
        sa.Column("search_document", sa.Text, nullable=False),
        sa.Column("content_fingerprint", sa.String(64), nullable=False),
        sa.Column("embedding", sa.JSON, nullable=False),
        sa.Column("embedding_model", sa.String(120), nullable=False),
        sa.Column("embedding_dimensions", sa.Integer, nullable=False),
        sa.Column("index_version", sa.String(40), nullable=False),
        sa.Column("index_status", sa.String(30), nullable=False),
        sa.Column("safe_error_code", sa.String(80)),
        sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "tenant_id", "tool_name", "tool_version", name="uq_tool_search_version"
        ),
    )
    op.create_index(
        "ix_tool_search_eligibility",
        "tool_search_index",
        ["tenant_id", "index_status", "tool_name"],
    )
    op.create_table(
        "tool_marketplace_profiles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("tool_name", sa.String(100), nullable=False),
        sa.Column("tool_version", sa.String(40), nullable=False),
        sa.Column("source", sa.String(30), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("health_status", sa.String(30), nullable=False),
        sa.Column("environment", sa.String(40), nullable=False),
        sa.Column("data_classifications", sa.JSON, nullable=False),
        sa.Column("approval_policy", sa.String(40), nullable=False),
        sa.Column("estimated_cost", sa.Float),
        sa.Column("currency", sa.String(8), nullable=False),
        sa.Column("agent_allowlist", sa.JSON, nullable=False),
        sa.Column("safe_metadata", sa.JSON, nullable=False),
        sa.Column("updated_by", sa.String(160), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "tenant_id", "tool_name", "tool_version", name="uq_marketplace_tool"
        ),
    )
    op.create_index(
        "ix_marketplace_catalog",
        "tool_marketplace_profiles",
        ["tenant_id", "status", "source"],
    )
    op.create_table(
        "tool_assignments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("tool_name", sa.String(100), nullable=False),
        sa.Column("tool_version", sa.String(40)),
        sa.Column("subject_type", sa.String(30), nullable=False),
        sa.Column("subject_id", sa.String(160), nullable=False),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("decision", sa.String(30), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("created_by", sa.String(160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_tool_assignment_lookup",
        "tool_assignments",
        ["tenant_id", "tool_name", "subject_type", "subject_id"],
    )
    op.create_table(
        "tool_governance_policies",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("lifecycle", sa.String(30), nullable=False),
        sa.Column("conditions", sa.JSON, nullable=False),
        sa.Column("actions", sa.JSON, nullable=False),
        sa.Column("decision", sa.String(30), nullable=False),
        sa.Column("priority", sa.Integer, nullable=False),
        sa.Column("change_note", sa.String(500), nullable=False),
        sa.Column("created_by", sa.String(160), nullable=False),
        sa.Column("updated_by", sa.String(160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "ix_governance_active",
        "tool_governance_policies",
        ["tenant_id", "lifecycle", "priority"],
    )
    op.create_table(
        "tool_discovery_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("actor_id", sa.String(160), nullable=False),
        sa.Column("agent_id", sa.String(160)),
        sa.Column("conversation_id", sa.String(160)),
        sa.Column("safe_intent", sa.JSON, nullable=False),
        sa.Column("candidate_count", sa.Integer, nullable=False),
        sa.Column("eligible_count", sa.Integer, nullable=False),
        sa.Column("selected_tool", sa.String(100)),
        sa.Column("selected_version", sa.String(40)),
        sa.Column("confidence", sa.String(20), nullable=False),
        sa.Column("outcome", sa.String(40), nullable=False),
        sa.Column("strategy_version", sa.String(40), nullable=False),
        sa.Column("embedding_model", sa.String(120)),
        sa.Column("duration_ms", sa.Float, nullable=False),
        sa.Column("correlation_id", sa.String(100), nullable=False),
        sa.Column("execution_id", sa.String(36)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_discovery_tenant_time",
        "tool_discovery_events",
        ["tenant_id", "created_at", "outcome"],
    )
    op.create_index(
        "ix_discovery_selected",
        "tool_discovery_events",
        ["tenant_id", "selected_tool", "created_at"],
    )
    op.create_index(
        "ix_discovery_correlation", "tool_discovery_events", ["correlation_id"]
    )
    op.create_table(
        "tool_candidate_decisions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("discovery_id", sa.String(36), nullable=False),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("tool_name", sa.String(100)),
        sa.Column("tool_version", sa.String(40)),
        sa.Column("eligible", sa.Boolean, nullable=False),
        sa.Column("exclusion_code", sa.String(80)),
        sa.Column("component_scores", sa.JSON, nullable=False),
        sa.Column("final_score", sa.Float, nullable=False),
        sa.Column("rank", sa.Integer),
        sa.Column("selected", sa.Boolean, nullable=False),
    )
    op.create_index(
        "ix_candidate_discovery_rank",
        "tool_candidate_decisions",
        ["discovery_id", "rank"],
    )
    op.create_table(
        "tool_discovery_feedback",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("discovery_id", sa.String(36), nullable=False),
        sa.Column("tenant_id", sa.String(120), nullable=False),
        sa.Column("actor_id", sa.String(160), nullable=False),
        sa.Column("feedback_type", sa.String(40), nullable=False),
        sa.Column("selected_tool", sa.String(100)),
        sa.Column("alternative_tool", sa.String(100)),
        sa.Column("safe_reason", sa.String(500), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_feedback_tenant_time",
        "tool_discovery_feedback",
        ["tenant_id", "created_at"],
    )


def downgrade():
    for table in [
        "tool_discovery_feedback",
        "tool_candidate_decisions",
        "tool_discovery_events",
        "tool_governance_policies",
        "tool_assignments",
        "tool_marketplace_profiles",
        "tool_search_index",
    ]:
        op.drop_table(table)
