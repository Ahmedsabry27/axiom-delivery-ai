from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.audit.events import append_audit_event
from app.auth.dependencies import get_current_user
from app.database.dependencies import get_db
from app.database.models.delivery import (
    DeliveryEvidence,
    DeliveryRAIDHistory,
    DeliveryRAIDItem,
    DeliveryRecommendation,
    DetectedRAIDCandidate,
    DetectedRAIDCandidateEvidence,
    ProposedAction,
    ProposedActionEvidence,
)
from app.delivery.copilot_service import DeliveryCopilotService
from app.delivery.raid_intelligence import RAIDValidationError, exposure
from app.delivery.raid_repository import (
    RAIDConflictError,
    RAIDNotFoundError,
    RAIDRepository,
)

router = APIRouter(prefix="/api/raid", tags=["RAID Intelligence"])


class RAIDCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    item_type: Literal[
        "RISK", "ASSUMPTION", "ISSUE", "DEPENDENCY", "DECISION", "ACTION"
    ]
    name: str = Field(min_length=2, max_length=255)
    description: str = Field(min_length=2, max_length=10000)
    project_id: str
    reference: str | None = Field(default=None, max_length=40)
    status: str | None = Field(default=None, max_length=30)
    priority: str | None = Field(default=None, max_length=30)
    owner_id: str | None = Field(default=None, max_length=255)
    sprint_id: str | None = None
    release_id: str | None = None
    milestone_id: str | None = None
    programme_id: str | None = None
    team_id: str | None = None
    work_item_id: str | None = None
    defect_id: str | None = None
    dependency_id: str | None = None
    impact: str | None = Field(default=None, max_length=30)
    probability: str | None = Field(default=None, max_length=30)
    residual_impact: str | None = Field(default=None, max_length=30)
    residual_probability: str | None = Field(default=None, max_length=30)
    due_date: date | None = None
    review_date: date | None = None
    trigger: str | None = Field(default=None, max_length=5000)
    mitigation_plan: str | None = Field(default=None, max_length=10000)
    contingency_plan: str | None = Field(default=None, max_length=10000)
    risk_response: str | None = Field(default=None, max_length=30)
    validation_owner_id: str | None = Field(default=None, max_length=255)
    validation_due_date: date | None = None
    validation_method: str | None = Field(default=None, max_length=5000)
    validation_status: str | None = Field(default=None, max_length=30)
    severity: str | None = Field(default=None, max_length=30)
    containment_plan: str | None = Field(default=None, max_length=10000)
    resolution_plan: str | None = Field(default=None, max_length=10000)
    root_cause: str | None = Field(default=None, max_length=10000)
    critical_path: bool = False
    blocked_since: datetime | None = None
    decision_owner_id: str | None = Field(default=None, max_length=255)
    rationale: str | None = Field(default=None, max_length=10000)
    completion_evidence_required: bool = False
    evidence_ids: list[str] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def normalize(self):
        for field in (
            "impact",
            "probability",
            "residual_impact",
            "residual_probability",
            "priority",
            "severity",
        ):
            value = getattr(self, field)
            if value:
                setattr(self, field, value.upper().replace(" ", "_"))
        return self


class RAIDUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    name: str | None = Field(default=None, min_length=2, max_length=255)
    description: str | None = Field(default=None, min_length=2, max_length=10000)
    priority: str | None = Field(default=None, max_length=30)
    owner_id: str | None = Field(default=None, max_length=255)
    impact: str | None = Field(default=None, max_length=30)
    probability: str | None = Field(default=None, max_length=30)
    residual_impact: str | None = Field(default=None, max_length=30)
    residual_probability: str | None = Field(default=None, max_length=30)
    due_date: date | None = None
    review_date: date | None = None
    sprint_id: str | None = None
    release_id: str | None = None
    milestone_id: str | None = None
    programme_id: str | None = None
    team_id: str | None = None
    work_item_id: str | None = None
    defect_id: str | None = None
    trigger: str | None = Field(default=None, max_length=5000)
    mitigation_plan: str | None = Field(default=None, max_length=10000)
    contingency_plan: str | None = Field(default=None, max_length=10000)
    risk_response: str | None = Field(default=None, max_length=30)
    validation_owner_id: str | None = Field(default=None, max_length=255)
    validation_due_date: date | None = None
    validation_method: str | None = Field(default=None, max_length=5000)
    validation_status: str | None = Field(default=None, max_length=30)
    severity: str | None = Field(default=None, max_length=30)
    containment_plan: str | None = Field(default=None, max_length=10000)
    resolution_plan: str | None = Field(default=None, max_length=10000)
    root_cause: str | None = Field(default=None, max_length=10000)
    critical_path: bool | None = None
    blocked_since: datetime | None = None
    decision_owner_id: str | None = Field(default=None, max_length=255)
    rationale: str | None = Field(default=None, max_length=10000)
    completion_evidence_required: bool | None = None


