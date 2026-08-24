from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database.dependencies import get_db
from app.database.models.agent import Agent
from app.models.runtime_execution import RuntimeExecution

router = APIRouter(
    prefix="/api/dashboard",
    tags=["Dashboard"],
)


# ==================================================
# Helpers
# ==================================================


def _tenant_id(user: dict) -> str:
    """
    Resolve the tenant for the authenticated user.
    """
    return user.get("custom:tenant_id", "default")


def _executions(
    db: Session,
    user_id: str,
) -> list[RuntimeExecution]:
    """
    Return runtime executions belonging to the current user.
    """
    return (
        db.query(RuntimeExecution)
        .filter(RuntimeExecution.user_id == user_id)
        .order_by(RuntimeExecution.started_at.desc())
        .all()
    )


def _enabled_agents(
    db: Session,
    tenant_id: str,
) -> list[Agent]:
    """
    Return all enabled persisted agents for the tenant.

    Persisted agents are the source of truth for the
    dashboard rather than the in-memory runtime registry.
    """
    return (
        db.query(Agent)
        .filter(
            Agent.tenant_id == tenant_id,
            Agent.lifecycle_status == "enabled",
        )
        .order_by(Agent.updated_at.desc())
        .all()
    )


def _agent_model_configuration(
    agent: Agent,
) -> tuple[str | None, str | None]:
    """
    Extract provider/model information from the persisted
    agent configuration.
    """
    try:
        configuration = json.loads(agent.configuration or "{}")
    except (TypeError, json.JSONDecodeError):
        configuration = {}

    model_configuration = (
        configuration.get(
            "model_configuration",
            {},
        )
        or {}
    )

    provider = (
        model_configuration.get("provider") or agent.model_configuration_ref or None
    )

    model = model_configuration.get("model") or None

    return provider, model


def _agent_runtime_status(
    agent: Agent,
) -> str:
    """
    Convert lifecycle state into the dashboard runtime status.

    An enabled agent is considered ready for execution even
    when operational_health has not yet been calculated.
    """
    if agent.lifecycle_status == "enabled":
        return "ready"

    return (agent.lifecycle_status or "unknown").lower()


# ==================================================
# Dashboard Metrics
# ==================================================


@router.get("/metrics")
def dashboard_metrics(
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    executions = _executions(
        db,
        user["sub"],
    )

    agents = _enabled_agents(
        db,
        _tenant_id(user),
    )

    status = Counter(execution.status for execution in executions)

    terminal = status["COMPLETED"] + status["FAILED"]

    actions = sum(
        1
        for execution in executions
        for step in execution.steps or []
        if (
            step.get("name") == "Generate Report Action"
            and step.get("status") == "completed"
        )
    )

    return {
        "total_workflows": len(executions),
        "active_workflows": status["RUNNING"],
        # Changed:
        # Use persisted enabled agents rather than
        # get_agent_registry().list_agents()
        "active_agents": len(agents),
        "actions_executed": actions,
        "success_rate": round(
            (status["COMPLETED"] / terminal * 100) if terminal else 0,
            1,
        ),
        "trends": {
            "workflows": 0,
            "agents": 0,
            "actions": 0,
            "success": 0,
        },
    }


# ==================================================
# Execution Trends
# ==================================================


@router.get("/executions/trends")
def execution_trends(
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    executions = _executions(
        db,
        user["sub"],
    )

    today = datetime.now(UTC).date()

    buckets = []

    for days_ago in range(6, -1, -1):
        day = today - timedelta(days=days_ago)

        rows = [item for item in executions if item.started_at.date() == day]

        statuses = Counter(item.status for item in rows)

        buckets.append(
            {
                "date": day.strftime("%b %d"),
                "successful": (statuses["COMPLETED"]),
                "running": (statuses["RUNNING"]),
                "failed": (statuses["FAILED"]),
            }
        )

    return buckets


# ==================================================
# Workflow Distribution
# ==================================================


@router.get("/workflow-distribution")
def workflow_distribution(
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    status = Counter(
        item.status
        for item in _executions(
            db,
            user["sub"],
        )
    )

    return {
        "completed": status["COMPLETED"],
        "running": status["RUNNING"],
        "pending": status["PENDING"],
        "failed": (status["FAILED"] + status["CANCELLED"]),
    }


# ==================================================
# Recent Executions
# ==================================================


@router.get("/recent-executions")
def recent_executions(
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    now = datetime.now(UTC)

    return [
        {
            "id": str(item.id),
            "workflow": (item.goal or (f"Workflow {str(item.workflow_id)[:8]}")),
            "agent": (item.agent or "default-agent"),
            "status": item.status.lower(),
            "duration_ms": item.duration_ms,
            "started_at": (item.started_at.isoformat()),
            "age_seconds": max(
                0,
                int((now.replace(tzinfo=None) - item.started_at).total_seconds()),
            ),
        }
        for item in _executions(
            db,
            user["sub"],
        )[:6]
    ]


# ==================================================
# Agent Status
# ==================================================


@router.get("/agents/status")
def agent_status(
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """
    Return all enabled persisted agents available to the
    authenticated tenant.

    Includes provider/model information so the frontend
    can distinguish OpenAI and Bedrock agents.
    """

    tenant_id = _tenant_id(user)

    agents = _enabled_agents(
        db,
        tenant_id,
    )

    result = []

    for agent in agents:
        provider, model = _agent_model_configuration(agent)

        result.append(
            {
                "id": agent.uuid,
                "name": agent.name,
                "slug": agent.slug,
                # Dashboard status
                "status": (_agent_runtime_status(agent)),
                # Actual persisted health
                "health": (agent.operational_health or "unknown"),
                "lifecycle_status": (agent.lifecycle_status),
                # AI configuration
                "provider": provider,
                "model": model,
                # Version information
                "version": (agent.published_version or agent.current_version),
            }
        )

    return result
