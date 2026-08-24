from __future__ import annotations

# FastAPI dependency injection intentionally uses callable defaults.
# ruff: noqa: B008
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import String, case, cast, func
from sqlalchemy.orm import Session

from app.agents.application_service import AgentIdentity
from app.agents.execution_service import ExecutionRequest, agent_execution_service
from app.auth.dependencies import get_current_user
from app.database.dependencies import get_db
from app.database.models.agent import Agent
from app.database.models.agent_execution import AgentContinuation, AgentExecution
from app.database.models.tool import ToolExecution
from app.database.models.tool_discovery import ToolDiscoveryEvent

agent_router = APIRouter(prefix="/api/v1/agents", tags=["Agent execution"])
execution_router = APIRouter(
    prefix="/api/v1/agent-executions", tags=["Agent continuation"]
)


class ExecutePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    message: str = Field(min_length=1, max_length=50_000)
    inputs: dict[str, Any] = Field(default_factory=dict)
    conversation_id: str | None = Field(default=None, max_length=36)
    environment: str = Field(
        default="production", pattern="^(development|staging|production)$"
    )


class ResumePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    resume_token: str = Field(min_length=32, max_length=200)
    response: dict[str, Any] = Field(default_factory=dict)


def identity(user: dict[str, Any]) -> AgentIdentity:
    return AgentIdentity.from_claims(user)


