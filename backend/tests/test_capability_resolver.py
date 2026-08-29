from uuid import uuid4

import pytest

from app.database.models.action import Action
from app.database.models.agent import Agent
from app.database.models.integration import (
    IntegrationAgentAssignment,
    IntegrationCapability,
    IntegrationConnection,
)
from app.database.models.tool import ToolDefinition
from app.database.session import SessionLocal
from app.models.runtime_execution import RuntimeExecution, RuntimeExecutionEvent
from app.runtime.capability_resolver import (
    CapabilityResolutionError,
    CapabilityResolver,
)
from app.runtime.parameter_reconciler import CanonicalParameter, ParameterState
from app.services.runtime_execution_service import RuntimeExecutionService


def intent(name):
    domain, resource, operation = name.split(".")
    return {
        "intent": name,
        "domain": domain,
        "resource": resource,
        "operation": operation,
        "confidence": 1,
        "ambiguous": False,
        "ambiguity_reason": None,
        "entities": {},
        "semantic_hints": [],
        "source": "deterministic",
        "error_code": None,
    }


def parameter(name, value):
    return CanonicalParameter(
        name=name,
        value=value,
        value_type="string",
        source="user_prompt",
        confidence=1,
        explicit=True,
        status="RESOLVED",
    )


def state(intent_name, **values):
    return ParameterState(
        intent=intent_name,
        parameters={name: parameter(name, value) for name, value in values.items()},
    )


def jira_connection(
    db, tenant="tenant-a", name="production", *, healthy=True, default=False
):
    row = IntegrationConnection(
        id=str(uuid4()),
        tenant_id=tenant,
        connector_type="jira",
        name=name,
        display_name=f"Jira {name.title()}",
        description="",
        auth_type="api_token",
        status="connected",
        health_status="healthy" if healthy else "unhealthy",
        base_url=f"https://{name}.atlassian.net",
        created_by="test",
        enabled=True,
        configuration={"is_default": default},
        safe_metadata={},
    )
    db.add(row)
    return row


def jira_capability(db, connection, name="jira.create_issue", *, enabled=True):
    write = name not in {"jira.search_issues", "jira.get_issue"}
    capability = IntegrationCapability(
        id=str(uuid4()),
        connection_id=connection.id,
        tenant_id=connection.tenant_id,
        external_name=name,
        display_name=name,
        description="",
        capability_type="action" if write else "tool",
        version="1.0.0",
        input_schema={
            "type": "object",
            "properties": {
                "project_key": {"type": "string"},
                **(
                    {"issue_type": {"type": "string"}, "summary": {"type": "string"}}
                    if write
                    else {}
                ),
            },
            "required": ["project_key", "issue_type", "summary"]
            if write
            else ["project_key"],
        },
        output_schema={},
        risk_level="medium",
        approval_required=False,
        governance={},
        enabled=enabled,
        provisioned=enabled,
    )
    db.add(capability)
    db.add(
        Action(
            tenant_id=connection.tenant_id,
            name=name,
            display_name=name,
            provider="jira",
            integration_connection_id=connection.id,
            risk_level="medium",
            approval_required=False,
            type="Integration",
            permissions={
                "required": ["jira.issue.create"] if write else ["jira.issue.read"]
            },
            status="ENABLED" if enabled else "DISABLED",
            usage=0,
        )
    )
    db.commit()
    return capability


def resolve(
    db, name="jira.issue.create", permissions=None, context=None, tenant="tenant-a"
):
    values = {"project_key": "KAN"}
    if name == "jira.issue.create":
        values.update(issue_type="Task", summary="Testing")
    return CapabilityResolver().resolve(
        db,
        intent_result=intent(name),
        parameter_state=state(name, **values),
        tenant_id=tenant,
        permissions=set(permissions or []),
        execution_context=context or {},
    )


def test_jira_create_resolves_actual_authorized_action(db_session):
    connection = jira_connection(db_session)
    jira_capability(db_session, connection)
    result = resolve(db_session, permissions={"jira.issue.create"})
    assert result.status == "RESOLVED"
    assert result.selected.name == "jira.create_issue"
    assert result.selected.capability_type == "action"
    assert result.selected.integration_connection_id == connection.id


