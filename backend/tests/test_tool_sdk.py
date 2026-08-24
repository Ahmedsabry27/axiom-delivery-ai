from __future__ import annotations

import asyncio

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.contracts.tool import Tool
from app.contracts.tool_models import (
    ExecutionContext,
    RetryPolicy,
    ToolMetadata,
    ToolResult,
)
from app.database.base import Base
from app.database.models.tool import ToolExecution
from app.tool_sdk.adapters import LocalFileAdapter
from app.tool_sdk.agent import authorized_model_tools, invoke_agent_tool
from app.tool_sdk.builtin_tools import (
    AzureBlobTool,
    KeyVaultMetadataTool,
    ServiceNowSearchTool,
)
from app.tool_sdk.errors import (
    PermissionDeniedError,
    ToolDisabledError,
    UnsafeOperationError,
    redact,
)
from app.tool_sdk.executor import ToolExecutor
from app.tool_sdk.registry import ToolRegistry
from app.tool_sdk.schema import validate_and_default


def metadata(**overrides):
    data = dict(
        name="example_tool",
        display_name="Example",
        description="Example test tool",
        category="testing",
        provider="internal",
        version="1.0.0",
        permissions=("example.read",),
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "minLength": 1},
                "limit": {"type": "integer", "minimum": 1, "maximum": 10, "default": 2},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    )
    data.update(overrides)
    return ToolMetadata(**data)


class FakeTool(Tool):
    def __init__(self, m=None, result=None, delay=0):
        self.metadata = m or metadata()
        self.result = result or {"ok": True}
        self.delay = delay
        self.calls = 0

    async def execute(self, input_data, context):
        self.calls += 1
        await asyncio.sleep(self.delay)
        return ToolResult.succeeded({**self.result, "input": input_data})


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    Base.metadata.drop_all(engine)


@pytest.mark.parametrize(
    "field,value", [("name", "Not Valid"), ("version", "1.0"), ("name", "a-b")]
)
def test_metadata_rejects_invalid_name_and_semver(field, value):
    with pytest.raises(ValidationError):
        metadata(**{field: value})


def test_metadata_rejects_credentials_and_unknown_fields():
    with pytest.raises(ValidationError):
        metadata(
            parameters={
                "type": "object",
                "properties": {"api_token": {"type": "string"}},
                "additionalProperties": False,
            }
        )
    with pytest.raises(ValidationError):
        ToolMetadata(**{**metadata().model_dump(), "surprise": True})


def test_schema_defaults_constraints_and_unknown_fields():
    assert validate_and_default(metadata().parameters, {"query": "x"})["limit"] == 2
    with pytest.raises(Exception):
        validate_and_default(metadata().parameters, {"query": "x", "unknown": 1})
    with pytest.raises(Exception):
        validate_and_default(metadata().parameters, {"query": "", "limit": 100})


def test_registry_versions_filters_and_toggle():
    r = ToolRegistry()
    a = FakeTool()
    b = FakeTool(metadata(version="2.0.0", provider="other"))
    r.register(a)
    r.register(b)
    assert r.get("example_tool").metadata.version == "2.0.0"
    assert r.versions("example_tool") == ["1.0.0", "2.0.0"]
    assert r.list(provider="other") == [b]
    r.set_enabled("example_tool", "2.0.0", False)
    assert not r.is_enabled(b)
    with pytest.raises(ValueError):
        r.register(a)


@pytest.mark.asyncio
async def test_executor_authorization_defaults_audit_and_idempotency(db):
    tool = FakeTool()
    r = ToolRegistry()
    r.register(tool)
    ex = ToolExecutor(r)
    ctx = ExecutionContext(
        actor_id="u1", permissions={"example.read"}, idempotency_key="same"
    )
    first = await ex.execute(tool.name, {"query": "hello"}, ctx, db)
    second = await ex.execute(tool.name, {"query": "hello"}, ctx, db)
    assert first.status == "succeeded" and first.data["input"]["limit"] == 2
    assert second.execution_id == first.execution_id
    assert tool.calls == 1
    row = db.get(ToolExecution, first.execution_id)
    assert row.status == "succeeded" and row.actor_id == "u1"


@pytest.mark.asyncio
async def test_executor_permission_disabled_timeout_and_redaction(db):
    r = ToolRegistry()
    tool = FakeTool()
    r.register(tool)
    ex = ToolExecutor(r)
    with pytest.raises(PermissionDeniedError):
        await ex.execute(
            tool.name,
            {"query": "x"},
            ExecutionContext(actor_id="u", permissions=set()),
            db,
        )
    r.set_enabled(tool.name, "1.0.0", False)
    with pytest.raises(ToolDisabledError):
        await ex.execute(
            tool.name,
            {"query": "x"},
            ExecutionContext(actor_id="u", permissions={"example.read"}),
            db,
        )
    timeout = FakeTool(metadata(timeout_seconds=1), delay=1.1)
    r2 = ToolRegistry()
    r2.register(timeout)
    result = await ToolExecutor(r2).execute(
        timeout.name,
        {"query": "x"},
        ExecutionContext(actor_id="u", permissions={"example.read"}),
        db,
    )
    assert result.error.code == "EXECUTION_TIMEOUT"
    assert redact({"authorization": "Bearer abc", "nested": {"password": "x"}}) == {
        "authorization": "[REDACTED]",
        "nested": {"password": "[REDACTED]"},
    }
    assert redact({"key": "KAN-1", "project_key": "KAN", "api_key": "secret"}) == {
        "key": "KAN-1",
        "project_key": "KAN",
        "api_key": "[REDACTED]",
    }


