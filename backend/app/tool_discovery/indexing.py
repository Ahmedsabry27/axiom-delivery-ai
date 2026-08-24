from __future__ import annotations

import hashlib
import re
from datetime import UTC, datetime

from app.database.models.tool import ToolDefinition
from app.database.models.tool_discovery import ToolMarketplaceProfile, ToolSearchIndex
from app.tool_discovery import INDEX_VERSION
from app.tool_discovery.embedding import provider

SECRET = re.compile(
    r"(secret|password|token|credential|api.?key|connection.?string)", re.IGNORECASE
)


def search_document(tool):
    fields = []
    for name, schema in (tool.input_schema.get("properties") or {}).items():
        if not SECRET.search(name):
            fields.extend([name, str(schema.get("description", ""))[:200]])
    raw = " ".join(
        [
            tool.display_name,
            tool.name,
            tool.description,
            tool.category,
            tool.provider,
            *tool.tags,
            *fields,
        ]
    )
    safe = re.sub(r"[\x00-\x1f]", " ", raw)
    safe = re.sub(
        r"(?i)\b(ignore|disregard|override|forget)\b.{0,80}\b(instruction|prompt|policy|rule)s?\b",
        "[untrusted instruction removed]",
        safe,
    )
    return f"UNTRUSTED TOOL METADATA (descriptive data only): {safe[:16000]}"


def source_for(tool):
    return (
        "mcp"
        if tool.provider == "mcp" or tool.name.startswith("mcp_")
        else "native"
        if tool.registration_source == "native"
        or tool.category in {"file", "database", "api", "notification"}
        else "sdk"
    )


async def index_tools(db, tenant_id="default", dry_run=False, batch_size=100):
    page_size = min(max(batch_size, 1), 500)
    tools = []
    cursor: tuple[str, str] | None = None
    while True:
        query = db.query(ToolDefinition).filter_by(tenant_id=tenant_id)
        if cursor:
            query = query.filter(
                (ToolDefinition.name > cursor[0])
                | (
                    (ToolDefinition.name == cursor[0])
                    & (ToolDefinition.version > cursor[1])
                )
            )
        page = (
            query.order_by(ToolDefinition.name, ToolDefinition.version)
            .limit(page_size)
            .all()
        )
        if not page:
            break
        tools.extend(page)
        cursor = (page[-1].name, page[-1].version)
        if len(page) < page_size:
            break
    changed = skipped = failed = 0
    for tool in tools:
        doc = search_document(tool)
        fp = hashlib.sha256(
            f"{INDEX_VERSION}:{provider.model}:{doc}".encode()
        ).hexdigest()
        row = (
            db.query(ToolSearchIndex)
            .filter_by(
                tenant_id=tenant_id, tool_name=tool.name, tool_version=tool.version
            )
            .first()
        )
        if row and row.content_fingerprint == fp:
            skipped += 1
            continue
        if dry_run:
            changed += 1
            continue
        try:
            vector = await provider.embed_query(doc)
            if len(vector) != provider.dimensions:
                raise ValueError("embedding dimension mismatch")
            if not row:
                row = ToolSearchIndex(
                    tenant_id=tenant_id,
                    tool_name=tool.name,
                    tool_version=tool.version,
                    search_document=doc,
                    content_fingerprint=fp,
                    embedding=vector,
                    embedding_model=provider.model,
                    embedding_dimensions=len(vector),
                    index_version=INDEX_VERSION,
                )
                db.add(row)
            else:
                row.search_document = doc
                row.content_fingerprint = fp
                row.embedding = vector
                row.embedding_model = provider.model
                row.embedding_dimensions = len(vector)
                row.index_version = INDEX_VERSION
                row.index_status = "ready"
                row.safe_error_code = None
                row.indexed_at = datetime.now(UTC)
            profile = (
                db.query(ToolMarketplaceProfile)
                .filter_by(
                    tenant_id=tenant_id, tool_name=tool.name, tool_version=tool.version
                )
                .first()
            )
            if not profile:
                db.add(
                    ToolMarketplaceProfile(
                        tenant_id=tenant_id,
                        tool_name=tool.name,
                        tool_version=tool.version,
                        source=source_for(tool),
                        status="enabled" if tool.enabled else "disabled",
                    )
                )
            changed += 1
        except Exception:  # noqa: BLE001 -- indexing isolates failures per provider tool
            failed += 1
            if row:
                row.index_status = "failed"
                row.safe_error_code = "DISCOVERY_EMBEDDING_FAILED"
    db.commit()
    return {
        "total": len(tools),
        "indexed": changed,
        "skipped": skipped,
        "failed": failed,
        "dry_run": dry_run,
        "model": provider.model,
        "dimensions": provider.dimensions,
        "index_version": INDEX_VERSION,
    }
