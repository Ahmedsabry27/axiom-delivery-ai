from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


def _id():
    return str(uuid4())


def _now():
    return datetime.now(UTC)


class CeremonyTemplate(Base):
    __tablename__ = "ceremony_templates"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    tenant_id: Mapped[str] = mapped_column(String(120), nullable=False)
    family_key: Mapped[str] = mapped_column(String(120), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    ceremony_type: Mapped[str] = mapped_column(String(60), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    purpose: Mapped[str] = mapped_column(Text, default="", nullable=False)
    required_roles: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    recommended_timebox_minutes: Mapped[int | None] = mapped_column(Integer)
    items: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    required_evidence: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    expected_decisions: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    expected_outputs: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    scoring_config: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    template_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    effective_date: Mapped[date | None] = mapped_column(Date)
    owner_id: Mapped[str | None] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(30), default="DRAFT", nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint(
            "tenant_id",
            "family_key",
            "template_version",
            name="uq_ceremony_template_version",
        ),
        Index(
            "ix_ceremony_template_type_status", "tenant_id", "ceremony_type", "status"
        ),
    )


class Ceremony(Base):
    __tablename__ = "ceremonies"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    tenant_id: Mapped[str] = mapped_column(String(120), nullable=False)
    meeting_id: Mapped[str | None] = mapped_column(String(36))
    template_id: Mapped[str] = mapped_column(String(36), nullable=False)
    template_version: Mapped[int] = mapped_column(Integer, nullable=False)
    template_snapshot: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    ceremony_type: Mapped[str] = mapped_column(String(60), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="PLANNED", nullable=False)
    team_id: Mapped[str | None] = mapped_column(String(36))
    programme_id: Mapped[str | None] = mapped_column(String(36))
    project_id: Mapped[str | None] = mapped_column(String(36))
    scheduled_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    facilitator_id: Mapped[str | None] = mapped_column(String(160))
    purpose: Mapped[str] = mapped_column(Text, default="", nullable=False)
    agenda: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    score_snapshot: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    analysis_findings: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    themes: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        ForeignKeyConstraint(
            ["tenant_id", "meeting_id"],
            ["meetings.tenant_id", "meetings.id"],
            ondelete="SET NULL",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "template_id"],
            ["ceremony_templates.tenant_id", "ceremony_templates.id"],
            ondelete="RESTRICT",
        ),
        Index(
            "ix_ceremony_scope_status",
            "tenant_id",
            "ceremony_type",
            "scheduled_start",
            "status",
        ),
    )


class CeremonyChecklistResponse(Base):
    __tablename__ = "ceremony_checklist_responses"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    tenant_id: Mapped[str] = mapped_column(String(120), nullable=False)
    ceremony_id: Mapped[str] = mapped_column(String(36), nullable=False)
    item_key: Mapped[str] = mapped_column(String(160), nullable=False)
    section: Mapped[str] = mapped_column(String(20), nullable=False)
    label: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    weight: Mapped[float] = mapped_column(Float, default=1, nullable=False)
    evidence_required: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    responsible_role: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(
        String(30), default="NOT_STARTED", nullable=False
    )
    comment: Mapped[str | None] = mapped_column(Text)
    evidence_refs: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    completed_by: Mapped[str | None] = mapped_column(String(160))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    applicability_reason: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(30), default="TEMPLATE", nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint(
            "tenant_id", "ceremony_id", "item_key", name="uq_ceremony_checklist_item"
        ),
        ForeignKeyConstraint(
            ["tenant_id", "ceremony_id"],
            ["ceremonies.tenant_id", "ceremonies.id"],
            ondelete="CASCADE",
        ),
        Index("ix_ceremony_checklist_status", "tenant_id", "ceremony_id", "status"),
    )


class Lesson(Base):
    __tablename__ = "ceremony_lessons"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    tenant_id: Mapped[str] = mapped_column(String(120), nullable=False)
    ceremony_id: Mapped[str | None] = mapped_column(String(36))
    meeting_id: Mapped[str | None] = mapped_column(String(36))
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    sentiment: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="DRAFT", nullable=False)
    context: Mapped[str] = mapped_column(Text, default="", nullable=False)
    expected_outcome: Mapped[str] = mapped_column(Text, default="", nullable=False)
    actual_outcome: Mapped[str] = mapped_column(Text, default="", nullable=False)
    root_cause: Mapped[str] = mapped_column(Text, default="", nullable=False)
    contributing_factors: Mapped[list] = mapped_column(
        JSON, default=list, nullable=False
    )
    recommendation: Mapped[str] = mapped_column(Text, default="", nullable=False)
    evidence_refs: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    affected_entities: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    applicability: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    owner_id: Mapped[str | None] = mapped_column(String(160))
    reviewer_id: Mapped[str | None] = mapped_column(String(160))
    review_date: Mapped[date | None] = mapped_column(Date)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        ForeignKeyConstraint(
            ["tenant_id", "ceremony_id"],
            ["ceremonies.tenant_id", "ceremonies.id"],
            ondelete="SET NULL",
        ),
        Index("ix_lesson_status_category", "tenant_id", "status", "category"),
    )


class LessonAdoption(Base):
    __tablename__ = "lesson_adoptions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    tenant_id: Mapped[str] = mapped_column(String(120), nullable=False)
    lesson_id: Mapped[str] = mapped_column(String(36), nullable=False)
    target_type: Mapped[str] = mapped_column(String(40), nullable=False)
    target_id: Mapped[str] = mapped_column(String(36), nullable=False)
    owner_id: Mapped[str | None] = mapped_column(String(160))
    status: Mapped[str] = mapped_column(String(30), default="PLANNED", nullable=False)
    success_measure: Mapped[str | None] = mapped_column(Text)
    verified_benefit: Mapped[str | None] = mapped_column(Text)
    evidence_refs: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint(
            "tenant_id",
            "lesson_id",
            "target_type",
            "target_id",
            name="uq_lesson_adoption_target",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "lesson_id"],
            ["ceremony_lessons.tenant_id", "ceremony_lessons.id"],
            ondelete="CASCADE",
        ),
        Index("ix_lesson_adoption_status", "tenant_id", "status"),
    )
