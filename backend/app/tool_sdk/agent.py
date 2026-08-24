"""The sole bridge exposed to agent runtimes for discovery and invocation."""

from app.contracts.tool_models import ExecutionContext
from app.tool_discovery.engine import engine
from app.tool_discovery.schemas import DiscoveryRequest
from app.tool_sdk.service import executor, registry


def authorized_model_tools(*, permissions: set[str], allowlist: set[str] | None = None):
    definitions = []
    for tool in registry.list(enabled=True):
        if allowlist is not None and tool.name not in allowlist:
            continue
        if (
            not set(tool.metadata.permissions) <= permissions
            and "tools.admin" not in permissions
        ):
            continue
        definitions.append(tool.metadata.model_tool_definition())
    return definitions


async def invoke_agent_tool(
    name,
    input_data,
    *,
    db,
    actor_id,
    permissions,
    tenant_id="default",
    agent_id=None,
    conversation_id=None,
    correlation_id=None,
):
    update = {}
    if correlation_id:
        update["correlation_id"] = correlation_id
    context = ExecutionContext(
        actor_id=actor_id,
        permissions=permissions,
        tenant_id=tenant_id,
        agent_id=agent_id,
        conversation_id=conversation_id,
    ).model_copy(update=update)
    return await executor.execute(name, input_data, context, db)


async def discover_agent_tools(
    query,
    *,
    db,
    actor_id,
    permissions,
    tenant_id="default",
    agent_id=None,
    conversation_id=None,
    max_candidates=5,
):
    """Small authorized candidate set for planners; never returns the full catalog."""
    context = ExecutionContext(
        actor_id=actor_id,
        permissions=permissions,
        tenant_id=tenant_id,
        agent_id=agent_id,
        conversation_id=conversation_id,
    )
    return await engine.discover(
        DiscoveryRequest(query=query, max_candidates=max_candidates), context, db
    )
