from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session

from app.api.tools import identity, require_admin
from app.auth.dependencies import get_current_user
from app.contracts.tool_models import ExecutionContext
from app.database.dependencies import get_db
from app.database.models.mcp import MCPCapability, MCPServer, MCPSyncRun
from app.database.models.tool import ToolExecution
from app.mcp_integration.errors import MCPError
from app.mcp_integration.oauth import authorization_url, exchange_code
from app.mcp_integration.security import normalize_slug, validate_server_url
from app.mcp_integration.service import (
    capability_dict,
    get_prompt,
    read_resource,
    register_capability_tool,
    server_dict,
    sync_server,
    test_server,
)
from app.tool_discovery.indexing import index_tools
from app.tool_sdk.errors import ToolSDKError
from app.tool_sdk.service import executor, registry, sync_catalog

router = APIRouter(prefix="/api/v1/mcp", tags=["MCP"])
logger = logging.getLogger(__name__)


class ServerPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    display_name: str = Field(min_length=2, max_length=120)
    slug: str | None = None
    description: str = Field(default="", max_length=2000)
    environment: str = Field(default="production", max_length=40)
    server_url: str = Field(max_length=500)
    transport: str = "streamable_http"
    auth_type: str = "none"
    secret_reference: str | None = Field(default=None, max_length=500)
    auth_config: dict = Field(default_factory=dict)
    requested_scopes: list[str] = Field(default_factory=list)
    policy: dict = Field(default_factory=dict)
    enabled: bool = False

    @field_validator("transport")
    @classmethod
    def transport_supported(cls, value):
        if value not in {"streamable_http", "sse"}:
            raise ValueError("transport must be streamable_http or sse")
        return value

    @field_validator("auth_type")
    @classmethod
    def auth_supported(cls, value):
        if value not in {"none", "api_key", "oauth2", "jwt", "service_account"}:
            raise ValueError("unsupported authentication type")
        return value

    @field_validator("secret_reference")
    @classmethod
    def secret_is_reference(cls, value):
        if value and not value.startswith("env://"):
            raise ValueError("credentials must be an env:// secret reference")
        return value

    @field_validator("server_url")
    @classmethod
    def safe_url_shape(cls, value):
        validate_server_url(value, [], resolve_dns=False)
        return value


class ServerUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    display_name: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    environment: str | None = Field(default=None, max_length=40)
    server_url: str | None = Field(default=None, max_length=500)
    transport: str | None = None
    auth_type: str | None = None
    secret_reference: str | None = Field(default=None, max_length=500)
    auth_config: dict | None = None
    requested_scopes: list[str] | None = None
    policy: dict | None = None
    enabled: bool | None = None

    @field_validator("server_url")
    @classmethod
    def safe_url_shape(cls, value):
        if value:
            validate_server_url(value, [], resolve_dns=False)
        return value


class CapabilityUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool | None = None
    approved: bool | None = None
    risk_level: str | None = None
    permission: str | None = Field(default=None, max_length=200)
    approval_policy: str | None = None


class ExecutePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    input: dict = Field(default_factory=dict)


class ResourcePayload(BaseModel):
    uri: str = Field(max_length=2000)


class PromptPayload(BaseModel):
    arguments: dict = Field(default_factory=dict)


def server_for(db: Session, server_id: str, tenant_id: str) -> MCPServer:
    row = (
        db.query(MCPServer)
        .filter_by(id=server_id, tenant_id=tenant_id, deleted_at=None)
        .first()
    )
    if not row:
        raise HTTPException(
            404, {"code": "MCP_SERVER_NOT_FOUND", "message": "MCP server was not found"}
        )
    return row


def fail(exc: Exception):
    if isinstance(exc, (MCPError, ToolSDKError)):
        raise HTTPException(
            exc.status_code, {"code": exc.code, "message": exc.safe_message}
        )
    raise exc