@agent_router.post("/{agent_id}/execute")
async def execute_agent(
    agent_id: str,
    payload: ExecutePayload,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    return await agent_execution_service.start(
        db,
        agent_id=agent_id,
        request=ExecutionRequest(**payload.model_dump()),
        identity=identity(user),
    )


@agent_router.post("/{agent_id}/test")
async def test_agent(
    agent_id: str,
    payload: ExecutePayload,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    return await agent_execution_service.start(
        db,
        agent_id=agent_id,
        request=ExecutionRequest(**payload.model_dump(), test_mode=True),
        identity=identity(user),
    )


@agent_router.get("/{agent_id}/executions")
def list_agent_executions(
    agent_id: str,
    status: str | None = None,
    mode: str | None = None,
    actor: str | None = None,
    started_from: datetime | None = None,
    started_to: datetime | None = None,
    tool: str | None = None,
    version: int | None = Query(None, ge=1),
    sort: Literal[
        "started_at", "duration_ms", "status", "agent_version"
    ] = "started_at",
    direction: Literal["asc", "desc"] = "desc",
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    items, total = agent_execution_service.list(
        db,
        identity(user),
        agent_id,
        status=status,
        mode=mode,
        actor=actor,
        started_from=started_from,
        started_to=started_to,
        tool=tool,
        version=version,
        sort=sort,
        direction=direction,
        page=page,
        page_size=page_size,
    )
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, (total + page_size - 1) // page_size),
    }


@agent_router.get("/{agent_id}/analytics")
def agent_analytics(
    agent_id: str,
    started_from: datetime | None = None,
    started_to: datetime | None = None,
    environment: Literal["development", "staging", "production"] | None = None,
    mode: Literal["test", "production"] | None = None,
    tool: str | None = None,
    status: str | None = None,
    version: int | None = Query(None, ge=1),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    ctx = identity(user)
    agent = db.query(Agent).filter_by(uuid=agent_id, tenant_id=ctx.tenant_id).first()
    if agent is None:
        from fastapi import HTTPException

        raise HTTPException(
            404, {"code": "AGENT_NOT_FOUND", "message": "Agent not found"}
        )
    if not ctx.allows("agents.analytics.read") and agent.owner_id != ctx.actor_id:
        from fastapi import HTTPException

        raise HTTPException(
            403, {"code": "AGENT_ACCESS_DENIED", "message": "Analytics access denied"}
        )
    filters = [
        AgentExecution.tenant_id == ctx.tenant_id,
        AgentExecution.agent_id == agent.id,
    ]
    if started_from:
        filters.append(AgentExecution.started_at >= started_from)
    if started_to:
        filters.append(AgentExecution.started_at <= started_to)
    if environment:
        filters.append(
            cast(AgentExecution.runtime_metadata, String).ilike(
                f'%"environment": "{environment}"%'
            )
        )
    if mode == "test":
        filters.append(AgentExecution.test_mode.is_(True))
    elif mode == "production":
        filters.append(AgentExecution.test_mode.is_(False))
    if status:
        filters.append(AgentExecution.status == status)
    if version is not None:
        filters.append(AgentExecution.agent_version == version)
    if tool:
        filters.append(
            db.query(ToolExecution.id)
            .filter(
                ToolExecution.correlation_id == AgentExecution.correlation_id,
                ToolExecution.tool_name == tool,
            )
            .exists()
        )

    total_tokens = func.coalesce(
        AgentExecution.token_usage["total_tokens"].as_integer(),
        AgentExecution.token_usage["total"].as_integer(),
        0,
    )
    row = (
        db.query(
            func.count(AgentExecution.id),
            func.sum(case((AgentExecution.status == "succeeded", 1), else_=0)),
            func.sum(case((AgentExecution.status == "failed", 1), else_=0)),
            func.sum(case((AgentExecution.status == "cancelled", 1), else_=0)),
            func.sum(case((AgentExecution.status == "timed_out", 1), else_=0)),
            func.avg(AgentExecution.duration_ms),
            func.sum(AgentExecution.estimated_cost),
            func.sum(AgentExecution.actual_cost),
            func.max(AgentExecution.started_at),
            func.sum(total_tokens),
        )
        .filter(*filters)
        .one()
    )
    total = row[0] or 0
    waiting: dict[str, int] = {
        kind: count
        for kind, count in db.query(AgentContinuation.kind, func.count())
        .join(AgentExecution, AgentExecution.id == AgentContinuation.execution_id)
        .filter(*filters, AgentContinuation.tenant_id == ctx.tenant_id)
        .group_by(AgentContinuation.kind)
        .all()
    }
    tools = (
        db.query(
            ToolExecution.tool_name,
            func.count(),
            func.sum(case((ToolExecution.status == "succeeded", 1), else_=0)),
            func.sum(case((ToolExecution.status == "failed", 1), else_=0)),
        )
        .join(
            AgentExecution,
            AgentExecution.correlation_id == ToolExecution.correlation_id,
        )
        .filter(*filters)
        .group_by(ToolExecution.tool_name)
        .all()
    )
    duration_query = (
        db.query(AgentExecution.duration_ms)
        .filter(*filters, AgentExecution.duration_ms.is_not(None))
        .order_by(AgentExecution.duration_ms.asc())
    )
    duration_count = duration_query.count()

    def percentile(percent: float) -> float | None:
        if not duration_count:
            return None
        offset = max(0, int((duration_count - 1) * percent + 0.999999))
        value = duration_query.offset(offset).limit(1).scalar()
        return round(float(value), 2) if value is not None else None

    versions = [
        {"version": item_version, "executions": count}
        for item_version, count in db.query(
            AgentExecution.agent_version, func.count(AgentExecution.id)
        )
        .filter(*filters)
        .group_by(AgentExecution.agent_version)
        .order_by(AgentExecution.agent_version)
        .all()
    ]
    environments = [
        {"environment": item_environment or "unknown", "executions": count}
        for item_environment, count in db.query(
            AgentExecution.runtime_metadata["environment"].as_string(),
            func.count(AgentExecution.id),
        )
        .filter(*filters)
        .group_by(AgentExecution.runtime_metadata["environment"].as_string())
        .all()
    ]
    return {
        "total_executions": total,
        "succeeded": row[1] or 0,
        "failed": row[2] or 0,
        "cancelled": row[3] or 0,
        "timed_out": row[4] or 0,
        "success_rate": round(100 * (row[1] or 0) / total, 1) if total else None,
        "average_duration_ms": round(row[5] or 0, 2),
        "p50_duration_ms": percentile(0.50),
        "p95_duration_ms": percentile(0.95),
        "estimated_cost": row[6] or 0,
        "actual_cost": row[7],
        "currency": "USD",
        "last_active_at": row[8],
        "total_tokens": row[9] or 0,
        "input_required": waiting.get("input", 0),
        "clarification_required": waiting.get("clarification", 0),
        "approval_required": waiting.get("approval", 0),
        "input_required_rate": round(waiting.get("input", 0) / total, 4)
        if total
        else None,
        "clarification_required_rate": round(waiting.get("clarification", 0) / total, 4)
        if total
        else None,
        "approval_required_rate": round(waiting.get("approval", 0) / total, 4)
        if total
        else None,
        "version_breakdown": versions,
        "environment_breakdown": environments,
        "knowledge_source_usage": [],
        "feedback": {"count": 0, "positive": 0, "negative": 0},
        "tool_usage": [
            {
                "name": name,
                "executions": count,
                "succeeded": succeeded or 0,
                "failed": failed or 0,
            }
            for name, count, succeeded, failed in tools
        ],
    }


@agent_router.get("/{agent_id}/executions/{execution_id}")
def get_agent_execution(
    agent_id: str,
    execution_id: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    result = agent_execution_service.get(db, identity(user), execution_id)
    if result["agent_id"] != agent_id:
        from fastapi import HTTPException

        raise HTTPException(
            404, {"code": "AGENT_EXECUTION_NOT_FOUND", "message": "Execution not found"}
        )
    continuation_rows = (
        db.query(AgentContinuation)
        .filter_by(execution_id=execution_id, tenant_id=identity(user).tenant_id)
        .order_by(AgentContinuation.created_at)
        .all()
    )
    tool_rows = (
        db.query(ToolExecution)
        .filter(ToolExecution.id.in_(result["tool_execution_ids"] or []))
        .all()
    )
    discovery = (
        db.get(ToolDiscoveryEvent, result["discovery_id"])
        if result["discovery_id"]
        else None
    )
    return {
        **result,
        "continuations": [
            {
                "id": row.id,
                "kind": row.kind,
                "status": row.status,
                "created_at": row.created_at,
                "expires_at": row.expires_at,
                "consumed_at": row.consumed_at,
            }
            for row in continuation_rows
        ],
        "tool_executions": [
            {
                "id": row.id,
                "tool_name": row.tool_name,
                "tool_version": row.tool_version,
                "status": row.status,
                "duration_ms": row.duration_ms,
                "error_code": row.error_code,
            }
            for row in tool_rows
        ],
        "discovery": {
            "id": discovery.id,
            "outcome": discovery.outcome,
            "selected_tool": discovery.selected_tool,
            "confidence": discovery.confidence,
            "duration_ms": discovery.duration_ms,
        }
        if discovery
        else None,
    }


@agent_router.post("/{agent_id}/executions/{execution_id}/cancel")
def cancel_agent_execution(
    agent_id: str,
    execution_id: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    result = agent_execution_service.cancel(db, identity(user), execution_id)
    if result["agent_id"] != agent_id:
        from fastapi import HTTPException

        raise HTTPException(
            404, {"code": "AGENT_EXECUTION_NOT_FOUND", "message": "Execution not found"}
        )
    return result


@execution_router.get("/{execution_id}/continuation")
def get_continuation(
    execution_id: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    return agent_execution_service.get(db, identity(user), execution_id)


async def resume(
    execution_id: str, payload: ResumePayload, action: str, db: Session, user: dict
):
    return await agent_execution_service.resume(
        db,
        execution_id=execution_id,
        token=payload.resume_token,
        response=payload.response,
        identity=identity(user),
        action=action,
    )


@execution_router.post("/{execution_id}/input")
async def submit_input(
    execution_id: str,
    payload: ResumePayload,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    return await resume(execution_id, payload, "input", db, user)


@execution_router.post("/{execution_id}/clarify")
async def clarify(
    execution_id: str,
    payload: ResumePayload,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    return await resume(execution_id, payload, "clarification", db, user)


@execution_router.post("/{execution_id}/approve")
async def approve(
    execution_id: str,
    payload: ResumePayload,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    return await resume(execution_id, payload, "approve", db, user)


@execution_router.post("/{execution_id}/deny")
async def deny(
    execution_id: str,
    payload: ResumePayload,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    return await resume(execution_id, payload, "deny", db, user)


@execution_router.post("/{execution_id}/resume")
async def resume_generic(
    execution_id: str,
    payload: ResumePayload,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    current = agent_execution_service.get(db, identity(user), execution_id)
    continuation = current.get("continuation") or {}
    return await resume(
        execution_id, payload, continuation.get("kind", "input"), db, user
    )