class TransitionRequest(BaseModel):
    expected_version: int = Field(ge=1)
    status: str = Field(min_length=2, max_length=30)
    note: str | None = Field(default=None, max_length=10000)


class AssignRequest(BaseModel):
    expected_version: int = Field(ge=1)
    owner_id: str | None = Field(default=None, max_length=255)


class EvidenceLinkRequest(BaseModel):
    evidence_id: str


class RelationshipRequest(BaseModel):
    entity_type: str = Field(min_length=2, max_length=30)
    entity_id: str
    relationship_type: str = Field(default="AFFECTS", min_length=2, max_length=40)


class ReviewRequest(BaseModel):
    expected_version: int = Field(ge=1)
    note: str = Field(min_length=2, max_length=10000)
    next_review_date: date | None = None


class CandidateCreate(BaseModel):
    candidate_type: Literal[
        "RISK", "ASSUMPTION", "ISSUE", "DEPENDENCY", "DECISION", "ACTION"
    ]
    title: str = Field(min_length=2, max_length=255)
    description: str = Field(min_length=2, max_length=10000)
    confidence: float = Field(ge=0, le=1)
    evidence_ids: list[str] = Field(min_length=1, max_length=50)
    affected_entities: list[dict[str, str]] = Field(default_factory=list, max_length=50)
    suggested_owner: str | None = Field(default=None, max_length=255)
    suggested_due_date: date | None = None
    suggested_probability: str | None = Field(default=None, max_length=30)
    suggested_impact: str | None = Field(default=None, max_length=30)
    project_id: str
    limitations: list[str] = Field(default_factory=list, max_length=20)


class CandidateAccept(BaseModel):
    project_id: str
    name: str | None = Field(default=None, min_length=2, max_length=255)
    description: str | None = Field(default=None, min_length=2, max_length=10000)
    owner_id: str | None = Field(default=None, max_length=255)
    due_date: date | None = None
    review_date: date | None = None
    probability: str | None = None
    impact: str | None = None
    severity: str | None = None
    validation_owner_id: str | None = None
    validation_due_date: date | None = None
    decision_owner_id: str | None = None


class CandidateDismiss(BaseModel):
    reason: str = Field(min_length=2, max_length=2000)


class CandidateMerge(BaseModel):
    raid_id: str


class ProposalRequest(BaseModel):
    action_type: Literal[
        "DRAFT_ESCALATION",
        "DRAFT_FOLLOW_UP",
        "REQUEST_DECISION",
        "REQUEST_OWNER",
        "REQUEST_EVIDENCE",
        "PROPOSE_MITIGATION_UPDATE",
        "PROPOSE_ACTION",
        "PROPOSE_STATUS_REVIEW",
        "PROPOSE_RAID_CONVERSION",
    ]
    content: str = Field(min_length=2, max_length=10000)
    owner_id: str | None = Field(default=None, max_length=255)
    due_date: date | None = None
    evidence_ids: list[str] = Field(default_factory=list, max_length=50)
    status: Literal["DRAFT", "PROPOSED", "PENDING_APPROVAL"] = "DRAFT"


class RAIDCopilotRequest(BaseModel):
    conversation_id: str
    question: str = Field(min_length=2, max_length=10000)
    raid_id: str | None = None


def _identity(user: dict) -> tuple[str, str]:
    tenant_id, actor_id = user.get("custom:tenant_id"), user.get("sub")
    if not tenant_id or not actor_id:
        raise HTTPException(401, "Incomplete authenticated identity")
    return tenant_id, actor_id


def _authorize(user: dict, capability: str) -> None:
    permissions = set(user.get("permissions") or [])
    if (
        permissions
        and capability not in permissions
        and "raid.admin" not in permissions
    ):
        raise HTTPException(403, "Insufficient RAID permission")


def _repository(db: Session, user: dict, capability: str) -> RAIDRepository:
    _authorize(user, capability)
    tenant_id, actor_id = _identity(user)
    return RAIDRepository(db, tenant_id, actor_id)


def _audit(
    db: Session,
    user: dict,
    event: str,
    entity_id: str,
    trace_id: str,
    *,
    before: dict | None = None,
    after: dict | None = None,
    metadata: dict | None = None,
) -> None:
    tenant_id, actor_id = _identity(user)
    append_audit_event(
        db,
        tenant_id=tenant_id,
        actor_id=actor_id,
        action=event,
        target_type="RAID_ITEM",
        target_id=entity_id,
        correlation_id=trace_id,
        before=before,
        after=after,
        metadata=metadata,
    )


