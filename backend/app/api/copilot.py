from __future__ import annotations

import re
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.audit.events import append_audit_event
from app.auth.dependencies import get_current_user
from app.database.dependencies import get_db
from app.database.models.copilot import (
    CopilotPromptFavorite,
    CopilotPromptTemplate,
    CopilotSavedInsight,
)
from app.database.models.delivery import CopilotFeedback

router = APIRouter(prefix="/api/copilot", tags=["Copilot organization"])
INSIGHT_STATUSES = {"SAVED", "SHARED", "STALE", "SUPERSEDED", "ARCHIVED"}
TEMPLATE_STATUSES = {
    "DRAFT",
    "PENDING_REVIEW",
    "APPROVED",
    "PUBLISHED",
    "SUPERSEDED",
    "ARCHIVED",
}
TEMPLATE_CATEGORIES = {
    "EXECUTIVE_REPORTING",
    "PORTFOLIO",
    "PROGRAMME",
    "PROJECT",
    "SPRINT",
    "RELEASE",
    "RAID",
    "DEPENDENCIES",
    "MEETINGS",
    "CEREMONIES",
    "KNOWLEDGE",
    "DECISIONS",
    "ACTIONS",
    "GOVERNANCE",
}
SECRET_PATTERN = re.compile(r"(?i)(api[_ -]?key|token|password|secret)\s*[:=]\s*\S+")


def _identity(user: dict) -> tuple[str, str]:
    tenant = user.get("custom:tenant_id")
    actor = user.get("sub")
    if not tenant or not actor:
        raise HTTPException(403, detail={"code": "TENANT_ASSIGNMENT_REQUIRED"})
    return str(tenant), str(actor)


def _require(user: dict, permission: str) -> None:
    groups = {str(value).lower() for value in user.get("cognito:groups", []) or []}
    permissions = {str(value) for value in user.get("permissions", []) or []}
    if (
        groups & {"admin", "administrators", "platform-admin"}
        or permission in permissions
    ):
        return
    raise HTTPException(403, detail={"code": "COPILOT_PERMISSION_REQUIRED"})


def _page(query, page: int, page_size: int):
    total = query.order_by(None).count()
    rows = query.offset((page - 1) * page_size).limit(page_size).all()
    return {"items": rows, "total": total, "page": page, "pageSize": page_size}


class InsightCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    summary: str = Field(min_length=1, max_length=10000)
    insight_type: str = Field(min_length=1, max_length=60)
    conversation_id: str | None = None
    execution_id: str | None = None
    response_reference: str | None = None
    delivery_context: dict = Field(default_factory=dict)
    confidence: str = "INSUFFICIENT_EVIDENCE"
    evidence_snapshots: list[dict] = Field(default_factory=list)
    evidence_freshness: str | None = None
    tags: list[str] = Field(default_factory=list)
    review_date: datetime | None = None


class InsightUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    summary: str | None = Field(default=None, min_length=1, max_length=10000)
    tags: list[str] | None = None
    review_date: datetime | None = None
    status: str | None = None
    version: int = Field(ge=1)


class TemplateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str = Field(default="", max_length=4000)
    category: str
    prompt_body: str = Field(min_length=1, max_length=20000)
    required_context_types: list[str] = Field(default_factory=list)
    expected_response_type: str = "STRUCTURED_DELIVERY"
    evidence_requirement: str = "REQUIRED"
    may_propose_action: bool = False


class TemplateUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=4000)
    prompt_body: str | None = Field(default=None, min_length=1, max_length=20000)
    required_context_types: list[str] | None = None
    expected_response_type: str | None = None
    evidence_requirement: str | None = None
    may_propose_action: bool | None = None
    version: int = Field(ge=1)


def _insight(row):
    return {
        "id": row.id,
        "title": row.title,
        "summary": row.summary,
        "insightType": row.insight_type,
        "conversationId": row.conversation_id,
        "executionId": row.execution_id,
        "responseReference": row.response_reference,
        "deliveryContext": row.delivery_context,
        "confidence": row.confidence,
        "evidenceSnapshots": row.evidence_snapshots,
        "evidenceFreshness": row.evidence_freshness,
        "ownerId": row.owner_id,
        "tags": row.tags,
        "reviewDate": row.review_date,
        "status": row.status,
        "version": row.version,
        "createdAt": row.created_at,
        "updatedAt": row.updated_at,
    }


def _template(row, favorite=False):
    return {
        "id": row.id,
        "templateKey": row.template_key,
        "name": row.name,
        "description": row.description,
        "category": row.category,
        "promptBody": row.prompt_body,
        "requiredContextTypes": row.required_context_types,
        "expectedResponseType": row.expected_response_type,
        "evidenceRequirement": row.evidence_requirement,
        "mayProposeAction": row.may_propose_action,
        "ownerId": row.owner_id,
        "version": row.version,
        "status": row.status,
        "favorite": favorite,
        "createdAt": row.created_at,
        "updatedAt": row.updated_at,
    }


