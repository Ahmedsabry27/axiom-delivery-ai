from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.agents.application_service import AgentIdentity
from app.auth.dependencies import get_current_user
from app.database.dependencies import get_db
from app.database.models.ceremony import Lesson
from app.database.models.delivery import DeliveryEvidence
from app.database.models.integration import IntegrationConnection
from app.database.models.knowledge import (
    KnowledgeDecision,
    KnowledgeTemplate,
)
from app.knowledge_intelligence.service import KnowledgeService

router = APIRouter(prefix="/api/knowledge", tags=["Knowledge Intelligence"])
DB = Annotated[Session, Depends(get_db)]
User = Annotated[dict, Depends(get_current_user)]


def svc(db, u):
    return KnowledgeService(db, AgentIdentity.from_claims(u))


def page(rows, p, size):
    return {
        "items": rows[(p - 1) * size : p * size],
        "total": len(rows),
        "page": p,
        "pageSize": size,
    }


def item_json(x):
    return {
        "id": x.id,
        "title": x.title,
        "type": x.item_type,
        "summary": x.summary,
        "content": x.content,
        "status": x.status,
        "trustStatus": x.trust_status,
        "freshnessStatus": x.freshness_status,
        "accessClassification": x.access_classification,
        "sourceSystem": x.source_system,
        "sourceRecordId": x.source_record_id,
        "sourceUrl": x.source_url,
        "ownerId": x.owner_id,
        "reviewers": x.reviewers,
        "tags": x.tags,
        "context": x.context,
        "contentFingerprint": x.content_fingerprint,
        "currentVersion": x.current_version,
        "evidenceCoverage": x.evidence_coverage,
        "lastSynchronizedAt": x.last_synchronized_at,
        "lastVerifiedAt": x.last_verified_at,
        "nextReviewAt": x.next_review_at,
        "version": x.version,
        "createdAt": x.created_at,
        "updatedAt": x.updated_at,
    }


class ItemIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=500)
    item_type: str
    summary: str = ""
    content: str = ""
    status: str = "DRAFT"
    trust_status: str = "UNVERIFIED"
    freshness_status: str = "UNKNOWN"
    access_classification: str = "INTERNAL"
    source_system: str = "AXIOM"
    source_record_id: str | None = None
    source_url: str | None = None
    owner_id: str | None = None
    reviewers: list[str] = []
    tags: list[str] = []
    context: dict = {}
    evidence_coverage: int | None = None


class ItemPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int
    title: str | None = None
    summary: str | None = None
    content: str | None = None
    status: str | None = None
    trust_status: str | None = None
    freshness_status: str | None = None
    tags: list[str] | None = None


class SearchIn(BaseModel):
    query: str = ""
    types: list[str] = []
    statuses: list[str] = []
    trust: list[str] = []
    freshness: list[str] = []
    page: int = 1
    page_size: int = 25


@router.get("/summary")
def summary(db: DB, user: User):
    rows = svc(db, user).list()

    def known(pred):
        return sum(1 for x in rows if pred(x))

    return {
        "totalActive": known(lambda x: x.status not in {"ARCHIVED", "SUPERSEDED"}),
        "verifiedEvidence": db.query(DeliveryEvidence)
        .filter_by(tenant_id=AgentIdentity.from_claims(user).tenant_id)
        .count(),
        "lessonsAwaitingReview": db.query(Lesson)
        .filter(
            Lesson.tenant_id == AgentIdentity.from_claims(user).tenant_id,
            Lesson.status.in_(["DRAFT", "IN_REVIEW", "REVIEWED"]),
        )
        .count(),
        "recentDecisions": db.query(KnowledgeDecision)
        .filter(
            KnowledgeDecision.tenant_id == AgentIdentity.from_claims(user).tenant_id,
            KnowledgeDecision.status.in_(["APPROVED", "ACTIVE"]),
        )
        .count(),
        "staleItems": known(lambda x: x.freshness_status == "STALE"),
        "issueItems": known(lambda x: x.freshness_status == "SOURCE_UNAVAILABLE"),
        "lastSynchronizedAt": max(
            (x.last_synchronized_at for x in rows if x.last_synchronized_at),
            default=None,
        ),
    }


