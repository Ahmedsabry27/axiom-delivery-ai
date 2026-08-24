from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.agents.application_service import AgentIdentity, agent_application_service
from app.auth.dependencies import get_current_user
from app.core.config import settings
from app.database.dependencies import get_db
from app.database.models.agent import Agent, AgentActivityEvent
from app.database.models.agent_assignment import (
    AgentKnowledgeAssignment,
    AgentToolAssignment,
)
from app.database.models.agent_execution import AgentExecution
from app.database.models.governance import (
    EvaluationDataset,
    EvaluationRun,
    GovernedModel,
)
from app.database.models.knowledge_source import KnowledgeSource
from app.database.models.tool import ToolDefinition
from app.governance.service import EvaluationRunnerService

router = APIRouter(prefix="/api/v1/agents", tags=["Agents v1"])


SUPPORTED_AGENT_MODELS: dict[str, tuple[dict[str, str], ...]] = {
    "openai": (
        {
            "provider": "openai",
            "model": "gpt-4.1-mini",
            "label": "OpenAI GPT-4.1 Mini",
        },
    ),
    "bedrock": (
        {
            "provider": "bedrock",
            "model": "amazon.nova-micro-v1:0",
            "label": "Amazon Nova Micro",
        },
        {
            "provider": "bedrock",
            "model": "amazon.nova-lite-v1:0",
            "label": "Amazon Nova Lite",
        },
        {
            "provider": "bedrock",
            "model": "amazon.nova-pro-v1:0",
            "label": "Amazon Nova Pro",
        },
        {
            "provider": "bedrock",
            "model": "openai.gpt-oss-20b-1:0",
            "label": "GPT OSS 20B through Bedrock",
        },
        {
            "provider": "bedrock",
            "model": "openai.gpt-oss-120b-1:0",
            "label": "GPT OSS 120B through Bedrock",
        },
        {
            "provider": "bedrock",
            "model": "qwen.qwen3-coder-next",
            "label": "Qwen 3 Coder Next through Bedrock",
        },
        {
            "provider": "bedrock",
            "model": "deepseek.v3.2",
            "label": "DeepSeek V3.2 through Bedrock",
        },
    ),
}


def default_agent_model() -> dict[str, str]:
    provider = settings.AI_PROVIDER.strip().lower()

    if provider == "bedrock":
        model = settings.BEDROCK_MODEL_ID
    else:
        provider = "openai"
        model = settings.OPENAI_MODEL

    return {
        "provider": provider,
        "model": model,
    }


def available_agent_models() -> list[dict[str, str | bool]]:
    default = default_agent_model()
    models: list[dict[str, str | bool]] = []

    for provider_models in SUPPORTED_AGENT_MODELS.values():
        for item in provider_models:
            models.append(
                {
                    **item,
                    "default": (
                        item["provider"] == default["provider"]
                        and item["model"] == default["model"]
                    ),
                }
            )

    models.sort(
        key=lambda item: (
            not bool(item["default"]),
            str(item["provider"]),
            str(item["label"]),
        )
    )

    return models


def validate_model_configuration(
    configuration: dict[str, Any] | None,
) -> None:
    if not configuration:
        return

    raw_provider = configuration.get("provider")
    raw_model = configuration.get("model")

    if raw_provider is None and raw_model is None:
        return

    provider = str(raw_provider or "").strip().lower()
    model = str(raw_model or "").strip()

    if not provider:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "MODEL_PROVIDER_REQUIRED",
                "message": (
                    "model_configuration.provider is required when a model is selected"
                ),
            },
        )

    if not model:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "MODEL_NAME_REQUIRED",
                "message": (
                    "model_configuration.model is required when a provider is selected"
                ),
            },
        )

    provider_models = SUPPORTED_AGENT_MODELS.get(provider)

    if provider_models is None:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "UNSUPPORTED_MODEL_PROVIDER",
                "message": f"Unsupported AI provider: {provider}",
            },
        )

    allowed_models = {item["model"] for item in provider_models}

    if model not in allowed_models:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "UNSUPPORTED_MODEL",
                "message": (
                    f"Model '{model}' is not enabled for provider '{provider}'"
                ),
                "provider": provider,
                "allowed_models": sorted(allowed_models),
            },
        )


class AgentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=2, max_length=120)
    slug: str | None = Field(default=None, max_length=120)
    description: str = Field(default="", max_length=4000)
    owner_id: str | None = Field(default=None, max_length=160)
    instructions: str = Field(default="", max_length=50000)
    model_configuration_ref: str | None = Field(default=None, max_length=200)
    model_configuration: dict[str, Any] = Field(default_factory=dict)
    planner_configuration: dict[str, Any] = Field(default_factory=dict)
    memory_configuration: dict[str, Any] = Field(default_factory=dict)
    execution_limits: dict[str, Any] = Field(default_factory=dict)
    tool_discovery_configuration: dict[str, Any] = Field(
        default_factory=lambda: {"mode": "assigned_only"}
    )
    capabilities: list[str] = Field(default_factory=list, max_length=100)
    change_note: str = Field(default="Initial draft", max_length=500)


class AgentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=2, max_length=120)
    slug: str | None = Field(default=None, max_length=120)
    description: str | None = Field(default=None, max_length=4000)
    instructions: str | None = Field(default=None, max_length=50000)
    model_configuration_ref: str | None = Field(default=None, max_length=200)
    model_configuration: dict[str, Any] | None = None
    planner_configuration: dict[str, Any] | None = None
    memory_configuration: dict[str, Any] | None = None
    execution_limits: dict[str, Any] | None = None
    tool_discovery_configuration: dict[str, Any] | None = None
    capabilities: list[str] | None = Field(default=None, max_length=100)
    change_note: str = Field(default="Draft updated", max_length=500)


class LifecyclePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    change_note: str = Field(default="", max_length=500)
    confirmed: bool = False


class AgentEvaluationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dataset_id: str = Field(min_length=1, max_length=36)
    model_id: str = Field(min_length=1, max_length=36)


class ToolAssignmentPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tool_name: str = Field(min_length=1, max_length=100)
    version_restriction: str | None = Field(default="active", max_length=80)
    assignment_action: Literal["execute", "discover"] = "execute"
    enabled: bool = True
    risk_mode: Literal["read", "write", "destructive"] = "read"
    approval_required: bool = False


class KnowledgeAssignmentPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    knowledge_source_id: int = Field(gt=0)
    access_mode: Literal["read", "search", "retrieve"] = "read"
    readiness_required: bool = True
    enabled: bool = True


class AccessAssignmentPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subject_type: Literal["user", "group", "role", "service"]
    subject_id: str = Field(min_length=1, max_length=160)
    action: Literal[
        "view",
        "edit",
        "publish",
        "execute",
        "manage_tools",
        "manage_knowledge",
        "manage_access",
        "view_executions",
        "view_analytics",
    ]
    enabled: bool = True


class ToolAssignments(BaseModel):
    model_config = ConfigDict(extra="forbid")
    assignments: list[ToolAssignmentPayload] = Field(max_length=100)


class KnowledgeAssignments(BaseModel):
    model_config = ConfigDict(extra="forbid")
    assignments: list[KnowledgeAssignmentPayload] = Field(max_length=100)


class AccessAssignments(BaseModel):
    model_config = ConfigDict(extra="forbid")
    assignments: list[AccessAssignmentPayload] = Field(max_length=200)


