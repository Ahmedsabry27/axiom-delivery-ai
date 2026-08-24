from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.tools import identity, require_admin
from app.audit.events import append_audit_event
from app.auth.dependencies import get_current_user
from app.database.dependencies import get_db
from app.database.models.tool import ToolExecution
from app.database.models.tool_discovery import (
    ToolAssignment,
    ToolCandidateDecision,
    ToolDiscoveryEvent,
    ToolDiscoveryFeedback,
    ToolGovernancePolicy,
    ToolMarketplaceProfile,
    ToolSearchIndex,
)
from app.tool_discovery.engine import engine
from app.tool_discovery.indexing import index_tools
from app.tool_discovery.rate_limit import limiter
from app.tool_discovery.schemas import DiscoveryRequest
from app.tool_sdk.service import registry

router = APIRouter(prefix="/api/v1", tags=["Tool Discovery & Governance"])
logger = logging.getLogger(__name__)


class FeedbackPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    feedback_type: str = Field(
        pattern="^(correct_tool|wrong_tool|no_useful_tool|helpful|unhelpful|manual_alternative|admin_review)$"
    )
    alternative_tool: str | None = None
    safe_reason: str = Field(default="", max_length=500)


class MarketplacePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str | None = None
    health_status: str | None = None
    environment: str | None = None
    data_classifications: list[str] | None = None
    approval_policy: str | None = None
    estimated_cost: float | None = None
    agent_allowlist: list[str] | None = None


class AssignmentPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    assignments: list[dict] = Field(max_length=200)


class PolicyPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=2, max_length=160)
    description: str = ""
    conditions: list[dict] = Field(default_factory=list, max_length=20)
    actions: dict = Field(default_factory=dict)
    decision: str
    priority: int = Field(default=100, ge=0, le=10000)
    change_note: str = Field(default="", max_length=500)


def profile_item(db, profile, tool):
    executions = (
        db.query(ToolExecution)
        .filter_by(tenant_id=profile.tenant_id, tool_name=profile.tool_name)
        .all()
    )
    success = (
        sum(x.status == "succeeded" for x in executions) / len(executions)
        if executions
        else None
    )
    duration = (
        sum((x.duration_ms or 0) for x in executions) / len(executions)
        if executions
        else None
    )
    assignments = (
        db.query(ToolAssignment)
        .filter_by(
            tenant_id=profile.tenant_id, tool_name=profile.tool_name, status="active"
        )
        .all()
    )
    return {
        "id": profile.id,
        "name": tool.name,
        "display_name": tool.metadata.display_name,
        "description": tool.metadata.description,
        "source": profile.source,
        "provider": tool.metadata.provider,
        "category": tool.metadata.category,
        "version": tool.metadata.version,
        "risk": tool.metadata.risk_level.value,
        "health": profile.health_status,
        "status": profile.status,
        "permissions": list(tool.metadata.permissions),
        "approval_policy": profile.approval_policy,
        "environment": profile.environment,
        "data_classifications": profile.data_classifications,
        "agent_allowlist": profile.agent_allowlist,
        "assignments": [
            {
                "subject_type": x.subject_type,
                "subject_id": x.subject_id,
                "decision": x.decision,
                "action": x.action,
            }
            for x in assignments
        ],
        "usage": len(executions),
        "success_rate": success,
        "average_duration_ms": duration,
        "estimated_cost": profile.estimated_cost,
        "currency": profile.currency,
        "input_schema": tool.metadata.parameters,
        "output_schema": tool.metadata.output_schema,
    }


def validate_policy(payload):
    if payload.decision not in {"allow", "deny", "approval_required"}:
        raise HTTPException(
            422, {"code": "POLICY_INVALID", "message": "Unsupported policy decision"}
        )
    from app.tool_discovery.governance import validate_conditions

    try:
        validate_conditions(payload.conditions)
    except ValueError as exc:
        raise HTTPException(
            422, {"code": "POLICY_INVALID", "message": str(exc)}
        ) from exc


