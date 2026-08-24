from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.events import append_audit_event
from app.auth.dependencies import get_current_user
from app.database.dependencies import get_db
from app.database.models.audit import AuditLog
from app.database.models.delivery import CopilotFeedback as CopilotFeedbackRecord
from app.database.models.delivery import (
    CopilotResponseEvidence,
    DeliveryCopilotResponse,
    DeliveryDependency,
    DeliveryPortfolio,
    DeliveryRecommendation,
    DeliverySprint,
    DeliveryWorkItem,
    ProposedAction,
    ProposedActionEvidence,
)
from app.delivery.copilot import classify_delivery_intent, mentioned_entity
from app.delivery.copilot_service import DeliveryCopilotService
from app.delivery.domain import contract_metadata
from app.delivery.metrics import metric_catalogue
from app.delivery.portfolio_service import PortfolioIntelligenceService
from app.delivery.read_service import DeliveryReadService
from app.delivery.repositories import (
    EvidenceRepository,
    FeedbackRepository,
    ProposedActionRepository,
)

router = APIRouter(prefix="/api/delivery", tags=["Delivery Foundation"])


class CopilotFeedback(BaseModel):
    conversation_id: str
    message_id: str
    trace_id: str | None = None
    feedback_type: str = Field(min_length=3, max_length=40)
    comment: str | None = Field(default=None, max_length=1000)


class ProposedActionRequest(BaseModel):
    conversation_id: str
    message_id: str | None = None
    response_id: str | None = None
    sprint_id: str | None = None
    work_item_id: str | None = None
    dependency_id: str | None = None
    recommendation_id: str | None = None
    trace_id: str | None = None
    action_type: str = Field(min_length=3, max_length=80)
    content: str = Field(min_length=1, max_length=10000)
    target: str | None = Field(default=None, max_length=200)
    evidence_ids: list[str] = Field(default_factory=list, max_length=50)
    status: str = "DRAFT"


class CopilotRouteRequest(BaseModel):
    message: str = Field(min_length=1, max_length=10000)
    delivery_context: dict | None = None


class SprintInsightRequest(BaseModel):
    conversation_id: str
    sprint_id: str
    message: str = Field(min_length=1, max_length=10000)


@router.get("/metadata", summary="Get supported delivery-domain metadata")
def delivery_metadata(
    user: dict = Depends(get_current_user), db: Session = Depends(get_db)
):
    tenant_id = user.get("custom:tenant_id", "default")
    portfolio = db.scalar(
        select(DeliveryPortfolio).where(DeliveryPortfolio.tenant_id == tenant_id)
    )
    is_demo = bool(
        portfolio
        and (portfolio.record_metadata or {}).get("data_classification") == "DEMO"
    )
    return {
        **contract_metadata(),
        "features": {
            "mock_delivery_data": False,
            "persistence": True,
            "release_readiness_engine": True,
        },
        "tenant_id": tenant_id,
        "workspace": {
            "is_demo": is_demo,
            "label": "Demo workspace" if is_demo else None,
        },
    }


@router.get("/metric-definitions", summary="Get versioned delivery metric definitions")
def delivery_metric_definitions(user: dict = Depends(get_current_user)):
    del user
    return {"items": metric_catalogue()}


@router.get("/health", summary="Check the delivery foundation API")
def delivery_health(user: dict = Depends(get_current_user)):
    return {
        "status": "healthy",
        "tenant_id": user.get("custom:tenant_id", "default"),
        "persistence": "database",
    }


@router.get("/command-center", summary="Get tenant-scoped delivery command center")
def delivery_command_center(
    context_id: str | None = None,
    user: dict = Depends(get_current_user), db: Session = Depends(get_db)
):
    return DeliveryReadService(
        db, user["custom:tenant_id"], user["sub"]
    ).command_center(context_id=context_id)


@router.get("/my-day", summary="Get tenant-scoped personal delivery agenda")
def delivery_my_day(
    user: dict = Depends(get_current_user), db: Session = Depends(get_db)
):
    return DeliveryReadService(db, user["custom:tenant_id"], user["sub"]).my_day()


@router.get("/attention-items", summary="List prioritised attention items")
def delivery_attention_items(
    user: dict = Depends(get_current_user), db: Session = Depends(get_db)
):
    data = DeliveryReadService(
        db, user["custom:tenant_id"], user["sub"]
    ).command_center()
    return {
        "tenant_id": user["custom:tenant_id"],
        "items": data["attentionItems"],
        "scoring_version": "1.0",
    }


