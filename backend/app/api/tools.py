from __future__ import annotations

from datetime import UTC, datetime
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.contracts.tool_models import ExecutionContext
from app.database.dependencies import get_db
from app.database.models.tool import (
    IntegrationConfiguration,
    ToolDefinition,
    ToolExecution,
)
from app.tool_sdk.errors import ToolSDKError
from app.tool_sdk.service import catalog_item, executor, registry, sync_catalog

router = APIRouter(prefix="/api/v1", tags=["Tool SDK"])


def identity(user):
    raw = user.get("scope", "")
    groups = user.get("cognito:groups", []) or []
    permissions = set(raw.split()) | set(user.get("permissions", []) or [])
    if any(
        str(g).lower() in {"admin", "administrators", "platform-admin"} for g in groups
    ):
        permissions.add("tools.admin")
    return ExecutionContext(
        actor_id=user.get("sub", "unknown"),
        tenant_id=user.get("custom:tenant_id", "default"),
        permissions=permissions,
        roles=set(user.get("roles", []) or []),
        groups={str(group) for group in groups},
    )


def require_admin(user):
    ctx = identity(user)
    if "tools.admin" not in ctx.permissions:
        raise HTTPException(
            403,
            {
                "code": "PERMISSION_DENIED",
                "message": "Tool administration permission is required",
            },
        )
    return ctx


def row_for(db, name, version, tenant="default"):
    return (
        db.query(ToolDefinition)
        .filter_by(tenant_id=tenant, name=name, version=version)
        .first()
    )


