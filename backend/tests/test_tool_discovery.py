import pytest

from app.contracts.tool_models import ExecutionContext
from app.database.models.tool_discovery import (
    ToolGovernancePolicy,
    ToolMarketplaceProfile,
)
from app.tool_discovery.embedding import HashEmbeddingProvider, cosine
from app.tool_discovery.engine import engine
from app.tool_discovery.indexing import index_tools, search_document
from app.tool_discovery.intent import extract_intent
from app.tool_discovery.schemas import DiscoveryRequest
from app.tool_sdk.errors import UnsafeOperationError
from app.tool_sdk.service import executor, registry, sync_catalog


@pytest.fixture
def catalog(db_session):
    sync_catalog(db_session)
    return db_session


def ctx(**updates):
    base = ExecutionContext(
        actor_id="alice",
        tenant_id="default",
        permissions={
            "files.read",
            "files.search",
            "files.metadata.read",
            "files.extract",
            "files.summarize",
            "servicenow.incidents.read",
            "notifications.email.send",
        },
    )
    return base.model_copy(update=updates)


def test_intent_and_safe_document(catalog):
    intent = extract_intent("Delete production deployment records")
    assert intent.operation == "delete" and intent.destructive
    tool = registry.get("file_read")
    doc = search_document(
        catalog.query(
            __import__(
                "app.database.models.tool", fromlist=["ToolDefinition"]
            ).ToolDefinition
        )
        .filter_by(name=tool.name)
        .one()
    )
    assert "secret" not in doc.lower()


@pytest.mark.asyncio
async def test_embedding_is_cached_and_dimensionally_stable():
    p = HashEmbeddingProvider(32)
    a = await p.embed_query("deployment report")
    b = await p.embed_query("deployment report")
    assert a == b and len(a) == 32 and cosine(a, b) == pytest.approx(1)


@pytest.mark.asyncio
async def test_hybrid_discovery_filters_permissions_and_is_explainable(catalog):
    result = await engine.discover(
        DiscoveryRequest(query="search files", risk_tolerance="read"), ctx(), catalog
    )
    assert result["outcome"] in {"selected", "clarification_required"}
    assert all(
        set(registry.get(x["tool_name"]).metadata.permissions) <= ctx().permissions
        for x in result["candidates"]
    )
    assert result["strategy_version"] == "1.0.0"
    assert result["candidates"][0]["component_scores"]["lexical"] >= 0


@pytest.mark.asyncio
async def test_explicit_deny_precedes_allow(catalog):
    await index_tools(catalog)
    catalog.add(
        ToolGovernancePolicy(
            tenant_id="default",
            name="deny incidents",
            decision="deny",
            lifecycle="active",
            conditions=[
                {
                    "field": "tool",
                    "operator": "equals",
                    "value": "servicenow_incident_search",
                }
            ],
            actions={},
            priority=1,
            created_by="admin",
            updated_by="admin",
        )
    )
    catalog.add(
        ToolGovernancePolicy(
            tenant_id="default",
            name="allow incidents",
            decision="allow",
            lifecycle="active",
            conditions=[
                {
                    "field": "tool",
                    "operator": "equals",
                    "value": "servicenow_incident_search",
                }
            ],
            actions={},
            priority=2,
            created_by="admin",
            updated_by="admin",
        )
    )
    catalog.commit()
    result = await engine.discover(
        DiscoveryRequest(
            query="servicenow incident search",
            explicit_tool="servicenow_incident_search",
        ),
        ctx(),
        catalog,
    )
    assert result["outcome"] == "no_authorized_tool" and result["selected"] is None
    assert result["safe_rejections"] == [{"reason_code": "POLICY_DENIED"}]


@pytest.mark.asyncio
async def test_approval_and_marketplace_disable_affect_discovery_immediately(catalog):
    await index_tools(catalog)
    profile = (
        catalog.query(ToolMarketplaceProfile)
        .filter_by(tool_name="notification_email_send")
        .one()
    )
    profile.approval_policy = "always"
    catalog.commit()
    request = DiscoveryRequest(
        query="send notification email",
        explicit_tool="notification_email_send",
        risk_tolerance="write",
        approval_allowed=True,
    )
    result = await engine.discover(request, ctx(), catalog)
    assert (
        result["outcome"] == "approval_required"
        and result["human_confirmation_required"]
    )
    profile.status = "disabled"
    catalog.commit()
    blocked = await engine.discover(request, ctx(), catalog)
    assert blocked["outcome"] == "no_authorized_tool"


@pytest.mark.asyncio
async def test_tenant_and_permission_isolation(catalog):
    result = await engine.discover(
        DiscoveryRequest(query="search production incidents"),
        ctx(tenant_id="other", permissions=set()),
        catalog,
    )
    assert result["candidates"] == [] and result["selected"] is None


@pytest.mark.asyncio
async def test_executor_rechecks_approval_at_time_of_use(catalog):
    await index_tools(catalog)
    profile = (
        catalog.query(ToolMarketplaceProfile)
        .filter_by(tool_name="notification_email_send")
        .one()
    )
    profile.approval_policy = "always"
    catalog.commit()
    with pytest.raises(UnsafeOperationError):
        await executor.execute(
            "notification_email_send",
            {
                "recipients": ["ops@example.com"],
                "message": "test",
                "idempotency_key": "approval-test-1",
            },
            ctx(),
            catalog,
        )
