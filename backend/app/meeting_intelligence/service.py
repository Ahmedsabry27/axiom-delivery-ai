from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import PurePath
from uuid import NAMESPACE_URL, uuid5

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.action_center.service import ActionCenterService
from app.agents.application_service import AgentIdentity
from app.audit.events import append_audit_event
from app.database.models.delivery import DeliveryEvidence
from app.database.models.meeting import (
    FindingEvidence,
    Meeting,
    MeetingArtifact,
    MeetingFinding,
    MeetingParticipant,
    MeetingTranscript,
    TranscriptSegment,
)

MAX_TRANSCRIPT_CHARACTERS = 250_000
SUPPORTED_SOURCE_TYPES = {"TEXT", "MARKDOWN", "VTT", "SRT", "NOTES"}
FINDING_TYPES = {"DECISION", "ACTION", "RISK", "ISSUE", "DEPENDENCY", "OPEN_QUESTION"}
TRANSITIONS = {
    "DRAFT": {"QUEUED", "ARCHIVED", "CANCELLED"},
    "QUEUED": {"PROCESSING", "CANCELLED", "FAILED"},
    "PROCESSING": {"EXTRACTED", "FAILED", "CANCELLED"},
    "EXTRACTED": {"NEEDS_REVIEW"},
    "NEEDS_REVIEW": {"PARTIALLY_REVIEWED", "REVIEWED", "ARCHIVED"},
    "PARTIALLY_REVIEWED": {"REVIEWED", "ARCHIVED"},
    "REVIEWED": {"COMPLETED", "ARCHIVED"},
    "COMPLETED": {"ARCHIVED"},
    "FAILED": {"QUEUED", "ARCHIVED"},
    "CANCELLED": {"QUEUED", "ARCHIVED"},
    "ARCHIVED": set(),
}


def _error(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status, {"code": code, "message": message})


@dataclass(frozen=True)
class ParsedSegment:
    sequence: int
    speaker: str
    text: str
    start_time: str | None = None
    end_time: str | None = None


class TranscriptParserService:
    _timestamp = re.compile(
        r"(?P<start>\d{1,2}:\d{2}(?::\d{2})?[,.]\d{3})\s+-->\s+(?P<end>\d{1,2}:\d{2}(?::\d{2})?[,.]\d{3})"
    )
    _speaker = re.compile(r"^(?P<speaker>[\w .'-]{1,80}):\s+(?P<text>.+)$")

    @classmethod
    def parse(cls, content: str, source_type: str) -> list[ParsedSegment]:
        source_type = source_type.upper()
        if source_type not in SUPPORTED_SOURCE_TYPES:
            raise _error(
                415, "UNSUPPORTED_TRANSCRIPT_TYPE", "Unsupported transcript type"
            )
        clean = content.replace("\x00", "").strip()
        if not clean:
            raise _error(422, "EMPTY_TRANSCRIPT", "Transcript content is required")
        if len(clean) > MAX_TRANSCRIPT_CHARACTERS:
            raise _error(
                413, "TRANSCRIPT_TOO_LARGE", "Transcript exceeds the character limit"
            )
        if source_type in {"VTT", "SRT"}:
            return cls._parse_captions(clean)
        result = []
        for line in (item.strip() for item in clean.splitlines()):
            if not line or line.startswith("#"):
                continue
            match = cls._speaker.match(line)
            result.append(
                ParsedSegment(
                    sequence=len(result) + 1,
                    speaker=match.group("speaker") if match else "Unknown speaker",
                    text=match.group("text") if match else line,
                )
            )
        if not result:
            raise _error(422, "EMPTY_TRANSCRIPT", "Transcript has no readable segments")
        return result

    @classmethod
    def _parse_captions(cls, content: str) -> list[ParsedSegment]:
        lines = [line.strip() for line in content.splitlines()]
        result: list[ParsedSegment] = []
        index = 0
        while index < len(lines):
            match = cls._timestamp.match(lines[index])
            if not match:
                index += 1
                continue
            index += 1
            text_lines = []
            while index < len(lines) and lines[index]:
                text_lines.append(lines[index])
                index += 1
            text = " ".join(text_lines).strip()
            if text:
                speaker_match = cls._speaker.match(text)
                result.append(
                    ParsedSegment(
                        sequence=len(result) + 1,
                        speaker=speaker_match.group("speaker")
                        if speaker_match
                        else "Unknown speaker",
                        text=speaker_match.group("text") if speaker_match else text,
                        start_time=match.group("start").replace(",", "."),
                        end_time=match.group("end").replace(",", "."),
                    )
                )
        if not result:
            raise _error(
                422, "MALFORMED_TRANSCRIPT", "No valid caption segments were found"
            )
        return result