@pytest.mark.asyncio
async def test_retry_for_safe_tool(db):
    class Flaky(FakeTool):
        async def execute(self, input_data, context):
            from app.tool_sdk.errors import IntegrationUnavailableError

            self.calls += 1
            if self.calls < 2:
                raise IntegrationUnavailableError("offline")
            return ToolResult.succeeded({"ok": True})

    tool = Flaky(
        metadata(retry_policy=RetryPolicy(max_attempts=2, base_delay_seconds=0))
    )
    r = ToolRegistry()
    r.register(tool)
    result = await ToolExecutor(r).execute(
        tool.name,
        {"query": "x"},
        ExecutionContext(actor_id="u", permissions={"example.read"}),
        db,
    )
    assert result.status == "succeeded" and tool.calls == 2


def test_local_file_security(tmp_path):
    root = tmp_path / "allowed"
    root.mkdir()
    (root / "safe.txt").write_text("hello")
    outside = tmp_path / "outside.txt"
    outside.write_text("secret")
    adapter = LocalFileAdapter([str(root)], max_bytes=10)
    assert adapter.read("safe.txt") == "hello"
    assert adapter.list(".")[0]["name"] == "safe.txt"
    with pytest.raises(UnsafeOperationError):
        adapter.read(str(outside))
    (root / "large.txt").write_text("x" * 11)
    with pytest.raises(UnsafeOperationError):
        adapter.read("large.txt")
    link = root / "link.txt"
    link.symlink_to(outside)
    with pytest.raises(UnsafeOperationError):
        adapter.read("link.txt")


def test_agent_discovery_is_permission_and_allowlist_scoped():
    names = {
        x["function"]["name"]
        for x in authorized_model_tools(
            permissions={"servicenow.incidents.read"},
            allowlist={"servicenow_incident_search", "file_read"},
        )
    }
    assert names == {"servicenow_incident_search"}


@pytest.mark.asyncio
async def test_agent_to_executor_records_normalized_result(db):
    from app.tool_sdk.service import registry

    tool = FakeTool(metadata(name="agent_test_tool", permissions=("agent.test",)))
    registry.register(tool)
    try:
        definitions = authorized_model_tools(
            permissions={"agent.test"}, allowlist={"agent_test_tool"}
        )
        assert definitions[0]["function"]["parameters"]["required"] == ["query"]
        result = await invoke_agent_tool(
            "agent_test_tool",
            {"query": "from model"},
            db=db,
            actor_id="user-1",
            agent_id="default-agent",
            permissions={"agent.test"},
            correlation_id="agent-correlation",
        )
        row = db.get(ToolExecution, result.execution_id)
        assert result.status == "succeeded"
        assert row.agent_id == "default-agent"
        assert row.correlation_id == "agent-correlation"
    finally:
        registry.unregister("agent_test_tool", "1.0.0")


@pytest.mark.asyncio
async def test_fake_provider_contract_mapping():
    class FakeServiceNow:
        async def search(self, table, params):
            return [
                {"number": "INC001", "short_description": "Network issue"}
            ], "snow-1"

        async def verify(self):
            return {"ready": True, "message": "ok"}

    snow = ServiceNowSearchTool(
        "servicenow_incident_search",
        "ServiceNow Incident Search",
        "servicenow.incidents.read",
        FakeServiceNow(),
    )
    result = await snow.execute(
        {"limit": 10, "offset": 0},
        ExecutionContext(actor_id="u", permissions={"servicenow.incidents.read"}),
    )
    assert (
        result.data["items"][0]["number"] == "INC001"
        and result.provider_request_id == "snow-1"
    )

    class FakeBlob:
        def allowed_container(self, name):
            assert name == "approved"

        async def request(self, *args, **kwargs):
            return {"items": [{"name": "report.txt"}]}, "azure-1"

    blob = AzureBlobTool("list", FakeBlob())
    result = await blob.execute(
        {"container": "approved", "prefix": "", "limit": 25},
        ExecutionContext(actor_id="u", permissions={"azure.blob.read"}),
    )
    assert result.provider_request_id == "azure-1"

    class FakeVault:
        async def metadata(self, name):
            return {"name": name, "enabled": True}, "vault-1"

        async def verify(self):
            return {"ready": True, "message": "ok"}

    vault = KeyVaultMetadataTool(FakeVault())
    result = await vault.execute(
        {"name": "database-password"},
        ExecutionContext(
            actor_id="internal", permissions={"azure.keyvault.secrets.read"}
        ),
    )
    assert "value" not in result.data and result.data["name"] == "database-password"