def test_jira_search_never_resolves_create(db_session):
    connection = jira_connection(db_session)
    jira_capability(db_session, connection)
    jira_capability(db_session, connection, "jira.search_issues")
    result = resolve(db_session, "jira.issue.search", {"jira.issue.read"})
    assert result.selected.name == "jira.search_issues"
    assert all(item.name != "jira.create_issue" for item in result.candidates)


@pytest.mark.parametrize("semantic", ["jira.report.generate", "sap.work_order.create"])
def test_unregistered_semantic_capability_is_unavailable(db_session, semantic):
    db_session.add(
        ToolDefinition(
            tenant_id="tenant-a",
            name="deployment_report",
            display_name="Deployment Report",
            description="",
            category="deployment",
            provider="platform",
            version="1",
            input_schema={"type": "object", "properties": {}},
            output_schema={},
            permissions=[],
            tags=[],
            risk_level="read",
            enabled=True,
            active=True,
        )
    )
    db_session.commit()
    result = resolve(db_session, semantic)
    assert result.status == "UNAVAILABLE"
    assert result.selected is None


def test_deployment_report_resolves_catalog_tool(db_session):
    db_session.add(
        ToolDefinition(
            tenant_id="tenant-a",
            name="deployment_report",
            display_name="Deployment Report",
            description="",
            category="deployment",
            provider="platform",
            version="1",
            input_schema={"type": "object", "properties": {}},
            output_schema={},
            permissions=[],
            tags=[],
            risk_level="read",
            enabled=True,
            active=True,
        )
    )
    db_session.commit()
    result = resolve(db_session, "deployment.report.generate")
    assert result.status == "RESOLVED"
    assert result.selected.name == "deployment_report"


def test_disabled_unhealthy_unauthorized_and_tenant_filters(db_session):
    disabled = jira_connection(db_session, name="disabled")
    jira_capability(db_session, disabled, enabled=False)
    assert (
        resolve(db_session, permissions={"jira.issue.create"}).status == "UNAVAILABLE"
    )

    other = jira_connection(db_session, tenant="tenant-b", name="other")
    jira_capability(db_session, other)
    result = resolve(db_session, permissions={"jira.issue.create"})
    assert all(item.tenant_id != "tenant-b" for item in result.candidates)


def test_unhealthy_and_unauthorized_are_distinct(db_session):
    unhealthy = jira_connection(db_session, healthy=False)
    jira_capability(db_session, unhealthy)
    assert resolve(db_session, permissions={"jira.issue.create"}).status == "UNHEALTHY"
    unhealthy.health_status = "healthy"
    db_session.commit()
    assert resolve(db_session).status == "UNAUTHORIZED"


def test_multiple_connections_are_ambiguous_unless_default_or_explicit(db_session):
    production = jira_connection(db_session, name="production")
    sandbox = jira_connection(db_session, name="sandbox")
    jira_capability(db_session, production)
    jira_capability(db_session, sandbox)
    permissions = {"jira.issue.create"}
    assert resolve(db_session, permissions=permissions).status == "AMBIGUOUS"
    production.configuration = {"is_default": True}
    db_session.commit()
    assert (
        resolve(db_session, permissions=permissions).selected.integration_connection_id
        == production.id
    )
    production.configuration = {}
    db_session.commit()
    result = resolve(
        db_session, permissions=permissions, context={"connection_name": "sandbox"}
    )
    assert result.selected.integration_connection_id == sandbox.id


def test_input_compatibility_ranks_compatible_candidate(db_session):
    first = jira_connection(db_session, name="compatible")
    second = jira_connection(db_session, name="incompatible")
    jira_capability(db_session, first)
    bad = jira_capability(db_session, second)
    bad.input_schema = {
        "type": "object",
        "properties": {"project": {"type": "string"}},
        "required": ["project"],
    }
    db_session.commit()
    result = resolve(db_session, permissions={"jira.issue.create"})
    assert result.status == "RESOLVED"
    assert result.selected.integration_connection_id == first.id