class MeetingService:
    def __init__(self, db: Session, identity: AgentIdentity):
        self.db = db
        self.identity = identity

    def _require(self, permission: str) -> None:
        if not self.identity.allows(permission):
            raise _error(
                403, "PERMISSION_DENIED", f"{permission} permission is required"
            )

    def get(self, meeting_id: str) -> Meeting:
        self._require("meetings.read")
        row = (
            self.db.query(Meeting)
            .filter_by(id=meeting_id, tenant_id=self.identity.tenant_id)
            .first()
        )
        if row is None:
            raise _error(404, "MEETING_NOT_FOUND", "Meeting was not found")
        return row

    def _audit(
        self, action: str, meeting: Meeting, metadata: dict | None = None
    ) -> None:
        append_audit_event(
            self.db,
            tenant_id=self.identity.tenant_id,
            actor_id=self.identity.actor_id,
            action=action,
            target_type="meeting",
            target_id=meeting.id,
            correlation_id=str(
                (meeting.meeting_metadata or {}).get("trace_id") or meeting.id
            ),
            metadata=metadata or {},
        )

    def create(self, values: dict) -> Meeting:
        self._require("meetings.create")
        meeting = Meeting(
            tenant_id=self.identity.tenant_id,
            title=values["title"],
            meeting_type=values.get("meeting_type", "OTHER").upper(),
            description=values.get("description", ""),
            organizer_id=values.get("organizer_id") or self.identity.actor_id,
            scheduled_start=values.get("scheduled_start"),
            scheduled_end=values.get("scheduled_end"),
            timezone=values.get("timezone", "UTC"),
            programme_id=values.get("programme_id"),
            project_id=values.get("project_id"),
            team_id=values.get("team_id"),
            sprint_id=values.get("sprint_id"),
            release_id=values.get("release_id"),
            milestone_id=values.get("milestone_id"),
            created_by=self.identity.actor_id,
            meeting_metadata={
                "trace_id": values.get("trace_id")
                or str(
                    uuid5(
                        NAMESPACE_URL,
                        f"meeting:{self.identity.tenant_id}:{values['title']}:{datetime.now(UTC).isoformat()}",
                    )
                )
            },
        )
        self.db.add(meeting)
        self.db.flush()
        for item in values.get("participants", []):
            self.db.add(
                MeetingParticipant(
                    tenant_id=self.identity.tenant_id, meeting_id=meeting.id, **item
                )
            )
        self._audit("meeting.created", meeting)
        self.db.commit()
        self.db.refresh(meeting)
        return meeting

    def list(
        self, status: str | None = None, search: str | None = None
    ) -> list[Meeting]:
        self._require("meetings.read")
        query = self.db.query(Meeting).filter_by(tenant_id=self.identity.tenant_id)
        if status:
            query = query.filter(Meeting.status == status.upper())
        if search:
            query = query.filter(Meeting.title.ilike(f"%{search[:100]}%"))
        return query.order_by(Meeting.updated_at.desc()).all()

    def update(self, meeting_id: str, values: dict) -> Meeting:
        self._require("meetings.create")
        meeting = self.get(meeting_id)
        expected_version = values.pop("expected_version")
        if meeting.version != expected_version:
            raise _error(
                409, "STALE_MEETING_VERSION", "Meeting changed; reload before editing"
            )
        if meeting.status == "ARCHIVED":
            raise _error(409, "MEETING_ARCHIVED", "Archived meetings cannot be edited")
        for key in (
            "title",
            "meeting_type",
            "description",
            "organizer_id",
            "scheduled_start",
            "scheduled_end",
            "timezone",
            "programme_id",
            "project_id",
            "team_id",
            "sprint_id",
            "release_id",
            "milestone_id",
        ):
            if key in values and values[key] is not None:
                setattr(
                    meeting,
                    key,
                    values[key].upper() if key == "meeting_type" else values[key],
                )
        meeting.version += 1
        self._audit("meeting.updated", meeting)
        self.db.commit()
        self.db.refresh(meeting)
        return meeting

    def _transition(self, meeting: Meeting, target: str, action: str) -> Meeting:
        target = target.upper()
        if target not in TRANSITIONS.get(meeting.status, set()):
            raise _error(
                409,
                "INVALID_MEETING_TRANSITION",
                f"Cannot transition {meeting.status} to {target}",
            )
        meeting.status = target
        meeting.version += 1
        now = datetime.now(UTC)
        if target == "ARCHIVED":
            meeting.archived_at = now
        elif target == "COMPLETED":
            meeting.review_completed_at = now
        self._audit(action, meeting, {"status": target})
        self.db.commit()
        self.db.refresh(meeting)
        return meeting

    def cancel_analysis(self, meeting_id: str) -> Meeting:
        self._require("meetings.analyse")
        return self._transition(
            self.get(meeting_id), "CANCELLED", "meeting.analysis.cancelled"
        )

    def complete_review(self, meeting_id: str) -> Meeting:
        self._require("meetings.review")
        meeting = self.get(meeting_id)
        mandatory = (
            self.db.query(MeetingFinding)
            .filter(
                MeetingFinding.tenant_id == self.identity.tenant_id,
                MeetingFinding.meeting_id == meeting.id,
                MeetingFinding.review_status == "UNREVIEWED",
                MeetingFinding.priority == "HIGH",
            )
            .count()
        )
        if mandatory:
            raise _error(
                409,
                "MANDATORY_FINDINGS_UNREVIEWED",
                "Review high-impact findings before completion",
            )
        if meeting.status == "PARTIALLY_REVIEWED":
            meeting.status = "REVIEWED"
        return self._transition(meeting, "COMPLETED", "meeting.review.completed")

    def archive(self, meeting_id: str) -> Meeting:
        self._require("meetings.review")
        return self._transition(self.get(meeting_id), "ARCHIVED", "meeting.archived")

    def add_transcript(self, meeting_id: str, values: dict) -> MeetingTranscript:
        self._require("meetings.create")
        meeting = self.get(meeting_id)
        if meeting.status == "ARCHIVED":
            raise _error(
                409, "MEETING_ARCHIVED", "Archived meetings cannot receive transcripts"
            )
        filename = values.get("original_filename")
        if filename and (PurePath(filename).name != filename or ".." in filename):
            raise _error(422, "UNSAFE_FILENAME", "Transcript filename is not safe")
        content = values["content"].replace("\x00", "").strip()
        source_type = values.get("source_type", "TEXT").upper()
        parsed = TranscriptParserService.parse(content, source_type)
        digest = hashlib.sha256(content.encode()).hexdigest()
        duplicate = (
            self.db.query(MeetingTranscript)
            .filter_by(
                tenant_id=self.identity.tenant_id,
                meeting_id=meeting.id,
                content_hash=digest,
            )
            .first()
        )
        if duplicate:
            return duplicate
        transcript = MeetingTranscript(
            tenant_id=self.identity.tenant_id,
            meeting_id=meeting.id,
            source_type=source_type,
            original_filename=filename,
            content_type=values.get("content_type", "text/plain"),
            content=content,
            character_count=len(content),
            content_hash=digest,
            language=values.get("language"),
            created_by=self.identity.actor_id,
        )
        self.db.add(transcript)
        self.db.flush()
        cursor = 0
        for item in parsed:
            start = content.find(item.text, cursor)
            start = cursor if start < 0 else start
            end = start + len(item.text)
            segment_hash = hashlib.sha256(
                f"{digest}:{item.sequence}:{item.text}".encode()
            ).hexdigest()
            stable_id = str(
                uuid5(
                    NAMESPACE_URL,
                    f"meeting-segment:{self.identity.tenant_id}:{meeting.id}:{segment_hash}",
                )
            )
            self.db.add(
                TranscriptSegment(
                    id=stable_id,
                    tenant_id=self.identity.tenant_id,
                    transcript_id=transcript.id,
                    sequence=item.sequence,
                    speaker=item.speaker,
                    start_time=item.start_time,
                    end_time=item.end_time,
                    start_offset=start,
                    end_offset=end,
                    text=item.text,
                    content_hash=segment_hash,
                )
            )
            cursor = end
        self._audit(
            "meeting.transcript.uploaded",
            meeting,
            {"source_type": source_type, "character_count": len(content)},
        )
        self.db.commit()
        self.db.refresh(transcript)
        return transcript

    def analyse(self, meeting_id: str) -> Meeting:
        self._require("meetings.analyse")
        meeting = self.get(meeting_id)
        transcript = (
            self.db.query(MeetingTranscript)
            .filter_by(tenant_id=self.identity.tenant_id, meeting_id=meeting.id)
            .order_by(MeetingTranscript.created_at.desc())
            .first()
        )
        if transcript is None:
            raise _error(
                422, "TRANSCRIPT_REQUIRED", "Authorized transcript content is required"
            )
        existing = (
            self.db.query(MeetingFinding)
            .filter_by(tenant_id=self.identity.tenant_id, meeting_id=meeting.id)
            .count()
        )
        if existing:
            return meeting
        meeting.status = "PROCESSING"
        meeting.analysis_started_at = datetime.now(UTC)
        self._audit("meeting.analysis.started", meeting)
        segments = (
            self.db.query(TranscriptSegment)
            .filter_by(tenant_id=self.identity.tenant_id, transcript_id=transcript.id)
            .order_by(TranscriptSegment.sequence)
            .all()
        )
        for segment in segments:
            finding_type = self._classify(segment.text)
            if finding_type is None:
                continue
            title = segment.text[:120].rstrip(". ")
            finding = MeetingFinding(
                tenant_id=self.identity.tenant_id,
                meeting_id=meeting.id,
                finding_type=finding_type,
                title=title,
                description=segment.text,
                original_output={"title": title, "description": segment.text},
                confidence=0.85,
                priority="HIGH"
                if finding_type in {"RISK", "ISSUE", "DEPENDENCY"}
                else "MEDIUM",
                impact="HIGH" if finding_type in {"RISK", "ISSUE"} else None,
                source_agent="meeting-intelligence-agent",
                model="deterministic-grounded-extractor-v1",
                prompt_version="meeting-analysis-v1",
            )
            self.db.add(finding)
            self.db.flush()
            self.db.add(
                FindingEvidence(
                    tenant_id=self.identity.tenant_id,
                    finding_id=finding.id,
                    transcript_segment_id=segment.id,
                    start_offset=0,
                    end_offset=len(segment.text),
                    evidence_excerpt=segment.text,
                )
            )
        meeting.status = "NEEDS_REVIEW"
        meeting.analysis_completed_at = datetime.now(UTC)
        meeting.meeting_metadata = {
            **(meeting.meeting_metadata or {}),
            "summary": "Meeting analysis completed from grounded transcript segments.",
            "analysis_mode": "deterministic",
        }
        self.db.flush()
        self._audit(
            "meeting.analysis.completed",
            meeting,
            {
                "finding_count": self.db.query(MeetingFinding)
                .filter_by(tenant_id=self.identity.tenant_id, meeting_id=meeting.id)
                .count()
            },
        )
        self.db.commit()
        self.db.refresh(meeting)
        return meeting

    @staticmethod
    def _classify(text: str) -> str | None:
        lowered = text.lower()
        rules = (
            ("DECISION", ("decided", "decision", "agreed")),
            ("ACTION", ("i will", "action:", "follow up", "owner:")),
            ("RISK", ("risk", "may delay", "threat")),
            ("ISSUE", ("issue", "blocked", "failure")),
            ("DEPENDENCY", ("depends on", "dependency", "waiting for")),
            ("OPEN_QUESTION", ("?", "open question")),
        )
        return next(
            (
                kind
                for kind, markers in rules
                if any(marker in lowered for marker in markers)
            ),
            None,
        )

    def findings(self, meeting_id: str) -> list[MeetingFinding]:
        meeting = self.get(meeting_id)
        return (
            self.db.query(MeetingFinding)
            .filter_by(tenant_id=self.identity.tenant_id, meeting_id=meeting.id)
            .order_by(MeetingFinding.created_at)
            .all()
        )

    def finding(self, meeting_id: str, finding_id: str) -> MeetingFinding:
        meeting = self.get(meeting_id)
        row = (
            self.db.query(MeetingFinding)
            .filter_by(
                id=finding_id,
                tenant_id=self.identity.tenant_id,
                meeting_id=meeting.id,
            )
            .first()
        )
        if row is None:
            raise _error(404, "FINDING_NOT_FOUND", "Meeting finding was not found")
        return row

    def review(
        self, meeting_id: str, finding_id: str, decision: str, values: dict
    ) -> MeetingFinding:
        self._require("meetings.review")
        meeting = self.get(meeting_id)
        finding = (
            self.db.query(MeetingFinding)
            .filter_by(
                id=finding_id, tenant_id=self.identity.tenant_id, meeting_id=meeting.id
            )
            .first()
        )
        if finding is None:
            raise _error(404, "FINDING_NOT_FOUND", "Meeting finding was not found")
        expected_version = values.get("expected_version", finding.version)
        if finding.version != expected_version:
            raise _error(
                409, "STALE_FINDING_VERSION", "Finding changed; reload before review"
            )
        decision = decision.upper()
        if (
            decision == "REJECTED"
            and finding.priority == "HIGH"
            and not values.get("reason", "").strip()
        ):
            raise _error(
                422,
                "REJECTION_REASON_REQUIRED",
                "High-impact rejection requires a reason",
            )
        if decision not in {"ACCEPTED", "EDITED", "REJECTED", "MERGED"}:
            raise _error(
                422, "INVALID_FINDING_TRANSITION", "Unsupported review decision"
            )
        if finding.review_status != "UNREVIEWED":
            raise _error(409, "FINDING_ALREADY_REVIEWED", "Finding is already reviewed")
        if decision == "EDITED":
            finding.title = values.get("title") or finding.title
            finding.description = values.get("description") or finding.description
            finding.suggested_owner_id = values.get("suggested_owner_id")
            finding.due_date = values.get("due_date")
        if decision == "MERGED":
            target = values.get("merged_into_id")
            if (
                not target
                or not self.db.query(MeetingFinding)
                .filter_by(
                    id=target, tenant_id=self.identity.tenant_id, meeting_id=meeting.id
                )
                .first()
            ):
                raise _error(
                    422,
                    "INVALID_MERGE_TARGET",
                    "Merge target must belong to this meeting",
                )
            finding.merged_into_id = target
        finding.review_status = decision
        finding.rejection_reason = (
            values.get("reason") if decision == "REJECTED" else None
        )
        finding.reviewed_by = self.identity.actor_id
        finding.reviewed_at = datetime.now(UTC)
        finding.version += 1
        self.db.flush()
        remaining = (
            self.db.query(func.count(MeetingFinding.id))
            .filter_by(
                tenant_id=self.identity.tenant_id,
                meeting_id=meeting.id,
                review_status="UNREVIEWED",
            )
            .scalar()
            or 0
        )
        meeting.status = "PARTIALLY_REVIEWED" if remaining else "REVIEWED"
        self._audit(
            "meeting.finding.reviewed",
            meeting,
            {"finding_id": finding.id, "decision": decision},
        )
        self.db.commit()
        self.db.refresh(finding)
        return finding

    def create_proposal(self, meeting_id: str, finding_id: str) -> MeetingFinding:
        self._require("meetings.propose")
        meeting = self.get(meeting_id)
        finding = (
            self.db.query(MeetingFinding)
            .filter_by(
                id=finding_id, tenant_id=self.identity.tenant_id, meeting_id=meeting.id
            )
            .first()
        )
        if finding is None:
            raise _error(404, "FINDING_NOT_FOUND", "Meeting finding was not found")
        if finding.review_status not in {"ACCEPTED", "EDITED"}:
            raise _error(
                409,
                "FINDING_NOT_ACCEPTED",
                "Only accepted findings can create proposals",
            )
        if finding.proposal_id:
            return finding
        action_type = {
            "RISK": "CREATE_RAID_ITEM",
            "ISSUE": "CREATE_RAID_ITEM",
            "DEPENDENCY": "CREATE_DEPENDENCY",
            "ACTION": "CREATE_DELIVERY_ACTION",
            "DECISION": "REQUEST_DECISION",
        }.get(finding.finding_type, "REQUEST_DECISION")
        evidence_links = (
            self.db.query(FindingEvidence)
            .filter_by(tenant_id=self.identity.tenant_id, finding_id=finding.id)
            .all()
        )
        delivery_evidence = DeliveryEvidence(
            tenant_id=self.identity.tenant_id,
            entity_type="MEETING_FINDING",
            entity_id=finding.id,
            source_type="MEETING_TRANSCRIPT",
            source_system="AXIOM_MEETING_INTELLIGENCE",
            source_record_id=f"meeting:{meeting.id}:finding:{finding.id}",
            title=f"Meeting evidence: {finding.title}"[:255],
            summary=" ".join(item.evidence_excerpt for item in evidence_links)[:2000],
            captured_at=datetime.now(UTC),
        )
        self.db.add(delivery_evidence)
        self.db.flush()
        action = ActionCenterService(self.db, self.identity).create(
            {
                "action_type": action_type,
                "title": finding.title,
                "description": finding.description,
                "origin": "AI",
                "target_entity_type": "MEETING",
                "target_entity_id": meeting.id,
                "target_system": "INTERNAL",
                "payload": {
                    "meeting_id": meeting.id,
                    "finding_id": finding.id,
                    "finding_type": finding.finding_type,
                },
                "evidence_ids": [delivery_evidence.id],
                "idempotency_key": f"meeting-finding-{finding.id}",
            }
        )
        finding.proposal_id = action.id
        finding.review_status = "PROPOSED"
        self._audit(
            "meeting.proposal.created",
            meeting,
            {"finding_id": finding.id, "proposal_id": action.id},
        )
        self.db.commit()
        self.db.refresh(finding)
        return finding

    def artifact(
        self, meeting_id: str, artifact_type: str, generate: bool = False
    ) -> MeetingArtifact | None:
        meeting = self.get(meeting_id)
        artifact_type = artifact_type.upper()
        existing = (
            self.db.query(MeetingArtifact)
            .filter_by(
                tenant_id=self.identity.tenant_id,
                meeting_id=meeting.id,
                artifact_type=artifact_type,
            )
            .order_by(MeetingArtifact.version.desc())
            .first()
        )
        if not generate:
            return existing
        self._require("meetings.review")
        reviewed = [
            item
            for item in self.findings(meeting.id)
            if item.review_status not in {"UNREVIEWED", "REJECTED"}
        ]
        version = (existing.version + 1) if existing else 1
        headings = {
            "MEETING_MINUTES": "Meeting Minutes",
            "EXECUTIVE_SUMMARY": "Executive Summary",
        }
        content = (
            f"# {headings.get(artifact_type, artifact_type.replace('_', ' ').title())}\n\n## {meeting.title}\n\n"
            + "\n".join(f"- [{item.finding_type}] {item.title}" for item in reviewed)
        )
        row = MeetingArtifact(
            tenant_id=self.identity.tenant_id,
            meeting_id=meeting.id,
            artifact_type=artifact_type,
            content=content,
            version=version,
            evidence_references=[item.id for item in reviewed],
            source_finding_versions={item.id: item.version for item in reviewed},
        )
        self.db.add(row)
        self._audit(
            "meeting.artifact.generated",
            meeting,
            {"artifact_type": artifact_type, "version": version},
        )
        self.db.commit()
        self.db.refresh(row)
        return row