@router.get("/portfolio", summary="Get tenant-scoped Portfolio Intelligence workspace")
def portfolio_workspace(
    user: dict = Depends(get_current_user), db: Session = Depends(get_db)
):
    return PortfolioIntelligenceService(
        db, user["custom:tenant_id"], user["sub"]
    ).workspace()


@router.get("/recommendations", summary="List evidence-backed recommendations")
def delivery_recommendations(
    user: dict = Depends(get_current_user), db: Session = Depends(get_db)
):
    data = DeliveryReadService(
        db, user["custom:tenant_id"], user["sub"]
    ).command_center()
    return {
        "tenant_id": user["custom:tenant_id"],
        "items": data["recommendations"],
        "external_writes": False,
    }


@router.post(
    "/copilot/route", summary="Classify a delivery question without invoking a model"
)
def route_copilot_question(
    payload: CopilotRouteRequest, user: dict = Depends(get_current_user)
):
    route = classify_delivery_intent(payload.message).to_dict()
    entity = mentioned_entity(payload.message)
    return {
        "trace_id": str(uuid4()),
        "tenant_id": user.get("custom:tenant_id", "default"),
        "route": route,
        "resolved_context": payload.delivery_context or entity,
        "external_writes": False,
    }


@router.post(
    "/copilot/sprint-insight", summary="Persist an evidence-backed sprint answer"
)
def sprint_copilot_insight(
    payload: SprintInsightRequest,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        return DeliveryCopilotService(
            db, user["custom:tenant_id"], user["sub"]
        ).sprint_insight(
            payload.conversation_id,
            payload.sprint_id,
            payload.message,
        )
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post(
    "/copilot/feedback", status_code=202, summary="Record non-blocking Copilot feedback"
)
def submit_copilot_feedback(
    payload: CopilotFeedback,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tenant_id = user.get("custom:tenant_id", "default")
    record = CopilotFeedbackRecord(
        **payload.model_dump(), tenant_id=tenant_id, user_id=user.get("sub")
    )
    FeedbackRepository(db, tenant_id).add(record)
    db.commit()
    return {"id": record.id, "status": "recorded"}


@router.post(
    "/proposed-actions", status_code=201, summary="Create an internal action draft"
)
def create_proposed_action(
    payload: ProposedActionRequest,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    allowed = {"DRAFT", "PROPOSED", "PENDING_APPROVAL"}
    if payload.status not in allowed:
        raise HTTPException(422, "AX-EP03 actions must stop before execution")
    tenant_id = user.get("custom:tenant_id", "default")
    try:
        evidence = EvidenceRepository(db, tenant_id).require_authorized_ids(
            payload.evidence_ids
        )
    except ValueError as exc:
        append_audit_event(
            db,
            tenant_id=tenant_id,
            actor_id=user["sub"],
            action="delivery.proposed_action.evidence_rejected",
            target_type="conversation",
            target_id=payload.conversation_id,
            correlation_id=payload.trace_id,
            metadata={"requested_evidence_count": len(payload.evidence_ids)},
        )
        db.commit()
        raise HTTPException(404, "Evidence not found or inaccessible") from exc
    links = (
        (DeliveryCopilotResponse, payload.response_id),
        (DeliverySprint, payload.sprint_id),
        (DeliveryWorkItem, payload.work_item_id),
        (DeliveryDependency, payload.dependency_id),
        (DeliveryRecommendation, payload.recommendation_id),
    )
    if any(
        identifier
        and db.scalar(
            select(model.id).where(model.tenant_id == tenant_id, model.id == identifier)
        )
        is None
        for model, identifier in links
    ):
        raise HTTPException(404, "Linked delivery record not found or inaccessible")
    if payload.response_id:
        response = db.scalar(
            select(DeliveryCopilotResponse).where(
                DeliveryCopilotResponse.tenant_id == tenant_id,
                DeliveryCopilotResponse.id == payload.response_id,
                DeliveryCopilotResponse.conversation_id == payload.conversation_id,
            )
        )
        authorized_response_evidence = {
            item[0]
            for item in db.execute(
                select(CopilotResponseEvidence.evidence_id).where(
                    CopilotResponseEvidence.tenant_id == tenant_id,
                    CopilotResponseEvidence.response_id == payload.response_id,
                )
            )
        }
        if response is None or not set(payload.evidence_ids).issubset(
            authorized_response_evidence
        ):
            raise HTTPException(
                422, "Proposal evidence must come from the linked Copilot response"
            )
    record = ProposedAction(
        tenant_id=tenant_id,
        conversation_id=payload.conversation_id,
        message_id=payload.message_id,
        response_id=payload.response_id,
        sprint_id=payload.sprint_id,
        work_item_id=payload.work_item_id,
        dependency_id=payload.dependency_id,
        recommendation_id=payload.recommendation_id,
        trace_id=payload.trace_id,
        action_type=payload.action_type,
        title=payload.content[:255],
        description=payload.content,
        content=payload.content,
        origin="AI" if payload.response_id else "USER",
        requester_id=user.get("sub"),
        target_entity_type="DELIVERY_CONTEXT",
        target_system="INTERNAL",
        payload={"content": payload.content, "target": payload.target},
        original_payload={"content": payload.content, "target": payload.target},
        target=payload.target,
        status=payload.status,
        created_by=user.get("sub"),
        approval_required=True,
    )
    ProposedActionRepository(db, tenant_id).add(record)
    db.flush()
    for item in evidence:
        db.add(
            ProposedActionEvidence(
                tenant_id=tenant_id, proposed_action_id=record.id, evidence_id=item.id
            )
        )
    append_audit_event(
        db,
        tenant_id=tenant_id,
        actor_id=user["sub"],
        action="delivery.proposed_action.created",
        target_type="proposed_action",
        target_id=record.id,
        correlation_id=payload.trace_id,
        metadata={
            "response_id": payload.response_id,
            "evidence_ids": payload.evidence_ids,
            "status": record.status,
        },
    )
    db.commit()
    return {
        "id": record.id,
        "tenant_id": tenant_id,
        "status": record.status,
        "approval_required": True,
        "external_execution": False,
        "response_id": record.response_id,
        "trace_id": record.trace_id,
        "evidence_ids": payload.evidence_ids,
    }


@router.get(
    "/proposed-actions/{action_id}", summary="Retrieve a tenant-scoped proposed action"
)
def get_proposed_action(
    action_id: str,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    record = ProposedActionRepository(db, user.get("custom:tenant_id", "default")).get(
        action_id
    )
    if not record:
        raise HTTPException(404, "Proposed action not found")
    evidence_ids = [
        item[0]
        for item in db.execute(
            select(ProposedActionEvidence.evidence_id).where(
                ProposedActionEvidence.tenant_id == record.tenant_id,
                ProposedActionEvidence.proposed_action_id == record.id,
            )
        )
    ]
    return {
        "id": record.id,
        "status": record.status,
        "action_type": record.action_type,
        "content": record.content,
        "approval_required": record.approval_required,
        "conversation_id": record.conversation_id,
        "message_id": record.message_id,
        "response_id": record.response_id,
        "sprint_id": record.sprint_id,
        "work_item_id": record.work_item_id,
        "dependency_id": record.dependency_id,
        "recommendation_id": record.recommendation_id,
        "trace_id": record.trace_id,
        "evidence_ids": evidence_ids,
    }


@router.get("/evidence/{evidence_id}", summary="Retrieve authorized delivery evidence")
def get_delivery_evidence(
    evidence_id: str,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    record = EvidenceRepository(db, user.get("custom:tenant_id", "default")).get(
        evidence_id
    )
    if not record:
        raise HTTPException(404, "Evidence not found")
    return {
        "id": record.id,
        "entity_type": record.entity_type,
        "entity_id": record.entity_id,
        "title": record.title,
        "summary": record.summary,
        "captured_at": record.captured_at,
        "source_updated_at": record.source_updated_at,
    }


@router.get("/audit-events", summary="Inspect tenant-scoped delivery audit evidence")
def delivery_audit_events(
    trace_id: str,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    records = list(
        db.scalars(
            select(AuditLog)
            .where(
                AuditLog.tenant_id == user["custom:tenant_id"],
                AuditLog.actor_id == user["sub"],
                AuditLog.correlation_id == trace_id,
                AuditLog.action.like("delivery.%"),
            )
            .order_by(AuditLog.id)
        )
    )
    return {
        "trace_id": trace_id,
        "items": [
            {
                "id": item.id,
                "action": item.action,
                "target_type": item.target_type,
                "target_id": item.target_id,
                "created_at": item.created_at,
            }
            for item in records
        ],
    }