def serialize(row: Agent, metrics: dict[str, Any] | None = None) -> dict[str, Any]:
    import json

    config = json.loads(row.configuration or "{}")
    model = config.get("model_configuration", {})
    return {
        "id": row.uuid,
        "tenant_id": row.tenant_id,
        "slug": row.slug,
        "name": row.name,
        "description": row.description,
        "owner_id": row.owner_id,
        "lifecycle_status": row.lifecycle_status,
        "operational_health": row.operational_health,
        "current_version": row.current_version,
        "published_version": row.published_version,
        "model_configuration_ref": row.model_configuration_ref,
        "model": model.get("model"),
        "model_provider": model.get("provider") or row.model_configuration_ref,
        "environment_restrictions": row.environment_restrictions,
        "tool_count": 0,
        "knowledge_count": 0,
        "execution_count": 0,
        "success_rate": None,
        "last_execution_at": None,
        "permissions": {},
        **(metrics or {}),
        "lock_version": row.lock_version,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


def identity(user: dict[str, Any]) -> AgentIdentity:
    return AgentIdentity.from_claims(user)


def assignment_dict(row: Any) -> dict[str, Any]:
    return {
        column.name: getattr(row, column.name)
        for column in row.__table__.columns
        if column.name not in {"agent_id", "tenant_id"}
    }


@router.get("")
def list_agents(
    search: str | None = None,
    status: Literal["draft", "published", "enabled", "disabled", "archived", "error"]
    | None = None,
    owner: str | None = None,
    model: str | None = None,
    environment: str | None = None,
    include_archived: bool = False,
    sort: Literal["name", "updated_at", "lifecycle", "owner"] = "updated_at",
    direction: Literal["asc", "desc"] = "desc",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),  # noqa: B008
    user: dict = Depends(get_current_user),  # noqa: B008
):
    rows, total = agent_application_service.list_agents(
        db,
        identity(user),
        search=search,
        status=status,
        owner=owner,
        page=page,
        page_size=page_size,
        include_archived=include_archived,
        model=model,
        environment=environment,
        sort=sort,
        direction=direction,
    )
    ids = [row.id for row in rows]
    metrics: dict[int, dict[str, Any]] = {row.id: {} for row in rows}
    if ids:
        for agent_id, count in (
            db.query(AgentToolAssignment.agent_id, func.count())
            .filter(
                AgentToolAssignment.agent_id.in_(ids),
                AgentToolAssignment.enabled.is_(True),
            )
            .group_by(AgentToolAssignment.agent_id)
        ):
            metrics[agent_id]["tool_count"] = count
        for agent_id, count in (
            db.query(AgentKnowledgeAssignment.agent_id, func.count())
            .filter(
                AgentKnowledgeAssignment.agent_id.in_(ids),
                AgentKnowledgeAssignment.enabled.is_(True),
            )
            .group_by(AgentKnowledgeAssignment.agent_id)
        ):
            metrics[agent_id]["knowledge_count"] = count
        for agent_id, count, succeeded, last_at in (
            db.query(
                AgentExecution.agent_id,
                func.count(),
                func.sum(case((AgentExecution.status == "succeeded", 1), else_=0)),
                func.max(AgentExecution.started_at),
            )
            .filter(
                AgentExecution.agent_id.in_(ids),
                AgentExecution.tenant_id == identity(user).tenant_id,
            )
            .group_by(AgentExecution.agent_id)
        ):
            metrics[agent_id].update(
                {
                    "execution_count": count,
                    "success_rate": round(100 * (succeeded or 0) / count, 1),
                    "last_execution_at": last_at,
                }
            )
    permission_flags = {
        "create": identity(user).allows("agents.create"),
        "admin": identity(user).allows("agents.admin"),
    }
    return {
        "items": [
            serialize(row, {**metrics[row.id], "permissions": permission_flags})
            for row in rows
        ],
        "page": page,
        "page_size": page_size,
        "total": total,
        "pages": max(1, (total + page_size - 1) // page_size),
    }


@router.get("/capabilities/options")
def capability_options(
    db: Session = Depends(get_db),  # noqa: B008
    user: dict = Depends(get_current_user),  # noqa: B008
):
    ctx = identity(user)
    agent_application_service._require(ctx, "agents.create")
    tools = (
        db.query(ToolDefinition)
        .filter_by(tenant_id=ctx.tenant_id, enabled=True, active=True)
        .order_by(ToolDefinition.display_name)
        .all()
    )
    knowledge = (
        db.query(KnowledgeSource)
        .filter_by(tenant_id=ctx.tenant_id)
        .order_by(KnowledgeSource.name)
        .all()
    )
    return {
        "models": available_agent_models(),
        "default_model": default_agent_model(),
        "planners": [
            {"name": "default", "label": "Default planner"},
            {"name": "sequential", "label": "Sequential planner"},
        ],
        "tools": [
            {
                "name": row.name,
                "display_name": row.display_name,
                "description": row.description,
                "provider": row.provider,
                "category": row.category,
                "version": row.version,
                "risk": row.risk_level,
                "enabled": row.enabled,
            }
            for row in tools
        ],
        "knowledge": [
            {
                "id": row.id,
                "name": row.name,
                "source_type": row.source_type,
                "owner_id": row.owner_id,
                "readiness": row.readiness_status,
                "health": row.health_status,
                "last_synchronized_at": row.last_synchronized_at,
            }
            for row in knowledge
        ],
        "access_actions": [
            "view",
            "edit",
            "publish",
            "execute",
            "manage_tools",
            "manage_knowledge",
            "manage_access",
            "view_executions",
            "view_analytics",
        ],
        "subject_types": ["user", "group", "role", "service"],
        "limits": {
            "max_steps": {"min": 1, "max": 100},
            "timeout_seconds": {"min": 1, "max": 3600},
            "cost_limit": {"min": 0},
        },
    }


@router.post("", status_code=201)
def create_agent(
    payload: AgentCreate,
    db: Session = Depends(get_db),  # noqa: B008
    user: dict = Depends(get_current_user),  # noqa: B008
):
    data = payload.model_dump()
    validate_model_configuration(data.get("model_configuration"))

    return serialize(
        agent_application_service.create(
            db,
            identity(user),
            data,
        )
    )


@router.get("/{agent_id}")
def get_agent(
    agent_id: str,
    db: Session = Depends(get_db),  # noqa: B008
    user: dict = Depends(get_current_user),  # noqa: B008
):
    import json

    row = agent_application_service.get(db, identity(user), agent_id)
    config = json.loads(row.configuration or "{}")
    return {
        **serialize(row),
        "configuration": config,
        "instructions": config.get("instructions", ""),
        "model_configuration": config.get("model_configuration", {}),
        "planner_configuration": config.get("planner_configuration", {}),
        "memory_configuration": config.get("memory_configuration", {}),
        "execution_limits": config.get("execution_limits", {}),
        "tool_discovery_configuration": config.get("tool_discovery_configuration", {}),
        "capabilities": config.get("capabilities", []),
        "permissions": {
            "edit": identity(user).allows("agents.update")
            or row.owner_id == identity(user).actor_id,
            "publish": identity(user).allows("agents.publish"),
            "enable": identity(user).allows("agents.enable"),
            "disable": identity(user).allows("agents.disable"),
            "archive": identity(user).allows("agents.archive"),
            "restore": identity(user).allows("agents.restore"),
            "manage_tools": identity(user).allows("agents.tools.manage"),
            "manage_knowledge": identity(user).allows("agents.knowledge.manage"),
            "manage_access": identity(user).allows("agents.access.manage"),
            "read_executions": identity(user).allows("agents.executions.read")
            or row.owner_id == identity(user).actor_id,
            "read_analytics": identity(user).allows("agents.analytics.read")
            or row.owner_id == identity(user).actor_id,
        },
    }


@router.patch("/{agent_id}")
def update_agent(
    agent_id: str,
    payload: AgentUpdate,
    if_match: int = Header(alias="If-Match"),
    db: Session = Depends(get_db),  # noqa: B008
    user: dict = Depends(get_current_user),  # noqa: B008
):
    data = payload.model_dump(exclude_none=True)

    if "model_configuration" in data:
        validate_model_configuration(data["model_configuration"])

    return serialize(
        agent_application_service.update(
            db,
            identity(user),
            agent_id,
            data,
            if_match,
        )
    )


@router.post("/{agent_id}/publish")
def publish_agent(
    agent_id: str,
    payload: LifecyclePayload,
    if_match: int = Header(alias="If-Match"),
    db: Session = Depends(get_db),  # noqa: B008
    user: dict = Depends(get_current_user),  # noqa: B008
):
    return serialize(
        agent_application_service.publish(
            db, identity(user), agent_id, if_match, payload.change_note
        )
    )


def lifecycle_response(
    action: str,
    agent_id: str,
    payload: LifecyclePayload,
    if_match: int,
    db: Session,
    user: dict,
):
    return serialize(
        agent_application_service.lifecycle(
            db,
            identity(user),
            agent_id,
            action,
            if_match,
            confirmed=payload.confirmed,
        )
    )


@router.post("/{agent_id}/enable")
def enable_agent(
    agent_id: str,
    payload: LifecyclePayload,
    if_match: int = Header(alias="If-Match"),
    db: Session = Depends(get_db),  # noqa: B008
    user: dict = Depends(get_current_user),  # noqa: B008
):
    return lifecycle_response("enable", agent_id, payload, if_match, db, user)


@router.post("/{agent_id}/disable")
def disable_agent(
    agent_id: str,
    payload: LifecyclePayload,
    if_match: int = Header(alias="If-Match"),
    db: Session = Depends(get_db),  # noqa: B008
    user: dict = Depends(get_current_user),  # noqa: B008
):
    return lifecycle_response("disable", agent_id, payload, if_match, db, user)


@router.post("/{agent_id}/archive")
def archive_agent(
    agent_id: str,
    payload: LifecyclePayload,
    if_match: int = Header(alias="If-Match"),
    db: Session = Depends(get_db),  # noqa: B008
    user: dict = Depends(get_current_user),  # noqa: B008
):
    return lifecycle_response("archive", agent_id, payload, if_match, db, user)


@router.post("/{agent_id}/restore")
def restore_agent(
    agent_id: str,
    payload: LifecyclePayload,
    if_match: int = Header(alias="If-Match"),
    db: Session = Depends(get_db),  # noqa: B008
    user: dict = Depends(get_current_user),  # noqa: B008
):
    return lifecycle_response("restore", agent_id, payload, if_match, db, user)


@router.get("/{agent_id}/versions")
def list_versions(
    agent_id: str,
    db: Session = Depends(get_db),  # noqa: B008
    user: dict = Depends(get_current_user),  # noqa: B008
):
    rows = agent_application_service.versions(db, identity(user), agent_id)
    import hashlib

    return [
        {
            "version": row.version,
            "instructions": row.instructions,
            "model_configuration": row.model_configuration,
            "planner_configuration": row.planner_configuration,
            "memory_configuration": row.memory_configuration,
            "execution_limits": row.execution_limits,
            "tool_discovery_configuration": row.tool_discovery_configuration,
            "change_note": row.change_note,
            "created_by": row.created_by,
            "created_at": row.created_at,
            "published": row.published,
            "fingerprint": hashlib.sha256(
                str(row.configuration_snapshot).encode()
            ).hexdigest(),
        }
        for row in rows
    ]


@router.get("/{agent_id}/evaluations")
def list_agent_evaluations(
    agent_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),  # noqa: B008
    user: dict = Depends(get_current_user),  # noqa: B008
):
    ctx = identity(user)
    row = agent_application_service.get(db, ctx, agent_id)
    query = db.query(EvaluationRun).filter_by(
        tenant_id=ctx.tenant_id, agent_id=row.uuid
    )
    total = query.count()
    runs = (
        query.order_by(EvaluationRun.started_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "items": [
            {
                "id": run.id,
                "agent_version": run.agent_version,
                "dataset_id": run.dataset_id,
                "dataset_version": run.dataset_version,
                "model_id": run.model_id,
                "status": run.status,
                "scores": run.scores,
                "failures": run.failures,
                "trace_ids": run.trace_ids,
                "started_at": run.started_at,
                "completed_at": run.completed_at,
            }
            for run in runs
        ],
        "page": page,
        "page_size": page_size,
        "total": total,
        "pages": max(1, (total + page_size - 1) // page_size),
    }


@router.post("/{agent_id}/evaluations", status_code=201)
def run_agent_evaluation(
    agent_id: str,
    payload: AgentEvaluationCreate,
    db: Session = Depends(get_db),  # noqa: B008
    user: dict = Depends(get_current_user),  # noqa: B008
):
    ctx = identity(user)
    agent_application_service._require(ctx, "agents.evaluate")
    agent = agent_application_service.get(db, ctx, agent_id)
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
                "message": "Evaluation dataset or governed model not found",
            },
        )
    run = EvaluationRunnerService.run(db, ctx, dataset, model)
    run.agent_id = agent.uuid
    run.agent_version = agent.current_version
    db.add(
        AgentActivityEvent(
            agent_id=agent.id,
            tenant_id=agent.tenant_id,
            event_type="agent.evaluation.completed",
            actor_id=ctx.actor_id,
            agent_version=agent.current_version,
            summary={"evaluation_run_id": run.id, "status": run.status},
        )
    )
    db.commit()
    db.refresh(run)
    return {
        "id": run.id,
        "agent_version": run.agent_version,
        "status": run.status,
        "scores": run.scores,
        "failures": run.failures,
        "started_at": run.started_at,
        "completed_at": run.completed_at,
    }


