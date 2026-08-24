from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.agents.application_service import AgentIdentity, agent_application_service
from app.api.runtime import runtime_events_stream
from app.auth.dependencies import get_current_user
from app.database.dependencies import get_db
from app.database.models.action import Action
from app.database.models.agent import Agent
from app.database.models.knowledge_source import KnowledgeSource
from app.database.models.workflow import (
    Workflow,
    WorkflowActivityEvent,
    WorkflowVersion,
)
from app.models.runtime_execution import RuntimeExecution

router = APIRouter(prefix="/api", tags=["Management"])


class AgentPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)
    type: str = "Workflow"
    description: str = ""
    capabilities: list[str] = Field(default_factory=list)
    purpose: str = ""
    model: str = "GPT-5.5"
    memory_enabled: bool = True
    instructions: str = ""
    tools: list[str] = Field(default_factory=list)
    knowledge_sources: list[str] = Field(default_factory=list)
    permissions: dict[str, bool] = Field(default_factory=dict)


class AgentPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=1, max_length=120)
    status: str | None = None
    type: str | None = None
    description: str | None = None
    capabilities: list[str] | None = None
    purpose: str | None = None
    model: str | None = None
    memory_enabled: bool | None = None
    instructions: str | None = None
    tools: list[str] | None = None
    knowledge_sources: list[str] | None = None
    permissions: dict[str, bool] | None = None


