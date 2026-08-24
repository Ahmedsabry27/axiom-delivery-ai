from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.agents.application_service import AgentIdentity
from app.auth.dependencies import get_current_user
from app.database.dependencies import get_db
from app.database.models.meeting import (
    FindingEvidence,
    MeetingArtifact,
    MeetingTranscript,
    TranscriptSegment,
)
from app.meeting_intelligence.service import MeetingService

router = APIRouter(prefix="/api/meetings", tags=["Meeting Intelligence"])
Database = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[dict, Depends(get_current_user)]


class ParticipantInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: str | None = Field(default=None, max_length=160)
    display_name: str = Field(min_length=1, max_length=255)
    email: str | None = Field(default=None, max_length=320)
    role: str | None = Field(default=None, max_length=80)
    attendance_status: str = Field(default="UNKNOWN", max_length=30)
    source_identifier: str | None = Field(default=None, max_length=255)


class MeetingInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=255)
    meeting_type: str = Field(default="OTHER", max_length=50)
    description: str = Field(default="", max_length=5000)
    organizer_id: str | None = Field(default=None, max_length=160)
    scheduled_start: datetime | None = None
    scheduled_end: datetime | None = None
    timezone: str = Field(default="UTC", max_length=80)
    programme_id: str | None = Field(default=None, max_length=36)
    project_id: str | None = Field(default=None, max_length=36)
    team_id: str | None = Field(default=None, max_length=36)
    sprint_id: str | None = Field(default=None, max_length=36)
    release_id: str | None = Field(default=None, max_length=36)
    milestone_id: str | None = Field(default=None, max_length=36)
    trace_id: str | None = Field(default=None, max_length=80)
    participants: list[ParticipantInput] = Field(default_factory=list, max_length=200)


class MeetingUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    title: str | None = Field(default=None, min_length=1, max_length=255)
    meeting_type: str | None = Field(default=None, max_length=50)
    description: str | None = Field(default=None, max_length=5000)
    organizer_id: str | None = Field(default=None, max_length=160)
    scheduled_start: datetime | None = None
    scheduled_end: datetime | None = None
    timezone: str | None = Field(default=None, max_length=80)
    programme_id: str | None = Field(default=None, max_length=36)
    project_id: str | None = Field(default=None, max_length=36)
    team_id: str | None = Field(default=None, max_length=36)
    sprint_id: str | None = Field(default=None, max_length=36)
    release_id: str | None = Field(default=None, max_length=36)
    milestone_id: str | None = Field(default=None, max_length=36)


class ProposalInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    finding_ids: list[str] = Field(min_length=1, max_length=100)


class TranscriptInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_type: str = Field(default="TEXT", max_length=20)
    original_filename: str | None = Field(default=None, max_length=255)
    content_type: str = Field(default="text/plain", max_length=120)
    content: str = Field(min_length=1, max_length=250_000)
    language: str | None = Field(default=None, max_length=20)
    authorized_to_process: bool


class ReviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    title: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    suggested_owner_id: str | None = Field(default=None, max_length=160)
    due_date: date | None = None
    reason: str | None = Field(default=None, max_length=2000)
    merged_into_id: str | None = Field(default=None, max_length=36)


def _service(db: Session, user: dict) -> MeetingService:
    return MeetingService(db, AgentIdentity.from_claims(user))


def _meeting_item(service: MeetingService, row) -> dict[str, Any]:
    findings = service.findings(row.id)
    return {
        "id": row.id,
        "title": row.title,
        "meetingType": row.meeting_type,
        "status": row.status,
        "description": row.description,
        "organizerId": row.organizer_id,
        "scheduledStart": row.scheduled_start,
        "scheduledEnd": row.scheduled_end,
        "timezone": row.timezone,
        "programmeId": row.programme_id,
        "projectId": row.project_id,
        "teamId": row.team_id,
        "sprintId": row.sprint_id,
        "releaseId": row.release_id,
        "milestoneId": row.milestone_id,
        "version": row.version,
        "metadata": row.meeting_metadata,
        "createdAt": row.created_at,
        "updatedAt": row.updated_at,
        "findingCounts": {
            kind: sum(item.finding_type == kind for item in findings)
            for kind in (
                "DECISION",
                "ACTION",
                "RISK",
                "ISSUE",
                "DEPENDENCY",
                "OPEN_QUESTION",
            )
        },
        "needsReview": sum(item.review_status == "UNREVIEWED" for item in findings),
    }


