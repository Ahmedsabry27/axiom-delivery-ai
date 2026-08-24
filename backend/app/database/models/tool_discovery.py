from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


def now():
    return datetime.now(UTC)


def uid():
    return str(uuid4())


class ToolSearchIndex(Base):
    __tablename__ = "tool_search_index"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "tool_name", "tool_version", name="uq_tool_search_version"
        ),
        Index("ix_tool_search_eligibility", "tenant_id", "index_status", "tool_name"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True)
    tool_name: Mapped[str] = mapped_column(String(100), index=True)
    tool_version: Mapped[str] = mapped_column(String(40))
    search_document: Mapped[str] = mapped_column(Text)
    content_fingerprint: Mapped[str] = mapped_column(String(64), index=True)
    embedding: Mapped[list] = mapped_column(JSON, default=list)
    embedding_model: Mapped[str] = mapped_column(String(120))
    embedding_dimensions: Mapped[int] = mapped_column(Integer)
    index_version: Mapped[str] = mapped_column(String(40))
    index_status: Mapped[str] = mapped_column(String(30), default="ready")
    safe_error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    indexed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ToolMarketplaceProfile(Base):
    __tablename__ = "tool_marketplace_profiles"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "tool_name", "tool_version", name="uq_marketplace_tool"
        ),
        Index("ix_marketplace_catalog", "tenant_id", "status", "source"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True)
    tool_name: Mapped[str] = mapped_column(String(100), index=True)
    tool_version: Mapped[str] = mapped_column(String(40))
    source: Mapped[str] = mapped_column(String(30), default="sdk")
    status: Mapped[str] = mapped_column(String(30), default="enabled")
    health_status: Mapped[str] = mapped_column(String(30), default="healthy")
    environment: Mapped[str] = mapped_column(String(40), default="all")
    data_classifications: Mapped[list] = mapped_column(
        JSON, default=lambda: ["public", "internal"]
    )
    approval_policy: Mapped[str] = mapped_column(String(40), default="none")
    estimated_cost: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String(8), default="USD")
    agent_allowlist: Mapped[list] = mapped_column(JSON, default=list)
    safe_metadata: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_by: Mapped[str] = mapped_column(String(160), default="system")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, onupdate=now
    )


class ToolAssignment(Base):
    __tablename__ = "tool_assignments"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "tool_name",
            "tool_version",
            "subject_type",
            "subject_id",
            "action",
            name="uq_tool_assignment_subject_action",
        ),
        Index(
            "ix_tool_assignment_lookup",
            "tenant_id",
            "tool_name",
            "subject_type",
            "subject_id",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True)
    tool_name: Mapped[str] = mapped_column(String(100), index=True)
    tool_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    subject_type: Mapped[str] = mapped_column(String(30))
    subject_id: Mapped[str] = mapped_column(String(160))
    action: Mapped[str] = mapped_column(String(40), default="execute")
    decision: Mapped[str] = mapped_column(String(30), default="allow")
    status: Mapped[str] = mapped_column(String(30), default="active")
    created_by: Mapped[str] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ToolGovernancePolicy(Base):
    __tablename__ = "tool_governance_policies"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "name", "version", name="uq_governance_policy_version"
        ),
        Index("ix_governance_active", "tenant_id", "lifecycle", "priority"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True)
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, default="")
    version: Mapped[int] = mapped_column(Integer, default=1)
    lifecycle: Mapped[str] = mapped_column(String(30), default="draft")
    conditions: Mapped[list] = mapped_column(JSON, default=list)
    actions: Mapped[dict] = mapped_column(JSON, default=dict)
    decision: Mapped[str] = mapped_column(String(30))
    priority: Mapped[int] = mapped_column(Integer, default=100)
    change_note: Mapped[str] = mapped_column(String(500), default="")
    created_by: Mapped[str] = mapped_column(String(160))
    updated_by: Mapped[str] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, onupdate=now
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class ToolDiscoveryEvent(Base):
    __tablename__ = "tool_discovery_events"
    __table_args__ = (
        Index("ix_discovery_tenant_time", "tenant_id", "created_at", "outcome"),
        Index("ix_discovery_selected", "tenant_id", "selected_tool", "created_at"),
        Index("ix_discovery_correlation", "correlation_id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(String(120), index=True)
    actor_id: Mapped[str] = mapped_column(String(160), index=True)
    agent_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    conversation_id: Mapped[str | None] = mapped_column(String(160), nullable=True)
    safe_intent: Mapped[dict] = mapped_column(JSON)
    candidate_count: Mapped[int] = mapped_column(Integer)
    eligible_count: Mapped[int] = mapped_column(Integer)
    selected_tool: Mapped[str | None] = mapped_column(String(100), nullable=True)
    selected_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    confidence: Mapped[str] = mapped_column(String(20))
    outcome: Mapped[str] = mapped_column(String(40), index=True)
    strategy_version: Mapped[str] = mapped_column(String(40))
    embedding_model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    duration_ms: Mapped[float] = mapped_column(Float)
    correlation_id: Mapped[str] = mapped_column(String(100))
    execution_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ToolCandidateDecision(Base):
    __tablename__ = "tool_candidate_decisions"
    __table_args__ = (Index("ix_candidate_discovery_rank", "discovery_id", "rank"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    discovery_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tool_discovery_events.id", ondelete="CASCADE"),
        index=True,
    )
    tenant_id: Mapped[str] = mapped_column(String(120), index=True)
    tool_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tool_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    eligible: Mapped[bool] = mapped_column(Boolean)
    exclusion_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    component_scores: Mapped[dict] = mapped_column(JSON, default=dict)
    final_score: Mapped[float] = mapped_column(Float, default=0)
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    selected: Mapped[bool] = mapped_column(Boolean, default=False)


class ToolDiscoveryFeedback(Base):
    __tablename__ = "tool_discovery_feedback"
    __table_args__ = (Index("ix_feedback_tenant_time", "tenant_id", "created_at"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    discovery_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tool_discovery_events.id", ondelete="CASCADE"),
        index=True,
    )
    tenant_id: Mapped[str] = mapped_column(String(120), index=True)
    actor_id: Mapped[str] = mapped_column(String(160))
    feedback_type: Mapped[str] = mapped_column(String(40))
    selected_tool: Mapped[str | None] = mapped_column(String(100), nullable=True)
    alternative_tool: Mapped[str | None] = mapped_column(String(100), nullable=True)
    safe_reason: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