@router.get("/{agent_id}/versions/{version}")
def get_version(
    agent_id: str,
    version: int,
    db: Session = Depends(get_db),  # noqa: B008
    user: dict = Depends(get_current_user),  # noqa: B008
):
    rows = agent_application_service.versions(db, identity(user), agent_id)
    item = next((row for row in rows if row.version == version), None)
    if item is None:
        raise HTTPException(
            404,
            {"code": "AGENT_VERSION_NOT_FOUND", "message": "Agent version not found"},
        )
    return {
        "version": item.version,
        "instructions": item.instructions,
        "model_configuration": item.model_configuration,
        "planner_configuration": item.planner_configuration,
        "memory_configuration": item.memory_configuration,
        "execution_limits": item.execution_limits,
        "tool_discovery_configuration": item.tool_discovery_configuration,
        "change_note": item.change_note,
        "created_by": item.created_by,
        "created_at": item.created_at,
        "published": item.published,
    }


def assignment_response(agent_id: str, kind: str, db: Session, user: dict):
    return [
        assignment_dict(row)
        for row in agent_application_service.assignments(
            db, identity(user), agent_id, kind
        )
    ]


@router.get("/{agent_id}/tools")
def get_tools(
    agent_id: str,
    db: Session = Depends(get_db),  # noqa: B008
    user: dict = Depends(get_current_user),  # noqa: B008
):
    return assignment_response(agent_id, "tools", db, user)


