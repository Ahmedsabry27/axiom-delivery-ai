from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.agents.application_service import AgentIdentity
from app.auth.dependencies import get_current_user
from app.ceremony_intelligence.service import (
    CeremonyService,
    LessonService,
    checklist_scores,
)
from app.database.dependencies import get_db
from app.database.models.audit import AuditLog
from app.database.models.ceremony import Lesson

router = APIRouter(tags=["Ceremony and Lessons Intelligence"])
DB = Annotated[Session, Depends(get_db)]
User = Annotated[dict, Depends(get_current_user)]


def cs(db, u):
    return CeremonyService(db, AgentIdentity.from_claims(u))


def ls(db, u):
    return LessonService(db, AgentIdentity.from_claims(u))


def page(rows, p, size):
    return {
        "items": rows[(p - 1) * size : p * size],
        "total": len(rows),
        "page": p,
        "pageSize": size,
    }


def template_json(x):
    return {
        "id": x.id,
        "familyKey": x.family_key,
        "name": x.name,
        "ceremonyType": x.ceremony_type,
        "description": x.description,
        "purpose": x.purpose,
        "requiredRoles": x.required_roles,
        "recommendedTimeboxMinutes": x.recommended_timebox_minutes,
        "items": x.items,
        "requiredEvidence": x.required_evidence,
        "expectedDecisions": x.expected_decisions,
        "expectedOutputs": x.expected_outputs,
        "scoringConfig": x.scoring_config,
        "templateVersion": x.template_version,
        "effectiveDate": x.effective_date,
        "ownerId": x.owner_id,
        "status": x.status,
        "version": x.version,
    }


def ceremony_json(s, x):
    items = s.checklist(x.id)
    scores = x.score_snapshot or checklist_scores(items)
    return {
        "id": x.id,
        "meetingId": x.meeting_id,
        "templateId": x.template_id,
        "templateVersion": x.template_version,
        "templateSnapshot": x.template_snapshot,
        "title": x.title,
        "ceremonyType": x.ceremony_type,
        "status": x.status,
        "teamId": x.team_id,
        "programmeId": x.programme_id,
        "projectId": x.project_id,
        "scheduledStart": x.scheduled_start,
        "facilitatorId": x.facilitator_id,
        "purpose": x.purpose,
        "agenda": x.agenda,
        "scores": scores,
        "analysisFindings": x.analysis_findings,
        "themes": x.themes,
        "version": x.version,
        "updatedAt": x.updated_at,
    }


def check_json(x):
    return {
        "id": x.id,
        "itemKey": x.item_key,
        "section": x.section,
        "label": x.label,
        "description": x.description,
        "required": x.required,
        "weight": x.weight,
        "evidenceRequired": x.evidence_required,
        "responsibleRole": x.responsible_role,
        "status": x.status,
        "comment": x.comment,
        "evidenceRefs": x.evidence_refs,
        "completedBy": x.completed_by,
        "completedAt": x.completed_at,
        "applicabilityReason": x.applicability_reason,
        "source": x.source,
        "version": x.version,
    }


def lesson_json(x, db):
    from app.database.models.ceremony import LessonAdoption

    ad = db.query(LessonAdoption).filter_by(tenant_id=x.tenant_id, lesson_id=x.id).all()
    return {
        "id": x.id,
        "ceremonyId": x.ceremony_id,
        "meetingId": x.meeting_id,
        "title": x.title,
        "category": x.category,
        "sentiment": x.sentiment,
        "status": x.status,
        "context": x.context,
        "expectedOutcome": x.expected_outcome,
        "actualOutcome": x.actual_outcome,
        "rootCause": x.root_cause,
        "contributingFactors": x.contributing_factors,
        "recommendation": x.recommendation,
        "evidenceRefs": x.evidence_refs,
        "affectedEntities": x.affected_entities,
        "applicability": x.applicability,
        "ownerId": x.owner_id,
        "reviewerId": x.reviewer_id,
        "reviewDate": x.review_date,
        "publishedAt": x.published_at,
        "version": x.version,
        "updatedAt": x.updated_at,
        "adoptions": [
            {
                "id": a.id,
                "targetType": a.target_type,
                "targetId": a.target_id,
                "status": a.status,
                "ownerId": a.owner_id,
                "successMeasure": a.success_measure,
                "verifiedBenefit": a.verified_benefit,
                "evidenceRefs": a.evidence_refs,
                "version": a.version,
            }
            for a in ad
        ],
    }


class TemplateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=255)
    ceremony_type: str
    description: str = ""
    purpose: str = ""
    required_roles: list[str] = []
    recommended_timebox_minutes: int | None = None
    items: list[dict] = []
    required_evidence: list[str] = []
    expected_decisions: list[str] = []
    expected_outputs: list[str] = []
    scoring_config: dict = {}
    effective_date: Any = None
    status: str = "DRAFT"
    family_key: str | None = None


class CeremonyIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str
    template_id: str
    meeting_id: str | None = None
    team_id: str | None = None
    programme_id: str | None = None
    project_id: str | None = None
    scheduled_start: datetime | None = None
    facilitator_id: str | None = None
    purpose: str = ""
    agenda: list[str] = []
    status: str = "PLANNED"


class ChecklistIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int
    status: str
    comment: str | None = None
    evidence_refs: list[dict] = []
    applicability_reason: str | None = None


class LessonIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str
    category: str
    sentiment: str = "NEGATIVE"
    ceremony_id: str | None = None
    meeting_id: str | None = None
    context: str = ""
    expected_outcome: str = ""
    actual_outcome: str = ""
    root_cause: str = ""
    contributing_factors: list[str] = []
    recommendation: str = ""
    evidence_refs: list[dict] = []
    affected_entities: list[dict] = []
    applicability: list[dict] = []
    owner_id: str | None = None
    status: str = "DRAFT"


class TransitionIn(BaseModel):
    expected_version: int
    status: str


class AdoptionIn(BaseModel):
    target_type: str
    target_id: str
    owner_id: str | None = None
    status: str = "PLANNED"
    success_measure: str | None = None
    evidence_refs: list[dict] = []


@router.get("/api/ceremonies/templates")
def templates(db: DB, user: User):
    return {"items": [template_json(x) for x in cs(db, user).templates()]}


@router.post("/api/ceremonies/templates", status_code=201)
def create_template(v: TemplateIn, db: DB, user: User):
    return template_json(cs(db, user).create_template(v.model_dump()))


@router.get("/api/ceremonies/templates/{id}")
def template(id: str, db: DB, user: User):
    return template_json(cs(db, user).template(id))


@router.get("/api/ceremonies")
def ceremonies(
    db: DB,
    user: User,
    page_number: int = Query(1, alias="page", ge=1),
    page_size: int = Query(25, ge=1, le=100),
):
    s = cs(db, user)
    rows = [ceremony_json(s, x) for x in s.ceremonies()]
    return page(rows, page_number, page_size)


@router.post("/api/ceremonies", status_code=201)
def create_ceremony(v: CeremonyIn, db: DB, user: User):
    s = cs(db, user)
    return ceremony_json(s, s.create(v.model_dump()))


@router.get("/api/ceremonies/{id}")
def ceremony(id: str, db: DB, user: User):
    s = cs(db, user)
    return ceremony_json(s, s.get(id))


@router.get("/api/ceremonies/{id}/preparation")
def preparation(id: str, db: DB, user: User):
    s = cs(db, user)
    items = s.checklist(id)
    return {
        "items": [check_json(x) for x in items if x.section.upper() == "BEFORE"],
        "scores": checklist_scores(items),
    }


@router.get("/api/ceremonies/{id}/checklist")
def checklist(id: str, db: DB, user: User):
    s = cs(db, user)
    items = s.checklist(id)
    return {"items": [check_json(x) for x in items], "scores": checklist_scores(items)}


@router.patch("/api/ceremonies/{id}/checklist/{item_key}")
def update_checklist(id: str, item_key: str, v: ChecklistIn, db: DB, user: User):
    return check_json(cs(db, user).update_checklist(id, item_key, v.model_dump()))


