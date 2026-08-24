from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


def uid():
    return str(uuid4())


def now():
    return datetime.now(UTC)


class KnowledgeItem(Base):
    __tablename__ = "knowledge_items"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(String(120), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    item_type: Mapped[str] = mapped_column(String(60), nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    content: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="DRAFT", nullable=False)
    trust_status: Mapped[str] = mapped_column(
        String(30), default="UNVERIFIED", nullable=False
    )
    freshness_status: Mapped[str] = mapped_column(
        String(30), default="UNKNOWN", nullable=False
    )
    access_classification: Mapped[str] = mapped_column(
        String(30), default="INTERNAL", nullable=False
    )
    source_system: Mapped[str] = mapped_column(
        String(60), default="AXIOM", nullable=False
    )
    source_record_id: Mapped[str | None] = mapped_column(String(255))
    source_url: Mapped[str | None] = mapped_column(String(1000))
    owner_id: Mapped[str] = mapped_column(String(160), nullable=False)
    reviewers: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    tags: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    context: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    content_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    current_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    evidence_coverage: Mapped[int | None] = mapped_column(Integer)
    last_synchronized_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_review_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[str] = mapped_column(String(160), nullable=False)
    updated_by: Mapped[str] = mapped_column(String(160), nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, onupdate=now, nullable=False
    )
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        Index(
            "ix_knowledge_item_search", "tenant_id", "status", "item_type", "updated_at"
        ),
    )


class KnowledgeItemVersion(Base):
    __tablename__ = "knowledge_item_versions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(String(120), nullable=False)
    item_id: Mapped[str] = mapped_column(String(36), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    change_summary: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    author_id: Mapped[str] = mapped_column(String(160), nullable=False)
    review_status: Mapped[str] = mapped_column(String(30), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, nullable=False
    )
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "item_id"],
            ["knowledge_items.tenant_id", "knowledge_items.id"],
            ondelete="CASCADE",
        ),
        UniqueConstraint("tenant_id", "item_id", "version_number"),
    )


class KnowledgeRelationship(Base):
    __tablename__ = "knowledge_relationships"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(String(120), nullable=False)
    item_id: Mapped[str] = mapped_column(String(36), nullable=False)
    related_type: Mapped[str] = mapped_column(String(50), nullable=False)
    related_id: Mapped[str] = mapped_column(String(160), nullable=False)
    relationship_type: Mapped[str] = mapped_column(String(50), nullable=False)
    label: Mapped[str] = mapped_column(String(500), default="", nullable=False)
    created_by: Mapped[str] = mapped_column(String(160), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, nullable=False
    )
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "item_id"],
            ["knowledge_items.tenant_id", "knowledge_items.id"],
            ondelete="CASCADE",
        ),
        UniqueConstraint(
            "tenant_id", "item_id", "related_type", "related_id", "relationship_type"
        ),
    )


class KnowledgeEvidenceReference(Base):
    __tablename__ = "knowledge_evidence_references"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(String(120), nullable=False)
    item_id: Mapped[str] = mapped_column(String(36), nullable=False)
    evidence_id: Mapped[str] = mapped_column(String(36), nullable=False)
    claim: Mapped[str] = mapped_column(Text, default="", nullable=False)
    strength: Mapped[str] = mapped_column(String(20), default="MEDIUM", nullable=False)
    immutable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, nullable=False
    )
    __table_args__ = (
        ForeignKeyConstraint(
            ["tenant_id", "item_id"],
            ["knowledge_items.tenant_id", "knowledge_items.id"],
            ondelete="CASCADE",
        ),
        UniqueConstraint("tenant_id", "item_id", "evidence_id"),
    )


class KnowledgeDecision(Base):
    __tablename__ = "knowledge_decisions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(String(120), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, default="", nullable=False)
    selected_option: Mapped[str] = mapped_column(Text, default="", nullable=False)
    options: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="DRAFT", nullable=False)
    owner_id: Mapped[str] = mapped_column(String(160), nullable=False)
    context: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    evidence_ids: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    approval_id: Mapped[str | None] = mapped_column(String(36))
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, onupdate=now, nullable=False
    )
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        Index("ix_knowledge_decision_status", "tenant_id", "status", "updated_at"),
    )


class KnowledgeTemplate(Base):
    __tablename__ = "knowledge_templates"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    tenant_id: Mapped[str] = mapped_column(String(120), nullable=False)
    family_key: Mapped[str] = mapped_column(String(120), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    template_type: Mapped[str] = mapped_column(String(60), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    schema: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    template_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="DRAFT", nullable=False)
    owner_id: Mapped[str] = mapped_column(String(160), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=now, nullable=False
    )
    __table_args__ = (UniqueConstraint("tenant_id", "family_key", "template_version"),)