def _finding_item(db: Session, row) -> dict[str, Any]:
    evidence = (
        db.query(FindingEvidence)
        .filter_by(tenant_id=row.tenant_id, finding_id=row.id)
        .all()
    )
    return {
        "id": row.id,
        "meetingId": row.meeting_id,
        "type": row.finding_type,
        "title": row.title,
        "description": row.description,
        "reviewStatus": row.review_status,
        "confidence": row.confidence,
        "suggestedOwnerId": row.suggested_owner_id,
        "dueDate": row.due_date,
        "priority": row.priority,
        "impact": row.impact,
        "proposalId": row.proposal_id,
        "version": row.version,
        "evidence": [
            {
                "segmentId": item.transcript_segment_id,
                "startOffset": item.start_offset,
                "endOffset": item.end_offset,
                "excerpt": item.evidence_excerpt,
            }
            for item in evidence
        ],
    }


@router.get("")
def list_meetings(
    db: Database,
    user: CurrentUser,
    status: str | None = None,
    search: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
):
    service = _service(db, user)
    rows = service.list(status, search)
    start = (page - 1) * page_size
    return {
        "items": [
            _meeting_item(service, row) for row in rows[start : start + page_size]
        ],
        "total": len(rows),
        "page": page,
    }


@router.post("", status_code=201)
def create_meeting(payload: MeetingInput, db: Database, user: CurrentUser):
    service = _service(db, user)
    return _meeting_item(service, service.create(payload.model_dump()))


@router.get("/{meeting_id}")
def get_meeting(meeting_id: str, db: Database, user: CurrentUser):
    service = _service(db, user)
    return _meeting_item(service, service.get(meeting_id))


@router.patch("/{meeting_id}")
def update_meeting(
    meeting_id: str, payload: MeetingUpdate, db: Database, user: CurrentUser
):
    service = _service(db, user)
    return _meeting_item(
        service, service.update(meeting_id, payload.model_dump(exclude_unset=True))
    )


@router.post("/{meeting_id}/transcript", status_code=201)
def add_transcript(
    meeting_id: str, payload: TranscriptInput, db: Database, user: CurrentUser
):
    if not payload.authorized_to_process:
        from fastapi import HTTPException

        raise HTTPException(
            422,
            {
                "code": "AUTHORIZATION_CONFIRMATION_REQUIRED",
                "message": "Confirm authorization before analysis",
            },
        )
    row = _service(db, user).add_transcript(
        meeting_id, payload.model_dump(exclude={"authorized_to_process"})
    )
    return {
        "id": row.id,
        "meetingId": row.meeting_id,
        "sourceType": row.source_type,
        "characterCount": row.character_count,
        "contentHash": row.content_hash,
    }


@router.get("/{meeting_id}/transcript")
def get_transcript(meeting_id: str, db: Database, user: CurrentUser):
    service = _service(db, user)
    meeting = service.get(meeting_id)
    row = (
        db.query(MeetingTranscript)
        .filter_by(tenant_id=service.identity.tenant_id, meeting_id=meeting.id)
        .order_by(MeetingTranscript.created_at.desc())
        .first()
    )
    if row is None:
        return {"transcript": None, "segments": []}
    segments = (
        db.query(TranscriptSegment)
        .filter_by(tenant_id=service.identity.tenant_id, transcript_id=row.id)
        .order_by(TranscriptSegment.sequence)
        .all()
    )
    return {
        "transcript": {
            "id": row.id,
            "sourceType": row.source_type,
            "characterCount": row.character_count,
        },
        "segments": [
            {
                "id": item.id,
                "sequence": item.sequence,
                "speaker": item.speaker,
                "startTime": item.start_time,
                "endTime": item.end_time,
                "text": item.text,
            }
            for item in segments
        ],
    }


@router.post("/{meeting_id}/analyse")
def analyse(meeting_id: str, db: Database, user: CurrentUser):
    service = _service(db, user)
    return _meeting_item(service, service.analyse(meeting_id))


@router.post("/{meeting_id}/cancel-analysis")
def cancel_analysis(meeting_id: str, db: Database, user: CurrentUser):
    service = _service(db, user)
    return _meeting_item(service, service.cancel_analysis(meeting_id))