def test_integration_agent_eligibility_is_scoped_per_capability(db_session):
    connection = jira_connection(db_session)
    jira_capability(db_session, connection, "jira.search_issues")
    jira_capability(db_session, connection, "jira.get_issue")
    agent = Agent(tenant_id="tenant-a", slug="jira-reader", name="Jira Reader")
    db_session.add(agent)
    db_session.flush()
    db_session.add(
        IntegrationAgentAssignment(
            connection_id=connection.id,
            agent_id=agent.id,
            tenant_id="tenant-a",
            capability_names=["jira.search_issues"],
            created_by="test",
        )
    )
    db_session.commit()

    search = resolve(
        db_session,
        name="jira.issue.search",
        permissions={"jira.issue.read"},
    )
    read = resolve(
        db_session,
        name="jira.issue.read",
        permissions={"jira.issue.read"},
    )

    assert search.selected.eligible_agent_ids == [str(agent.id)]
    assert read.selected.eligible_agent_ids == []


def test_explicit_agent_without_capability_is_not_silently_ignored(db_session):
    connection = jira_connection(db_session)
    jira_capability(db_session, connection)
    result = resolve(
        db_session,
        permissions={"jira.issue.create"},
        context={"selected_agent_id": "agent-1", "selected_agent_tools": []},
    )
    assert result.status == "UNAVAILABLE"
    assert "SELECTED_AGENT_INCOMPATIBLE" in result.candidates[0].rejection_reasons


def test_inventory_failure_is_technical_not_unavailable(db_session, monkeypatch):
    resolver = CapabilityResolver()
    monkeypatch.setattr(
        resolver, "_inventory", lambda *_: (_ for _ in ()).throw(RuntimeError("db"))
    )
    with pytest.raises(CapabilityResolutionError):
        resolver.resolve(
            db_session,
            intent_result=intent("jira.issue.create"),
            parameter_state=state(
                "jira.issue.create", project_key="KAN", issue_type="Task", summary="T"
            ),
            tenant_id="tenant-a",
            permissions={"jira.issue.create"},
        )


@pytest.mark.asyncio
async def test_runtime_resolution_is_persisted_and_event_is_durable():
    db = SessionLocal()
    try:
        runtime = RuntimeExecution(
            id=uuid4(),
            conversation_id=uuid4(),
            workflow_id=uuid4(),
            user_id="user-a",
            tenant_id="tenant-a",
            status="RUNNING",
            runtime_metadata={},
        )
        db.add(runtime)
        db.add(
            ToolDefinition(
                tenant_id="tenant-a",
                name="deployment_report",
                display_name="Deployment Report",
                description="",
                category="deployment",
                provider="platform",
                version="1",
                input_schema={"type": "object"},
                output_schema={},
                permissions=[],
                tags=[],
                risk_level="read",
                enabled=True,
                active=True,
            )
        )
        db.commit()
        service = RuntimeExecutionService()
        result = await service._resolve_capability_once(
            str(runtime.id),
            structured_intent=intent("deployment.report.generate"),
            parameter_state=state("deployment.report.generate").model_dump(mode="json"),
            permissions=set(),
            selected_agent=None,
        )
        db.expire_all()
        stored = db.get(RuntimeExecution, runtime.id)
        events = (
            db.query(RuntimeExecutionEvent)
            .filter_by(
                execution_id=runtime.id,
                event_type="capability_resolution.completed",
            )
            .all()
        )
        assert result["status"] == "RESOLVED"
        assert (
            stored.runtime_metadata["capability_resolution"]["selected"]["name"]
            == "deployment_report"
        )
        assert len(events) == 1
        await service._resolve_capability_once(
            str(runtime.id),
            structured_intent=intent("deployment.report.generate"),
            parameter_state=state("deployment.report.generate").model_dump(mode="json"),
            permissions=set(),
            selected_agent=None,
        )
        assert (
            db.query(RuntimeExecutionEvent)
            .filter_by(
                execution_id=runtime.id,
                event_type="capability_resolution.completed",
            )
            .count()
            == 1
        )
    finally:
        db.close()
