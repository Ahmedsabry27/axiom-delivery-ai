from types import SimpleNamespace

import pytest
from mcp.types import Prompt, Resource, ResourceTemplate, TextContent, Tool

from app.contracts.tool_models import ExecutionContext
from app.database.models.mcp import MCPCapability, MCPServer
from app.mcp_integration.client import MCPClientManager
from app.mcp_integration.security import normalize_schema, validate_server_url
from app.mcp_integration.service import sync_server
from app.tool_sdk.executor import ToolExecutor
from app.tool_sdk.registry import ToolRegistry


class FakeClient:
    def __init__(self, server):
        self.server = server
        self.initialized = SimpleNamespace(
            protocolVersion="2025-11-25",
            serverInfo=SimpleNamespace(name="Sprint13 Fake MCP", version="1.0.0"),
            capabilities=SimpleNamespace(
                model_dump=lambda **_: {"tools": {}, "resources": {}, "prompts": {}}
            ),
        )

    async def connect(self):
        return self.initialized

    async def disconnect(self):
        return None

    async def ping(self):
        return True

    async def list_tools(self):
        return [
            Tool(
                name="search_customer",
                description="Search customers",
                inputSchema={
                    "type": "object",
                    "properties": {"email": {"type": "string"}},
                    "required": ["email"],
                },
            )
        ]

    async def list_resources(self):
        return [
            Resource(
                name="policy", uri="customer://policy", description="Customer policy"
            )
        ]

    async def list_resource_templates(self):
        return [
            ResourceTemplate(
                name="customer",
                uriTemplate="customer://{customer_id}",
                description="Customer record",
            )
        ]

    async def list_prompts(self):
        return [
            Prompt(name="support_summary", description="Summarize customer support")
        ]

    async def call_tool(self, name, args):
        assert name == "search_customer"
        return SimpleNamespace(
            model_dump=lambda **_: {
                "content": [
                    TextContent(type="text", text=f"found:{args['email']}").model_dump(
                        mode="json"
                    )
                ],
                "isError": False,
            }
        )

    async def read_resource(self, uri):
        return {"contents": [{"uri": str(uri), "text": "policy"}]}

    async def get_prompt(self, name, args):
        return {"name": name, "arguments": args}

    def bounded(self, value):
        return value


def make_server():
    return MCPServer(
        tenant_id="acme",
        display_name="Customer Data MCP",
        slug="customer_data",
        server_url="https://mcp.example.com/mcp",
        transport="streamable_http",
        auth_type="none",
        policy={"allowed_hosts": ["mcp.example.com"]},
        enabled=True,
        created_by="admin",
        updated_by="admin",
    )


@pytest.mark.asyncio
async def test_discovery_adapts_all_capability_types_and_executes_through_tool_executor(
    db_session, monkeypatch
):
    server = make_server()
    db_session.add(server)
    db_session.commit()
    registry = ToolRegistry()
    manager = MCPClientManager(FakeClient)
    result = await sync_server(db_session, server, registry, manager)
    assert result == {
        "sync_id": result["sync_id"],
        "status": "succeeded",
        "added": 4,
        "changed": 0,
        "removed": 0,
        "warnings": 0,
    }
    assert {x.capability_type for x in db_session.query(MCPCapability).all()} == {
        "tool",
        "resource",
        "resource_template",
        "prompt",
    }
    tool_cap = db_session.query(MCPCapability).filter_by(capability_type="tool").one()
    assert tool_cap.enabled is False
    tool_cap.approved = True
    tool_cap.enabled = True
    tool_cap.change_status = "approved"
    db_session.commit()
    from app.mcp_integration import service

    monkeypatch.setattr(service, "manager", manager)
    service.register_capability_tool(tool_cap, registry)
    envelope = await ToolExecutor(registry).execute(
        tool_cap.internal_name,
        {"email": "alice@example.com"},
        ExecutionContext(
            actor_id="admin", tenant_id="acme", permissions={"tools.admin"}
        ),
        db_session,
    )
    assert envelope.status == "succeeded"
    assert envelope.data["content"][0]["text"] == "found:alice@example.com"


@pytest.mark.asyncio
async def test_schema_change_requires_review_and_disables_tool(db_session):
    server = make_server()
    db_session.add(server)
    db_session.commit()
    registry = ToolRegistry()
    manager = MCPClientManager(FakeClient)
    await sync_server(db_session, server, registry, manager)
    cap = db_session.query(MCPCapability).filter_by(capability_type="tool").one()
    cap.approved = cap.enabled = True
    cap.fingerprint = "old"
    db_session.commit()
    await sync_server(db_session, server, registry, manager)
    assert cap.change_status == "review_required"
    assert cap.enabled is False
    assert cap.approved is False


def test_url_and_schema_safety_controls():
    assert validate_server_url(
        "https://mcp.example.com/mcp", ["mcp.example.com"], resolve_dns=False
    )
    with pytest.raises(Exception):
        validate_server_url("http://127.0.0.1/mcp", [], resolve_dns=False)
    with pytest.raises(ValueError):
        normalize_schema({"type": "array"})
