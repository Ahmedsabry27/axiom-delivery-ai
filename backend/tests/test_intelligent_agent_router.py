from uuid import uuid4

import pytest

from app.agents.application_service import AgentIdentity
from app.database.models.agent import Agent, AgentVersion
from app.database.models.agent_assignment import AgentToolAssignment
from app.database.models.integration import IntegrationAgentAssignment
from app.database.session import SessionLocal
from app.models.runtime_execution import RuntimeExecution, RuntimeExecutionEvent
from app.runtime.agent_router import AgentRouter
from app.runtime.capability_resolver import CapabilityResolutionResult
from app.runtime.parameter_reconciler import ParameterState
from app.services.runtime_execution_service import RuntimeExecutionService

IDENTITY = AgentIdentity(
    actor_id="user-a",
    tenant_id="tenant-a",
    permissions=frozenset({"agents.execute"}),
    groups=frozenset(),
    roles=frozenset(),
)


def capability(
    *,
    semantic="jira.issue.create",
    implementation="jira.create_issue",
    connection="jira-prod",
    eligible_ids=None,
):
    domain, resource, operation = semantic.split(".")
    selected = {
        "capability_id": "cap-1",
        "semantic_capability": semantic,
        "name": implementation,
        "display_name": implementation,
        "capability_type": "action" if operation in {"create", "update"} else "tool",
        "domain": domain,
        "resource": resource,
        "operation": operation,
        "provider": "jira",
        "source": "integration_capability",
        "enabled": True,
        "healthy": True,
        "tenant_id": "tenant-a",
        "integration_connection_id": connection,
        "integration_connection_name": "production",
        "integration_connection_display_name": "Jira Production",
        "connection_default": False,
        "permissions": [],
        "input_schema": {},
        "output_schema": {},
        "risk_level": "medium",
        "approval_required": False,
        "version": "1",
        "eligible_agent_ids": eligible_ids or [],
        "score": 100,
        "eligible": True,
        "rejection_reasons": [],
        "authorized": True,
        "input_compatible": True,
        "parameter_bindings": {},
        "explicit_connection_match": False,
    }
    return CapabilityResolutionResult.model_validate(
        {
            "intent": semantic,
            "status": "RESOLVED",
            "selected": selected,
            "candidates": [selected],
            "required_semantic_capability": semantic,
            "confidence": 1,
            "reason_code": None,
        }
    )