@router.get("/tools")
def list_tools(
    search: str | None = None,
    category: str | None = None,
    provider: str | None = None,
    tag: str | None = None,
    enabled: bool | None = None,
    risk_level: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort: str = "display_name",
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    sync_catalog(db)
    ctx = identity(user)
    tools = registry.list(
        category=category,
        provider=provider,
        tag=tag,
        enabled=enabled,
        risk_level=risk_level,
    )
    tools = [
        tool
        for tool in tools
        if not ("integration" in tool.metadata.tags and "action" in tool.metadata.tags)
    ]
    visible = [
        t
        for t in tools
        if "tools.admin" in ctx.permissions
        or set(t.metadata.permissions) <= ctx.permissions
    ]
    if search:
        visible = [
            t
            for t in visible
            if search.lower()
            in f"{t.metadata.display_name} {t.metadata.name} {t.metadata.description}".lower()
        ]
    key = {
        "name": lambda t: t.metadata.name,
        "provider": lambda t: t.metadata.provider,
        "category": lambda t: t.metadata.category,
    }.get(sort, lambda t: t.metadata.display_name.lower())
    visible = sorted(visible, key=key)
    start = (page - 1) * page_size
    items = []
    for t in visible[start : start + page_size]:
        items.append(
            catalog_item(t, row_for(db, t.name, t.metadata.version, ctx.tenant_id))
        )
    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "total": len(visible),
        "pages": max(1, (len(visible) + page_size - 1) // page_size),
    }


@router.get("/tools/categories")
def categories(user: dict = Depends(get_current_user)):
    return sorted({t.metadata.category for t in registry.list()})


@router.get("/tools/providers")
def providers(user: dict = Depends(get_current_user)):
    return sorted({t.metadata.provider for t in registry.list()})


@router.get("/tools/{name}/versions")
def versions(name: str, user: dict = Depends(get_current_user)):
    return {"name": name, "versions": registry.versions(name)}


@router.get("/tools/{name}")
async def detail(
    name: str,
    version: str | None = None,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    try:
        tool = registry.get(name, version)
    except ToolSDKError as exc:
        raise HTTPException(
            exc.status_code, {"code": exc.code, "message": exc.safe_message}
        ) from exc
    ctx = identity(user)
    if (
        "tools.admin" not in ctx.permissions
        and not set(tool.metadata.permissions) <= ctx.permissions
    ):
        raise HTTPException(
            403,
            {
                "code": "PERMISSION_DENIED",
                "message": "Tool is not visible to this identity",
            },
        )
    health = await tool.health()
    row = row_for(db, name, tool.metadata.version, ctx.tenant_id)
    recent = (
        db.query(ToolExecution)
        .filter_by(tenant_id=ctx.tenant_id, tool_name=name)
        .order_by(ToolExecution.started_at.desc())
        .limit(5)
        .all()
    )
    return {
        **catalog_item(tool, row, health),
        "recent_executions": [execution_item(x) for x in recent],
    }


class ExecutePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    input: dict = Field(default_factory=dict)
    version: str | None = None


@router.post("/tools/{name}/execute")
async def execute(
    name: str,
    payload: ExecutePayload,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
    x_correlation_id: str | None = Header(None, alias="X-Correlation-ID"),
    approval_request_id: str | None = Header(None, alias="X-Approval-Request-ID"),
    approval_resume_token: str | None = Header(None, alias="X-Approval-Resume-Token"),
):
    ctx = identity(user).model_copy(
        update={
            "idempotency_key": idempotency_key,
            "correlation_id": x_correlation_id or identity(user).correlation_id,
            "approval_request_id": approval_request_id,
            "approval_resume_token": approval_resume_token,
        }
    )
    try:
        return await executor.execute(name, payload.input, ctx, db, payload.version)
    except ToolSDKError as exc:
        raise HTTPException(
            exc.status_code,
            {"code": exc.code, "message": exc.safe_message, "fields": exc.fields},
        ) from exc


def execution_item(x):
    return {
        "execution_id": x.id,
        "tool": x.tool_name,
        "version": x.tool_version,
        "status": x.status,
        "actor": x.actor_id,
        "agent_id": x.agent_id,
        "started_at": x.started_at.isoformat(),
        "finished_at": x.finished_at.isoformat() if x.finished_at else None,
        "duration_ms": x.duration_ms,
        "error_code": x.error_code,
        "error_message": x.error_message,
        "correlation_id": x.correlation_id,
        "retry_count": x.retry_count,
        "provider_request_id": x.provider_request_id,
    }


@router.get("/tool-executions")
def history(
    tool: str | None = None,
    status_filter: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    ctx = identity(user)
    q = db.query(ToolExecution).filter_by(tenant_id=ctx.tenant_id)
    if "tools.admin" not in ctx.permissions:
        q = q.filter(ToolExecution.actor_id == ctx.actor_id)
    if tool:
        q = q.filter(ToolExecution.tool_name == tool)
    if status_filter:
        q = q.filter(ToolExecution.status == status_filter)
    total = q.count()
    rows = (
        q.order_by(ToolExecution.started_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "items": [execution_item(x) for x in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/tool-executions/{execution_id}")
def execution_detail(
    execution_id: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    ctx = identity(user)
    x = db.get(ToolExecution, execution_id)
    if (
        not x
        or x.tenant_id != ctx.tenant_id
        or ("tools.admin" not in ctx.permissions and x.actor_id != ctx.actor_id)
    ):
        raise HTTPException(404, "Execution not found")
    return {
        **execution_item(x),
        "input_summary": x.input_summary,
        "output_summary": x.output_summary,
    }


class IntegrationPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    display_name: str = Field(min_length=1, max_length=120)
    base_url: str | None = Field(None, max_length=500)
    account_identifier: str | None = Field(None, max_length=255)
    auth_method: str | None = Field(None, max_length=80)
    secret_reference: str | None = Field(None, max_length=500)
    safe_metadata: dict = Field(default_factory=dict)
    enabled: bool = True

    @field_validator("base_url")
    @classmethod
    def safe_url(cls, value):
        if value:
            parsed = urlparse(value)
            host = (parsed.hostname or "").lower()
            if (
                parsed.scheme != "https"
                or host in {"localhost", "127.0.0.1", "::1"}
                or host.endswith(".local")
            ):
                raise ValueError("base_url must be a public HTTPS URL")
        return value


def integration_item(x):
    return {
        "id": x.id,
        "provider": x.provider,
        "display_name": x.display_name,
        "base_url": x.base_url,
        "account_identifier": x.account_identifier,
        "auth_method": x.auth_method,
        "credential_configured": bool(x.secret_reference),
        "safe_metadata": x.safe_metadata,
        "enabled": x.enabled,
        "health_status": x.health_status,
        "health_message": x.health_message,
        "last_verified_at": x.last_verified_at.isoformat()
        if x.last_verified_at
        else None,
    }


@router.get("/integrations")
def integrations(db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    ctx = identity(user)
    existing = {
        x.provider: x
        for x in db.query(IntegrationConfiguration)
        .filter_by(tenant_id=ctx.tenant_id)
        .all()
    }
    providers = {
        "servicenow": "ServiceNow",
        "local_files": "Local Files",
        "microsoft_graph": "Microsoft Graph / SharePoint / OneDrive",
        "azure_blob": "Azure Blob Storage",
        "azure_keyvault": "Azure Key Vault",
    }
    return [
        integration_item(existing[p])
        if p in existing
        else {
            "provider": p,
            "display_name": name,
            "configured": False,
            "credential_configured": False,
            "enabled": False,
            "health_status": "not_configured",
            "last_verified_at": None,
            "safe_metadata": {},
        }
        for p, name in providers.items()
    ]


@router.put("/integrations/{provider}")
def upsert_integration(
    provider: str,
    payload: IntegrationPayload,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    ctx = require_admin(user)
    row = (
        db.query(IntegrationConfiguration)
        .filter_by(tenant_id=ctx.tenant_id, provider=provider)
        .first()
    )
    if not row:
        row = IntegrationConfiguration(
            tenant_id=ctx.tenant_id,
            provider=provider,
            display_name=payload.display_name,
        )
        db.add(row)
    data = payload.model_dump(exclude_unset=True)
    secret = data.pop("secret_reference", None)
    for k, v in data.items():
        setattr(row, k, v)
    if secret is not None:
        row.secret_reference = secret
    row.health_status = "unknown" if row.enabled else "disabled"
    db.commit()
    db.refresh(row)
    return integration_item(row)


@router.post("/integrations/{provider}/verify")
async def verify_integration(
    provider: str, db: Session = Depends(get_db), user: dict = Depends(get_current_user)
):
    ctx = require_admin(user)
    row = (
        db.query(IntegrationConfiguration)
        .filter_by(tenant_id=ctx.tenant_id, provider=provider)
        .first()
    )
    tools = [t for t in registry.list(provider=provider)]
    result = (
        await tools[0].health()
        if tools
        else {"ready": False, "message": "No adapter is registered"}
    )
    if row:
        row.health_status = "healthy" if result["ready"] else "unhealthy"
        row.health_message = str(result["message"])
        row.last_verified_at = datetime.now(UTC)
        db.commit()
    return result


@router.patch("/tools/{name}/{version}/enabled")
def enable_tool(
    name: str,
    version: str,
    enabled: bool,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    ctx = require_admin(user)
    registry.set_enabled(name, version, enabled)
    row = row_for(db, name, version, ctx.tenant_id)
    if row:
        row.enabled = enabled
        row.updated_by = ctx.actor_id
        db.commit()
    return {"name": name, "version": version, "enabled": enabled}