@router.get("/items")
def items(
    db: DB,
    user: User,
    search: str | None = None,
    item_type: str | None = None,
    status: str | None = None,
    trust: str | None = None,
    freshness: str | None = None,
    p: int = Query(1, alias="page", ge=1),
    size: int = Query(25, alias="page_size", ge=1, le=100),
):
    return page(
        [
            item_json(x)
            for x in svc(db, user).list(search, item_type, status, trust, freshness)
        ],
        p,
        size,
    )


@router.post("/items", status_code=201)
def create(v: ItemIn, db: DB, user: User):
    return item_json(svc(db, user).create(v.model_dump()))


@router.get("/items/{id}")
def detail(id: str, db: DB, user: User):
    return item_json(svc(db, user).visible(id))


@router.patch("/items/{id}")
def update(id: str, v: ItemPatch, db: DB, user: User):
    values = v.model_dump(exclude_none=True)
    expected = values.pop("expected_version")
    return item_json(svc(db, user).update(id, values, expected))


@router.get("/items/{id}/versions")
def versions(id: str, db: DB, user: User):
    return {
        "items": [
            {
                "id": x.id,
                "version": x.version_number,
                "authorId": x.author_id,
                "changeSummary": x.change_summary,
                "reviewStatus": x.review_status,
                "contentFingerprint": x.content_fingerprint,
                "createdAt": x.created_at,
            }
            for x in svc(db, user).versions(id)
        ]
    }


@router.get("/items/{id}/relationships")
def relationships(id: str, db: DB, user: User):
    return {
        "items": [
            {
                "id": x.id,
                "relatedType": x.related_type,
                "relatedId": x.related_id,
                "relationshipType": x.relationship_type,
                "label": x.label,
            }
            for x in svc(db, user).relationships(id)
        ]
    }


@router.get("/items/{id}/evidence")
def item_evidence(id: str, db: DB, user: User):
    refs = svc(db, user).evidence_refs(id)
    ids = [x.evidence_id for x in refs]
    rows = (
        db.query(DeliveryEvidence)
        .filter(
            DeliveryEvidence.tenant_id == AgentIdentity.from_claims(user).tenant_id,
            DeliveryEvidence.id.in_(ids),
        )
        .all()
        if ids
        else []
    )
    return {
        "items": [
            {
                "id": x.id,
                "title": x.title,
                "sourceSystem": x.source_system,
                "summary": x.summary,
                "capturedAt": x.captured_at,
                "contentHash": x.content_hash,
                "sourceUrl": x.source_url,
            }
            for x in rows
        ]
    }


@router.post("/search")
def search(v: SearchIn, db: DB, user: User):
    rows = svc(db, user).list(v.query)
    rows = [
        x
        for x in rows
        if (not v.types or x.item_type in v.types)
        and (not v.statuses or x.status in v.statuses)
        and (not v.trust or x.trust_status in v.trust)
        and (not v.freshness or x.freshness_status in v.freshness)
    ]
    return page(
        [
            {
                **item_json(x),
                "excerpt": x.summary or x.content[:240],
                "matchExplanation": "Authorized title, summary, content, or tag match",
            }
            for x in rows
        ],
        v.page,
        v.page_size,
    )


@router.get("/evidence")
def evidence(db: DB, user: User):
    ident = AgentIdentity.from_claims(user)
    svc(db, user).require("evidence.read")
    rows = (
        db.query(DeliveryEvidence)
        .filter_by(tenant_id=ident.tenant_id)
        .order_by(DeliveryEvidence.captured_at.desc())
        .limit(200)
        .all()
    )
    return {
        "items": [
            {
                "id": x.id,
                "title": x.title,
                "type": x.source_type,
                "sourceSystem": x.source_system,
                "relatedEntity": f"{x.entity_type}:{x.entity_id}",
                "capturedAt": x.captured_at,
                "summary": x.summary,
                "sourceUrl": x.source_url,
                "contentHash": x.content_hash,
                "verificationStatus": "SOURCE_VERIFIED"
                if x.content_hash
                else "UNVERIFIED",
            }
            for x in rows
        ]
    }


