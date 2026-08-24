from __future__ import annotations

from datetime import UTC, date, datetime
from uuid import uuid4

from sqlalchemy import (
    JSON,
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


def _id() -> str:
    return str(uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


class Meeting(Base):
    __tablename__ = "meetings"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    tenant_id: Mapped[str] = mapped_column(String(120), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    meeting_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="OTHER"
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="DRAFT")
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    organizer_id: Mapped[str | None] = mapped_column(String(160))
    scheduled_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    scheduled_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    timezone: Mapped[str] = mapped_column(String(80), nullable=False, default="UTC")
    programme_id: Mapped[str | None] = mapped_column(String(36))
    project_id: Mapped[str | None] = mapped_column(String(36))
    team_id: Mapped[str | None] = mapped_column(String(36))
    sprint_id: Mapped[str | None] = mapped_column(String(36))
    release_id: Mapped[str | None] = mapped_column(String(36))
    milestone_id: Mapped[str | None] = mapped_column(String(36))
    source_system: Mapped[str] = mapped_column(
        String(50), nullable=False, default="MANUAL"
    )
    external_id: Mapped[str | None] = mapped_column(String(255))
    created_by: Mapped[str] = mapped_column(String(160), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )
    analysis_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    analysis_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    review_completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    meeting_metadata: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        Index("ix_meeting_tenant_status", "tenant_id", "status", "updated_at"),
    )


class MeetingParticipant(Base):
    __tablename__ = "meeting_participants"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    tenant_id: Mapped[str] = mapped_column(String(120), nullable=False)
    meeting_id: Mapped[str] = mapped_column(String(36), nullable=False)
    user_id: Mapped[str | None] = mapped_column(String(160))
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320))
    role: Mapped[str | None] = mapped_column(String(80))
    attendance_status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="UNKNOWN"
    )
    source_identifier: Mapped[str | None] = mapped_column(String(255))
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        ForeignKeyConstraint(
            ["tenant_id", "meeting_id"],
            ["meetings.tenant_id", "meetings.id"],
            ondelete="CASCADE",
        ),
        Index("ix_meeting_participant_meeting", "tenant_id", "meeting_id"),
    )


class MeetingTranscript(Base):
    __tablename__ = "meeting_transcripts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    tenant_id: Mapped[str] = mapped_column(String(120), nullable=False)
    meeting_id: Mapped[str] = mapped_column(String(36), nullable=False)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)
    original_filename: Mapped[str | None] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(
        String(120), nullable=False, default="text/plain"
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    character_count: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    language: Mapped[str | None] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
    created_by: Mapped[str] = mapped_column(String(160), nullable=False)
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint(
            "tenant_id",
            "meeting_id",
            "content_hash",
            name="uq_meeting_transcript_content",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "meeting_id"],
            ["meetings.tenant_id", "meetings.id"],
            ondelete="CASCADE",
        ),
    )


class TranscriptSegment(Base):
    __tablename__ = "meeting_transcript_segments"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String(120), nullable=False)
    transcript_id: Mapped[str] = mapped_column(String(36), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    speaker: Mapped[str] = mapped_column(
        String(255), nullable=False, default="Unknown speaker"
    )
    start_time: Mapped[str | None] = mapped_column(String(30))
    end_time: Mapped[str | None] = mapped_column(String(30))
    start_offset: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    end_offset: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        UniqueConstraint("tenant_id", "transcript_id", "sequence"),
        ForeignKeyConstraint(
            ["tenant_id", "transcript_id"],
            ["meeting_transcripts.tenant_id", "meeting_transcripts.id"],
            ondelete="CASCADE",
        ),
        Index("ix_transcript_segment_order", "tenant_id", "transcript_id", "sequence"),
    )


class MeetingFinding(Base):
    __tablename__ = "meeting_findings"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    tenant_id: Mapped[str] = mapped_column(String(120), nullable=False)
    meeting_id: Mapped[str] = mapped_column(String(36), nullable=False)
    finding_type: Mapped[str] = mapped_column(String(30), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    original_output: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    review_status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="UNREVIEWED"
    )
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    suggested_owner_id: Mapped[str | None] = mapped_column(String(160))
    due_date: Mapped[date | None] = mapped_column(Date)
    priority: Mapped[str | None] = mapped_column(String(20))
    impact: Mapped[str | None] = mapped_column(String(20))
    probability: Mapped[str | None] = mapped_column(String(20))
    severity: Mapped[str | None] = mapped_column(String(20))
    source_agent: Mapped[str] = mapped_column(String(120), nullable=False)
    model: Mapped[str | None] = mapped_column(String(200))
    prompt_version: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )
    reviewed_by: Mapped[str | None] = mapped_column(String(160))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rejection_reason: Mapped[str | None] = mapped_column(Text)
    merged_into_id: Mapped[str | None] = mapped_column(String(36))
    proposal_id: Mapped[str | None] = mapped_column(String(36))
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    __table_args__ = (
        UniqueConstraint("tenant_id", "id"),
        ForeignKeyConstraint(
            ["tenant_id", "meeting_id"],
            ["meetings.tenant_id", "meetings.id"],
            ondelete="CASCADE",
        ),
        Index("ix_meeting_finding_review", "tenant_id", "meeting_id", "review_status"),
    )


class FindingEvidence(Base):
    __tablename__ = "meeting_finding_evidence"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    tenant_id: Mapped[str] = mapped_column(String(120), nullable=False)
    finding_id: Mapped[str] = mapped_column(String(36), nullable=False)
    transcript_segment_id: Mapped[str] = mapped_column(String(64), nullable=False)
    start_offset: Mapped[int | None] = mapped_column(Integer)
    end_offset: Mapped[int | None] = mapped_column(Integer)
    evidence_excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    __table_args__ = (
        UniqueConstraint("tenant_id", "finding_id", "transcript_segment_id"),
        ForeignKeyConstraint(
            ["tenant_id", "finding_id"],
            ["meeting_findings.tenant_id", "meeting_findings.id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["tenant_id", "transcript_segment_id"],
            ["meeting_transcript_segments.tenant_id", "meeting_transcript_segments.id"],
            ondelete="RESTRICT",
        ),
    )


class MeetingArtifact(Base):
    __tablename__ = "meeting_artifacts"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_id)
    tenant_id: Mapped[str] = mapped_column(String(120), nullable=False)
    meeting_id: Mapped[str] = mapped_column(String(36), nullable=False)
    artifact_type: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    review_state: Mapped[str] = mapped_column(
        String(30), nullable=False, default="DRAFT"
    )
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    evidence_references: Mapped[list] = mapped_column(
        JSON, nullable=False, default=list
    )
    source_finding_versions: Mapped[dict] = mapped_column(
        JSON, nullable=False, default=dict
    )
    __table_args__ = (
        UniqueConstraint("tenant_id", "meeting_id", "artifact_type", "version"),
        ForeignKeyConstraint(
            ["tenant_id", "meeting_id"],
            ["meetings.tenant_id", "meetings.id"],
            ondelete="CASCADE",
        ),
    )
