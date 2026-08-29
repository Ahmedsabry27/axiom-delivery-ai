import json
from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.contracts.tool_models import ExecutionContext
from app.database.base import Base
from app.database.models.action import Action
from app.database.models.agent import Agent
from app.database.models.agent_assignment import AgentToolAssignment
from app.database.models.integration import (
    IntegrationAgentAssignment,
    IntegrationCapability,
    IntegrationConnection,
)
from app.database.models.tool import ToolDefinition
from app.integrations.errors import IntegrationError
from app.integrations.jira import CAPABILITIES, JiraConnector
from app.integrations.provisioning import (
    provision_capability,
    sync_connection_assignments,
)
from app.integrations.registry import connector_registry
from app.integrations.runtime import IntegrationTool
from app.integrations.secrets import SecretProvider
from app.tool_sdk.registry import ToolRegistry


def connection(**overrides):
    values = {
        "base_url": "https://company.atlassian.net",
        "auth_type": "api_token",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_registry_exposes_connector_pack_and_rejects_unimplemented_connectors():
    assert {
        "jira",
        "confluence",
        "outlook_calendar",
        "microsoft_teams",
    } <= connector_registry.implemented()
    assert connector_registry.get("jira").connector_type == "jira"
    with pytest.raises(IntegrationError, match="not implemented"):
        connector_registry.get("salesforce")


def test_secret_provider_resolves_json_environment_without_exposing_it(monkeypatch):
    monkeypatch.setenv(
        "JIRA_TEST_CREDENTIALS",
        json.dumps({"email": "bot@example.com", "api_token": "secret"}),
    )
    assert SecretProvider().resolve("env://JIRA_TEST_CREDENTIALS") == {
        "email": "bot@example.com",
        "api_token": "secret",
    }


def test_jira_capabilities_include_required_input_and_no_delete():
    names = {item.name for item in CAPABILITIES}
    assert {
        "jira.search_issues",
        "jira.get_issue",
        "jira.create_issue",
        "jira.transition_issue",
    } <= names
    assert not any("delete" in name for name in names)
    create = next(item for item in CAPABILITIES if item.name == "jira.create_issue")
    assert create.input_schema["required"] == ["project_key", "issue_type", "summary"]


@pytest.mark.asyncio
async def test_jira_test_connection_and_project_discovery_make_real_requests(
    monkeypatch,
):
    seen = []

    def handler(request: httpx.Request):
        seen.append(request.url.path)
        if request.url.path.endswith("/myself"):
            return httpx.Response(
                200, json={"displayName": "Automation Bot", "accountId": "abc"}
            )
        return httpx.Response(
            200,
            json={
                "values": [
                    {
                        "id": "1",
                        "key": "COPILOT",
                        "name": "Enterprise AI",
                        "projectTypeKey": "software",
                    }
                ]
            },
        )

    transport = httpx.MockTransport(handler)
    original = httpx.AsyncClient
    monkeypatch.setattr(
        httpx, "AsyncClient", lambda **kwargs: original(transport=transport, **kwargs)
    )
    connector = JiraConnector()
    secret = {"email": "bot@example.com", "api_token": "token"}
    result = await connector.test_connection(connection(), secret)
    capabilities, metadata = await connector.discover_capabilities(connection(), secret)
    assert result == {"healthy": True, "account": "Automation Bot", "account_id": "abc"}
    assert metadata["projects"][0]["key"] == "COPILOT"
    assert len(capabilities) == 10
    assert seen == ["/rest/api/3/myself", "/rest/api/3/project/search"]


@pytest.mark.asyncio
async def test_jira_invalid_credentials_are_normalized(monkeypatch):
    transport = httpx.MockTransport(
        lambda request: httpx.Response(401, json={"errorMessages": ["Unauthorized"]})
    )
    original = httpx.AsyncClient
    monkeypatch.setattr(
        httpx, "AsyncClient", lambda **kwargs: original(transport=transport, **kwargs)
    )
    with pytest.raises(IntegrationError) as error:
        await JiraConnector().test_connection(
            connection(), {"email": "bot@example.com", "api_token": "wrong"}
        )
    assert error.value.code == "INTEGRATION_AUTH_FAILED"


@pytest.mark.asyncio
async def test_jira_create_metadata_uses_supported_staged_endpoints(monkeypatch):
    seen = []

    def handler(request: httpx.Request):
        seen.append(request.url.path)
        if request.url.path.endswith("/issuetypes"):
            return httpx.Response(
                200,
                json={"issueTypes": [{"id": "10001", "name": "Bug", "subtask": False}]},
            )
        return httpx.Response(
            200,
            json={
                "fields": [{"fieldId": "summary", "name": "Summary", "required": True}]
            },
        )

    original = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs),
    )
    result = await JiraConnector().execute_tool(
        connection(),
        "jira.get_create_metadata",
        {"project_key": "KAN", "issue_type": "Bug"},
        {"email": "bot@example.com", "api_token": "token"},
    )
    assert result["selected_issue_type"] == {"id": "10001", "name": "Bug"}
    assert result["fields"][0]["fieldId"] == "summary"
    assert seen == [
        "/rest/api/3/issue/createmeta/KAN/issuetypes",
        "/rest/api/3/issue/createmeta/KAN/issuetypes/10001",
    ]


@pytest.fixture
def integration_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    Base.metadata.drop_all(engine)


