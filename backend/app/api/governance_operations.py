from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.agents.application_service import AgentIdentity
from app.audit.events import append_audit_event
from app.auth.dependencies import get_current_user
from app.database.dependencies import get_db
from app.database.models.audit import AuditLog
from app.database.models.delivery import ProposedAction
from app.database.models.governance import (
    AccessReview,
    AIIncident,
    Budget,
    BudgetAlert,
    BudgetOverride,
    BudgetReservation,
    EvaluationDataset,
    EvaluationResult,
    EvaluationRun,
    GovernedModel,
    ModelPrice,
    RetentionPolicy,
    UsageRecord,
)
from app.governance.service import (
    HIGH_RISK_PERMISSIONS,
    PERMISSION_CATALOGUE,
    ROLE_MATRIX,
    AuditIntegrityService,
    EvaluationRunnerService,
    governance_overview,
    governance_policy_service,
    require,
)
from app.models.runtime_execution import RuntimeExecution, RuntimeExecutionEvent

router = APIRouter(tags=["Governance and AI Operations"])
Database = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[dict, Depends(get_current_user)]


def identity(user: dict) -> AgentIdentity:
    return AgentIdentity.from_claims(user)


def page(items: list, total: int, page_number: int, page_size: int) -> dict:
    return {"items": items, "total": total, "page": page_number, "page_size": page_size}


def fields(row, names: tuple[str, ...]) -> dict:
    result = {}
    for name in names:
        value = getattr(row, name)
        if isinstance(value, datetime):
            value = value.isoformat()
        elif isinstance(value, Decimal):
            value = str(value)
        result[name] = value
    return result


POLICY_FIELDS = (
    "id",
    "tenant_id",
    "policy_key",
    "name",
    "description",
    "category",
    "version",
    "status",
    "priority",
    "conditions",
    "effect",
    "reason_codes",
    "effective_from",
    "effective_until",
    "review_date",
    "created_by",
    "approved_by",
    "created_at",
    "activated_at",
    "retired_at",
    "supersedes_id",
    "state_version",
)
MODEL_FIELDS = (
    "id",
    "tenant_id",
    "model_key",
    "provider",
    "provider_model_id",
    "display_name",
    "model_family",
    "capabilities",
    "approved_use_cases",
    "prohibited_use_cases",
    "allowed_data_classifications",
    "allowed_regions",
    "status",
    "context_limit",
    "configuration_version",
    "effective_from",
    "effective_until",
    "created_by",
    "created_at",
)


class PolicyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    policy_key: str | None = Field(None, max_length=120)
    name: str = Field(min_length=3, max_length=200)
    description: str = Field("", max_length=2000)
    category: str
    priority: int = Field(100, ge=0, le=1000)
    conditions: dict[str, Any] = Field(default_factory=dict)
    effect: dict[str, Any] = Field(default_factory=dict)
    reason_codes: list[str] = Field(default_factory=list, max_length=20)
    review_date: datetime | None = None
    global_scope: bool = False
    supersedes_id: str | None = None


class PolicyUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(None, min_length=3, max_length=200)
    description: str | None = Field(None, max_length=2000)
    priority: int | None = Field(None, ge=0, le=1000)
    conditions: dict[str, Any] | None = None
    effect: dict[str, Any] | None = None
    reason_codes: list[str] | None = Field(None, max_length=20)
    review_date: datetime | None = None


class SimulationPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scenario: dict[str, Any] = Field(default_factory=dict)


@router.get("/api/governance/overview")
def overview(db: Database, user: CurrentUser):
    return governance_overview(db, identity(user))


@router.get("/api/governance/policies")
def policies(db: Database, user: CurrentUser):
    rows = governance_policy_service.list(db, identity(user))
    return {"items": [fields(row, POLICY_FIELDS) for row in rows], "total": len(rows)}


@router.post("/api/governance/policies", status_code=201)
def create_policy(payload: PolicyCreate, db: Database, user: CurrentUser):
    return fields(
        governance_policy_service.create(db, identity(user), payload.model_dump()),
        POLICY_FIELDS,
    )


@router.get("/api/governance/policies/{policy_id}")
def policy_detail(policy_id: str, db: Database, user: CurrentUser):
    row = next(
        (
            item
            for item in governance_policy_service.list(db, identity(user))
            if item.id == policy_id
        ),
        None,
    )
    if row is None:
        raise HTTPException(
            404, {"code": "POLICY_NOT_FOUND", "message": "Policy not found"}
        )
    return fields(row, POLICY_FIELDS)


@router.patch("/api/governance/policies/{policy_id}")
def update_policy(
    policy_id: str, payload: PolicyUpdate, db: Database, user: CurrentUser
):
    row = governance_policy_service.update_draft(
        db, identity(user), policy_id, payload.model_dump(exclude_unset=True)
    )
    return fields(row, POLICY_FIELDS)


@router.post("/api/governance/policies/{policy_id}/submit")
def submit_policy(policy_id: str, db: Database, user: CurrentUser):
    return fields(
        governance_policy_service.submit(db, identity(user), policy_id), POLICY_FIELDS
    )


@router.post("/api/governance/policies/{policy_id}/activate")
def activate_policy(policy_id: str, db: Database, user: CurrentUser):
    return fields(
        governance_policy_service.activate(db, identity(user), policy_id), POLICY_FIELDS
    )


@router.post("/api/governance/policies/{policy_id}/retire")
def retire_policy(policy_id: str, db: Database, user: CurrentUser):
    return fields(
        governance_policy_service.retire(db, identity(user), policy_id), POLICY_FIELDS
    )


@router.post("/api/governance/policies/{policy_id}/simulate")
def simulate_policy(
    policy_id: str, payload: SimulationPayload, db: Database, user: CurrentUser
):
    return governance_policy_service.simulate(
        db, identity(user), policy_id, payload.scenario
    )


@router.get("/api/governance/permissions")
def permission_catalogue(user: CurrentUser):
    ctx = identity(user)
    require(ctx, "policies.manage")
    return {
        "items": [
            {
                "key": key,
                "description": description,
                "risk": risk,
                "resource": resource,
                "roles": sorted(
                    role
                    for role, permissions in ROLE_MATRIX.items()
                    if key in permissions
                ),
                "assigned_user_count": None,
                "last_reviewed": None,
                "high_risk": key in HIGH_RISK_PERMISSIONS,
            }
            for key, description, risk, resource in PERMISSION_CATALOGUE
        ],
        "sources": ["claims catalogue", "role matrix"],
    }


@router.get("/api/governance/roles")
def roles(user: CurrentUser):
    ctx = identity(user)
    require(ctx, "policies.manage")
    return {
        "items": [
            {
                "role": role,
                "permissions": sorted(permissions),
                "high_risk_permissions": sorted(permissions & HIGH_RISK_PERMISSIONS),
            }
            for role, permissions in ROLE_MATRIX.items()
        ]
    }


class AccessReviewCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=3, max_length=200)
    scope: dict[str, Any]
    reviewer_id: str
    access_items: list[dict[str, Any]] = Field(default_factory=list, max_length=500)
    recommendation: str | None = Field(None, max_length=2000)
    evidence: list[dict[str, Any]] = Field(default_factory=list, max_length=100)
    due_at: datetime


@router.get("/api/governance/access-reviews")
def access_reviews(
    db: Database,
    user: CurrentUser,
    page_number: int = Query(1, alias="page", ge=1),
    page_size: int = Query(50, ge=1, le=100),
):
    ctx = identity(user)
    require(ctx, "policies.manage")
    query = db.query(AccessReview).filter_by(tenant_id=ctx.tenant_id)
    total = query.count()
    rows = (
        query.order_by(AccessReview.due_at)
        .offset((page_number - 1) * page_size)
        .limit(page_size)
        .all()
    )
    names = (
        "id",
        "name",
        "scope",
        "reviewer_id",
        "access_items",
        "recommendation",
        "decision",
        "evidence",
        "due_at",
        "status",
        "created_by",
        "created_at",
    )
    return page([fields(row, names) for row in rows], total, page_number, page_size)


@router.post("/api/governance/access-reviews", status_code=201)
def create_access_review(payload: AccessReviewCreate, db: Database, user: CurrentUser):
    ctx = identity(user)
    require(ctx, "policies.manage", human=True)
    row = AccessReview(
        tenant_id=ctx.tenant_id,
        created_by=ctx.actor_id,
        created_at=datetime.now(UTC),
        status="OPEN",
        **payload.model_dump(),
    )
    db.add(row)
    db.flush()
    append_audit_event(
        db,
        tenant_id=ctx.tenant_id,
        actor_id=ctx.actor_id,
        action="access_review.created",
        target_type="access_review",
        target_id=row.id,
    )
    db.commit()
    db.refresh(row)
    return fields(row, ("id", "name", "status", "due_at", "reviewer_id"))


def audit_query(
    db: Session,
    ctx: AgentIdentity,
    trace_id: str | None = None,
    event_type: str | None = None,
    result: str | None = None,
):
    require(ctx, "audit.read")
    query = db.query(AuditLog).filter_by(tenant_id=ctx.tenant_id)
    if trace_id:
        query = query.filter(AuditLog.trace_id == trace_id)
    if event_type:
        query = query.filter(AuditLog.event_type == event_type)
    if result:
        query = query.filter(AuditLog.result == result)
    return query


def audit_item(row: AuditLog, sensitive: bool) -> dict:
    metadata = (
        row.metadata_json
        if sensitive
        else ({"redacted": True} if row.metadata_json else None)
    )
    return {
        "event_id": row.event_id or str(row.id),
        "trace_id": row.trace_id or row.correlation_id,
        "tenant_id": row.tenant_id,
        "timestamp": (row.created_at or row.timestamp).isoformat(),
        "actor_type": row.actor_type or "user",
        "actor_id": row.actor_id,
        "event_type": row.event_type,
        "resource_type": row.target_type or row.entity,
        "resource_id": row.target_id or row.entity_id,
        "action": row.action,
        "result": row.result or "SUCCESS",
        "policy_id": row.policy_id,
        "policy_version": row.policy_version,
        "agent_id": row.agent_id,
        "model_id": row.model_id,
        "provider": row.provider,
        "tool_id": row.tool_id,
        "execution_id": row.execution_id,
        "approval_id": row.approval_id,
        "safe_metadata": metadata,
        "previous_hash": row.previous_hash,
        "integrity_hash": row.integrity_hash,
        "severity": row.severity or "INFO",
    }