def intent(semantic="jira.issue.create"):
    domain, resource, operation = semantic.split(".")
    return {
        "intent": semantic,
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


def state(semantic="jira.issue.create"):
    return ParameterState(intent=semantic, parameters={})


def agent(
    db,
    name,
    *,
    tenant="tenant-a",
    capabilities=None,
    tools=None,
    connection="jira-prod",
    provider="bedrock",
    model="model-1",
    health="healthy",
    lifecycle="enabled",
    published=True,
    environments=None,
    priority=0,
    default=False,
    owner="user-a",
):
    row = Agent(
        uuid=str(uuid4()),
        tenant_id=tenant,
        slug=name.lower().replace(" ", "-"),
        name=name,
        description="",
        owner_id=owner,
        lifecycle_status=lifecycle,
        operational_health=health,
        current_version=1,
        published_version=1 if published else None,
        model_configuration_ref=provider if provider else None,
        planner_configuration={},
        environment_restrictions=environments or [],
        configuration="{}",
        created_by="test",
        updated_by="test",
    )
    db.add(row)
    db.flush()
    if published:
        db.add(
            AgentVersion(
                agent_id=row.id,
                tenant_id=tenant,
                version=1,
                instructions="Execute safely",
                model_configuration={"provider": provider, "model": model}
                if provider or model
                else {},
                planner_configuration={
                    "routing_priority": priority,
                    "is_default": default,
                },
                memory_configuration={},
                execution_limits={},
                tool_discovery_configuration={},
                configuration_snapshot={"capabilities": capabilities or []},
                change_note="test",
                created_by="test",
                published=True,
            )
        )
    for tool in tools or []:
        db.add(
            AgentToolAssignment(
                agent_id=row.id,
                agent_version=1,
                tenant_id=tenant,
                tool_name=tool,
                assignment_action="execute",
                enabled=True,
                risk_mode="write",
                approval_required=False,
                added_by="test",
            )
        )
    if connection:
        db.add(
            IntegrationAgentAssignment(
                connection_id=connection,
                agent_id=row.id,
                tenant_id=tenant,
                capability_names=tools or [],
                created_by="test",
            )
        )
    db.commit()
    return row


def route(db, *, explicit=None, cap=None, environment="production", identity=IDENTITY):
    resolved = cap or capability()
    return AgentRouter().route(
        db,
        capability_resolution=resolved,
        intent_result=intent(resolved.intent),
        parameter_state=state(resolved.intent),
        tenant_id="tenant-a",
        identity=identity,
        execution_context={"environment": environment},
        explicit_agent_id=explicit,
    )


def test_auto_jira_create_selects_exact_operations_agent(db_session):
    agent(
        db_session, "General Agent", capabilities=["general-execution"], connection=None
    )
    agent(db_session, "Jira Read Agent", tools=["jira.search_issues"])
    operations = agent(db_session, "Jira Operations Agent", tools=["jira.create_issue"])
    result = route(db_session)
    assert result.status == "RESOLVED"
    assert result.selected_agent.agent_id == operations.uuid


def test_explicit_compatible_agent_is_honored(db_session):
    selected = agent(db_session, "Bedrock Jira Agent", tools=["jira.create_issue"])
    agent(db_session, "Other Jira Agent", tools=["jira.create_issue"])
    result = route(db_session, explicit=selected.uuid)
    assert result.status == "EXPLICIT_SELECTED"
    assert result.selection_mode == "user_selected"
    assert result.selected_agent.agent_id == selected.uuid


def test_explicit_general_agent_is_incompatible_without_fallback(db_session):
    general = agent(
        db_session, "General Agent", capabilities=["general-execution"], connection=None
    )
    agent(db_session, "Jira Agent", tools=["jira.create_issue"])
    result = route(db_session, explicit=general.uuid)
    assert result.status == "INCOMPATIBLE"
    assert result.selected_agent is None


@pytest.mark.parametrize(
    ("kwargs", "reason"),
    [
        ({"lifecycle": "draft"}, "NOT_PUBLISHED"),
        ({"published": False}, "NOT_PUBLISHED"),
        ({"health": "unhealthy"}, "UNHEALTHY"),
        ({"environments": ["test"]}, "ENVIRONMENT_RESTRICTED"),
        ({"provider": "", "model": ""}, "AGENT_RUNTIME_UNAVAILABLE"),
    ],
)
def test_ineligible_agent_states_are_filtered(db_session, kwargs, reason):
    agent(db_session, "Jira Agent", tools=["jira.create_issue"], **kwargs)
    result = route(db_session)
    assert result.selected_agent is None
    assert reason in result.candidates[0].rejection_reasons


def test_healthy_agent_beats_unknown_health(db_session):
    agent(db_session, "Unknown Agent", tools=["jira.create_issue"], health="unknown")
    healthy = agent(
        db_session, "Healthy Agent", tools=["jira.create_issue"], health="healthy"
    )
    assert route(db_session).selected_agent.agent_id == healthy.uuid


def test_connection_and_tenant_mismatch_are_not_eligible(db_session):
    wrong = agent(
        db_session,
        "Production Agent",
        tools=["jira.create_issue"],
        connection="jira-other",
    )
    agent(db_session, "Other Tenant", tenant="tenant-b", tools=["jira.create_issue"])
    result = route(db_session)
    assert result.status == "UNAVAILABLE"
    assert [item.agent_id for item in result.candidates] == [wrong.uuid]
    assert "CONNECTION_MISMATCH" in result.candidates[0].rejection_reasons


def test_equal_provider_candidates_are_ambiguous(db_session):
    agent(db_session, "OpenAI Jira", tools=["jira.create_issue"], provider="openai")
    agent(db_session, "Bedrock Jira", tools=["jira.create_issue"], provider="bedrock")
    assert route(db_session).status == "AMBIGUOUS"


def test_configured_priority_breaks_tie(db_session):
    preferred = agent(db_session, "Preferred", tools=["jira.create_issue"], priority=5)
    agent(db_session, "Other", tools=["jira.create_issue"])
    assert route(db_session).selected_agent.agent_id == preferred.uuid


def test_capability_assigned_agent_ids_are_authoritative(db_session):
    allowed = agent(db_session, "Allowed", tools=["jira.create_issue"])
    agent(db_session, "Not Assigned", tools=["jira.create_issue"])
    result = route(db_session, cap=capability(eligible_ids=[str(allowed.id)]))
    assert result.selected_agent.agent_id == allowed.uuid


def test_router_never_invokes_ai_provider(db_session, monkeypatch):
    agent(db_session, "Jira Agent", tools=["jira.create_issue"])
    monkeypatch.setattr(
        "app.ai.factory.AIProviderFactory.get_provider",
        lambda **_: pytest.fail("agent routing must be deterministic"),
    )
    assert route(db_session).status == "RESOLVED"


def test_default_is_fallback_not_winner(db_session):
    default = agent(db_session, "Default", tools=["jira.create_issue"], default=True)
    specialized = agent(db_session, "Specialized", tools=["jira.create_issue"])
    result = route(db_session)
    assert result.selected_agent.agent_id == specialized.uuid
    db_session.delete(specialized)
    db_session.commit()
    result = route(db_session)
    assert result.selected_agent.agent_id == default.uuid
    assert result.selection_mode == "default_fallback"


@pytest.mark.asyncio
async def test_runtime_routing_persists_identity_and_exactly_one_event():
    db = SessionLocal()
    try:
        selected = agent(db, "Jira Operations", tools=["jira.create_issue"])
        runtime = RuntimeExecution(
            id=uuid4(),
            conversation_id=uuid4(),
            workflow_id=uuid4(),
            user_id="user-a",
            tenant_id="tenant-a",
            status="RUNNING",
            runtime_metadata={
                "request": {"agent_id": None},
                "identity": {
                    "actor_id": "user-a",
                    "tenant_id": "tenant-a",
                    "permissions": ["agents.execute"],
                    "groups": [],
                    "roles": [],
                    "subject_type": "user",
                },
            },
        )
        db.add(runtime)
        db.commit()
        service = RuntimeExecutionService()
        result = await service._route_agent_once(
            str(runtime.id),
            capability_resolution=capability().persisted_dict(),
            structured_intent=intent(),
            parameter_state=state().model_dump(mode="json"),
        )
        db.expire_all()
        stored = db.get(RuntimeExecution, runtime.id)
        assert result["selected_agent"]["agent_id"] == selected.uuid
        assert stored.selected_agent_id == selected.uuid
        assert stored.runtime_metadata["agent_routing"]["status"] == "RESOLVED"
        assert (
            db.query(RuntimeExecutionEvent)
            .filter_by(execution_id=runtime.id, event_type="agent_routing.completed")
            .count()
            == 1
        )
        await service._route_agent_once(
            str(runtime.id),
            capability_resolution=capability().persisted_dict(),
            structured_intent=intent(),
            parameter_state=state().model_dump(mode="json"),
        )
        assert (
            db.query(RuntimeExecutionEvent)
            .filter_by(execution_id=runtime.id, event_type="agent_routing.completed")
            .count()
            == 1
        )
    finally:
        db.close()
