from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from uuid import uuid4

from app.contracts.tool import Tool
from app.contracts.tool_models import ToolMetadata, ToolResult
from app.database.models.mcp import MCPCapability, MCPServer, MCPSyncRun
from app.mcp_integration.client import manager
from app.mcp_integration.errors import (
    MCPPromptNotFound,
    MCPResourceNotFound,
    MCPServerDisabled,
    MCPServerNotFound,
    MCPToolDisabled,
    MCPToolNotFound,
)
from app.mcp_integration.security import (
    fingerprint,
    normalize_name,
    normalize_schema,
    sanitize_text,
)
from app.tool_sdk.errors import UnsafeOperationError

logger = logging.getLogger(__name__)


def server_permission(server):
    return f"mcp.{server.slug}.tools.execute"


def internal_tool_name(server, remote):
    return f"mcp_{server.slug}_{normalize_name(remote)}"[:100]


def capability_dict(row):
    return {
        "id": row.id,
        "server_id": row.server_id,
        "type": row.capability_type,
        "remote_name": row.remote_name,
        "internal_name": row.internal_name,
        "display_name": row.display_name,
        "description": row.description,
        "uri": row.uri,
        "mime_type": row.mime_type,
        "schema": row.schema_json,
        "fingerprint": row.fingerprint,
        "previous_fingerprint": row.previous_fingerprint,
        "change_status": row.change_status,
        "risk_level": row.risk_level,
        "permission": row.permission,
        "approval_policy": row.approval_policy,
        "enabled": row.enabled,
        "approved": row.approved,
        "missing": row.missing,
        "last_discovered_at": row.last_discovered_at.isoformat(),
    }


def server_dict(row):
    return {
        "id": row.id,
        "display_name": row.display_name,
        "slug": row.slug,
        "description": row.description,
        "environment": row.environment,
        "server_url": row.server_url,
        "transport": row.transport,
        "auth_type": row.auth_type,
        "credential_configured": bool(row.secret_reference),
        "requested_scopes": row.requested_scopes,
        "granted_scopes": row.granted_scopes,
        "policy": row.policy,
        "requested_protocol_version": row.requested_protocol_version,
        "negotiated_protocol_version": row.negotiated_protocol_version,
        "sdk_version": row.sdk_version,
        "server_name": row.server_name,
        "server_version": row.server_version,
        "capabilities": row.capabilities,
        "enabled": row.enabled,
        "health_status": row.health_status,
        "sync_status": row.sync_status,
        "last_connected_at": row.last_connected_at.isoformat()
        if row.last_connected_at
        else None,
        "last_synced_at": row.last_synced_at.isoformat()
        if row.last_synced_at
        else None,
        "configuration_version": row.configuration_version,
    }


def normalize_content(result):
    data = result.model_dump(mode="json") if hasattr(result, "model_dump") else result
    if isinstance(data, dict):
        blocks = []
        for item in data.get("content", []):
            if item.get("type") == "text":
                blocks.append(
                    {"type": "text", "text": sanitize_text(item.get("text"), 100_000)}
                )
            elif item.get("type") in {"image", "audio", "resource", "resource_link"}:
                safe_item = {
                    key: value
                    for key, value in item.items()
                    if key not in {"data", "blob"}
                }
                safe_item["omitted_binary"] = "data" in item or "blob" in item
                blocks.append(safe_item)
        return {
            "content": blocks,
            "is_error": data.get("isError", data.get("is_error", False)),
            "structured_content": data.get(
                "structuredContent", data.get("structured_content")
            ),
        }
    return {"content": [{"type": "text", "text": sanitize_text(data, 100_000)}]}


class MCPRemoteTool(Tool):
    def __init__(
        self,
        server_id,
        capability_id,
        name,
        display,
        description,
        schema,
        permission,
        risk="read",
        timeout=30,
    ):
        self.server_id = server_id
        self.capability_id = capability_id
        self.metadata = ToolMetadata(
            name=name,
            display_name=display,
            description=description or "External MCP tool",
            category="mcp",
            provider="mcp",
            version="1.0.0",
            permissions=(permission,),
            tags=("mcp",),
            parameters=schema,
            output_schema=None,
            risk_level=risk,
            timeout_seconds=min(timeout, 120),
            idempotent=risk == "read",
            configuration_requirements=("mcp_server",),
        )

    async def execute(self, input_data, context):
        db = context.db_session
        server = (
            db.query(MCPServer)
            .filter_by(id=self.server_id, tenant_id=context.tenant_id, deleted_at=None)
            .first()
        )
        if not server:
            raise MCPServerNotFound("MCP server was not found")
        if not server.enabled:
            raise MCPServerDisabled("MCP server is disabled")
        cap = (
            db.query(MCPCapability)
            .filter_by(
                id=self.capability_id, server_id=server.id, capability_type="tool"
            )
            .first()
        )
        if not cap:
            raise MCPToolNotFound("MCP tool was not found")
        if (
            not cap.enabled
            or not cap.approved
            or cap.missing
            or cap.change_status == "review_required"
        ):
            raise MCPToolDisabled("MCP tool is disabled or awaiting review")
        if cap.approval_policy == "always" and not context.internal:
            raise UnsafeOperationError(
                "MCP tool requires an approved execution context"
            )
        async with manager.session(server) as client:
            remote = [x for x in await client.list_tools() if x.name == cap.remote_name]
            if not remote:
                raise MCPToolNotFound("Remote MCP tool is no longer advertised")
            result = await client.call_tool(cap.remote_name, input_data)
            return ToolResult.succeeded(client.bounded(normalize_content(result)))


