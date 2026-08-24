from __future__ import annotations

import base64
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.api.tools import identity, require_admin
from app.auth.dependencies import get_current_user
from app.database.dependencies import get_db
from app.database.models.native_tool import (
    NativeConnection,
    NativeFile,
    NativeFileContent,
    NativeNotification,
)
from app.tool_sdk.errors import ToolSDKError
from app.tool_sdk.native_tools import file_item, notification_item
from app.tool_sdk.service import executor, registry

router = APIRouter(prefix="/api/v1", tags=["Native Enterprise Tools"])
NATIVE_PREFIX = ("file_", "database_", "rest_api_", "notification_")


def native_item(t):
    m = t.metadata
    return {
        **m.model_dump(mode="json"),
        "family": m.name.split("_")[0],
        "health": "configured"
        if not m.configuration_requirements
        else "configuration_required",
    }


@router.get("/native-tools")
def list_native_tools(
    search: str | None = None, user: dict = Depends(get_current_user)
):
    ctx = identity(user)
    tools = [
        t
        for t in registry.list()
        if t.name.startswith(NATIVE_PREFIX)
        and (
            "tools.admin" in ctx.permissions
            or set(t.metadata.permissions) <= ctx.permissions
        )
    ]
    items = [
        native_item(t)
        for t in tools
        if not search or search.lower() in f"{t.name} {t.metadata.display_name}".lower()
    ]
    return {"items": items, "total": len(items)}


@router.get("/native-tools/{name}")
def get_native_tool(name: str, user: dict = Depends(get_current_user)):
    try:
        t = registry.get(name)
    except ToolSDKError as exc:
        raise HTTPException(
            exc.status_code, {"code": exc.code, "message": exc.safe_message}
        ) from exc
    return native_item(t)


class ExecuteBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    input: dict = Field(default_factory=dict)