@router.get("/api/ceremonies/{id}/analysis")
def analysis(id: str, db: DB, user: User):
    x = cs(db, user).get(id)
    return {
        "items": x.analysis_findings,
        "themes": x.themes,
        "scores": x.score_snapshot,
        "limitations": ["AI suggestions require human review"],
    }


@router.get("/api/ceremonies/{id}/decisions")
def decisions(id: str, db: DB, user: User):
    s = cs(db, user)
    return {
        "items": [
            {
                "id": x.id,
                "title": x.title,
                "description": x.description,
                "confidence": x.confidence,
                "reviewStatus": x.review_status,
                "proposalId": x.proposal_id,
            }
            for x in s.related(id)["decisions"]
        ]
    }


@router.get("/api/ceremonies/{id}/actions")
def actions(id: str, db: DB, user: User):
    s = cs(db, user)
    return {
        "items": [
            {
                "id": x.id,
                "title": x.title,
                "description": x.description,
                "confidence": x.confidence,
                "reviewStatus": x.review_status,
                "proposalId": x.proposal_id,
            }
            for x in s.related(id)["actions"]
        ]
    }


@router.get("/api/ceremonies/{id}/{section}")
def section(id: str, section: str, db: DB, user: User):
    service = cs(db, user)
    ceremony = service.get(id)
    if section == "lessons":
        rows = (
            db.query(Lesson)
            .filter_by(tenant_id=ceremony.tenant_id, ceremony_id=id)
            .order_by(Lesson.updated_at.desc())
            .all()
        )
        return {"items": [lesson_json(row, db) for row in rows]}
    if section == "evidence":
        items = []
        for checklist_item in service.checklist(id):
            for evidence in checklist_item.evidence_refs or []:
                items.append(
                    {
                        "id": evidence.get("id")
                        or evidence.get("url")
                        or checklist_item.id,
                        "title": evidence.get("title") or checklist_item.label,
                        "description": evidence.get("url")
                        or evidence.get("type")
                        or "Authorized evidence reference",
                        "checklistItemKey": checklist_item.item_key,
                    }
                )
        return {"items": items}
    if section == "activity":
        rows = (
            db.query(AuditLog)
            .filter_by(
                tenant_id=ceremony.tenant_id,
                target_type="ceremony",
                target_id=id,
            )
            .order_by(AuditLog.id.desc())
            .limit(100)
            .all()
        )
        return {
            "items": [
                {
                    "id": str(row.id),
                    "title": row.action or row.event_type,
                    "description": f"{row.actor_id or row.user_id or 'System'} · {row.created_at or row.timestamp}",
                    "metadata": row.metadata_json or {},
                }
                for row in rows
            ]
        }
    return {
        "items": [],
        "section": section,
        "limitations": ["No authorized persisted records are available"],
    }


@router.get("/api/lessons")
def lessons(
    db: DB,
    user: User,
    page_number: int = Query(1, alias="page", ge=1),
    page_size: int = Query(25, ge=1, le=100),
):
    return page(
        [lesson_json(x, db) for x in ls(db, user).list()], page_number, page_size
    )


@router.post("/api/lessons", status_code=201)
def create_lesson(v: LessonIn, db: DB, user: User):
    return lesson_json(ls(db, user).create(v.model_dump()), db)


@router.get("/api/lessons/{id}")
def lesson(id: str, db: DB, user: User):
    return lesson_json(ls(db, user).get(id), db)


@router.patch("/api/lessons/{id}")
def transition_lesson(id: str, v: TransitionIn, db: DB, user: User):
    return lesson_json(ls(db, user).transition(id, v.status, v.expected_version), db)


@router.post("/api/lessons/{id}/publish")
def publish(id: str, v: TransitionIn, db: DB, user: User):
    return lesson_json(ls(db, user).transition(id, "PUBLISHED", v.expected_version), db)


@router.post("/api/lessons/{id}/adopt", status_code=201)
def adopt(id: str, v: AdoptionIn, db: DB, user: User):
    x = ls(db, user).adopt(id, v.model_dump())
    return {"id": x.id, "status": x.status, "version": x.version}


@router.get("/api/lessons/{id}/activity")
def lesson_activity(id: str, db: DB, user: User):
    ls(db, user).get(id)
    return {"items": []}
