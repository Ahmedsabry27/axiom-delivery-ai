from __future__ import annotations

from app.database.models.tool import ToolDefinition
from app.tool_sdk.builtin_tools import builtin_tools
from app.tool_sdk.executor import ToolExecutor
from app.tool_sdk.native_tools import native_tools
from app.tool_sdk.registry import ToolRegistry

registry = ToolRegistry()
registry.register_many(builtin_tools() + native_tools())
executor = ToolExecutor(registry)


def sync_catalog(db):
    for tool in registry.list():
        m = tool.metadata
        if "integration" in m.tags and "action" in m.tags:
            continue
        row = (
            db.query(ToolDefinition)
            .filter_by(tenant_id="default", name=m.name, version=m.version)
            .first()
        )
        values = {
            "display_name": m.display_name,
            "description": m.description,
            "category": m.category,
            "provider": m.provider,
            "input_schema": m.parameters,
            "output_schema": m.output_schema,
            "permissions": list(m.permissions),
            "tags": list(m.tags),
            "risk_level": m.risk_level.value,
            "registration_source": "native",
            "deprecated": m.deprecated,
            "configuration_state": "not_configured"
            if m.configuration_requirements
            else "ready",
        }
        if row:
            for key, value in values.items():
                setattr(row, key, value)
            registry.set_enabled(m.name, m.version, row.enabled)
        else:
            db.add(
                ToolDefinition(
                    tenant_id="default",
                    name=m.name,
                    version=m.version,
                    enabled=m.enabled,
                    active=True,
                    **values,
                )
            )
    db.commit()


def catalog_item(tool, row=None, health=None):
    m = tool.metadata
    enabled = row.enabled if row else registry.is_enabled(tool)
    return {
        **m.model_dump(mode="json"),
        "enabled": enabled,
        "active": row.active if row else True,
        "configuration_state": row.configuration_state
        if row
        else ("not_configured" if m.configuration_requirements else "ready"),
        "health": health,
    }