@router.post("/native-tools/{name}/execute")
async def execute_native(
    name: str,
    payload: ExecuteBody,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    try:
        return await executor.execute(name, payload.input, identity(user), db)
    except ToolSDKError as exc:
        raise HTTPException(
            exc.status_code, {"code": exc.code, "message": exc.safe_message}
        ) from exc


@router.post("/files", status_code=201)
async def upload_file(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    data = await file.read(5_242_881)
    ctx = identity(user)
    try:
        return await executor.execute(
            "file_upload",
            {
                "filename": file.filename or "upload",
                "content_base64": base64.b64encode(data).decode(),
            },
            ctx,
            db,
        )
    except ToolSDKError as exc:
        raise HTTPException(
            exc.status_code, {"code": exc.code, "message": exc.safe_message}
        ) from exc


@router.get("/files")
def list_files(
    search: str | None = None,
    status: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    ctx = identity(user)
    q = db.query(NativeFile).filter_by(tenant_id=ctx.tenant_id)
    if search:
        q = q.filter(NativeFile.original_filename.ilike(f"%{search}%"))
    if status:
        q = q.filter_by(processing_status=status)
    total = q.count()
    rows = (
        q.order_by(NativeFile.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {"items": [file_item(x) for x in rows], "total": total, "page": page}


@router.get("/files/{file_id}")
def get_file(
    file_id: str, db: Session = Depends(get_db), user: dict = Depends(get_current_user)
):
    ctx = identity(user)
    row = db.query(NativeFile).filter_by(id=file_id, tenant_id=ctx.tenant_id).first()
    if not row:
        raise HTTPException(404, "File not found")
    return file_item(row)


@router.get("/files/{file_id}/content")
def file_content(
    file_id: str, db: Session = Depends(get_db), user: dict = Depends(get_current_user)
):
    ctx = identity(user)
    row = (
        db.query(NativeFile)
        .filter_by(id=file_id, tenant_id=ctx.tenant_id, scan_status="safe")
        .first()
    )
    if not row:
        raise HTTPException(404, "File not found")
    chunks = (
        db.query(NativeFileContent)
        .filter_by(file_id=file_id, tenant_id=ctx.tenant_id)
        .order_by(NativeFileContent.sequence)
        .all()
    )
    return {"file": file_item(row), "content": "\n".join(x.text for x in chunks)}


@router.post("/files/{file_id}/extract")
async def extract(
    file_id: str, db: Session = Depends(get_db), user: dict = Depends(get_current_user)
):
    return await executor.execute(
        "file_extract", {"file_id": file_id}, identity(user), db
    )


@router.post("/files/{file_id}/summarize")
async def summarize(
    file_id: str,
    payload: dict | None = None,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    return await executor.execute(
        "file_summarize",
        {"file_id": file_id, "focus": (payload or {}).get("focus", "")},
        identity(user),
        db,
    )


@router.post("/files/search")
async def search_files(
    payload: dict, db: Session = Depends(get_db), user: dict = Depends(get_current_user)
):
    return await executor.execute(
        "file_search", {"query": payload.get("query", "")}, identity(user), db
    )


class ConnectionBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    display_name: str = Field(min_length=1, max_length=120)
    engine: str | None = None
    base_url: str | None = None
    secret_reference: str | None = None
    safe_config: dict = Field(default_factory=dict)
    enabled: bool = True


@router.get("/database-connections")
def database_connections(
    db: Session = Depends(get_db), user: dict = Depends(get_current_user)
):
    return connection_list("database", db, identity(user).tenant_id)


@router.post("/database-connections", status_code=201)
def create_database_connection(
    payload: ConnectionBody,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    return create_connection("database", payload, db, require_admin(user))


@router.get("/api-connections")
def api_connections(
    db: Session = Depends(get_db), user: dict = Depends(get_current_user)
):
    return connection_list("rest", db, identity(user).tenant_id)


@router.post("/api-connections", status_code=201)
def create_api_connection(
    payload: ConnectionBody,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    return create_connection("rest", payload, db, require_admin(user))


def connection_list(kind, db, tenant):
    return [
        connection_item(x)
        for x in db.query(NativeConnection).filter_by(tenant_id=tenant, kind=kind).all()
    ]


def connection_item(x):
    return {
        "id": x.id,
        "kind": x.kind,
        "display_name": x.display_name,
        "engine": x.engine,
        "base_url": x.base_url,
        "credential_configured": bool(x.secret_reference),
        "safe_config": x.safe_config,
        "enabled": x.enabled,
        "health_status": x.health_status,
        "last_verified_at": x.last_verified_at.isoformat()
        if x.last_verified_at
        else None,
    }


def create_connection(kind, payload, db, ctx):
    row = NativeConnection(
        tenant_id=ctx.tenant_id,
        kind=kind,
        display_name=payload.display_name,
        engine=payload.engine,
        base_url=payload.base_url,
        secret_reference=payload.secret_reference,
        safe_config=payload.safe_config,
        enabled=payload.enabled,
        created_by=ctx.actor_id,
        updated_by=ctx.actor_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return connection_item(row)


@router.post("/database/query/execute")
async def database_execute(
    payload: dict, db: Session = Depends(get_db), user: dict = Depends(get_current_user)
):
    return await executor.execute("database_query", payload, identity(user), db)


@router.post("/api-connections/{connection_id}/request")
async def api_request(
    connection_id: str,
    payload: dict,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    return await executor.execute(
        "rest_api_request",
        {"connection_id": connection_id, **payload},
        identity(user),
        db,
    )


@router.post("/notifications/{channel}")
async def create_notification(
    channel: str,
    payload: dict,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    names = {
        "email": "notification_email_send",
        "teams": "notification_teams_send",
        "alerts": "notification_alert_create",
    }
    if channel not in names:
        raise HTTPException(404, "Notification channel not found")
    return await executor.execute(names[channel], payload, identity(user), db)


@router.get("/notifications")
def notifications(
    db: Session = Depends(get_db), user: dict = Depends(get_current_user)
):
    ctx = identity(user)
    rows = (
        db.query(NativeNotification)
        .filter_by(tenant_id=ctx.tenant_id)
        .order_by(NativeNotification.created_at.desc())
        .limit(100)
        .all()
    )
    return {"items": [notification_item(x) for x in rows]}


@router.post("/notifications/{notification_id}/approve")
def approve_notification(
    notification_id: str,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    ctx = require_admin(user)
    if (
        "notifications.approve" not in ctx.permissions
        and "tools.admin" not in ctx.permissions
    ):
        raise HTTPException(403, "Approval permission required")
    row = (
        db.query(NativeNotification)
        .filter_by(
            id=notification_id, tenant_id=ctx.tenant_id, status="pending_approval"
        )
        .first()
    )
    if not row:
        raise HTTPException(404, "Pending notification not found")
    row.status = "sent"
    row.approval_state = "approved"
    row.provider_message_id = f"approved-{row.id}"
    row.sent_at = datetime.now(UTC)
    db.commit()
    return notification_item(row)