def persisted_connection(tenant="tenant-a", enabled=True):
    return IntegrationConnection(
        tenant_id=tenant,
        connector_type="jira",
        name=f"jira-{tenant}",
        display_name="Jira Production",
        auth_type="api_token",
        status="connected",
        health_status="healthy",
        base_url="https://company.atlassian.net",
        secret_ref="env://JIRA_TEST",
        created_by="admin",
        enabled=enabled,
    )


def persisted_capability(connection, name="jira.search_issues", capability_type="tool"):
    definition = next(item for item in CAPABILITIES if item.name == name)
    return IntegrationCapability(
        connection_id=connection.id,
        tenant_id=connection.tenant_id,
        external_name=name,
        display_name=definition.display_name,
        description=definition.description,
        capability_type=capability_type,
        version=definition.version,
        input_schema=definition.input_schema,
        output_schema=definition.output_schema,
        risk_level=definition.risk_level,
        approval_required=definition.approval_required,
    )


def test_provisioning_creates_catalog_rows_and_is_idempotent(integration_db):
    registry = ToolRegistry()
    connection = persisted_connection()
    integration_db.add(connection)
    integration_db.flush()
    tool_cap = persisted_capability(connection)
    action_cap = persisted_capability(connection, "jira.create_issue", "action")
    integration_db.add_all([tool_cap, action_cap])
    integration_db.flush()
    for _ in range(2):
        provision_capability(integration_db, connection, tool_cap, "admin", registry)
        provision_capability(integration_db, connection, action_cap, "admin", registry)
        integration_db.commit()
    tool = (
        integration_db.query(ToolDefinition).filter_by(name="jira.search_issues").one()
    )
    action = integration_db.query(Action).filter_by(name="jira.create_issue").one()
    assert tool.integration_connection_id == connection.id
    assert tool.permissions == ["jira.issue.read"]
    assert action.integration_connection_id == connection.id
    assert (
        integration_db.query(ToolDefinition)
        .filter_by(name="jira.search_issues")
        .count()
        == 1
    )
    assert integration_db.query(Action).filter_by(name="jira.create_issue").count() == 1
    assert registry.get("jira.search_issues").metadata.provider == "jira"


def test_provisioning_is_tenant_scoped(integration_db):
    for tenant in ("tenant-a", "tenant-b"):
        connection = persisted_connection(tenant)
        integration_db.add(connection)
        integration_db.flush()
        capability = persisted_capability(connection)
        integration_db.add(capability)
        integration_db.flush()
        provision_capability(
            integration_db, connection, capability, "admin", ToolRegistry()
        )
    integration_db.commit()
    assert (
        integration_db.query(ToolDefinition)
        .filter_by(name="jira.search_issues")
        .count()
        == 2
    )


def test_assignment_sync_preserves_explicit_read_scope_and_disables_stale_writes(
    integration_db,
):
    registry = ToolRegistry()
    connection = persisted_connection()
    agent = Agent(tenant_id="tenant-a", slug="read-agent", name="Read Agent")
    integration_db.add_all([connection, agent])
    integration_db.flush()
    read_capability = persisted_capability(connection)
    write_capability = persisted_capability(
        connection, "jira.create_issue", "action"
    )
    integration_db.add_all([read_capability, write_capability])
    integration_db.flush()
    provision_capability(
        integration_db, connection, read_capability, "admin", registry
    )
    provision_capability(
        integration_db, connection, write_capability, "admin", registry
    )
    integration_db.add_all(
        [
            IntegrationAgentAssignment(
                connection_id=connection.id,
                agent_id=agent.id,
                tenant_id="tenant-a",
                capability_names=["jira.search_issues"],
                created_by="admin",
            ),
            AgentToolAssignment(
                agent_id=agent.id,
                agent_version=1,
                tenant_id="tenant-a",
                tool_name="jira.create_issue",
                version_restriction="1.0.0",
                assignment_action="execute",
                enabled=True,
                risk_mode="write",
                approval_required=True,
                added_by="admin",
            ),
        ]
    )
    integration_db.commit()

    sync_connection_assignments(
        integration_db, connection, "admin", agent_ids={agent.id}
    )
    integration_db.commit()

    assignments = {
        item.tool_name: item
        for item in integration_db.query(AgentToolAssignment).filter_by(
            agent_id=agent.id,
            assignment_action="execute",
        )
    }
    assert assignments["jira.search_issues"].enabled is True
    assert assignments["jira.search_issues"].risk_mode == "read"
    assert assignments["jira.create_issue"].enabled is False
    integration_assignment = integration_db.query(IntegrationAgentAssignment).one()
    assert integration_assignment.capability_names == ["jira.search_issues"]


@pytest.mark.asyncio
async def test_disabled_integration_blocks_runtime_execution(integration_db):
    connection = persisted_connection(enabled=False)
    integration_db.add(connection)
    integration_db.flush()
    capability = persisted_capability(connection)
    capability.enabled = True
    capability.provisioned = True
    integration_db.add(capability)
    integration_db.commit()
    result = await IntegrationTool(connection, capability).execute(
        {"jql": "project = COPILOT"},
        ExecutionContext(
            actor_id="user", tenant_id="tenant-a", db_session=integration_db
        ),
    )
    assert result.success is False
    assert result.error.code == "CAPABILITY_UNAVAILABLE"