@router.get("/api/audit/events")
def audit_events(
    db: Database,
    user: CurrentUser,
    trace_id: str | None = None,
    event_type: str | None = None,
    result: str | None = None,
    page_number: int = Query(1, alias="page", ge=1),
    page_size: int = Query(50, ge=1, le=100),
):
    ctx = identity(user)
    query = audit_query(db, ctx, trace_id, event_type, result)
    total = query.count()
    rows = (
        query.order_by(AuditLog.id.desc())
        .offset((page_number - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return page(
        [audit_item(row, ctx.allows("audit.read_sensitive")) for row in rows],
        total,
        page_number,
        page_size,
    )


@router.get("/api/audit/events/{event_id}")
def audit_event(event_id: str, db: Database, user: CurrentUser):
    ctx = identity(user)
    require(ctx, "audit.read")
    row = (
        db.query(AuditLog).filter_by(tenant_id=ctx.tenant_id, event_id=event_id).first()
    )
    if row is None:
        raise HTTPException(
            404, {"code": "AUDIT_EVENT_NOT_FOUND", "message": "Audit event not found"}
        )
    item = audit_item(row, ctx.allows("audit.read_sensitive"))
    item["related_events"] = []
    return item


@router.post("/api/audit/verify")
def verify_audit(db: Database, user: CurrentUser):
    return AuditIntegrityService.verify(db, identity(user))


@router.post("/api/audit/export")
def export_audit(
    response: Response,
    db: Database,
    user: CurrentUser,
    limit: int = Query(100, ge=1, le=1000),
    trace_id: str | None = None,
):
    ctx = identity(user)
    require(ctx, "audit.export", human=True)
    rows = (
        audit_query(db, ctx, trace_id=trace_id)
        .order_by(AuditLog.id.desc())
        .limit(limit)
        .all()
    )
    append_audit_event(
        db,
        tenant_id=ctx.tenant_id,
        actor_id=ctx.actor_id,
        action="audit.exported",
        target_type="audit_export",
        target_id=str(len(rows)),
        metadata={"limit": limit, "trace_id": trace_id},
    )
    db.commit()
    response.headers["Content-Disposition"] = 'attachment; filename="audit-export.json"'
    return {
        "items": [audit_item(row, ctx.allows("audit.read_sensitive")) for row in rows],
        "count": len(rows),
        "limited": len(rows) == limit,
    }


class ModelCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    model_key: str
    provider: str
    provider_model_id: str
    display_name: str
    model_family: str
    capabilities: list[str] = Field(default_factory=list)
    approved_use_cases: list[str] = Field(default_factory=list)
    prohibited_use_cases: list[str] = Field(default_factory=list)
    allowed_data_classifications: list[str] = Field(default_factory=list)
    allowed_regions: list[str] = Field(default_factory=list)
    status: str = "DRAFT"
    context_limit: int | None = Field(None, gt=0)


class ModelUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    display_name: str | None = None
    capabilities: list[str] | None = None
    approved_use_cases: list[str] | None = None
    prohibited_use_cases: list[str] | None = None
    allowed_data_classifications: list[str] | None = None
    allowed_regions: list[str] | None = None
    context_limit: int | None = Field(None, gt=0)
    status: str | None = None


@router.get("/api/models")
def models(db: Database, user: CurrentUser):
    ctx = identity(user)
    require(ctx, "models.manage")
    rows = (
        db.query(GovernedModel)
        .filter(
            (GovernedModel.tenant_id == ctx.tenant_id)
            | (GovernedModel.tenant_id.is_(None))
        )
        .order_by(GovernedModel.display_name)
        .all()
    )
    return {"items": [fields(row, MODEL_FIELDS) for row in rows], "total": len(rows)}


@router.get("/api/models/catalog")
def model_catalog(user: CurrentUser):
    ctx = identity(user)
    require(ctx, "models.manage")
    return {
        "items": [
            {
                "provider": "openai",
                "name": "OpenAI",
                "availability": "CONFIGURED_BY_ENVIRONMENT",
                "credentials": "hidden",
                "adapter": "OpenAIProvider",
            },
            {
                "provider": "bedrock",
                "name": "AWS Bedrock",
                "availability": "CONFIGURED_BY_ENVIRONMENT",
                "credentials": "hidden",
                "adapter": "BedrockProvider",
            },
            {
                "provider": "test",
                "name": "Controlled test provider",
                "availability": "TEST_ONLY",
                "credentials": "not_required",
                "adapter": "TestProvider",
            },
        ]
    }


@router.get("/api/models/summary")
def model_summary(db: Database, user: CurrentUser):
    ctx = identity(user)
    require(ctx, "models.manage")
    rows = (
        db.query(GovernedModel)
        .filter(
            (GovernedModel.tenant_id == ctx.tenant_id)
            | (GovernedModel.tenant_id.is_(None))
        )
        .all()
    )
    usage = db.query(UsageRecord).filter_by(tenant_id=ctx.tenant_id).all()
    incidents = db.query(AIIncident).filter_by(tenant_id=ctx.tenant_id).all()
    return {
        "total": len(rows),
        "active": sum(row.status == "ACTIVE" for row in rows),
        "awaitingApproval": sum(row.status in {"DRAFT", "IN_REVIEW"} for row in rows),
        "blocked": sum(row.status == "BLOCKED" for row in rows),
        "deprecated": sum(row.status == "DEPRECATED" for row in rows),
        "calls": len(usage),
        "totalCost": str(sum((row.total_cost or Decimal("0")) for row in usage)),
        "openIncidents": sum(
            row.status not in {"RESOLVED", "CLOSED"} for row in incidents
        ),
        "currency": next((row.currency for row in usage if row.currency), None),
        "period": "all persisted tenant records",
        "source": "governed_models, ai_usage_records, ai_incidents",
    }


@router.post("/api/models", status_code=201)
def create_model(payload: ModelCreate, db: Database, user: CurrentUser):
    ctx = identity(user)
    require(ctx, "models.manage", human=True)
    version = (
        db.query(func.max(GovernedModel.configuration_version))
        .filter_by(tenant_id=ctx.tenant_id, model_key=payload.model_key)
        .scalar()
        or 0
    ) + 1
    if payload.status == "ACTIVE":
        raise HTTPException(
            422,
            {
                "code": "MODEL_ACTIVATION_REQUIRES_APPROVAL",
                "message": "Create models as draft or approved",
            },
        )
    row = GovernedModel(
        tenant_id=ctx.tenant_id,
        configuration_version=version,
        created_by=ctx.actor_id,
        created_at=datetime.now(UTC),
        **payload.model_dump(),
    )
    db.add(row)
    db.flush()
    append_audit_event(
        db,
        tenant_id=ctx.tenant_id,
        actor_id=ctx.actor_id,
        action="model.created",
        target_type="governed_model",
        target_id=row.id,
        model_id=row.id,
        provider=row.provider,
    )
    db.commit()
    db.refresh(row)
    return fields(row, MODEL_FIELDS)


@router.get("/api/models/{model_id}")
def model_detail(model_id: str, db: Database, user: CurrentUser):
    ctx = identity(user)
    require(ctx, "models.manage")
    row = (
        db.query(GovernedModel).filter_by(id=model_id, tenant_id=ctx.tenant_id).first()
    )
    if row is None:
        raise HTTPException(
            404, {"code": "MODEL_NOT_FOUND", "message": "Model not found"}
        )
    item = fields(row, MODEL_FIELDS)
    item["pricing"] = [
        fields(
            price,
            (
                "id",
                "version",
                "input_cost_per_million",
                "output_cost_per_million",
                "currency",
                "effective_from",
                "effective_until",
            ),
        )
        for price in db.query(ModelPrice)
        .filter_by(model_id=row.id)
        .order_by(ModelPrice.version.desc())
        .all()
    ]
    return item


def _model_row(model_id: str, db: Session, ctx: AgentIdentity) -> GovernedModel:
    row = (
        db.query(GovernedModel)
        .filter(
            GovernedModel.id == model_id,
            (GovernedModel.tenant_id == ctx.tenant_id)
            | (GovernedModel.tenant_id.is_(None)),
        )
        .first()
    )
    if row is None:
        raise HTTPException(
            404, {"code": "MODEL_NOT_FOUND", "message": "Model not found"}
        )
    return row


@router.get("/api/models/{model_id}/capabilities")
def model_capabilities(model_id: str, db: Database, user: CurrentUser):
    ctx = identity(user)
    require(ctx, "models.manage")
    row = _model_row(model_id, db, ctx)
    return {
        "items": [
            {
                "capability": item,
                "providerDeclared": True,
                "axiomVerified": None,
                "verificationState": "NOT_EVALUATED",
            }
            for item in (row.capabilities or [])
        ],
        "limitations": "Provider declaration is not internal verification",
    }


@router.get("/api/models/{model_id}/pricing")
def model_pricing(model_id: str, db: Database, user: CurrentUser):
    ctx = identity(user)
    require(ctx, "models.manage")
    row = _model_row(model_id, db, ctx)
    prices = (
        db.query(ModelPrice)
        .filter_by(model_id=row.id)
        .order_by(ModelPrice.version.desc())
        .all()
    )
    return {
        "items": [
            fields(
                price,
                (
                    "id",
                    "version",
                    "input_cost_per_million",
                    "output_cost_per_million",
                    "currency",
                    "effective_from",
                    "effective_until",
                ),
            )
            for price in prices
        ],
        "decimalSafe": True,
    }


@router.get("/api/models/{model_id}/routing")
def model_routing(model_id: str, db: Database, user: CurrentUser):
    ctx = identity(user)
    require(ctx, "models.manage")
    row = _model_row(model_id, db, ctx)
    eligible = (
        row.status == "ACTIVE"
        and bool(row.allowed_data_classifications)
        and bool(row.allowed_regions)
    )
    return {
        "decision": "ALLOW" if eligible else "BLOCK",
        "eligible": eligible,
        "reasonCodes": ["ACTIVE_ALLOWLISTED"]
        if eligible
        else ["MODEL_NOT_ACTIVE_OR_INCOMPLETE"],
        "approvedUseCases": row.approved_use_cases,
        "prohibitedUseCases": row.prohibited_use_cases,
        "dataClassifications": row.allowed_data_classifications,
        "regions": row.allowed_regions,
        "fallback": "Evaluated by BudgetEnforcementService",
        "frontendAuthoritative": False,
    }


@router.get("/api/models/{model_id}/evaluations")
def model_evaluations(model_id: str, db: Database, user: CurrentUser):
    ctx = identity(user)
    require(ctx, "models.manage")
    row = _model_row(model_id, db, ctx)
    runs = (
        db.query(EvaluationRun)
        .filter_by(tenant_id=ctx.tenant_id, model_id=row.id)
        .order_by(EvaluationRun.started_at.desc())
        .all()
    )
    return {
        "items": [
            fields(
                run,
                (
                    "id",
                    "dataset_id",
                    "dataset_version",
                    "status",
                    "scores",
                    "failures",
                    "started_at",
                    "completed_at",
                ),
            )
            for run in runs
        ]
    }


@router.get("/api/models/{model_id}/usage")
def model_usage(model_id: str, db: Database, user: CurrentUser):
    ctx = identity(user)
    require(ctx, "models.manage")
    row = _model_row(model_id, db, ctx)
    usage = (
        db.query(UsageRecord).filter_by(tenant_id=ctx.tenant_id, model_id=row.id).all()
    )
    total_cost = sum((item.total_cost or Decimal("0")) for item in usage)
    return {
        "requests": len(usage),
        "successful": sum(item.status == "COMPLETED" for item in usage),
        "failed": sum(item.status == "FAILED" for item in usage),
        "inputTokens": sum(item.input_tokens or 0 for item in usage),
        "outputTokens": sum(item.output_tokens or 0 for item in usage),
        "totalCost": str(total_cost),
        "currency": next((item.currency for item in usage if item.currency), None),
        "averageLatencyMs": round(
            sum(item.latency_ms or 0 for item in usage) / len(usage), 2
        )
        if usage
        else None,
        "source": "ai_usage_records",
    }


@router.get("/api/models/{model_id}/incidents")
def model_incidents(model_id: str, db: Database, user: CurrentUser):
    ctx = identity(user)
    require(ctx, "models.manage")
    row = _model_row(model_id, db, ctx)
    incidents = (
        db.query(AIIncident)
        .filter_by(tenant_id=ctx.tenant_id)
        .order_by(AIIncident.created_at.desc())
        .all()
    )
    related = [
        item
        for item in incidents
        if row.id in (item.affected_services or [])
        or row.provider_model_id in (item.affected_services or [])
    ]
    return {
        "items": [
            fields(
                item,
                (
                    "id",
                    "incident_type",
                    "severity",
                    "status",
                    "owner_id",
                    "impact_summary",
                    "created_at",
                    "updated_at",
                ),
            )
            for item in related
        ]
    }


@router.get("/api/models/{model_id}/versions")
def model_versions(model_id: str, db: Database, user: CurrentUser):
    ctx = identity(user)
    require(ctx, "models.manage")
    row = _model_row(model_id, db, ctx)
    versions = (
        db.query(GovernedModel)
        .filter_by(tenant_id=row.tenant_id, model_key=row.model_key)
        .order_by(GovernedModel.configuration_version.desc())
        .all()
    )
    return {"items": [fields(item, MODEL_FIELDS) for item in versions]}


@router.get("/api/models/{model_id}/activity")
def model_activity(model_id: str, db: Database, user: CurrentUser):
    ctx = identity(user)
    require(ctx, "models.manage")
    row = _model_row(model_id, db, ctx)
    events = (
        db.query(AuditLog)
        .filter_by(tenant_id=ctx.tenant_id, model_id=row.id)
        .order_by(AuditLog.id.desc())
        .limit(100)
        .all()
    )
    return {
        "items": [
            {
                "id": event.id,
                "event": event.action,
                "actorId": event.actor_id,
                "occurredAt": (event.created_at or event.timestamp).isoformat()
                if (event.created_at or event.timestamp)
                else None,
                "correlationId": event.correlation_id,
            }
            for event in events
        ]
    }


@router.get("/api/models/{model_id}/access")
def model_access(model_id: str, db: Database, user: CurrentUser):
    ctx = identity(user)
    require(ctx, "models.manage")
    row = _model_row(model_id, db, ctx)
    return {
        "tenantScope": row.tenant_id or "GLOBAL",
        "createdBy": row.created_by,
        "dataClassifications": row.allowed_data_classifications,
        "regions": row.allowed_regions,
        "permissions": ["models.manage"],
        "credentialManagement": "Integration and secret-management boundary",
    }


class ModelPriceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int = Field(ge=1)
    input_cost_per_million: Decimal = Field(ge=0)
    output_cost_per_million: Decimal = Field(ge=0)
    currency: str = Field(min_length=3, max_length=3)
    effective_from: datetime
    effective_until: datetime | None = None


@router.post("/api/models/{model_id}/prices", status_code=201)
def create_model_price(
    model_id: str, payload: ModelPriceCreate, db: Database, user: CurrentUser
):
    ctx = identity(user)
    require(ctx, "models.manage", human=True)
    model = (
        db.query(GovernedModel).filter_by(id=model_id, tenant_id=ctx.tenant_id).first()
    )
    if model is None:
        raise HTTPException(
            404, {"code": "MODEL_NOT_FOUND", "message": "Model not found"}
        )
    row = ModelPrice(model_id=model.id, tenant_id=ctx.tenant_id, **payload.model_dump())
    db.add(row)
    db.flush()
    append_audit_event(
        db,
        tenant_id=ctx.tenant_id,
        actor_id=ctx.actor_id,
        action="model.price.created",
        target_type="model_price",
        target_id=row.id,
        model_id=model.id,
        provider=model.provider,
        metadata={"version": row.version, "currency": row.currency},
    )
    db.commit()
    db.refresh(row)
    return fields(
        row,
        (
            "id",
            "model_id",
            "version",
            "input_cost_per_million",
            "output_cost_per_million",
            "currency",
            "effective_from",
        ),
    )


@router.patch("/api/models/{model_id}")
def update_model(model_id: str, payload: ModelUpdate, db: Database, user: CurrentUser):
    ctx = identity(user)
    require(ctx, "models.manage", human=True)
    current = (
        db.query(GovernedModel).filter_by(id=model_id, tenant_id=ctx.tenant_id).first()
    )
    if current is None:
        raise HTTPException(
            404, {"code": "MODEL_NOT_FOUND", "message": "Model not found"}
        )
    changes = payload.model_dump(exclude_unset=True)
    target_status = changes.pop("status", None)
    if target_status is not None:
        allowed = {
            "DRAFT": {"APPROVED"},
            "APPROVED": {"ACTIVE", "BLOCKED"},
            "ACTIVE": {"DEPRECATED", "DISABLED", "BLOCKED"},
            "DEPRECATED": {"DISABLED", "BLOCKED"},
        }
        if target_status not in allowed.get(current.status, set()):
            raise HTTPException(
                409,
                {
                    "code": "INVALID_MODEL_STATE",
                    "message": "Model status transition is not allowed",
                },
            )
        if current.created_by == ctx.actor_id and target_status in {
            "APPROVED",
            "ACTIVE",
        }:
            raise HTTPException(
                403,
                {
                    "code": "SELF_APPROVAL_FORBIDDEN",
                    "message": "Model author cannot approve or activate the model",
                },
            )
        current.status = target_status
        current.effective_from = current.effective_from or (
            datetime.now(UTC) if target_status == "ACTIVE" else None
        )
        append_audit_event(
            db,
            tenant_id=ctx.tenant_id,
            actor_id=ctx.actor_id,
            action=f"model.{target_status.lower()}",
            target_type="governed_model",
            target_id=current.id,
            model_id=current.id,
            provider=current.provider,
        )
        db.commit()
        db.refresh(current)
        return fields(current, MODEL_FIELDS)
    data = {
        name: getattr(current, name)
        for name in (
            "provider",
            "provider_model_id",
            "display_name",
            "model_family",
            "capabilities",
            "approved_use_cases",
            "prohibited_use_cases",
            "allowed_data_classifications",
            "allowed_regions",
            "context_limit",
        )
    }
    data.update(changes)
    data["model_key"] = current.model_key
    data["status"] = "DRAFT"
    version = (
        db.query(func.max(GovernedModel.configuration_version))
        .filter_by(tenant_id=ctx.tenant_id, model_key=current.model_key)
        .scalar()
        or 0
    ) + 1
    row = GovernedModel(
        tenant_id=ctx.tenant_id,
        configuration_version=version,
        created_by=ctx.actor_id,
        created_at=datetime.now(UTC),
        **data,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return fields(row, MODEL_FIELDS)


def execution_item(row: RuntimeExecution, events: int | None = None) -> dict:
    return {
        "id": str(row.id),
        "trace_id": str(row.workflow_id),
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "user": row.user_id,
        "agent": row.agent,
        "model": row.model_name,
        "provider": row.provider_name,
        "status": row.status,
        "latency_ms": row.duration_ms,
        "tokens": row.token_usage or None,
        "cost": str(row.actual_cost)
        if row.actual_cost is not None
        else (str(row.estimated_cost) if row.estimated_cost is not None else None),
        "event_count": events,
    }


@router.get("/api/ai-operations/overview")
def operations_overview(db: Database, user: CurrentUser):
    ctx = identity(user)
    require(ctx, "runtime.execute")
    rows = db.query(RuntimeExecution).filter_by(tenant_id=ctx.tenant_id).all()
    completed = [row for row in rows if row.status == "COMPLETED"]
    costs = [
        record.total_cost
        for record in db.query(UsageRecord).filter_by(tenant_id=ctx.tenant_id).all()
        if record.total_cost is not None
    ]
    incidents = (
        db.query(AIIncident)
        .filter_by(tenant_id=ctx.tenant_id)
        .filter(AIIncident.status.notin_(["RESOLVED", "CLOSED"]))
        .count()
    )
    return {
        "summary": {
            "ai_executions": len(rows),
            "success_rate": round(len(completed) / len(rows) * 100, 1)
            if rows
            else None,
            "p95_latency": None,
            "evidence_grounded_responses": None,
            "policy_blocks": None,
            "approval_rate": None,
            "estimated_cost": str(sum(costs)) if costs else None,
            "open_incidents": incidents,
        },
        "charts": {"executions": [], "latency": [], "tokens": [], "cost": []},
        "attention": [],
        "sources": ["runtime_executions", "ai_usage_records", "ai_incidents"],
    }


@router.get("/api/ai-operations/executions")
def executions(
    db: Database,
    user: CurrentUser,
    page_number: int = Query(1, alias="page", ge=1),
    page_size: int = Query(50, ge=1, le=100),
):
    ctx = identity(user)
    require(ctx, "runtime.execute")
    query = db.query(RuntimeExecution).filter_by(tenant_id=ctx.tenant_id)
    total = query.count()
    rows = (
        query.order_by(RuntimeExecution.started_at.desc())
        .offset((page_number - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return page([execution_item(row) for row in rows], total, page_number, page_size)


@router.get("/api/ai-operations/executions/{execution_id}")
def execution_detail(execution_id: str, db: Database, user: CurrentUser):
    ctx = identity(user)
    require(ctx, "runtime.execute")
    row = (
        db.query(RuntimeExecution)
        .filter_by(id=execution_id, tenant_id=ctx.tenant_id)
        .first()
    )
    if row is None:
        raise HTTPException(
            404, {"code": "EXECUTION_NOT_FOUND", "message": "Execution not found"}
        )
    events = (
        db.query(RuntimeExecutionEvent)
        .filter_by(execution_id=row.id)
        .order_by(RuntimeExecutionEvent.sequence)
        .all()
    )
    item = execution_item(row, len(events))
    item["timeline"] = [
        {
            "sequence": event.sequence,
            "type": event.event_type,
            "status": event.status,
            "timestamp": event.created_at.isoformat(),
            "safe_summary": event.description,
        }
        for event in events
    ]
    reservation = (
        db.query(BudgetReservation)
        .filter_by(tenant_id=ctx.tenant_id, execution_id=execution_id)
        .order_by(BudgetReservation.created_at.desc())
        .first()
    )
    usage_row = (
        db.query(UsageRecord)
        .filter_by(tenant_id=ctx.tenant_id, execution_id=execution_id)
        .first()
    )
    item["budget"] = (
        fields(
            reservation,
            (
                "budget_id",
                "model_id",
                "price_version",
                "estimated_amount",
                "settled_amount",
                "currency",
                "status",
                "failure_reason",
            ),
        )
        if reservation
        else None
    )
    item["usage"] = (
        fields(
            usage_row,
            (
                "model_id",
                "provider",
                "input_tokens",
                "output_tokens",
                "total_cost",
                "currency",
            ),
        )
        if usage_row
        else None
    )
    item["audit_event_count"] = (
        db.query(AuditLog)
        .filter_by(tenant_id=ctx.tenant_id, execution_id=execution_id)
        .count()
    )
    item["evaluation_run_ids"] = [
        value.id
        for value in db.query(EvaluationRun)
        .filter(EvaluationRun.tenant_id == ctx.tenant_id)
        .all()
        if execution_id in (value.trace_ids or [])
    ]
    return item


@router.get("/api/ai-operations/usage")
def usage(db: Database, user: CurrentUser):
    ctx = identity(user)
    require(ctx, "budgets.manage")
    rows = (
        db.query(UsageRecord)
        .filter_by(tenant_id=ctx.tenant_id)
        .order_by(UsageRecord.started_at.desc())
        .limit(100)
        .all()
    )
    return {
        "items": [
            fields(
                row,
                (
                    "id",
                    "trace_id",
                    "execution_id",
                    "agent_id",
                    "model_id",
                    "provider",
                    "input_tokens",
                    "output_tokens",
                    "latency_ms",
                    "status",
                    "total_cost",
                    "currency",
                    "cost_estimated",
                    "started_at",
                ),
            )
            for row in rows
        ],
        "total": len(rows),
    }


@router.get("/api/ai-operations/costs")
def costs(db: Database, user: CurrentUser):
    ctx = identity(user)
    require(ctx, "budgets.manage")
    records = db.query(UsageRecord).filter_by(tenant_id=ctx.tenant_id).all()
    known = [row.total_cost for row in records if row.total_cost is not None]
    budgets = db.query(Budget).filter_by(tenant_id=ctx.tenant_id, status="ACTIVE").all()
    reservations = db.query(BudgetReservation).filter_by(tenant_id=ctx.tenant_id).all()
    active_reserved = sum(
        (row.estimated_amount for row in reservations if row.status == "RESERVED"),
        Decimal(0),
    )
    return {
        "current_spend": str(sum(known)) if known else None,
        "budget": str(sum(row.hard_limit for row in budgets)) if budgets else None,
        "forecast": None,
        "forecast_method": "Unavailable until sufficient daily history exists",
        "cost_per_execution": str(sum(known) / len(known)) if known else None,
        "active_reservations": str(active_reserved),
        "blocked_calls": db.query(AuditLog)
        .filter_by(tenant_id=ctx.tenant_id, action="budget.reservation.blocked")
        .count(),
        "reconciliation_issues": sum(
            row.status == "RECONCILIATION_REQUIRED" for row in reservations
        ),
        "sources": ["ai_usage_records", "ai_budgets", "budget_reservations"],
    }


@router.get("/api/ai-operations/budgets")
def budgets(db: Database, user: CurrentUser):
    ctx = identity(user)
    require(ctx, "budgets.manage")
    rows = db.query(Budget).filter_by(tenant_id=ctx.tenant_id).all()
    names = (
        "id",
        "scope_type",
        "scope_id",
        "period",
        "soft_limit",
        "hard_limit",
        "currency",
        "alert_thresholds",
        "effective_from",
        "effective_until",
        "status",
    )
    return {"items": [fields(row, names) for row in rows], "total": len(rows)}


class BudgetCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scope_type: str
    scope_id: str
    period: str
    soft_limit: Decimal = Field(gt=0)
    hard_limit: Decimal = Field(gt=0)
    currency: str = Field(min_length=3, max_length=3)
    alert_thresholds: list[int] = Field(default_factory=lambda: [50, 75, 90, 100])
    effective_from: datetime
    effective_until: datetime | None = None


@router.get("/api/ai-operations/budgets/{budget_id}")
def budget_detail(budget_id: str, db: Database, user: CurrentUser):
    ctx = identity(user)
    require(ctx, "budgets.manage")
    row = db.query(Budget).filter_by(id=budget_id, tenant_id=ctx.tenant_id).first()
    if row is None:
        raise HTTPException(
            404, {"code": "BUDGET_NOT_FOUND", "message": "Budget not found"}
        )
    reservations = (
        db.query(BudgetReservation)
        .filter_by(tenant_id=ctx.tenant_id, budget_id=row.id)
        .all()
    )
    settled = sum(
        (
            item.settled_amount or Decimal(0)
            for item in reservations
            if item.status == "SETTLED"
        ),
        Decimal(0),
    )
    reserved = sum(
        (item.estimated_amount for item in reservations if item.status == "RESERVED"),
        Decimal(0),
    )
    item = fields(
        row,
        (
            "id",
            "scope_type",
            "scope_id",
            "period",
            "soft_limit",
            "hard_limit",
            "currency",
            "alert_thresholds",
            "effective_from",
            "effective_until",
            "status",
        ),
    )
    item.update(
        {
            "settled_cost": str(settled),
            "reserved_cost": str(reserved),
            "available_amount": str(
                max(Decimal(0), row.hard_limit - settled - reserved)
            ),
            "reservations": [
                fields(
                    value,
                    (
                        "id",
                        "trace_id",
                        "execution_id",
                        "model_id",
                        "price_version",
                        "estimated_amount",
                        "settled_amount",
                        "status",
                        "created_at",
                        "expires_at",
                    ),
                )
                for value in reservations
            ],
            "alerts": [
                fields(
                    value, ("id", "alert_type", "threshold", "trace_id", "created_at")
                )
                for value in db.query(BudgetAlert)
                .filter_by(tenant_id=ctx.tenant_id, budget_id=row.id)
                .all()
            ],
            "overrides": [
                fields(
                    value,
                    (
                        "id",
                        "requested_amount",
                        "remaining_amount",
                        "status",
                        "requested_by",
                        "approved_by",
                        "expires_at",
                        "uses_remaining",
                    ),
                )
                for value in db.query(BudgetOverride)
                .filter_by(tenant_id=ctx.tenant_id, budget_id=row.id)
                .all()
            ],
        }
    )
    return item


class OverrideCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    requested_amount: Decimal = Field(gt=0)
    scope: dict[str, Any] = Field(default_factory=dict)
    reason: str = Field(min_length=5, max_length=2000)
    business_impact: str = Field(default="", max_length=2000)
    expires_at: datetime
    single_use: bool = True
    uses_remaining: int = Field(default=1, ge=1, le=100)
    model_restrictions: list[str] = Field(default_factory=list)
    policy_id: str | None = None
    proposed_action_id: str | None = None
    evidence: list[dict[str, Any]] = Field(default_factory=list)


@router.post("/api/ai-operations/budgets/{budget_id}/overrides", status_code=201)
def request_budget_override(
    budget_id: str, payload: OverrideCreate, db: Database, user: CurrentUser
):
    ctx = identity(user)
    require(ctx, "budgets.manage", human=True)
    budget = db.query(Budget).filter_by(id=budget_id, tenant_id=ctx.tenant_id).first()
    if budget is None:
        raise HTTPException(
            404, {"code": "BUDGET_NOT_FOUND", "message": "Budget not found"}
        )
    if payload.expires_at.replace(tzinfo=None) <= datetime.now(UTC).replace(
        tzinfo=None
    ):
        raise HTTPException(
            422,
            {
                "code": "INVALID_OVERRIDE_EXPIRY",
                "message": "Override expiry must be in the future",
            },
        )
    if payload.proposed_action_id:
        action = (
            db.query(ProposedAction)
            .filter_by(
                id=payload.proposed_action_id,
                tenant_id=ctx.tenant_id,
            )
            .first()
        )
        if action is None:
            raise HTTPException(
                404,
                {
                    "code": "PROPOSED_ACTION_NOT_FOUND",
                    "message": "AX-EP07 proposed action not found",
                },
            )
    row = BudgetOverride(
        tenant_id=ctx.tenant_id,
        budget_id=budget.id,
        requested_by=ctx.actor_id,
        status="PENDING",
        remaining_amount=payload.requested_amount,
        created_at=datetime.now(UTC),
        **payload.model_dump(),
    )
    db.add(row)
    db.flush()
    append_audit_event(
        db,
        tenant_id=ctx.tenant_id,
        actor_id=ctx.actor_id,
        action="budget.override.requested",
        target_type="budget_override",
        target_id=row.id,
        metadata={
            "budget_id": budget.id,
            "requested_amount": str(row.requested_amount),
        },
    )
    db.commit()
    db.refresh(row)
    return fields(
        row,
        ("id", "budget_id", "requested_amount", "status", "requested_by", "expires_at"),
    )


@router.post("/api/ai-operations/budget-overrides/{override_id}/approve")
def approve_budget_override(override_id: str, db: Database, user: CurrentUser):
    ctx = identity(user)
    require(ctx, "approvals.approve", human=True)
    row = (
        db.query(BudgetOverride)
        .filter_by(id=override_id, tenant_id=ctx.tenant_id)
        .with_for_update()
        .first()
    )
    if row is None:
        raise HTTPException(
            404, {"code": "OVERRIDE_NOT_FOUND", "message": "Budget override not found"}
        )
    if row.requested_by == ctx.actor_id:
        raise HTTPException(
            403,
            {
                "code": "SELF_APPROVAL_FORBIDDEN",
                "message": "Requester cannot approve their own override",
            },
        )
    if row.status != "PENDING":
        raise HTTPException(
            409,
            {"code": "INVALID_OVERRIDE_STATE", "message": "Override is not pending"},
        )
    row.status = "APPROVED"
    row.approved_by = ctx.actor_id
    row.decided_at = datetime.now(UTC)
    append_audit_event(
        db,
        tenant_id=ctx.tenant_id,
        actor_id=ctx.actor_id,
        action="budget.override.approved",
        target_type="budget_override",
        target_id=row.id,
        metadata={"budget_id": row.budget_id},
    )
    db.commit()
    db.refresh(row)
    return fields(
        row,
        (
            "id",
            "budget_id",
            "status",
            "requested_by",
            "approved_by",
            "remaining_amount",
            "uses_remaining",
        ),
    )


@router.post("/api/ai-operations/budgets", status_code=201)
def create_budget(payload: BudgetCreate, db: Database, user: CurrentUser):
    ctx = identity(user)
    require(ctx, "budgets.manage", human=True)
    if payload.soft_limit > payload.hard_limit:
        raise HTTPException(
            422,
            {
                "code": "INVALID_BUDGET_LIMITS",
                "message": "Soft limit cannot exceed hard limit",
            },
        )
    row = Budget(
        tenant_id=ctx.tenant_id,
        status="ACTIVE",
        created_by=ctx.actor_id,
        **payload.model_dump(),
    )
    db.add(row)
    db.flush()
    append_audit_event(
        db,
        tenant_id=ctx.tenant_id,
        actor_id=ctx.actor_id,
        action="budget.created",
        target_type="budget",
        target_id=row.id,
    )
    db.commit()
    db.refresh(row)
    return fields(
        row, ("id", "scope_type", "scope_id", "hard_limit", "currency", "status")
    )


class DatasetCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dataset_key: str
    name: str
    description: str = ""
    version: int = Field(1, ge=1)
    status: str = "DRAFT"
    use_case: str
    cases: list[dict[str, Any]] = Field(default_factory=list, max_length=1000)


@router.get("/api/evaluations/datasets")
def datasets(db: Database, user: CurrentUser):
    ctx = identity(user)
    require(ctx, "evaluations.manage")
    rows = db.query(EvaluationDataset).filter_by(tenant_id=ctx.tenant_id).all()
    return {
        "items": [
            fields(
                row,
                (
                    "id",
                    "dataset_key",
                    "name",
                    "description",
                    "version",
                    "status",
                    "use_case",
                    "cases",
                    "approved_by",
                    "created_at",
                ),
            )
            for row in rows
        ],
        "total": len(rows),
    }


@router.post("/api/evaluations/datasets", status_code=201)
def create_dataset(payload: DatasetCreate, db: Database, user: CurrentUser):
    ctx = identity(user)
    require(ctx, "evaluations.manage", human=True)
    row = EvaluationDataset(
        tenant_id=ctx.tenant_id,
        created_by=ctx.actor_id,
        approved_by=ctx.actor_id if payload.status == "APPROVED" else None,
        created_at=datetime.now(UTC),
        **payload.model_dump(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return fields(row, ("id", "name", "version", "status", "use_case"))


class EvaluationRunCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dataset_id: str
    model_id: str
    trace_ids: list[str] = Field(default_factory=list, max_length=20)


@router.get("/api/evaluations/runs")
def evaluation_runs(db: Database, user: CurrentUser):
    ctx = identity(user)
    require(ctx, "evaluations.manage")
    rows = (
        db.query(EvaluationRun)
        .filter_by(tenant_id=ctx.tenant_id)
        .order_by(EvaluationRun.started_at.desc())
        .all()
    )
    return {
        "items": [
            fields(
                row,
                (
                    "id",
                    "dataset_id",
                    "dataset_version",
                    "agent_id",
                    "agent_version",
                    "prompt_version",
                    "model_id",
                    "policy_version",
                    "status",
                    "scores",
                    "failures",
                    "trace_ids",
                    "started_at",
                    "completed_at",
                ),
            )
            for row in rows
        ],
        "total": len(rows),
    }


@router.post("/api/evaluations/runs", status_code=201)
def create_evaluation_run(
    payload: EvaluationRunCreate, db: Database, user: CurrentUser
):
    ctx = identity(user)
    dataset = (
        db.query(EvaluationDataset)
        .filter_by(id=payload.dataset_id, tenant_id=ctx.tenant_id)
        .first()
    )
    model = (
        db.query(GovernedModel)
        .filter_by(id=payload.model_id, tenant_id=ctx.tenant_id)
        .first()
    )
    if dataset is None or model is None:
        raise HTTPException(
            404,
            {
                "code": "EVALUATION_INPUT_NOT_FOUND",
                "message": "Dataset or model not found",
            },
        )
    row = EvaluationRunnerService.run(db, ctx, dataset, model)
    if payload.trace_ids:
        row.trace_ids = payload.trace_ids
        db.commit()
        db.refresh(row)
    return fields(
        row, ("id", "status", "scores", "failures", "dataset_version", "model_id")
    )


@router.get("/api/evaluations/runs/{run_id}")
def evaluation_run(run_id: str, db: Database, user: CurrentUser):
    ctx = identity(user)
    require(ctx, "evaluations.manage")
    row = db.query(EvaluationRun).filter_by(id=run_id, tenant_id=ctx.tenant_id).first()
    if row is None:
        raise HTTPException(
            404, {"code": "EVALUATION_NOT_FOUND", "message": "Evaluation run not found"}
        )
    item = fields(
        row,
        (
            "id",
            "dataset_id",
            "dataset_version",
            "model_id",
            "status",
            "scores",
            "failures",
            "started_at",
            "completed_at",
        ),
    )
    item["results"] = [
        fields(
            result,
            (
                "id",
                "test_case_id",
                "score",
                "passed",
                "reason_codes",
                "actual_behavior_summary",
                "evidence_validation",
                "latency_ms",
                "tokens",
                "cost",
                "failure_category",
            ),
        )
        for result in db.query(EvaluationResult)
        .filter_by(run_id=row.id, tenant_id=ctx.tenant_id)
        .all()
    ]
    return item


class IncidentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    incident_type: str
    severity: str
    owner_id: str | None = None
    affected_services: list[str] = Field(default_factory=list)
    affected_tenant_refs: list[str] = Field(default_factory=list)
    trace_ids: list[str] = Field(default_factory=list)
    impact_summary: str = Field(max_length=4000)


class IncidentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str
    mitigation: str | None = Field(None, max_length=4000)
    root_cause: str | None = Field(None, max_length=4000)
    corrective_actions: list[dict[str, Any]] = Field(default_factory=list)


@router.get("/api/ai-operations/incidents")
def incidents(db: Database, user: CurrentUser):
    ctx = identity(user)
    require(ctx, "incidents.manage")
    rows = (
        db.query(AIIncident)
        .filter_by(tenant_id=ctx.tenant_id)
        .order_by(AIIncident.created_at.desc())
        .all()
    )
    names = (
        "id",
        "incident_type",
        "severity",
        "status",
        "owner_id",
        "affected_services",
        "trace_ids",
        "impact_summary",
        "mitigation",
        "root_cause",
        "corrective_actions",
        "timeline",
        "created_at",
        "updated_at",
    )
    return {"items": [fields(row, names) for row in rows], "total": len(rows)}


@router.post("/api/ai-operations/incidents", status_code=201)
def create_incident(payload: IncidentCreate, db: Database, user: CurrentUser):
    ctx = identity(user)
    require(ctx, "incidents.manage", human=True)
    now = datetime.now(UTC)
    row = AIIncident(
        tenant_id=ctx.tenant_id,
        status="OPEN",
        created_by=ctx.actor_id,
        created_at=now,
        updated_at=now,
        timeline=[{"status": "OPEN", "at": now.isoformat(), "actor": ctx.actor_id}],
        **payload.model_dump(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return fields(row, ("id", "incident_type", "severity", "status", "created_at"))


@router.patch("/api/ai-operations/incidents/{incident_id}")
def update_incident(
    incident_id: str, payload: IncidentUpdate, db: Database, user: CurrentUser
):
    ctx = identity(user)
    require(ctx, "incidents.manage", human=True)
    row = (
        db.query(AIIncident).filter_by(id=incident_id, tenant_id=ctx.tenant_id).first()
    )
    if row is None:
        raise HTTPException(
            404, {"code": "INCIDENT_NOT_FOUND", "message": "Incident not found"}
        )
    row.status = payload.status
    row.mitigation = payload.mitigation
    row.root_cause = payload.root_cause
    row.corrective_actions = payload.corrective_actions
    row.updated_at = datetime.now(UTC)
    row.timeline = [
        *(row.timeline or []),
        {"status": row.status, "at": row.updated_at.isoformat(), "actor": ctx.actor_id},
    ]
    db.commit()
    db.refresh(row)
    return fields(row, ("id", "status", "updated_at"))


@router.get("/api/governance/retention")
def retention(db: Database, user: CurrentUser):
    ctx = identity(user)
    require(ctx, "retention.manage")
    rows = db.query(RetentionPolicy).filter_by(tenant_id=ctx.tenant_id).all()
    names = (
        "id",
        "resource_type",
        "classification",
        "retention_days",
        "allowed_models",
        "allowed_providers",
        "allowed_regions",
        "logging_controls",
        "export_allowed",
        "status",
        "created_at",
    )
    return {"items": [fields(row, names) for row in rows], "total": len(rows)}


class RetentionPreview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    resource_type: str
    as_of: datetime | None = None


@router.post("/api/governance/retention/preview")
def retention_preview(payload: RetentionPreview, db: Database, user: CurrentUser):
    ctx = identity(user)
    require(ctx, "retention.manage", human=True)
    row = (
        db.query(RetentionPolicy)
        .filter_by(
            tenant_id=ctx.tenant_id,
            resource_type=payload.resource_type,
            status="ACTIVE",
        )
        .first()
    )
    if row is None:
        raise HTTPException(
            404,
            {
                "code": "RETENTION_POLICY_NOT_FOUND",
                "message": "Retention policy not found",
            },
        )
    cutoff = (payload.as_of or datetime.now(UTC)) - timedelta(days=row.retention_days)
    protected = payload.resource_type == "audit"
    result = {
        "resource_type": row.resource_type,
        "classification": row.classification,
        "cutoff": cutoff.isoformat(),
        "candidate_count": None,
        "protected_from_deletion": protected,
        "dry_run": True,
        "executed": False,
    }
    append_audit_event(
        db,
        tenant_id=ctx.tenant_id,
        actor_id=ctx.actor_id,
        action="retention.previewed",
        target_type="retention_policy",
        target_id=row.id,
        metadata=result,
    )
    db.commit()
    return result