@router.get("/evidence/{id}")
def evidence_detail(id: str, db: DB, user: User):
    ident = AgentIdentity.from_claims(user)
    svc(db, user).require("evidence.read")
    x = db.query(DeliveryEvidence).filter_by(tenant_id=ident.tenant_id, id=id).first()
    if not x:
        from fastapi import HTTPException

        raise HTTPException(
            404, {"code": "EVIDENCE_NOT_FOUND", "message": "Evidence was not found"}
        )
    return {
        "id": x.id,
        "title": x.title,
        "type": x.source_type,
        "sourceSystem": x.source_system,
        "relatedEntity": f"{x.entity_type}:{x.entity_id}",
        "capturedAt": x.captured_at,
        "summary": x.summary,
        "sourceUrl": x.source_url,
        "contentHash": x.content_hash,
        "verificationStatus": "SOURCE_VERIFIED" if x.content_hash else "UNVERIFIED",
    }


@router.get("/lessons")
def lessons(db: DB, user: User):
    ident = AgentIdentity.from_claims(user)
    svc(db, user).require("knowledge.read")
    rows = (
        db.query(Lesson)
        .filter_by(tenant_id=ident.tenant_id)
        .order_by(Lesson.updated_at.desc())
        .all()
    )
    return {
        "items": [
            {
                "id": x.id,
                "title": x.title,
                "summary": x.recommendation or x.context,
                "category": x.category,
                "status": x.status,
                "ownerId": x.owner_id,
                "updatedAt": x.updated_at,
                "evidenceCount": len(x.evidence_refs or []),
            }
            for x in rows
        ]
    }


@router.get("/decisions")
def decisions(db: DB, user: User):
    ident = AgentIdentity.from_claims(user)
    svc(db, user).require("knowledge.read")
    rows = (
        db.query(KnowledgeDecision)
        .filter_by(tenant_id=ident.tenant_id)
        .order_by(KnowledgeDecision.updated_at.desc())
        .all()
    )
    return {
        "items": [
            {
                "id": x.id,
                "title": x.title,
                "statement": x.statement,
                "rationale": x.rationale,
                "status": x.status,
                "ownerId": x.owner_id,
                "context": x.context,
                "evidenceIds": x.evidence_ids,
                "version": x.version,
                "updatedAt": x.updated_at,
            }
            for x in rows
        ]
    }


@router.get("/templates")
def templates(db: DB, user: User):
    ident = AgentIdentity.from_claims(user)
    svc(db, user).require("knowledge.read")
    rows = (
        db.query(KnowledgeTemplate)
        .filter_by(tenant_id=ident.tenant_id)
        .order_by(KnowledgeTemplate.name)
        .all()
    )
    return {
        "items": [
            {
                "id": x.id,
                "name": x.name,
                "type": x.template_type,
                "description": x.description,
                "schema": x.schema,
                "templateVersion": x.template_version,
                "status": x.status,
            }
            for x in rows
        ]
    }


@router.get("/sources")
def sources(db: DB, user: User):
    ident = AgentIdentity.from_claims(user)
    svc(db, user).require("knowledge.read")
    rows = (
        db.query(IntegrationConnection)
        .filter_by(tenant_id=ident.tenant_id)
        .order_by(IntegrationConnection.display_name)
        .all()
    )
    return {
        "items": [
            {
                "id": x.id,
                "provider": x.connector_type,
                "name": x.display_name,
                "status": x.status,
                "health": x.health_status,
                "lastVerifiedAt": x.last_verified_at,
                "enabled": x.enabled,
                "lastError": x.last_error_message_safe,
            }
            for x in rows
        ]
    }