@router.get("/{meeting_id}/findings")
def findings(meeting_id: str, db: Database, user: CurrentUser):
    service = _service(db, user)
    return {"items": [_finding_item(db, row) for row in service.findings(meeting_id)]}


@router.get("/{meeting_id}/findings/{finding_id}")
def get_finding(meeting_id: str, finding_id: str, db: Database, user: CurrentUser):
    return _finding_item(db, _service(db, user).finding(meeting_id, finding_id))


@router.patch("/{meeting_id}/findings/{finding_id}")
def edit_finding(
    meeting_id: str,
    finding_id: str,
    payload: ReviewInput,
    db: Database,
    user: CurrentUser,
):
    row = _service(db, user).review(
        meeting_id, finding_id, "EDITED", payload.model_dump()
    )
    return _finding_item(db, row)


def _review_finding(
    meeting_id: str,
    finding_id: str,
    decision: str,
    payload: ReviewInput,
    db: Database,
    user: CurrentUser,
):
    row = _service(db, user).review(
        meeting_id, finding_id, decision, payload.model_dump()
    )
    return _finding_item(db, row)


@router.post("/{meeting_id}/findings/{finding_id}/accept")
def accept_finding(
    meeting_id: str,
    finding_id: str,
    payload: ReviewInput,
    db: Database,
    user: CurrentUser,
):
    return _review_finding(meeting_id, finding_id, "ACCEPTED", payload, db, user)


@router.post("/{meeting_id}/findings/{finding_id}/reject")
def reject_finding(
    meeting_id: str,
    finding_id: str,
    payload: ReviewInput,
    db: Database,
    user: CurrentUser,
):
    return _review_finding(meeting_id, finding_id, "REJECTED", payload, db, user)


@router.post("/{meeting_id}/findings/{finding_id}/merge")
def merge_finding(
    meeting_id: str,
    finding_id: str,
    payload: ReviewInput,
    db: Database,
    user: CurrentUser,
):
    return _review_finding(meeting_id, finding_id, "MERGED", payload, db, user)


@router.post("/{meeting_id}/findings/{finding_id}/proposal")
def create_proposal(meeting_id: str, finding_id: str, db: Database, user: CurrentUser):
    row = _service(db, user).create_proposal(meeting_id, finding_id)
    return _finding_item(db, row)


@router.post("/{meeting_id}/proposals")
def create_proposals(
    meeting_id: str, payload: ProposalInput, db: Database, user: CurrentUser
):
    service = _service(db, user)
    return {
        "items": [
            _finding_item(db, service.create_proposal(meeting_id, finding_id))
            for finding_id in payload.finding_ids
        ]
    }


@router.post("/{meeting_id}/complete-review")
def complete_review(meeting_id: str, db: Database, user: CurrentUser):
    service = _service(db, user)
    return _meeting_item(service, service.complete_review(meeting_id))


@router.post("/{meeting_id}/archive")
def archive_meeting(meeting_id: str, db: Database, user: CurrentUser):
    service = _service(db, user)
    return _meeting_item(service, service.archive(meeting_id))


def _artifact_item(row: MeetingArtifact | None):
    return (
        None
        if row is None
        else {
            "id": row.id,
            "type": row.artifact_type,
            "content": row.content,
            "version": row.version,
            "reviewState": row.review_state,
            "generatedAt": row.generated_at,
        }
    )


@router.get("/{meeting_id}/minutes")
def get_minutes(meeting_id: str, db: Database, user: CurrentUser):
    return _artifact_item(_service(db, user).artifact(meeting_id, "MEETING_MINUTES"))


@router.post("/{meeting_id}/minutes")
def generate_minutes(meeting_id: str, db: Database, user: CurrentUser):
    return _artifact_item(
        _service(db, user).artifact(meeting_id, "MEETING_MINUTES", True)
    )


@router.get("/{meeting_id}/executive-summary")
def get_summary(meeting_id: str, db: Database, user: CurrentUser):
    return _artifact_item(_service(db, user).artifact(meeting_id, "EXECUTIVE_SUMMARY"))


@router.post("/{meeting_id}/executive-summary")
def generate_summary(meeting_id: str, db: Database, user: CurrentUser):
    return _artifact_item(
        _service(db, user).artifact(meeting_id, "EXECUTIVE_SUMMARY", True)
    )