@router.get("/servers")
def list_servers(
    search: str | None = None,
    enabled: bool | None = None,
    health: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    ctx = identity(user)
    query = db.query(MCPServer).filter_by(tenant_id=ctx.tenant_id, deleted_at=None)
    if enabled is not None:
        query = query.filter(MCPServer.enabled == enabled)
    if health:
        query = query.filter(MCPServer.health_status == health)
    if search:
        query = query.filter(MCPServer.display_name.ilike(f"%{search[:100]}%"))
    total = query.count()
    rows = (
        query.order_by(MCPServer.display_name)
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "items": [server_dict(row) for row in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/servers", status_code=201)
def create_server(
    payload: ServerPayload,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    ctx = require_admin(user)
    slug = normalize_slug(payload.slug or payload.display_name)
    if db.query(MCPServer).filter_by(tenant_id=ctx.tenant_id, slug=slug).first():
        raise HTTPException(
            409,
            {
                "code": "MCP_SERVER_EXISTS",
                "message": "An MCP server with this slug already exists",
            },
        )
    values = payload.model_dump()
    values["slug"] = slug
    row = MCPServer(
        tenant_id=ctx.tenant_id,
        created_by=ctx.actor_id,
        updated_by=ctx.actor_id,
        **values,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return server_dict(row)


@router.get("/servers/{server_id}")
def get_server(
    server_id: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    ctx = identity(user)
    row = server_for(db, server_id, ctx.tenant_id)
    result = server_dict(row)
    result["capability_counts"] = {
        kind: db.query(MCPCapability)
        .filter_by(server_id=row.id, capability_type=kind)
        .count()
        for kind in ("tool", "resource", "resource_template", "prompt")
    }
    return result


@router.patch("/servers/{server_id}")
def update_server(
    server_id: str,
    payload: ServerUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    ctx = require_admin(user)
    row = server_for(db, server_id, ctx.tenant_id)
    values = payload.model_dump(exclude_unset=True)
    if "transport" in values and values["transport"] not in {"streamable_http", "sse"}:
        raise HTTPException(422, "Unsupported transport")
    if "auth_type" in values and values["auth_type"] not in {
        "none",
        "api_key",
        "oauth2",
        "jwt",
        "service_account",
    }:
        raise HTTPException(422, "Unsupported authentication type")
    if values.get("secret_reference") and not values["secret_reference"].startswith(
        "env://"
    ):
        raise HTTPException(422, "Credentials must be an env:// secret reference")
    for key, value in values.items():
        setattr(row, key, value)
    row.configuration_version += 1
    row.updated_by = ctx.actor_id
    db.commit()
    return server_dict(row)


@router.delete("/servers/{server_id}", status_code=204)
def delete_server(
    server_id: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    ctx = require_admin(user)
    row = server_for(db, server_id, ctx.tenant_id)
    row.deleted_at = datetime.now(UTC)
    row.enabled = False
    for cap in db.query(MCPCapability).filter_by(server_id=row.id).all():
        cap.enabled = False
        if cap.capability_type == "tool":
            try:
                registry.set_enabled(cap.internal_name, "1.0.0", False)
            except Exception:  # noqa: BLE001 -- registry adapters expose no stable exception base
                logger.exception(
                    "Failed to disable MCP capability",
                    extra={"capability": cap.internal_name},
                )
    db.commit()


@router.post("/servers/{server_id}/test")
async def test_connection(
    server_id: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    ctx = require_admin(user)
    row = server_for(db, server_id, ctx.tenant_id)
    return await test_server(db, row)


@router.post("/servers/{server_id}/sync")
async def synchronize(
    server_id: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
    correlation_id: str | None = Header(None, alias="X-Correlation-ID"),
):
    ctx = require_admin(user)
    row = server_for(db, server_id, ctx.tenant_id)
    try:
        result = await sync_server(db, row, registry, correlation_id=correlation_id)
        sync_catalog(db)
        await index_tools(db, ctx.tenant_id, batch_size=500)
        return result
    except Exception as exc:  # noqa: BLE001 -- API boundary normalizes MCP and transport errors
        fail(exc)


@router.get("/servers/{server_id}/capabilities")
def capabilities(
    server_id: str,
    type: str | None = None,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    ctx = identity(user)
    row = server_for(db, server_id, ctx.tenant_id)
    query = db.query(MCPCapability).filter_by(server_id=row.id)
    if type:
        query = query.filter(MCPCapability.capability_type == type)
    return {
        "items": [
            capability_dict(item)
            for item in query.order_by(
                MCPCapability.capability_type, MCPCapability.display_name
            ).all()
        ]
    }


@router.patch("/servers/{server_id}/capabilities/{capability_id}")
def update_capability(
    server_id: str,
    capability_id: str,
    payload: CapabilityUpdate,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    ctx = require_admin(user)
    server = server_for(db, server_id, ctx.tenant_id)
    row = (
        db.query(MCPCapability).filter_by(id=capability_id, server_id=server.id).first()
    )
    if not row:
        raise HTTPException(404, "MCP capability was not found")
    values = payload.model_dump(exclude_unset=True)
    if values.get("enabled") and (
        row.missing
        or (
            row.change_status == "review_required"
            and not values.get("approved", row.approved)
        )
    ):
        raise HTTPException(
            409,
            {
                "code": "MCP_REVIEW_REQUIRED",
                "message": "Approve the changed capability before enabling it",
            },
        )
    for key, value in values.items():
        setattr(row, key, value)
    if row.approved and row.change_status in {"new", "review_required"}:
        row.change_status = "approved"
    db.commit()
    if row.capability_type == "tool":
        register_capability_tool(row, registry)
    return capability_dict(row)


@router.post("/servers/{server_id}/tools/{capability_id}/execute")
async def execute_tool(
    server_id: str,
    capability_id: str,
    payload: ExecutePayload,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    correlation_id: str | None = Header(None, alias="X-Correlation-ID"),
):
    ctx = identity(user)
    server = server_for(db, server_id, ctx.tenant_id)
    cap = (
        db.query(MCPCapability)
        .filter_by(id=capability_id, server_id=server.id, capability_type="tool")
        .first()
    )
    if not cap:
        raise HTTPException(404, "MCP tool was not found")
    execute_context: ExecutionContext = ctx.model_copy(
        update={
            "idempotency_key": idempotency_key,
            "correlation_id": correlation_id or ctx.correlation_id,
        }
    )
    try:
        return await executor.execute(
            cap.internal_name, payload.input, execute_context, db
        )
    except Exception as exc:  # noqa: BLE001 -- API boundary normalizes MCP and transport errors
        fail(exc)


@router.post("/servers/{server_id}/resources/read")
async def resource_read(
    server_id: str,
    payload: ResourcePayload,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    ctx = identity(user)
    server = server_for(db, server_id, ctx.tenant_id)
    try:
        return await read_resource(db, server, payload.uri)
    except Exception as exc:  # noqa: BLE001 -- API boundary normalizes MCP and transport errors
        fail(exc)


@router.post("/servers/{server_id}/prompts/{name}")
async def prompt_get(
    server_id: str,
    name: str,
    payload: PromptPayload,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    ctx = identity(user)
    server = server_for(db, server_id, ctx.tenant_id)
    try:
        return await get_prompt(db, server, name, payload.arguments)
    except Exception as exc:  # noqa: BLE001 -- API boundary normalizes MCP and transport errors
        fail(exc)


@router.get("/servers/{server_id}/sync-runs")
def sync_runs(
    server_id: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    ctx = identity(user)
    server = server_for(db, server_id, ctx.tenant_id)
    rows = (
        db.query(MCPSyncRun)
        .filter_by(server_id=server.id)
        .order_by(MCPSyncRun.started_at.desc())
        .limit(50)
        .all()
    )
    return {
        "items": [
            {
                "id": x.id,
                "status": x.status,
                "started_at": x.started_at.isoformat(),
                "finished_at": x.finished_at.isoformat() if x.finished_at else None,
                "added": x.added_count,
                "changed": x.changed_count,
                "removed": x.removed_count,
                "warnings": x.warning_count,
                "error_code": x.error_code,
                "message": x.safe_error,
                "correlation_id": x.correlation_id,
            }
            for x in rows
        ]
    }


@router.get("/servers/{server_id}/executions")
def executions(
    server_id: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    ctx = identity(user)
    server = server_for(db, server_id, ctx.tenant_id)
    names = [
        x.internal_name
        for x in db.query(MCPCapability)
        .filter_by(server_id=server.id, capability_type="tool")
        .all()
    ]
    rows = (
        db.query(ToolExecution)
        .filter(
            ToolExecution.tenant_id == ctx.tenant_id, ToolExecution.tool_name.in_(names)
        )
        .order_by(ToolExecution.started_at.desc())
        .limit(100)
        .all()
        if names
        else []
    )
    return {
        "items": [
            {
                "id": x.id,
                "tool": x.tool_name,
                "status": x.status,
                "actor": x.actor_id,
                "started_at": x.started_at.isoformat(),
                "duration_ms": x.duration_ms,
                "error_code": x.error_code,
                "correlation_id": x.correlation_id,
            }
            for x in rows
        ]
    }


@router.post("/servers/{server_id}/oauth/start")
def oauth_start(
    server_id: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    ctx = require_admin(user)
    server = server_for(db, server_id, ctx.tenant_id)
    if server.auth_type != "oauth2":
        raise HTTPException(409, "Server does not use OAuth")
    try:
        return {"authorization_url": authorization_url(server, ctx.actor_id)}
    except Exception as exc:  # noqa: BLE001 -- OAuth library errors are normalized by fail
        fail(exc)


@router.get("/servers/{server_id}/oauth/callback")
async def oauth_callback(
    server_id: str,
    state: str,
    code: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    ctx = require_admin(user)
    server = server_for(db, server_id, ctx.tenant_id)
    try:
        result = await exchange_code(server, ctx.actor_id, state, code)
    except Exception as exc:  # noqa: BLE001 -- OAuth library errors are normalized by fail
        fail(exc)
    server.granted_scopes = result["scope"]
    db.commit()
    return result