@router.post("/tool-discovery/search")
async def discover(
    payload: DiscoveryRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    ctx = identity(user)
    limiter.check(f"{ctx.tenant_id}:{ctx.actor_id}")
    return await engine.discover(payload, ctx, db)


@router.post("/tool-discovery/simulate")
async def simulate(
    payload: DiscoveryRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    require_admin(user)
    return await engine.discover(payload, identity(user), db, simulate=True)


@router.get("/tool-discovery/index/status")
def index_status(db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    ctx = require_admin(user)
    q = db.query(ToolSearchIndex).filter_by(tenant_id=ctx.tenant_id)
    return {
        "total": q.count(),
        "ready": q.filter_by(index_status="ready").count(),
        "failed": q.filter_by(index_status="failed").count(),
        "models": sorted({x.embedding_model for x in q.all()}),
    }


@router.post("/tool-discovery/index/rebuild")
async def rebuild(
    dry_run: bool = False,
    batch_size: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    ctx = require_admin(user)
    return await index_tools(db, ctx.tenant_id, dry_run, batch_size)


@router.get("/tool-discovery/{discovery_id}")
def discovery_detail(
    discovery_id: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    ctx = identity(user)
    event = (
        db.query(ToolDiscoveryEvent)
        .filter_by(id=discovery_id, tenant_id=ctx.tenant_id)
        .first()
    )
    if not event:
        raise HTTPException(
            404, {"code": "DISCOVERY_NO_MATCH", "message": "Discovery was not found"}
        )
    candidates = (
        db.query(ToolCandidateDecision)
        .filter_by(discovery_id=event.id, eligible=True)
        .order_by(ToolCandidateDecision.rank)
        .all()
    )
    return {
        "id": event.id,
        "outcome": event.outcome,
        "safe_intent": event.safe_intent,
        "selected_tool": event.selected_tool,
        "confidence": event.confidence,
        "strategy_version": event.strategy_version,
        "duration_ms": event.duration_ms,
        "correlation_id": event.correlation_id,
        "candidates": [
            {
                "tool_name": x.tool_name,
                "version": x.tool_version,
                "scores": x.component_scores,
                "score": x.final_score,
                "rank": x.rank,
                "selected": x.selected,
            }
            for x in candidates
        ],
    }


@router.post("/tool-discovery/{discovery_id}/feedback", status_code=201)
def feedback(
    discovery_id: str,
    payload: FeedbackPayload,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    ctx = identity(user)
    event = (
        db.query(ToolDiscoveryEvent)
        .filter_by(id=discovery_id, tenant_id=ctx.tenant_id)
        .first()
    )
    if not event:
        raise HTTPException(404, "Discovery was not found")
    row = ToolDiscoveryFeedback(
        discovery_id=event.id,
        tenant_id=ctx.tenant_id,
        actor_id=ctx.actor_id,
        feedback_type=payload.feedback_type,
        selected_tool=event.selected_tool,
        alternative_tool=payload.alternative_tool,
        safe_reason=payload.safe_reason,
    )
    db.add(row)
    db.flush()
    append_audit_event(
        db,
        tenant_id=ctx.tenant_id,
        actor_id=ctx.actor_id,
        action="tool.discovery.feedback.created",
        target_type="tool_discovery_feedback",
        target_id=row.id,
        correlation_id=ctx.correlation_id,
        after={"feedback_type": row.feedback_type, "discovery_id": event.id},
    )
    db.commit()
    return {"id": row.id}


@router.get("/tool-marketplace")
async def marketplace(
    search: str | None = None,
    source: str | None = None,
    status: str | None = None,
    category: str | None = None,
    risk: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    ctx = identity(user)
    await index_tools(db, ctx.tenant_id)
    profiles = db.query(ToolMarketplaceProfile).filter_by(tenant_id=ctx.tenant_id).all()
    items = []
    for profile in profiles:
        try:
            tool = registry.get(profile.tool_name, profile.tool_version)
        except Exception:  # noqa: BLE001 -- registry plugins expose heterogeneous lookup failures
            logger.warning("Skipped unavailable marketplace tool", exc_info=True)
            continue
        if (
            set(tool.metadata.permissions) - ctx.permissions
            and "tools.admin" not in ctx.permissions
        ):
            continue
        item = profile_item(db, profile, tool)
        if (
            search
            and search.lower()
            not in f"{item['display_name']} {item['name']} {item['description']}".lower()
        ):
            continue
        if (
            source
            and item["source"] != source
            or status
            and item["status"] != status
            or category
            and item["category"] != category
            or risk
            and item["risk"] != risk
        ):
            continue
        items.append(item)
    items.sort(key=lambda x: (x["display_name"].lower(), x["version"]))
    start = (page - 1) * page_size
    return {
        "items": items[start : start + page_size],
        "total": len(items),
        "page": page,
        "page_size": page_size,
    }


@router.get("/tool-marketplace/{tool_id}")
def marketplace_detail(
    tool_id: str, db: Session = Depends(get_db), user: dict = Depends(get_current_user)
):
    ctx = identity(user)
    profile = (
        db.query(ToolMarketplaceProfile)
        .filter_by(id=tool_id, tenant_id=ctx.tenant_id)
        .first()
    )
    if not profile:
        raise HTTPException(404, "Tool was not found")
    tool = registry.get(profile.tool_name, profile.tool_version)
    if (
        set(tool.metadata.permissions) - ctx.permissions
        and "tools.admin" not in ctx.permissions
    ):
        raise HTTPException(404, "Tool was not found")
    return profile_item(db, profile, tool)


@router.patch("/tool-marketplace/{tool_id}")
def marketplace_update(
    tool_id: str,
    payload: MarketplacePatch,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    ctx = require_admin(user)
    row = (
        db.query(ToolMarketplaceProfile)
        .filter_by(id=tool_id, tenant_id=ctx.tenant_id)
        .first()
    )
    if not row:
        raise HTTPException(404, "Tool was not found")
    values = payload.model_dump(exclude_unset=True)
    if values.get("status") not in {
        None,
        "draft",
        "pending_review",
        "enabled",
        "disabled",
        "degraded",
        "deprecated",
        "quarantined",
        "unavailable",
    }:
        raise HTTPException(422, "Invalid marketplace status")
    for key, value in values.items():
        setattr(row, key, value)
    row.updated_by = ctx.actor_id
    append_audit_event(
        db,
        tenant_id=ctx.tenant_id,
        actor_id=ctx.actor_id,
        action="tool.marketplace.updated",
        target_type="tool_marketplace_profile",
        target_id=row.id,
        correlation_id=ctx.correlation_id,
        after={
            "status": row.status,
            "tool": row.tool_name,
            "version": row.tool_version,
        },
    )
    db.commit()
    registry.set_enabled(
        row.tool_name, row.tool_version, row.status in {"enabled", "degraded"}
    )
    return profile_item(db, row, registry.get(row.tool_name, row.tool_version))


@router.post("/tool-marketplace/{tool_id}/enable")
def marketplace_enable(
    tool_id: str, db: Session = Depends(get_db), user: dict = Depends(get_current_user)
):
    return marketplace_update(tool_id, MarketplacePatch(status="enabled"), db, user)


@router.post("/tool-marketplace/{tool_id}/disable")
def marketplace_disable(
    tool_id: str, db: Session = Depends(get_db), user: dict = Depends(get_current_user)
):
    return marketplace_update(tool_id, MarketplacePatch(status="disabled"), db, user)


@router.put("/tool-marketplace/{tool_id}/assignments")
def assignments(
    tool_id: str,
    payload: AssignmentPayload,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    ctx = require_admin(user)
    profile = (
        db.query(ToolMarketplaceProfile)
        .filter_by(id=tool_id, tenant_id=ctx.tenant_id)
        .first()
    )
    if not profile:
        raise HTTPException(404, "Tool was not found")
    db.query(ToolAssignment).filter_by(
        tenant_id=ctx.tenant_id, tool_name=profile.tool_name
    ).delete()
    for item in payload.assignments:
        if item.get("subject_type") not in {
            "user",
            "role",
            "group",
            "agent",
        } or item.get("decision") not in {"allow", "deny", "approval_required"}:
            raise HTTPException(422, "Invalid assignment")
        db.add(
            ToolAssignment(
                tenant_id=ctx.tenant_id,
                tool_name=profile.tool_name,
                tool_version=profile.tool_version,
                subject_type=item["subject_type"],
                subject_id=str(item["subject_id"])[:160],
                action=item.get("action", "execute"),
                decision=item["decision"],
                created_by=ctx.actor_id,
            )
        )
    db.commit()
    return {"updated": len(payload.assignments)}


@router.put("/tool-marketplace/{tool_id}/governance")
def governance(
    tool_id: str,
    payload: MarketplacePatch,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    return marketplace_update(tool_id, payload, db, user)


@router.get("/tool-governance/policies")
def policies(db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    ctx = require_admin(user)
    return {
        "items": [
            policy_item(x)
            for x in db.query(ToolGovernancePolicy)
            .filter_by(tenant_id=ctx.tenant_id)
            .order_by(ToolGovernancePolicy.priority)
            .all()
        ]
    }


def policy_item(x):
    return {
        "id": x.id,
        "name": x.name,
        "description": x.description,
        "version": x.version,
        "lifecycle": x.lifecycle,
        "conditions": x.conditions,
        "actions": x.actions,
        "decision": x.decision,
        "priority": x.priority,
        "change_note": x.change_note,
        "published_at": x.published_at.isoformat() if x.published_at else None,
    }


@router.post("/tool-governance/policies", status_code=201)
def create_policy(
    payload: PolicyPayload,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    ctx = require_admin(user)
    validate_policy(payload)
    row = ToolGovernancePolicy(
        tenant_id=ctx.tenant_id,
        created_by=ctx.actor_id,
        updated_by=ctx.actor_id,
        **payload.model_dump(),
    )
    db.add(row)
    db.flush()
    append_audit_event(
        db,
        tenant_id=ctx.tenant_id,
        actor_id=ctx.actor_id,
        action="governance.policy.created",
        target_type="governance_policy",
        target_id=row.id,
        correlation_id=ctx.correlation_id,
        after=policy_item(row),
    )
    db.commit()
    return policy_item(row)


@router.get("/tool-governance/policies/{policy_id}")
def get_policy(
    policy_id: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    ctx = require_admin(user)
    row = (
        db.query(ToolGovernancePolicy)
        .filter_by(id=policy_id, tenant_id=ctx.tenant_id)
        .first()
    )
    if not row:
        raise HTTPException(
            404, {"code": "POLICY_NOT_FOUND", "message": "Policy was not found"}
        )
    return policy_item(row)


@router.patch("/tool-governance/policies/{policy_id}")
def update_policy(
    policy_id: str,
    payload: PolicyPayload,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    ctx = require_admin(user)
    validate_policy(payload)
    row = (
        db.query(ToolGovernancePolicy)
        .filter_by(id=policy_id, tenant_id=ctx.tenant_id)
        .first()
    )
    if not row:
        raise HTTPException(404, "Policy was not found")
    if row.lifecycle == "active":
        row.lifecycle = "superseded"
        new = ToolGovernancePolicy(
            tenant_id=ctx.tenant_id,
            created_by=ctx.actor_id,
            updated_by=ctx.actor_id,
            version=row.version + 1,
            **payload.model_dump(),
        )
        db.add(new)
        db.commit()
        return policy_item(new)
    for key, value in payload.model_dump().items():
        setattr(row, key, value)
    row.updated_by = ctx.actor_id
    db.commit()
    return policy_item(row)


@router.post("/tool-governance/policies/{policy_id}/publish")
def publish_policy(
    policy_id: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    ctx = require_admin(user)
    row = (
        db.query(ToolGovernancePolicy)
        .filter_by(id=policy_id, tenant_id=ctx.tenant_id)
        .first()
    )
    if not row:
        raise HTTPException(404, "Policy was not found")
    row.lifecycle = "active"
    row.published_at = datetime.now(UTC)
    row.updated_by = ctx.actor_id
    append_audit_event(
        db,
        tenant_id=ctx.tenant_id,
        actor_id=ctx.actor_id,
        action="governance.policy.published",
        target_type="governance_policy",
        target_id=row.id,
        correlation_id=ctx.correlation_id,
        after={"lifecycle": "active", "version": row.version},
    )
    db.commit()
    return policy_item(row)


@router.post("/tool-governance/policies/{policy_id}/test")
async def test_policy(
    policy_id: str,
    payload: DiscoveryRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    require_admin(user)
    return await engine.discover(payload, identity(user), db, simulate=True)


@router.post("/tool-governance/evaluate")
async def evaluate_policy(
    payload: DiscoveryRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    require_admin(user)
    return await engine.discover(payload, identity(user), db, simulate=True)


def window_start(days):
    return datetime.now(UTC) - timedelta(days=min(days, 365))


@router.get("/tool-analytics/summary")
def analytics_summary(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    ctx = require_admin(user)
    start = window_start(days)
    events = (
        db.query(ToolDiscoveryEvent)
        .filter(
            ToolDiscoveryEvent.tenant_id == ctx.tenant_id,
            ToolDiscoveryEvent.created_at >= start,
        )
        .all()
    )
    executions = (
        db.query(ToolExecution)
        .filter(
            ToolExecution.tenant_id == ctx.tenant_id, ToolExecution.started_at >= start
        )
        .all()
    )
    success = sum(x.status == "succeeded" for x in executions)
    durations = [x.duration_ms for x in executions if x.duration_ms is not None]
    return {
        "discoveries": len(events),
        "executions": len(executions),
        "success_rate": success / len(executions) if executions else None,
        "average_duration_ms": sum(durations) / len(durations) if durations else None,
        "clarification_rate": sum(x.outcome == "clarification_required" for x in events)
        / len(events)
        if events
        else None,
        "no_match_rate": sum(
            x.outcome in {"no_matching_tool", "no_authorized_tool"} for x in events
        )
        / len(events)
        if events
        else None,
        "approval_rate": sum(x.outcome == "approval_required" for x in events)
        / len(events)
        if events
        else None,
        "estimated_cost": None,
        "actual_cost": None,
        "currency": "USD",
    }


def analytics_rows(db, ctx, days):
    start = window_start(days)
    return db.query(ToolDiscoveryEvent).filter(
        ToolDiscoveryEvent.tenant_id == ctx.tenant_id,
        ToolDiscoveryEvent.created_at >= start,
    ).all(), db.query(ToolExecution).filter(
        ToolExecution.tenant_id == ctx.tenant_id, ToolExecution.started_at >= start
    ).all()


@router.get("/tool-analytics/usage")
def usage(
    days: int = 30,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    ctx = require_admin(user)
    _, rows = analytics_rows(db, ctx, days)
    counts = {}
    for x in rows:
        counts[x.tool_name] = counts.get(x.tool_name, 0) + 1
    return {
        "items": [
            {"tool": k, "executions": v}
            for k, v in sorted(counts.items(), key=lambda x: -x[1])
        ]
    }


@router.get("/tool-analytics/outcomes")
def outcomes(
    days: int = 30,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    ctx = require_admin(user)
    rows, _ = analytics_rows(db, ctx, days)
    counts = {}
    for x in rows:
        counts[x.outcome] = counts.get(x.outcome, 0) + 1
    return {"items": [{"outcome": k, "count": v} for k, v in sorted(counts.items())]}


@router.get("/tool-analytics/performance")
def performance(
    days: int = 30,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    ctx = require_admin(user)
    _, rows = analytics_rows(db, ctx, days)
    return {
        "items": [
            {
                "tool": x.tool_name,
                "status": x.status,
                "duration_ms": x.duration_ms,
                "started_at": x.started_at.isoformat(),
            }
            for x in rows[-500:]
        ]
    }


@router.get("/tool-analytics/cost")
def cost(user: dict = Depends(get_current_user)):
    require_admin(user)
    return {
        "estimated": None,
        "actual": None,
        "currency": "USD",
        "message": "No provider cost data is available",
    }


@router.get("/tool-analytics/discovery-quality")
def quality(
    days: int = 30,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    ctx = require_admin(user)
    rows, _ = analytics_rows(db, ctx, days)
    feedback = db.query(ToolDiscoveryFeedback).filter_by(tenant_id=ctx.tenant_id).all()
    return {
        "total": len(rows),
        "confidence": {
            "high": sum(x.confidence == "high" for x in rows),
            "medium": sum(x.confidence == "medium" for x in rows),
            "low": sum(x.confidence == "low" for x in rows),
        },
        "feedback": len(feedback),
    }


@router.get("/tool-analytics/failures")
def failures(
    days: int = 30,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    ctx = require_admin(user)
    _, rows = analytics_rows(db, ctx, days)
    return {
        "items": [
            {
                "tool": x.tool_name,
                "error_code": x.error_code,
                "duration_ms": x.duration_ms,
            }
            for x in rows
            if x.status != "succeeded"
        ][:100]
    }


@router.get("/tool-analytics/recommendations")
def recommendations(
    days: int = 30,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    require_admin(user)
    summary = analytics_summary(days, db, user)
    items = []
    if summary["clarification_rate"] and summary["clarification_rate"] > 0.25:
        items.append(
            {
                "code": "HIGH_CLARIFICATION_RATE",
                "message": "Review low-confidence discoveries",
                "measured_value": summary["clarification_rate"],
            }
        )
    return {"items": items}