@router.get("/saved-insights")
def list_insights(
    search: str = "",
    status: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tenant, actor = _identity(user)
    _require(user, "copilot.insights.read")
    query = db.query(CopilotSavedInsight).filter(
        CopilotSavedInsight.tenant_id == tenant, CopilotSavedInsight.owner_id == actor
    )
    if search:
        query = query.filter(
            func.lower(CopilotSavedInsight.title).contains(search.lower())
        )
    if status:
        query = query.filter(CopilotSavedInsight.status == status.upper())
    result = _page(
        query.order_by(CopilotSavedInsight.updated_at.desc(), CopilotSavedInsight.id),
        page,
        page_size,
    )
    result["items"] = [_insight(row) for row in result["items"]]
    return result


@router.post("/saved-insights", status_code=201)
def create_insight(
    payload: InsightCreate,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tenant, actor = _identity(user)
    _require(user, "copilot.insights.create")
    now = datetime.now(UTC)
    row = CopilotSavedInsight(
        tenant_id=tenant,
        owner_id=actor,
        created_by=actor,
        updated_by=actor,
        created_at=now,
        updated_at=now,
        status="SAVED",
        version=1,
        **payload.model_dump(),
    )
    db.add(row)
    db.flush()
    append_audit_event(
        db,
        tenant_id=tenant,
        actor_id=actor,
        action="copilot.insight.created",
        target_type="copilot_saved_insight",
        target_id=row.id,
        after={"status": row.status, "evidence_count": len(row.evidence_snapshots)},
    )
    db.commit()
    db.refresh(row)
    return _insight(row)


def _owned_insight(db, tenant, actor, insight_id):
    row = (
        db.query(CopilotSavedInsight)
        .filter_by(id=insight_id, tenant_id=tenant, owner_id=actor)
        .one_or_none()
    )
    if row is None:
        raise HTTPException(404, "Saved insight not found")
    return row


@router.get("/saved-insights/{insight_id}")
def get_insight(
    insight_id: str,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tenant, actor = _identity(user)
    _require(user, "copilot.insights.read")
    return _insight(_owned_insight(db, tenant, actor, insight_id))


@router.patch("/saved-insights/{insight_id}")
def update_insight(
    insight_id: str,
    payload: InsightUpdate,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tenant, actor = _identity(user)
    _require(user, "copilot.insights.update")
    row = _owned_insight(db, tenant, actor, insight_id)
    if row.version != payload.version:
        raise HTTPException(409, detail={"code": "VERSION_CONFLICT"})
    values = payload.model_dump(exclude={"version"}, exclude_none=True)
    if values.get("status") and values["status"] not in INSIGHT_STATUSES:
        raise HTTPException(422, "Invalid insight status")
    for key, value in values.items():
        setattr(row, key, value)
    row.version += 1
    row.updated_by = actor
    row.updated_at = datetime.now(UTC)
    append_audit_event(
        db,
        tenant_id=tenant,
        actor_id=actor,
        action="copilot.insight.updated",
        target_type="copilot_saved_insight",
        target_id=row.id,
        after={"status": row.status, "version": row.version},
    )
    db.commit()
    db.refresh(row)
    return _insight(row)


@router.post("/saved-insights/{insight_id}/archive")
def archive_insight(
    insight_id: str,
    version: int,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return update_insight(
        insight_id, InsightUpdate(status="ARCHIVED", version=version), user, db
    )


@router.get("/prompt-templates")
def list_templates(
    search: str = "",
    category: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tenant, actor = _identity(user)
    _require(user, "copilot.templates.read")
    query = db.query(CopilotPromptTemplate).filter(
        CopilotPromptTemplate.tenant_id == tenant
    )
    if search:
        query = query.filter(
            func.lower(CopilotPromptTemplate.name).contains(search.lower())
        )
    if category:
        query = query.filter(CopilotPromptTemplate.category == category.upper())
    result = _page(
        query.order_by(
            CopilotPromptTemplate.updated_at.desc(), CopilotPromptTemplate.id
        ),
        page,
        page_size,
    )
    favorites = {
        row.template_id
        for row in db.query(CopilotPromptFavorite).filter_by(
            tenant_id=tenant, user_id=actor
        )
    }
    result["items"] = [_template(row, row.id in favorites) for row in result["items"]]
    return result


@router.post("/prompt-templates", status_code=201)
def create_template(
    payload: TemplateCreate,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tenant, actor = _identity(user)
    _require(user, "copilot.templates.manage")
    if payload.category.upper() not in TEMPLATE_CATEGORIES:
        raise HTTPException(422, "Invalid template category")
    if SECRET_PATTERN.search(payload.prompt_body):
        raise HTTPException(422, detail={"code": "SECRET_LIKE_CONTENT"})
    now = datetime.now(UTC)
    row = CopilotPromptTemplate(
        id=str(uuid4()),
        tenant_id=tenant,
        template_key=str(uuid4()),
        owner_id=actor,
        version=1,
        status="DRAFT",
        created_by=actor,
        updated_by=actor,
        created_at=now,
        updated_at=now,
        **{**payload.model_dump(), "category": payload.category.upper()},
    )
    db.add(row)
    db.flush()
    append_audit_event(
        db,
        tenant_id=tenant,
        actor_id=actor,
        action="copilot.template.created",
        target_type="copilot_prompt_template",
        target_id=row.id,
        after={"status": row.status, "version": row.version},
    )
    db.commit()
    db.refresh(row)
    return _template(row)


def _template_row(db, tenant, template_id):
    row = (
        db.query(CopilotPromptTemplate)
        .filter_by(id=template_id, tenant_id=tenant)
        .one_or_none()
    )
    if row is None:
        raise HTTPException(404, "Prompt template not found")
    return row


@router.get("/prompt-templates/{template_id}")
def get_template(
    template_id: str,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tenant, actor = _identity(user)
    _require(user, "copilot.templates.read")
    row = _template_row(db, tenant, template_id)
    favorite = (
        db.query(CopilotPromptFavorite.id)
        .filter_by(tenant_id=tenant, user_id=actor, template_id=row.id)
        .first()
        is not None
    )
    return _template(row, favorite)


@router.patch("/prompt-templates/{template_id}")
def update_template(
    template_id: str,
    payload: TemplateUpdate,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tenant, actor = _identity(user)
    _require(user, "copilot.templates.manage")
    row = _template_row(db, tenant, template_id)
    if row.owner_id != actor or row.status != "DRAFT":
        raise HTTPException(403, "Only the draft owner can edit this template")
    if row.version != payload.version:
        raise HTTPException(409, detail={"code": "VERSION_CONFLICT"})
    values = payload.model_dump(exclude={"version"}, exclude_none=True)
    if SECRET_PATTERN.search(values.get("prompt_body", "")):
        raise HTTPException(422, detail={"code": "SECRET_LIKE_CONTENT"})
    for key, value in values.items():
        setattr(row, key, value)
    row.version += 1
    row.updated_by = actor
    row.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(row)
    return _template(row)


@router.post("/prompt-templates/{template_id}/lifecycle/{transition}")
def transition_template(
    template_id: str,
    transition: str,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tenant, actor = _identity(user)
    _require(user, "copilot.templates.manage")
    row = _template_row(db, tenant, template_id)
    transitions = {
        "submit": ("DRAFT", "PENDING_REVIEW"),
        "approve": ("PENDING_REVIEW", "APPROVED"),
        "publish": ("APPROVED", "PUBLISHED"),
        "supersede": ("PUBLISHED", "SUPERSEDED"),
        "archive": (row.status, "ARCHIVED"),
    }
    if transition not in transitions or row.status != transitions[transition][0]:
        raise HTTPException(409, detail={"code": "INVALID_TRANSITION"})
    if transition in {"approve", "publish"} and row.created_by == actor:
        raise HTTPException(403, detail={"code": "SEPARATION_OF_DUTIES"})
    row.status = transitions[transition][1]
    row.updated_by = actor
    row.updated_at = datetime.now(UTC)
    append_audit_event(
        db,
        tenant_id=tenant,
        actor_id=actor,
        action=f"copilot.template.{transition}",
        target_type="copilot_prompt_template",
        target_id=row.id,
        after={"status": row.status},
    )
    db.commit()
    db.refresh(row)
    return _template(row)


@router.post("/prompt-templates/{template_id}/favorite", status_code=201)
def favorite_template(
    template_id: str,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tenant, actor = _identity(user)
    _require(user, "copilot.templates.read")
    _template_row(db, tenant, template_id)
    row = (
        db.query(CopilotPromptFavorite)
        .filter_by(tenant_id=tenant, user_id=actor, template_id=template_id)
        .one_or_none()
    )
    if row is None:
        row = CopilotPromptFavorite(
            tenant_id=tenant,
            user_id=actor,
            template_id=template_id,
            created_at=datetime.now(UTC),
        )
        db.add(row)
        db.commit()
    return {"favorite": True}


@router.delete("/prompt-templates/{template_id}/favorite", status_code=204)
def unfavorite_template(
    template_id: str,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tenant, actor = _identity(user)
    _require(user, "copilot.templates.read")
    row = (
        db.query(CopilotPromptFavorite)
        .filter_by(tenant_id=tenant, user_id=actor, template_id=template_id)
        .one_or_none()
    )
    if row:
        db.delete(row)
        db.commit()


@router.get("/feedback")
def list_feedback(
    feedback_type: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tenant, actor = _identity(user)
    _require(user, "copilot.feedback.read")
    query = db.query(CopilotFeedback).filter(
        CopilotFeedback.tenant_id == tenant,
        CopilotFeedback.user_id == actor,
    )
    if feedback_type:
        query = query.filter(CopilotFeedback.feedback_type == feedback_type.upper())
    result = _page(
        query.order_by(CopilotFeedback.created_at.desc(), CopilotFeedback.id),
        page,
        page_size,
    )
    result["items"] = [
        {
            "id": row.id,
            "conversationId": row.conversation_id,
            "messageId": row.message_id,
            "traceId": row.trace_id,
            "feedbackType": row.feedback_type,
            "comment": row.comment,
            "submittedAt": row.created_at,
            "status": "RECORDED",
        }
        for row in result["items"]
    ]
    return result