def register_capability_tool(row, registry):
    if row.capability_type != "tool":
        return
    try:
        registry.unregister(row.internal_name, "1.0.0")
    except Exception:  # noqa: BLE001 -- registry implementations expose no common missing-key error
        logger.debug("MCP capability was not previously registered", exc_info=True)
    tool = MCPRemoteTool(
        row.server_id,
        row.id,
        row.internal_name,
        row.display_name,
        row.description,
        row.schema_json,
        row.permission,
        row.risk_level,
        (row.safe_metadata or {}).get("timeout_seconds", 30),
    )
    registry.register(tool)
    registry.set_enabled(
        tool.name,
        tool.metadata.version,
        bool(
            row.enabled
            and row.approved
            and not row.missing
            and row.change_status != "review_required"
        ),
    )


def load_mcp_tools(db, registry):
    for row in db.query(MCPCapability).filter_by(capability_type="tool").all():
        register_capability_tool(row, registry)


async def test_server(db, server, client_manager=manager):
    try:
        async with client_manager.session(server) as client:
            initialized = client.initialized
            await client.ping()
            tools = await client.list_tools()
            resources = await client.list_resources()
            templates = await client.list_resource_templates()
            prompts = await client.list_prompts()
            server.negotiated_protocol_version = getattr(
                initialized, "protocolVersion", None
            ) or getattr(initialized, "protocol_version", None)
            info = getattr(initialized, "serverInfo", None) or getattr(
                initialized, "server_info", None
            )
            server.server_name = getattr(info, "name", None)
            server.server_version = getattr(info, "version", None)
            caps = getattr(initialized, "capabilities", None)
            server.capabilities = (
                caps.model_dump(mode="json") if hasattr(caps, "model_dump") else {}
            )
            server.health_status = "healthy"
            server.last_health_check = datetime.now(UTC)
            server.last_connected_at = datetime.now(UTC)
            db.commit()
            return {
                "healthy": True,
                "protocol_version": server.negotiated_protocol_version,
                "server_name": server.server_name,
                "server_version": server.server_version,
                "counts": {
                    "tools": len(tools),
                    "resources": len(resources),
                    "resource_templates": len(templates),
                    "prompts": len(prompts),
                },
            }
    except Exception as exc:  # noqa: BLE001 -- health endpoint reports all transport failures as data
        server.health_status = "unhealthy"
        server.last_health_check = datetime.now(UTC)
        db.commit()
        return {
            "healthy": False,
            "error_code": getattr(exc, "code", "MCP_CONNECTION_FAILED"),
            "message": getattr(exc, "safe_message", "MCP connection test failed"),
        }


def _remote_data(kind, item, server):
    data = item.model_dump(mode="json") if hasattr(item, "model_dump") else dict(item)
    remote = str(data.get("name") or data.get("uri"))
    schema = (
        data.get("inputSchema")
        or data.get("input_schema")
        or data.get("arguments")
        or {"type": "object", "properties": {}, "additionalProperties": False}
    )
    if kind == "tool":
        schema = normalize_schema(schema)
    else:
        schema = schema if isinstance(schema, dict) else {}
    internal = (
        internal_tool_name(server, remote)
        if kind == "tool"
        else f"mcp_{server.slug}_{kind}_{normalize_name(remote)}"[:180]
    )
    safe = {
        k: v
        for k, v in data.items()
        if k not in {"inputSchema", "input_schema", "arguments", "contents", "messages"}
    }
    return (
        remote,
        internal,
        sanitize_text(data.get("title") or data.get("name") or remote, 160),
        sanitize_text(data.get("description"), 2000),
        str(data.get("uri")) if data.get("uri") else None,
        data.get("mimeType") or data.get("mime_type"),
        schema,
        safe,
        fingerprint(
            {
                "kind": kind,
                "remote": remote,
                "schema": schema,
                "description": data.get("description"),
            }
        ),
    )


_sync_locks: dict[str, asyncio.Lock] = {}