def _commit(db: Session, operation):
    try:
        result = operation()
        db.commit()
        return result
    except (RAIDValidationError, ValueError) as exc:
        db.rollback()
        raise HTTPException(422, str(exc)) from exc
    except RAIDNotFoundError as exc:
        db.rollback()
        raise HTTPException(404, str(exc)) from exc
    except RAIDConflictError as exc:
        db.rollback()
        raise HTTPException(409, str(exc)) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            409, "RAID change conflicts with an existing record"
        ) from exc


@router.get("", summary="List tenant-scoped persisted RAID items")
def list_raid_items(
    item_type: str | None = Query(default=None, alias="type"),
    raid_status: str | None = Query(default=None, alias="status"),
    exposure_band: str | None = None,
    probability: str | None = None,
    impact: str | None = None,
    priority: str | None = None,
    project_id: str | None = None,
    programme_id: str | None = None,
    team_id: str | None = None,
    sprint_id: str | None = None,
    release_id: str | None = None,
    milestone_id: str | None = None,
    owner_id: str | None = None,
    source_system: str | None = None,
    search: str | None = Query(default=None, max_length=200),
    overdue: bool = False,
    stale: bool = False,
    unowned: bool = False,
    critical_path: bool = False,
    due_from: date | None = None,
    due_to: date | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    sort: str = "attention",
    direction: str = "desc",
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo = _repository(db, user, "raid.read")
    filters = {
        "item_type": item_type.upper() if item_type else None,
        "status": raid_status.upper() if raid_status else None,
        "exposure_band": exposure_band.upper() if exposure_band else None,
        "probability": probability.upper() if probability else None,
        "impact": impact.upper() if impact else None,
        "priority": priority.upper() if priority else None,
        "project_id": project_id,
        "programme_id": programme_id,
        "team_id": team_id,
        "sprint_id": sprint_id,
        "release_id": release_id,
        "milestone_id": milestone_id,
        "owner_id": owner_id,
        "source_system": source_system,
        "search": search,
        "overdue": overdue,
        "stale": stale,
        "unowned": unowned,
        "critical_path": critical_path,
        "due_from": due_from,
        "due_to": due_to,
    }
    try:
        items, total = repo.list(
            filters=filters,
            page=page,
            page_size=page_size,
            sort=sort,
            direction=direction,
        )
    except RAIDValidationError as exc:
        raise HTTPException(422, str(exc)) from exc
    trace_id = str(uuid4())
    return {
        "items": [_item_json(item, repo.evidence_count(item.id)) for item in items],
        "page": page,
        "pageSize": page_size,
        "total": total,
        "pages": (total + page_size - 1) // page_size,
        "traceId": trace_id,
        "generatedAt": datetime.now(UTC).isoformat(),
        "source": "persisted",
    }


@router.post("", status_code=201, summary="Create a persisted RAID item")
def create_raid_item(
    payload: RAIDCreate,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo = _repository(db, user, "raid.create")
    trace_id = str(uuid4())
    values = payload.model_dump(exclude={"evidence_ids"}, exclude_none=True)
    evidence_ids = payload.evidence_ids

    def operation():
        duplicates = repo.duplicates(values)
        item = repo.create(values, trace_id=trace_id)
        for evidence_id in evidence_ids:
            repo.link_evidence(item.id, evidence_id, trace_id=trace_id)
        _audit(
            db,
            user,
            "raid.item.created",
            item.id,
            trace_id,
            after={"reference": item.reference, "type": item.item_type},
            metadata={"possibleDuplicates": duplicates},
        )
        return {
            "item": _item_json(item, len(evidence_ids)),
            "possibleDuplicates": duplicates,
            "traceId": trace_id,
            "externalWrites": False,
        }

    return _commit(db, operation)


@router.get("/summary", summary="Get persisted RAID summary counts")
def raid_summary(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    repo = _repository(db, user, "raid.read")
    return {
        **repo.summary(),
        "generatedAt": datetime.now(UTC).isoformat(),
        "source": "persisted",
    }


@router.get("/attention", summary="List RAID items needing attention")
def raid_attention(
    user: dict = Depends(get_current_user), db: Session = Depends(get_db)
):
    repo = _repository(db, user, "raid.read")
    items, _ = repo.list(page_size=100, sort="attention")
    return {
        "items": [
            _item_json(item, repo.evidence_count(item.id))
            for item in items
            if (item.attention_score or 0) > 0
        ],
        "generatedAt": datetime.now(UTC).isoformat(),
    }


@router.get("/hygiene", summary="Get deterministic RAID hygiene findings")
def raid_hygiene(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    repo = _repository(db, user, "raid.read")
    findings = repo.hygiene()
    return {
        "items": findings,
        "total": len(findings),
        "generatedAt": datetime.now(UTC).isoformat(),
        "method": "deterministic-rules-v1",
    }


@router.get("/heatmap", summary="Get accessible persisted risk heatmap values")
def raid_heatmap(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    repo = _repository(db, user, "raid.read")
    items, _ = repo.list(filters={"item_type": "RISK"}, page_size=100)
    cells = []
    for probability in ("RARE", "UNLIKELY", "POSSIBLE", "LIKELY", "ALMOST_CERTAIN"):
        for impact in ("LOW", "MINOR", "MODERATE", "HIGH", "CRITICAL"):
            scored = exposure(probability, impact)
            matching = [
                item
                for item in items
                if item.probability == probability
                and item.impact
                in ({impact, "MEDIUM"} if impact == "MODERATE" else {impact})
            ]
            cells.append(
                {
                    "probability": probability,
                    "impact": impact,
                    "score": scored.value,
                    "band": scored.band,
                    "count": len(matching),
                    "itemIds": [item.id for item in matching],
                }
            )
    return {
        "cells": cells,
        "totalRisks": len(items),
        "generatedAt": datetime.now(UTC).isoformat(),
    }


@router.get(
    "/candidates", summary="List detected RAID candidates awaiting human review"
)
def list_candidates(
    user: dict = Depends(get_current_user), db: Session = Depends(get_db)
):
    repo = _repository(db, user, "raid.review_candidates")
    return {
        "items": [
            _candidate_json(candidate, repo.candidate_evidence(candidate.id))
            for candidate in repo.list_candidates()
        ],
        "externalWrites": False,
    }


@router.post(
    "/detected",
    status_code=201,
    summary="Persist an evidence-backed RAID candidate for human review",
)
def detect_candidate(
    payload: CandidateCreate,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo = _repository(db, user, "raid.review_candidates")
    trace_id = str(uuid4())

    def operation():
        evidence = []
        for evidence_id in dict.fromkeys(payload.evidence_ids):
            repo._require_entity("EVIDENCE", evidence_id)
            evidence.append(evidence_id)
        duplicates = repo.duplicates(
            {
                "title": payload.title,
                "project_id": payload.project_id,
                "owner_id": payload.suggested_owner,
                "due_date": payload.suggested_due_date,
            }
        )
        candidate = DetectedRAIDCandidate(
            tenant_id=repo.tenant_id,
            candidate_type=payload.candidate_type,
            title=payload.title,
            description=payload.description,
            confidence=payload.confidence,
            affected_entities=payload.affected_entities,
            suggested_owner=payload.suggested_owner,
            suggested_due_date=payload.suggested_due_date,
            suggested_probability=payload.suggested_probability.upper()
            if payload.suggested_probability
            else None,
            suggested_impact=payload.suggested_impact.upper()
            if payload.suggested_impact
            else None,
            possible_duplicates=duplicates,
            limitations=payload.limitations,
            detected_by_agent="axiom-raid-deterministic-detector",
            model="deterministic-rules-v1",
            trace_id=trace_id,
        )
        db.add(candidate)
        db.flush()
        for evidence_id in evidence:
            db.add(
                DetectedRAIDCandidateEvidence(
                    tenant_id=repo.tenant_id,
                    candidate_id=candidate.id,
                    evidence_id=evidence_id,
                )
            )
        _audit(
            db,
            user,
            "raid.candidate.detected",
            candidate.id,
            trace_id,
            after={"type": candidate.candidate_type, "status": candidate.status},
            metadata={"evidenceCount": len(evidence), "possibleDuplicates": duplicates},
        )
        return {
            "candidate": _candidate_json(candidate, []),
            "traceId": trace_id,
            "humanReviewRequired": True,
        }

    return _commit(db, operation)


@router.post(
    "/detected/{candidate_id}/accept",
    status_code=201,
    summary="Accept a reviewed candidate as a durable RAID item",
)
def accept_candidate(
    candidate_id: str,
    payload: CandidateAccept,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo = _repository(db, user, "raid.review_candidates")

    def operation():
        candidate, item = repo.accept_candidate(
            candidate_id, payload.model_dump(exclude_none=True)
        )
        _audit(
            db,
            user,
            "raid.candidate.accepted",
            item.id,
            candidate.trace_id,
            after={"candidateId": candidate.id, "reference": item.reference},
        )
        return {
            "candidate": _candidate_json(
                candidate, repo.candidate_evidence(candidate.id)
            ),
            "item": _item_json(item, repo.evidence_count(item.id)),
            "humanReviewed": True,
            "externalWrites": False,
        }

    return _commit(db, operation)


@router.post(
    "/detected/{candidate_id}/dismiss",
    summary="Dismiss a candidate with an auditable reason",
)
def dismiss_candidate(
    candidate_id: str,
    payload: CandidateDismiss,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo = _repository(db, user, "raid.review_candidates")

    def operation():
        candidate = repo.dismiss_candidate(candidate_id, payload.reason)
        _audit(
            db,
            user,
            "raid.candidate.dismissed",
            candidate.id,
            candidate.trace_id,
            after={"reason": payload.reason},
        )
        return {
            "candidate": _candidate_json(
                candidate, repo.candidate_evidence(candidate.id)
            ),
            "humanReviewed": True,
        }

    return _commit(db, operation)


@router.post(
    "/detected/{candidate_id}/merge",
    summary="Merge candidate evidence into an existing RAID item",
)
def merge_candidate(
    candidate_id: str,
    payload: CandidateMerge,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo = _repository(db, user, "raid.review_candidates")

    def operation():
        candidate = repo.merge_candidate(candidate_id, payload.raid_id)
        _audit(
            db,
            user,
            "raid.candidate.merged",
            payload.raid_id,
            candidate.trace_id,
            after={"candidateId": candidate.id},
        )
        return {
            "candidate": _candidate_json(
                candidate, repo.candidate_evidence(candidate.id)
            ),
            "mergedInto": payload.raid_id,
            "humanReviewed": True,
        }

    return _commit(db, operation)


@router.get(
    "/reports/{report_type}", summary="Generate a persisted-evidence RAID summary"
)
def raid_report(
    report_type: Literal["executive", "weekly"],
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo = _repository(db, user, "raid.read")
    summary = repo.summary()
    items, _ = repo.list(page_size=100)
    trace_id = str(uuid4())
    _audit(
        db,
        user,
        "raid.report.generated",
        report_type,
        trace_id,
        metadata={"recordCount": len(items)},
    )
    db.commit()
    return {
        "reportType": report_type,
        "summary": summary,
        "topItems": [
            _item_json(item, repo.evidence_count(item.id)) for item in items[:10]
        ],
        "hygieneFindings": repo.hygiene()[:10],
        "dataFreshness": datetime.now(UTC).isoformat(),
        "limitations": [
            "Historical trend requires multiple persisted reporting periods"
        ],
        "traceId": trace_id,
        "externalWrites": False,
    }


@router.post(
    "/copilot", summary="Persist a structured evidence-backed RAID Copilot response"
)
def raid_copilot(
    payload: RAIDCopilotRequest,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _authorize(user, "raid.read")
    tenant_id, actor_id = _identity(user)
    try:
        return DeliveryCopilotService(db, tenant_id, actor_id).raid_insight(
            payload.conversation_id, payload.question, payload.raid_id
        )
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/{raid_id}", summary="Get a tenant-authorized persisted RAID item")
def get_raid_item(
    raid_id: str, user: dict = Depends(get_current_user), db: Session = Depends(get_db)
):
    repo = _repository(db, user, "raid.read")
    try:
        details = repo.details(raid_id)
    except RAIDNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    trace_id = str(uuid4())
    _audit(db, user, "raid.item.viewed", raid_id, trace_id)
    db.commit()
    return _details_json(details, trace_id)


@router.patch("/{raid_id}", summary="Update a RAID item with optimistic concurrency")
def update_raid_item(
    raid_id: str,
    payload: RAIDUpdate,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo = _repository(db, user, "raid.update")
    trace_id = str(uuid4())
    values = payload.model_dump(exclude={"expected_version"}, exclude_unset=True)

    def operation():
        item = repo.update(
            raid_id,
            values,
            expected_version=payload.expected_version,
            trace_id=trace_id,
        )
        _audit(
            db,
            user,
            "raid.item.updated",
            item.id,
            trace_id,
            after={"version": item.version, "fields": sorted(values)},
        )
        return {
            "item": _item_json(item, repo.evidence_count(item.id)),
            "traceId": trace_id,
        }

    return _commit(db, operation)


@router.post(
    "/{raid_id}/transition", summary="Apply a validated RAID lifecycle transition"
)
def transition_raid_item(
    raid_id: str,
    payload: TransitionRequest,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo = _repository(db, user, "raid.update")
    trace_id = str(uuid4())

    def operation():
        item = repo.transition(
            raid_id,
            payload.status,
            expected_version=payload.expected_version,
            note=payload.note,
            trace_id=trace_id,
        )
        _audit(
            db,
            user,
            "raid.status.transitioned",
            item.id,
            trace_id,
            after={"status": item.status, "version": item.version},
        )
        return {
            "item": _item_json(item, repo.evidence_count(item.id)),
            "traceId": trace_id,
        }

    return _commit(db, operation)


@router.post("/{raid_id}/assign", summary="Assign or explicitly unassign a RAID owner")
def assign_raid_item(
    raid_id: str,
    payload: AssignRequest,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo = _repository(db, user, "raid.assign")
    trace_id = str(uuid4())

    def operation():
        item = repo.assign(
            raid_id,
            payload.owner_id,
            expected_version=payload.expected_version,
            trace_id=trace_id,
        )
        _audit(
            db,
            user,
            "raid.owner.assigned",
            item.id,
            trace_id,
            after={"ownerId": payload.owner_id},
        )
        return {
            "item": _item_json(item, repo.evidence_count(item.id)),
            "traceId": trace_id,
        }

    return _commit(db, operation)


@router.post(
    "/{raid_id}/evidence", status_code=201, summary="Link authorized persisted evidence"
)
def link_raid_evidence(
    raid_id: str,
    payload: EvidenceLinkRequest,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo = _repository(db, user, "raid.manage_evidence")
    trace_id = str(uuid4())

    def operation():
        repo.link_evidence(raid_id, payload.evidence_id, trace_id=trace_id)
        _audit(
            db,
            user,
            "raid.evidence.linked",
            raid_id,
            trace_id,
            after={"evidenceId": payload.evidence_id},
        )
        return {
            "raidId": raid_id,
            "evidenceId": payload.evidence_id,
            "traceId": trace_id,
        }

    return _commit(db, operation)


@router.delete(
    "/{raid_id}/evidence/{evidence_id}",
    status_code=204,
    summary="Remove a RAID evidence link without deleting evidence",
)
def unlink_raid_evidence(
    raid_id: str,
    evidence_id: str,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo = _repository(db, user, "raid.manage_evidence")
    trace_id = str(uuid4())

    def operation():
        repo.unlink_evidence(raid_id, evidence_id, trace_id=trace_id)
        _audit(
            db,
            user,
            "raid.evidence.unlinked",
            raid_id,
            trace_id,
            after={"evidenceId": evidence_id},
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return _commit(db, operation)


@router.post(
    "/{raid_id}/relationships",
    status_code=201,
    summary="Link an authorized delivery entity",
)
def add_raid_relationship(
    raid_id: str,
    payload: RelationshipRequest,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo = _repository(db, user, "raid.manage_relationships")
    trace_id = str(uuid4())

    def operation():
        relationship = repo.add_relationship(
            raid_id,
            payload.entity_type,
            payload.entity_id,
            payload.relationship_type,
            trace_id=trace_id,
        )
        _audit(
            db,
            user,
            "raid.relationship.added",
            raid_id,
            trace_id,
            after={"relationshipId": relationship.id},
        )
        return {"relationship": _relationship_json(relationship), "traceId": trace_id}

    return _commit(db, operation)


@router.delete(
    "/{raid_id}/relationships/{relationship_id}",
    status_code=204,
    summary="Safely unlink a RAID delivery relationship",
)
def remove_raid_relationship(
    raid_id: str,
    relationship_id: str,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo = _repository(db, user, "raid.manage_relationships")
    trace_id = str(uuid4())

    def operation():
        repo.remove_relationship(raid_id, relationship_id, trace_id=trace_id)
        _audit(
            db,
            user,
            "raid.relationship.removed",
            raid_id,
            trace_id,
            after={"relationshipId": relationship_id},
        )
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return _commit(db, operation)


@router.get("/{raid_id}/history", summary="Get append-only RAID item history")
def raid_history(
    raid_id: str, user: dict = Depends(get_current_user), db: Session = Depends(get_db)
):
    repo = _repository(db, user, "raid.read")
    try:
        return {"items": [_history_json(item) for item in repo.history(raid_id)]}
    except RAIDNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post(
    "/{raid_id}/review", status_code=201, summary="Record an auditable RAID review note"
)
def review_raid_item(
    raid_id: str,
    payload: ReviewRequest,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo = _repository(db, user, "raid.review")
    trace_id = str(uuid4())

    def operation():
        review = repo.review(
            raid_id,
            payload.note,
            payload.next_review_date,
            expected_version=payload.expected_version,
            trace_id=trace_id,
        )
        _audit(
            db,
            user,
            "raid.review.completed",
            raid_id,
            trace_id,
            after={"reviewId": review.id},
        )
        return {
            "review": {
                "id": review.id,
                "note": review.note,
                "reviewedBy": review.reviewed_by,
                "reviewedAt": review.reviewed_at.isoformat(),
                "nextReviewDate": review.next_review_date.isoformat()
                if review.next_review_date
                else None,
            },
            "traceId": trace_id,
        }

    return _commit(db, operation)


@router.post(
    "/{raid_id}/close", summary="Close or resolve a RAID item through its lifecycle"
)
def close_raid_item(
    raid_id: str,
    payload: TransitionRequest,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _authorize(user, "raid.close")
    return transition_raid_item(raid_id, payload, user, db)


@router.post(
    "/{raid_id}/proposals",
    status_code=201,
    summary="Create an internal proposed intervention only",
)
def create_raid_proposal(
    raid_id: str,
    payload: ProposalRequest,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo = _repository(db, user, "raid.update")
    trace_id = str(uuid4())

    def operation():
        item = repo.require(raid_id)
        evidence = []
        for evidence_id in dict.fromkeys(payload.evidence_ids):
            repo._require_entity("EVIDENCE", evidence_id)
            evidence.append(evidence_id)
        proposal = ProposedAction(
            tenant_id=repo.tenant_id,
            raid_id=item.id,
            trace_id=trace_id,
            action_type=payload.action_type,
            title=payload.content[:255],
            description=payload.content,
            content=payload.content,
            origin="USER",
            requester_id=repo.actor_id,
            target_entity_type="RAID_ITEM",
            target_entity_id=item.id,
            target_system="INTERNAL",
            payload={"content": payload.content, "raid_id": item.id},
            original_payload={"content": payload.content, "raid_id": item.id},
            target=item.reference,
            owner_id=payload.owner_id,
            due_date=payload.due_date,
            status=payload.status,
            risk_classification="CONTROLLED",
            approval_required=True,
            created_by=repo.actor_id,
        )
        db.add(proposal)
        db.flush()
        for evidence_id in evidence:
            db.add(
                ProposedActionEvidence(
                    tenant_id=repo.tenant_id,
                    proposed_action_id=proposal.id,
                    evidence_id=evidence_id,
                )
            )
        item.version += 1
        repo._history(
            item,
            "PROPOSED_INTERVENTION_CREATED",
            trace_id=trace_id,
            change_data={"proposedActionId": proposal.id, "status": proposal.status},
        )
        _audit(
            db,
            user,
            "raid.proposed_intervention.created",
            item.id,
            trace_id,
            after={"proposedActionId": proposal.id, "status": proposal.status},
        )
        return {
            "proposal": _proposal_json(proposal),
            "traceId": trace_id,
            "externalWrites": False,
            "approvalRequired": True,
        }

    return _commit(db, operation)


@router.post(
    "/{raid_id}/recommendations",
    status_code=201,
    summary="Create an evidence-backed RAID recommendation",
)
def create_raid_recommendation(
    raid_id: str,
    payload: ProposalRequest,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo = _repository(db, user, "raid.update")
    trace_id = str(uuid4())

    def operation():
        item = repo.require(raid_id)
        if not payload.evidence_ids:
            raise RAIDValidationError("Recommendation requires evidence")
        for evidence_id in payload.evidence_ids:
            repo._require_entity("EVIDENCE", evidence_id)
        recommendation = DeliveryRecommendation(
            tenant_id=repo.tenant_id,
            entity_type="RAID",
            entity_id=item.id,
            raid_id=item.id,
            title=payload.action_type.replace("_", " ").title(),
            explanation=payload.content,
            priority=item.priority or item.exposure_band or "MEDIUM",
            confidence=0.8,
            status="NEW",
        )
        db.add(recommendation)
        db.flush()
        _audit(
            db,
            user,
            "raid.recommendation.created",
            item.id,
            trace_id,
            after={"recommendationId": recommendation.id},
        )
        return {
            "recommendation": {
                "id": recommendation.id,
                "title": recommendation.title,
                "explanation": recommendation.explanation,
                "priority": recommendation.priority,
                "confidence": recommendation.confidence,
            },
            "traceId": trace_id,
        }

    return _commit(db, operation)


def _item_json(item: DeliveryRAIDItem, evidence_count: int = 0) -> dict[str, Any]:
    fields = [
        "id",
        "reference",
        "name",
        "description",
        "item_type",
        "status",
        "priority",
        "owner_id",
        "project_id",
        "programme_id",
        "team_id",
        "sprint_id",
        "release_id",
        "milestone_id",
        "work_item_id",
        "defect_id",
        "dependency_id",
        "impact",
        "probability",
        "residual_impact",
        "residual_probability",
        "exposure_score",
        "exposure_band",
        "residual_exposure_score",
        "residual_exposure_band",
        "attention_score",
        "attention_reasons",
        "due_date",
        "review_date",
        "identified_at",
        "last_reviewed_at",
        "closed_at",
        "closure_reason",
        "source_system",
        "source_url",
        "trigger",
        "mitigation_plan",
        "contingency_plan",
        "risk_response",
        "validation_owner_id",
        "validation_due_date",
        "validation_method",
        "validation_status",
        "severity",
        "containment_plan",
        "resolution_plan",
        "root_cause",
        "critical_path",
        "blocked_since",
        "decision_owner_id",
        "rationale",
        "created_by",
        "updated_by",
        "created_at",
        "updated_at",
        "version",
    ]
    result = {
        _camel(field): _json_value(getattr(item, field, None)) for field in fields
    }
    result["evidenceCount"] = evidence_count
    result["ageDays"] = max(0, (datetime.now(UTC) - _aware(item.identified_at)).days)
    return result


def _details_json(details: dict[str, Any], trace_id: str) -> dict[str, Any]:
    return {
        "item": _item_json(details["item"], len(details["evidence"])),
        "evidence": [
            {
                "id": item.id,
                "title": item.title,
                "summary": item.summary,
                "sourceType": item.source_type,
                "sourceSystem": item.source_system,
                "sourceUrl": item.source_url,
                "capturedAt": item.captured_at.isoformat(),
            }
            for item in details["evidence"]
        ],
        "relationships": [
            _relationship_json(item) for item in details["relationships"]
        ],
        "recommendations": [
            {
                "id": item.id,
                "title": item.title,
                "explanation": item.explanation,
                "priority": item.priority,
                "confidence": item.confidence,
                "status": item.status,
            }
            for item in details["recommendations"]
        ],
        "proposals": [_proposal_json(item) for item in details["proposals"]],
        "reviews": [
            {
                "id": item.id,
                "note": item.note,
                "reviewedBy": item.reviewed_by,
                "reviewedAt": item.reviewed_at.isoformat(),
                "nextReviewDate": _json_value(item.next_review_date),
            }
            for item in details["reviews"]
        ],
        "relatedItems": [
            {
                "raidId": item.raid_id,
                "relatedRaidId": item.related_raid_id,
                "relationshipType": item.relationship_type,
            }
            for item in details["related"]
        ],
        "history": [_history_json(item) for item in details["history"]],
        "traceId": trace_id,
        "source": "persisted",
        "externalWrites": False,
    }


def _candidate_json(
    candidate: DetectedRAIDCandidate, evidence: list[DeliveryEvidence]
) -> dict[str, Any]:
    return {
        "id": candidate.id,
        "candidateType": candidate.candidate_type,
        "title": candidate.title,
        "description": candidate.description,
        "confidence": candidate.confidence,
        "evidence": [
            {"id": item.id, "title": item.title, "sourceType": item.source_type}
            for item in evidence
        ],
        "affectedEntities": candidate.affected_entities or [],
        "suggestedOwner": candidate.suggested_owner,
        "suggestedDueDate": _json_value(candidate.suggested_due_date),
        "suggestedProbability": candidate.suggested_probability,
        "suggestedImpact": candidate.suggested_impact,
        "possibleDuplicates": candidate.possible_duplicates or [],
        "limitations": candidate.limitations or [],
        "detectedAt": candidate.detected_at.isoformat(),
        "agent": candidate.detected_by_agent,
        "model": candidate.model,
        "traceId": candidate.trace_id,
        "status": candidate.status,
        "version": candidate.version,
    }


def _history_json(item: DeliveryRAIDHistory) -> dict[str, Any]:
    return {
        "id": item.id,
        "eventType": item.event_type,
        "previousStatus": item.previous_status,
        "newStatus": item.new_status,
        "note": item.note,
        "actorId": item.actor_id,
        "traceId": item.trace_id,
        "recordVersion": item.record_version,
        "changedAt": item.changed_at.isoformat(),
        "changeData": item.change_data,
    }


def _relationship_json(item) -> dict[str, Any]:
    return {
        "id": item.id,
        "entityType": item.entity_type,
        "entityId": item.entity_id,
        "relationshipType": item.relationship_type,
        "createdBy": item.created_by,
        "createdAt": item.created_at.isoformat(),
    }


def _proposal_json(item: ProposedAction) -> dict[str, Any]:
    return {
        "id": item.id,
        "actionType": item.action_type,
        "content": item.content,
        "target": item.target,
        "ownerId": item.owner_id,
        "dueDate": _json_value(item.due_date),
        "status": item.status,
        "approvalRequired": item.approval_required,
        "createdAt": item.created_at.isoformat(),
    }


def _camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(part.title() for part in tail)


def _json_value(value: Any) -> Any:
    return value.isoformat() if isinstance(value, (date, datetime)) else value


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value