@router.get("/{agent_id}/knowledge")
def get_knowledge(
    agent_id: str,
    db: Session = Depends(get_db),  # noqa: B008
    user: dict = Depends(get_current_user),  # noqa: B008
):
    return assignment_response(agent_id, "knowledge", db, user)


@router.get("/{agent_id}/access")
def get_access(
    agent_id: str,
    db: Session = Depends(get_db),  # noqa: B008
    user: dict = Depends(get_current_user),  # noqa: B008
):
    return assignment_response(agent_id, "access", db, user)


@router.get("/{agent_id}/effective-access")
def get_effective_access(
    agent_id: str,
    action: Literal[
        "view",
        "edit",
        "publish",
        "execute",
        "manage_tools",
        "manage_knowledge",
        "manage_access",
        "view_executions",
        "view_analytics",
    ] = "view",
    db: Session = Depends(get_db),  # noqa: B008
    user: dict = Depends(get_current_user),  # noqa: B008
):
    return agent_application_service.effective_access(
        db, identity(user), agent_id, action
    )


@router.put("/{agent_id}/tools")
def put_tools(
    agent_id: str,
    payload: ToolAssignments,
    db: Session = Depends(get_db),  # noqa: B008
    user: dict = Depends(get_current_user),  # noqa: B008
):
    rows = agent_application_service.set_tools(
        db,
        identity(user),
        agent_id,
        [item.model_dump() for item in payload.assignments],
    )
    return [assignment_dict(row) for row in rows]