async def sync_server(
    db, server, registry, client_manager=manager, correlation_id=None
):
    lock = _sync_locks.setdefault(server.id, asyncio.Lock())
    if lock.locked():
        raise RuntimeError("Synchronization is already running")
    run = MCPSyncRun(
        server_id=server.id,
        tenant_id=server.tenant_id,
        status="running",
        correlation_id=correlation_id or str(uuid4()),
    )
    db.add(run)
    db.commit()
    async with lock:
        try:
            async with client_manager.session(server) as client:
                groups = {
                    "tool": await client.list_tools(),
                    "resource": await client.list_resources(),
                    "resource_template": await client.list_resource_templates(),
                    "prompt": await client.list_prompts(),
                }
                seen = set()
                added = changed = warnings = 0
                now = datetime.now(UTC)
                for kind, items in groups.items():
                    for item in items:
                        try:
                            (
                                remote,
                                internal,
                                display,
                                description,
                                uri,
                                mime,
                                schema,
                                safe,
                                fp,
                            ) = _remote_data(kind, item, server)
                        except Exception:  # noqa: BLE001 -- malformed remote entries are isolated per item
                            logger.warning(
                                "Skipped malformed MCP capability", exc_info=True
                            )
                            warnings += 1
                            continue
                        seen.add((kind, remote))
                        row = (
                            db.query(MCPCapability)
                            .filter_by(
                                server_id=server.id,
                                capability_type=kind,
                                remote_name=remote,
                            )
                            .first()
                        )
                        if not row:
                            default_enable = (
                                bool(
                                    (server.policy or {}).get(
                                        f"auto_enable_{kind}s", False
                                    )
                                )
                                and kind != "tool"
                            )
                            row = MCPCapability(
                                server_id=server.id,
                                tenant_id=server.tenant_id,
                                capability_type=kind,
                                remote_name=remote,
                                internal_name=internal,
                                display_name=display,
                                description=description,
                                uri=uri,
                                mime_type=mime,
                                schema_json=schema,
                                safe_metadata=safe,
                                fingerprint=fp,
                                permission=server_permission(server)
                                if kind == "tool"
                                else f"mcp.{server.slug}.{kind}s.read",
                                enabled=default_enable,
                                approved=default_enable,
                                change_status="new",
                            )
                            db.add(row)
                            db.flush()
                            added += 1
                        else:
                            if row.fingerprint != fp:
                                row.previous_fingerprint = row.fingerprint
                                row.fingerprint = fp
                                row.change_status = "review_required"
                                row.enabled = False
                                row.approved = False
                                changed += 1
                            row.display_name = display
                            row.description = description
                            row.uri = uri
                            row.mime_type = mime
                            row.schema_json = schema
                            row.safe_metadata = safe
                            row.missing = False
                            row.last_discovered_at = now
                            row.last_synced_at = now
                        if kind == "tool":
                            register_capability_tool(row, registry)
                removed = 0
                for row in db.query(MCPCapability).filter_by(server_id=server.id).all():
                    if (row.capability_type, row.remote_name) not in seen:
                        row.missing = True
                        row.enabled = False
                        row.change_status = "removed"
                        removed += 1
                server.last_synced_at = now
                server.sync_status = "succeeded"
                server.health_status = "healthy"
                run.status = "succeeded"
                run.added_count = added
                run.changed_count = changed
                run.removed_count = removed
                run.warning_count = warnings
                run.finished_at = now
                db.commit()
                return {
                    "sync_id": run.id,
                    "status": "succeeded",
                    "added": added,
                    "changed": changed,
                    "removed": removed,
                    "warnings": warnings,
                }
        except Exception as exc:
            run.status = "failed"
            run.error_code = getattr(exc, "code", "MCP_CONNECTION_FAILED")
            run.safe_error = getattr(exc, "safe_message", "MCP synchronization failed")
            run.finished_at = datetime.now(UTC)
            server.sync_status = "failed"
            server.health_status = "unhealthy"
            db.commit()
            raise


async def read_resource(db, server, uri, client_manager=manager):
    row = (
        db.query(MCPCapability)
        .filter_by(
            server_id=server.id,
            tenant_id=server.tenant_id,
            capability_type="resource",
            uri=uri,
            enabled=True,
            missing=False,
        )
        .first()
    )
    if not row:
        raise MCPResourceNotFound("MCP resource is not enabled or was not discovered")
    if len(uri) > 2000 or uri.split(":", 1)[0] not in {
        "file",
        "https",
        "mcp",
        "resource",
    }:
        raise MCPResourceNotFound("MCP resource URI scheme is not allowed")
    async with client_manager.session(server) as client:
        return client.bounded(await client.read_resource(uri))


async def get_prompt(db, server, name, args, client_manager=manager):
    row = (
        db.query(MCPCapability)
        .filter_by(
            server_id=server.id,
            tenant_id=server.tenant_id,
            capability_type="prompt",
            remote_name=name,
            enabled=True,
            missing=False,
        )
        .first()
    )
    if not row:
        raise MCPPromptNotFound("MCP prompt is not enabled or was not discovered")
    async with client_manager.session(server) as client:
        return {
            "untrusted_provider_content": True,
            "prompt": client.bounded(await client.get_prompt(name, args)),
        }