class WorkflowPayload(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str = ""
    assigned_agent: str | None = None
    trigger_type: str = "MANUAL"
    definition: dict = Field(default_factory=dict)


class ActionPayload(BaseModel):
    name: str
    type: str
    permissions: dict = Field(default_factory=dict)


class KnowledgePayload(BaseModel):
    name: str
    source_type: str = "DOCUMENT"
    location: str | None = None


def _agent_response(agent: Agent, executions: list[RuntimeExecution]) -> dict:
    config = json.loads(agent.configuration or "{}")
    related = [item for item in executions if item.agent == agent.name]
    finished = [item for item in related if item.status in {"COMPLETED", "FAILED"}]
    success_rate = (
        round(
            100 * sum(item.status == "COMPLETED" for item in finished) / len(finished),
            1,
        )
        if finished
        else 0
    )
    last_active = max((item.started_at for item in related), default=agent.created_at)
    model_config = config.get("model_configuration", {})
    return {
        "id": agent.id,
        "uuid": agent.uuid,
        "name": agent.name,
        "status": agent.lifecycle_status,
        "type": config.get("type", "Workflow"),
        "description": agent.description,
        "purpose": config.get("purpose", ""),
        "model": model_config.get("model", config.get("model", "")),
        "memory_enabled": config.get("memory_configuration", {}).get(
            "enabled", config.get("memory_enabled", True)
        ),
        "instructions": config.get("instructions", ""),
        "capabilities": config.get("capabilities", []),
        "tools": config.get("tool_discovery_configuration", {}).get(
            "legacy_tools", config.get("tools", [])
        ),
        "knowledge_sources": config.get("knowledge_sources", []),
        "permissions": config.get("permissions", {}),
        "executions": len(related),
        "success_rate": success_rate,
        "last_active": last_active.isoformat(),
        "created_at": agent.created_at.isoformat(),
    }


def _agent_identity(user: dict) -> AgentIdentity:
    return AgentIdentity.from_claims(user)


@router.get("/agents")
def list_agents(db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    ctx = _agent_identity(user)
    agent_application_service._require(ctx, "agents.list")
    executions = (
        db.query(RuntimeExecution).filter(RuntimeExecution.user_id == user["sub"]).all()
    )
    rows = db.query(Agent).filter(
        Agent.tenant_id == ctx.tenant_id,
        Agent.deleted_at.is_(None),
        Agent.lifecycle_status != "archived",
    )
    if not ctx.allows("agents.read"):
        rows = rows.filter(Agent.owner_id == ctx.actor_id)
    return [
        _agent_response(agent, executions) for agent in rows.order_by(Agent.name).all()
    ]


@router.get("/agents/{agent_id}")
def get_agent(
    agent_id: int, db: Session = Depends(get_db), user: dict = Depends(get_current_user)
):
    ctx = _agent_identity(user)
    agent_application_service._require(ctx, "agents.read")
    agent = (
        db.query(Agent)
        .filter(
            Agent.id == agent_id,
            Agent.tenant_id == ctx.tenant_id,
            Agent.deleted_at.is_(None),
        )
        .first()
    )
    if not agent:
        raise HTTPException(404, "Agent not found")
    executions = (
        db.query(RuntimeExecution).filter(RuntimeExecution.user_id == user["sub"]).all()
    )
    return _agent_response(agent, executions)


@router.get("/agents/{agent_id}/executions")
def get_agent_executions(
    agent_id: int, db: Session = Depends(get_db), user: dict = Depends(get_current_user)
):
    ctx = _agent_identity(user)
    agent_application_service._require(ctx, "agents.executions.read")
    agent = (
        db.query(Agent)
        .filter(
            Agent.id == agent_id,
            Agent.tenant_id == ctx.tenant_id,
            Agent.deleted_at.is_(None),
        )
        .first()
    )
    if not agent:
        raise HTTPException(404, "Agent not found")
    rows = (
        db.query(RuntimeExecution)
        .filter(
            RuntimeExecution.user_id == user["sub"],
            RuntimeExecution.agent == agent.name,
        )
        .order_by(RuntimeExecution.started_at.desc())
        .all()
    )
    return [
        {
            "execution_id": str(row.id),
            "status": row.status.lower(),
            "started_at": row.started_at.isoformat(),
            "duration": row.duration_ms,
            "result": "SUCCESS"
            if row.status == "COMPLETED"
            else "FAILED"
            if row.status == "FAILED"
            else row.status,
        }
        for row in rows
    ]


@router.get("/executions/{execution_id}/events")
async def execution_events(
    execution_id: UUID,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    """Compatibility route for execution detail screens; delegates to the durable runtime SSE stream."""
    return await runtime_events_stream(execution_id, db, user)


@router.get("/action-catalog")
def list_actions(db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    tenant_id = user.get("custom:tenant_id", "default")
    return [
        {
            "id": x.id,
            "name": x.name,
            "display_name": x.display_name or x.name,
            "type": x.type,
            "provider": x.provider,
            "category": x.category,
            "integration_connection_id": x.integration_connection_id,
            "risk_level": x.risk_level,
            "approval_required": x.approval_required,
            "permissions": x.permissions,
            "status": x.status.lower(),
            "usage": x.usage,
        }
        for x in db.query(Action)
        .filter_by(tenant_id=tenant_id)
        .order_by(Action.name)
        .all()
    ]


@router.post("/action-catalog", status_code=201)
def create_action(
    payload: ActionPayload,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    action = Action(
        tenant_id=user.get("custom:tenant_id", "default"),
        name=payload.name,
        type=payload.type,
        permissions=payload.permissions,
        status="ENABLED",
        usage=0,
    )
    db.add(action)
    db.commit()
    db.refresh(action)
    return {
        "id": action.id,
        "name": action.name,
        "type": action.type,
        "permissions": action.permissions,
        "status": "enabled",
        "usage": 0,
    }


@router.patch("/action-catalog/{action_id}")
def update_action(
    action_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    action = (
        db.query(Action)
        .filter_by(id=action_id, tenant_id=user.get("custom:tenant_id", "default"))
        .first()
    )
    if not action:
        raise HTTPException(404, "Action not found")
    if "status" in payload:
        action.status = payload["status"].upper()
    db.commit()
    return {"id": action.id, "status": action.status.lower()}


@router.post("/action-catalog/{action_id}/execute")
def execute_action(
    action_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    action = (
        db.query(Action)
        .filter_by(id=action_id, tenant_id=user.get("custom:tenant_id", "default"))
        .first()
    )
    if not action:
        raise HTTPException(404, "Action not found")
    if action.status != "ENABLED":
        raise HTTPException(409, "Action is disabled")
    action.usage += 1
    db.commit()
    return {"id": action.id, "status": "completed", "usage": action.usage}


@router.get("/knowledge")
def list_knowledge(
    search: str | None = None,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    rows = db.query(KnowledgeSource).order_by(KnowledgeSource.created_at.desc()).all()
    return [
        {
            "id": x.id,
            "name": x.name,
            "type": x.source_type,
            "location": x.location,
            "created_at": x.created_at.isoformat(),
        }
        for x in rows
        if not search or search.lower() in x.name.lower()
    ]


@router.post("/knowledge", status_code=201)
def create_knowledge(
    payload: KnowledgePayload,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    item = KnowledgeSource(
        name=payload.name, source_type=payload.source_type, location=payload.location
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return {
        "id": item.id,
        "name": item.name,
        "type": item.source_type,
        "location": item.location,
    }


@router.delete("/knowledge/{source_id}", status_code=204)
def delete_knowledge(
    source_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    item = db.get(KnowledgeSource, source_id)
    if not item:
        raise HTTPException(404, "Knowledge source not found")
    db.delete(item)
    db.commit()


@router.post("/agents", status_code=status.HTTP_201_CREATED)
def create_agent(
    payload: AgentPayload,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    data = payload.model_dump()
    agent = agent_application_service.create(
        db,
        _agent_identity(user),
        {
            "name": data["name"],
            "description": data["description"],
            "instructions": data["instructions"],
            "model_configuration": {"model": data["model"]},
            "memory_configuration": {"enabled": data["memory_enabled"]},
            "capabilities": data["capabilities"],
            "tool_discovery_configuration": {
                "mode": "assigned_only",
                "legacy_tools": data["tools"],
            },
            "change_note": "Created through legacy compatibility API",
        },
    )
    return _agent_response(agent, [])


@router.patch("/agents/{agent_id}")
def update_agent(
    agent_id: int,
    payload: AgentPatch,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    ctx = _agent_identity(user)
    agent = (
        db.query(Agent)
        .filter(
            Agent.id == agent_id,
            Agent.tenant_id == ctx.tenant_id,
            Agent.deleted_at.is_(None),
        )
        .first()
    )
    if not agent:
        raise HTTPException(404, "Agent not found")
    data = payload.model_dump(exclude_none=True)
    if "status" in data:
        raise HTTPException(
            409,
            {
                "code": "LIFECYCLE_ENDPOINT_REQUIRED",
                "message": "Use the governed lifecycle API",
            },
        )
    mapped = {
        key: value
        for key, value in data.items()
        if key in {"name", "description", "instructions", "capabilities"}
    }
    if "model" in data:
        mapped["model_configuration"] = {"model": data["model"]}
    if "memory_enabled" in data:
        mapped["memory_configuration"] = {"enabled": data["memory_enabled"]}
    if "tools" in data:
        mapped["tool_discovery_configuration"] = {
            "mode": "assigned_only",
            "legacy_tools": data["tools"],
        }
    mapped["change_note"] = "Updated through legacy compatibility API"
    agent = agent_application_service.update(
        db, ctx, agent.uuid, mapped, agent.lock_version
    )
    return _agent_response(agent, [])


@router.delete("/agents/{agent_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_agent(
    agent_id: int, db: Session = Depends(get_db), user: dict = Depends(get_current_user)
):
    raise HTTPException(
        405,
        {
            "code": "HARD_DELETE_DISABLED",
            "message": "Agents must be archived through the governed lifecycle API",
        },
    )


def _workflow_response(workflow: Workflow) -> dict:
    return {
        "id": workflow.id,
        "public_id": workflow.public_id,
        "name": workflow.goal,
        "description": workflow.description or "",
        "assigned_agent": workflow.assigned_agent,
        "trigger_type": workflow.trigger_type,
        "definition": workflow.definition or {"nodes": [], "edges": []},
        "status": workflow.lifecycle_status.lower(),
        "lifecycle_status": workflow.lifecycle_status,
        "owner_id": workflow.owner_id,
        "current_version": workflow.current_version,
        "published_version": workflow.published_version,
        "lock_version": workflow.lock_version,
        "executions": 0,
        "success_rate": 0,
        "last_modified": workflow.updated_at or workflow.created_at,
    }


def _managed_workflow(db: Session, workflow_id: int, user: dict) -> Workflow:
    workflow = (
        db.query(Workflow)
        .filter_by(
            id=workflow_id,
            tenant_id=str(user.get("custom:tenant_id", "default")),
        )
        .one_or_none()
    )
    if workflow is None:
        raise HTTPException(404, "Workflow not found")
    return workflow


def _validate_definition(definition: dict) -> dict:
    nodes = definition.get("nodes") if isinstance(definition, dict) else None
    edges = definition.get("edges") if isinstance(definition, dict) else None
    errors: list[dict] = []
    warnings: list[dict] = []
    if not isinstance(nodes, list):
        errors.append({"path": "definition.nodes", "message": "Nodes must be a list"})
        nodes = []
    if not isinstance(edges, list):
        errors.append({"path": "definition.edges", "message": "Edges must be a list"})
        edges = []
    ids = [str(node.get("id", "")) for node in nodes if isinstance(node, dict)]
    if len(ids) != len(set(ids)) or any(not value for value in ids):
        errors.append(
            {
                "path": "definition.nodes",
                "message": "Node IDs must be present and unique",
            }
        )
    types = [
        str(node.get("type", "")).lower() for node in nodes if isinstance(node, dict)
    ]
    if "start" not in types:
        errors.append(
            {"path": "definition.nodes", "message": "A start node is required"}
        )
    if "end" not in types:
        errors.append(
            {"path": "definition.nodes", "message": "An end node is required"}
        )
    allowed = {
        "start",
        "end",
        "agent",
        "tool",
        "condition",
        "approval",
        "human_input",
        "notification",
    }
    invalid = sorted({item for item in types if item not in allowed})
    if invalid:
        errors.append(
            {
                "path": "definition.nodes",
                "message": f"Unsupported node types: {', '.join(invalid)}",
            }
        )
    known = set(ids)
    for index, edge in enumerate(edges):
        if (
            not isinstance(edge, dict)
            or str(edge.get("source", "")) not in known
            or str(edge.get("target", "")) not in known
        ):
            errors.append(
                {
                    "path": f"definition.edges.{index}",
                    "message": "Edge references an unknown node",
                }
            )
    if not nodes:
        warnings.append(
            {
                "path": "definition.nodes",
                "message": "Add workflow steps before publishing",
            }
        )
    return {"valid": not errors, "errors": errors, "warnings": warnings}


def _record_workflow_event(
    db: Session,
    workflow: Workflow,
    user: dict,
    event_type: str,
    summary: dict | None = None,
) -> None:
    db.add(
        WorkflowActivityEvent(
            workflow_id=workflow.id,
            tenant_id=workflow.tenant_id,
            event_type=event_type,
            actor_id=str(user.get("sub", "system")),
            workflow_version=workflow.current_version,
            summary=summary or {},
        )
    )


@router.get("/workflows")
def list_managed_workflows(
    db: Session = Depends(get_db), user: dict = Depends(get_current_user)
):
    return [
        _workflow_response(item)
        for item in db.query(Workflow)
        .filter_by(tenant_id=str(user.get("custom:tenant_id", "default")))
        .order_by(Workflow.updated_at.desc())
        .all()
    ]


@router.post("/workflows", status_code=status.HTTP_201_CREATED)
def create_managed_workflow(
    payload: WorkflowPayload,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    workflow = Workflow(
        goal=payload.name,
        description=payload.description,
        assigned_agent=payload.assigned_agent,
        trigger_type=payload.trigger_type.upper(),
        definition=payload.definition,
        status="CREATED",
        lifecycle_status="DRAFT",
        tenant_id=str(user.get("custom:tenant_id", "default")),
        owner_id=str(user["sub"]),
        updated_by=str(user["sub"]),
        created_by=user["sub"],
    )
    db.add(workflow)
    db.flush()
    validation = _validate_definition(workflow.definition)
    db.add(
        WorkflowVersion(
            workflow_id=workflow.id,
            tenant_id=workflow.tenant_id,
            version=1,
            definition=workflow.definition,
            trigger_type=workflow.trigger_type,
            validation_result=validation,
            change_summary="Initial draft",
            created_by=str(user["sub"]),
        )
    )
    _record_workflow_event(
        db, workflow, user, "WORKFLOW_CREATED", {"name": workflow.goal}
    )
    db.commit()
    db.refresh(workflow)
    return _workflow_response(workflow)


@router.get("/workflows/{workflow_id}")
def get_managed_workflow(
    workflow_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    workflow = _managed_workflow(db, workflow_id, user)
    return _workflow_response(workflow)


@router.put("/workflows/{workflow_id}")
def update_managed_workflow(
    workflow_id: int,
    payload: WorkflowPayload,
    if_match: str | None = Header(default=None, alias="If-Match"),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    workflow = _managed_workflow(db, workflow_id, user)
    if workflow.lifecycle_status != "DRAFT":
        raise HTTPException(
            409,
            {
                "code": "IMMUTABLE_VERSION",
                "message": "Only draft workflows can be edited",
            },
        )
    if if_match is None:
        raise HTTPException(
            428,
            {
                "code": "IF_MATCH_REQUIRED",
                "message": "If-Match lock version is required",
            },
        )
    try:
        expected_lock = int(if_match.strip('"'))
    except ValueError as exc:
        raise HTTPException(400, "Invalid If-Match value") from exc
    if expected_lock != workflow.lock_version:
        raise HTTPException(
            409,
            {
                "code": "STALE_WORKFLOW",
                "message": "Workflow changed; refresh before saving",
            },
        )
    workflow.goal = payload.name
    workflow.description = payload.description
    workflow.assigned_agent = payload.assigned_agent
    workflow.trigger_type = payload.trigger_type.upper()
    workflow.definition = payload.definition
    workflow.current_version += 1
    workflow.lock_version += 1
    workflow.updated_at = datetime.now(UTC)
    workflow.updated_by = str(user["sub"])
    validation = _validate_definition(workflow.definition)
    db.add(
        WorkflowVersion(
            workflow_id=workflow.id,
            tenant_id=workflow.tenant_id,
            version=workflow.current_version,
            definition=workflow.definition,
            trigger_type=workflow.trigger_type,
            validation_result=validation,
            change_summary="Draft updated",
            created_by=str(user["sub"]),
        )
    )
    _record_workflow_event(db, workflow, user, "WORKFLOW_UPDATED")
    db.commit()
    db.refresh(workflow)
    return _workflow_response(workflow)


@router.post("/workflows/{workflow_id}/execute")
def execute_managed_workflow(
    workflow_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    workflow = _managed_workflow(db, workflow_id, user)
    if workflow.lifecycle_status != "PUBLISHED":
        raise HTTPException(
            409,
            {"code": "NOT_PUBLISHED", "message": "Only published workflows can run"},
        )
    raise HTTPException(
        501,
        {
            "code": "RUNTIME_HANDOFF_REQUIRED",
            "message": "Use the governed test endpoint until runtime binding is configured",
        },
    )


@router.post("/workflows/{workflow_id}/validate")
def validate_managed_workflow(
    workflow_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    workflow = _managed_workflow(db, workflow_id, user)
    result = _validate_definition(workflow.definition)
    _record_workflow_event(db, workflow, user, "WORKFLOW_VALIDATED", result)
    db.commit()
    return result


@router.post("/workflows/{workflow_id}/test")
def test_managed_workflow(
    workflow_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    workflow = _managed_workflow(db, workflow_id, user)
    validation = _validate_definition(workflow.definition)
    result = {
        "status": "VALIDATED" if validation["valid"] else "INVALID",
        "mode": "SAFE_VALIDATION_ONLY",
        "workflow_id": workflow.id,
        "workflow_version": workflow.current_version,
        "validation": validation,
        "external_mutations": 0,
    }
    _record_workflow_event(db, workflow, user, "WORKFLOW_SAFE_TESTED", result)
    db.commit()
    return result


@router.get("/workflows/{workflow_id}/versions")
def list_workflow_versions(
    workflow_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    workflow = _managed_workflow(db, workflow_id, user)
    rows = (
        db.query(WorkflowVersion)
        .filter_by(workflow_id=workflow.id, tenant_id=workflow.tenant_id)
        .order_by(WorkflowVersion.version.desc())
        .all()
    )
    return [
        {
            "id": row.id,
            "version": row.version,
            "change_summary": row.change_summary,
            "validation_result": row.validation_result,
            "published": row.published,
            "created_by": row.created_by,
            "created_at": row.created_at,
        }
        for row in rows
    ]


@router.get("/workflows/{workflow_id}/activity")
def list_workflow_activity(
    workflow_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    workflow = _managed_workflow(db, workflow_id, user)
    rows = (
        db.query(WorkflowActivityEvent)
        .filter_by(workflow_id=workflow.id, tenant_id=workflow.tenant_id)
        .order_by(WorkflowActivityEvent.created_at.desc())
        .limit(100)
        .all()
    )
    return [
        {
            "id": row.id,
            "event_type": row.event_type,
            "actor_id": row.actor_id,
            "workflow_version": row.workflow_version,
            "summary": row.summary,
            "created_at": row.created_at,
        }
        for row in rows
    ]


@router.post("/workflows/{workflow_id}/retire")
def retire_managed_workflow(
    workflow_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    workflow = _managed_workflow(db, workflow_id, user)
    workflow.lifecycle_status = "RETIRED"
    workflow.status = "RETIRED"
    workflow.retired_at = datetime.now(UTC)
    workflow.updated_at = workflow.retired_at
    workflow.updated_by = str(user["sub"])
    workflow.lock_version += 1
    _record_workflow_event(db, workflow, user, "WORKFLOW_RETIRED")
    db.commit()
    db.refresh(workflow)
    return _workflow_response(workflow)


@router.delete("/workflows/{workflow_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_managed_workflow(
    workflow_id: int,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    _managed_workflow(db, workflow_id, user)
    raise HTTPException(
        405,
        {
            "code": "HARD_DELETE_DISABLED",
            "message": "Workflows must be retired through the governed lifecycle API",
        },
    )


@router.get("/audit")
def list_audit_logs(
    action: str | None = None,
    agent: str | None = None,
    date: str = "7d",
    search: str | None = None,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(
        days=30 if date == "30d" else 7
    )
    executions = (
        db.query(RuntimeExecution)
        .filter(
            RuntimeExecution.user_id == user["sub"],
            RuntimeExecution.started_at >= cutoff,
        )
        .order_by(RuntimeExecution.started_at.desc())
        .all()
    )
    rows = [
        {
            "id": str(item.id),
            "time": item.started_at.isoformat(),
            "action": item.goal or "Runtime execution",
            "agent": item.agent or "default-agent",
            "status": item.status.lower(),
            "details": item.error
            or item.result_message
            or "Workflow execution recorded",
        }
        for item in executions
    ]

    def matches(row):
        value = " ".join(str(v) for v in row.values()).lower()
        return (
            (not action or action.lower() in row["action"].lower())
            and (not agent or agent.lower() == row["agent"].lower())
            and (not search or search.lower() in value)
        )

    return [row for row in rows if matches(row)]