@router.put("/{agent_id}/knowledge")
def put_knowledge(
    agent_id: str,
    payload: KnowledgeAssignments,
    db: Session = Depends(get_db),  # noqa: B008
    user: dict = Depends(get_current_user),  # noqa: B008
):
    rows = agent_application_service.set_knowledge(
        db,
        identity(user),
        agent_id,
        [item.model_dump() for item in payload.assignments],
    )
    return [assignment_dict(row) for row in rows]


@router.put("/{agent_id}/access")
def put_access(
    agent_id: str,
    payload: AccessAssignments,
    db: Session = Depends(get_db),  # noqa: B008
    user: dict = Depends(get_current_user),  # noqa: B008
):
    rows = agent_application_service.set_access(
        db,
        identity(user),
        agent_id,
        [item.model_dump() for item in payload.assignments],
    )
    return [assignment_dict(row) for row in rows]


@router.delete("/{agent_id}/{kind}/{assignment_id}", status_code=204)
def delete_assignment(
    agent_id: str,
    kind: Literal["tools", "knowledge", "access"],
    assignment_id: str,
    db: Session = Depends(get_db),  # noqa: B008
    user: dict = Depends(get_current_user),  # noqa: B008
):
    agent_application_service.remove_assignment(
        db, identity(user), agent_id, kind, assignment_id
    )


@router.get("/{agent_id}/activity")
def get_activity(
    agent_id: str,
    event_type: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),  # noqa: B008
    user: dict = Depends(get_current_user),  # noqa: B008
):
    rows = agent_application_service.activity(db, identity(user), agent_id)
    if event_type:
        rows = [row for row in rows if row.event_type == event_type]
    total = len(rows)
    rows = rows[(page - 1) * page_size : page * page_size]
    return {
        "items": [
            {
                "id": row.id,
                "event_type": row.event_type,
                "actor_id": row.actor_id,
                "agent_version": row.agent_version,
                "summary": row.summary,
                "created_at": row.created_at,
            }
            for row in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, (total + page_size - 1) // page_size),
    }
