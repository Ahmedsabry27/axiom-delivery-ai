from __future__ import annotations

import json
from uuid import uuid4

import pytest

from app.agents.application_service import AgentIdentity
from app.ai.models import AIResponse
from app.database.models.action import Action
from app.database.models.agent import Agent, AgentVersion
from app.database.models.agent_assignment import AgentToolAssignment
from app.database.models.integration import (
    IntegrationAgentAssignment,
    IntegrationCapability,
    IntegrationConnection,
)
from app.integrations.jira import CAPABILITIES, JiraConnector
from app.planners.capability_aware_planner import CapabilityAwarePlanner
from app.runtime.agent_router import AgentRouter
from app.runtime.capability_resolver import CapabilityResolver
from app.runtime.context import RuntimeContext
from app.runtime.input_requirements import (
    MissingFieldResolver,
    RequirementSchemaProvider,
)
from app.runtime.intent_analyzer import IntentAnalyzer
from app.runtime.parameter_extractor import ParameterExtractor
from app.runtime.parameter_reconciler import ParameterReconciler


class _Provider:
    def __init__(self, payload: dict):
        self.payload = payload
        self.calls = 0

    def ask(self, _messages):
        self.calls += 1
        return AIResponse(text=json.dumps(self.payload), model="mock-semantic-model")


def _definition(name: str) -> list[dict]:
    capability = next(item for item in CAPABILITIES if item.name == name)
    return [
        {
            "type": "function",
            "function": {
                "name": capability.name,
                "description": capability.description,
                "parameters": capability.input_schema,
                "version": "1.0.0",
            },
        }
    ]


def _inventory(db, name: str, capability_type: str):
    definition = next(item for item in CAPABILITIES if item.name == name)
    connection = IntegrationConnection(
        id=str(uuid4()),
        tenant_id="tenant-a",
        connector_type="jira",
        name="production",
        display_name="Jira Production",
        description="",
        auth_type="api_token",
        status="connected",
        health_status="healthy",
        base_url="https://example.atlassian.net",
        created_by="test",
        enabled=True,
        configuration={"is_default": True},
        safe_metadata={},
    )
    db.add(connection)
    capability = IntegrationCapability(
        id=str(uuid4()),
        connection_id=connection.id,
        tenant_id="tenant-a",
        external_name=name,
        display_name=definition.display_name,
        description=definition.description,
        capability_type=capability_type,
        version="1.0.0",
        input_schema=definition.input_schema,
        output_schema=definition.output_schema,
        risk_level=definition.risk_level,
        approval_required=definition.approval_required,
        governance={},
        enabled=True,
        provisioned=True,
    )
    db.add(capability)
    permission = (
        "jira.issue.create" if capability_type == "action" else "jira.issue.read"
    )
    db.add(
        Action(
            tenant_id="tenant-a",
            name=name,
            display_name=name,
            provider="jira",
            integration_connection_id=connection.id,
            risk_level=definition.risk_level,
            approval_required=definition.approval_required,
            type="Integration",
            permissions={"required": [permission]},
            status="ENABLED",
            usage=0,
        )
    )
    agent = Agent(
        uuid=str(uuid4()),
        tenant_id="tenant-a",
        slug="jira-operations-agent",
        name="Jira Operations Agent",
        description="",
        owner_id="user-a",
        lifecycle_status="enabled",
        operational_health="healthy",
        current_version=1,
        published_version=1,
        model_configuration_ref="bedrock",
        planner_configuration={},
        environment_restrictions=[],
        configuration="{}",
        created_by="test",
        updated_by="test",
    )
    db.add(agent)
    db.flush()
    db.add(
        AgentVersion(
            agent_id=agent.id,
            tenant_id="tenant-a",
            version=1,
            instructions="Execute the resolved Jira capability.",
            model_configuration={"provider": "bedrock", "model": "mock-agent-model"},
            planner_configuration={},
            memory_configuration={},
            execution_limits={},
            tool_discovery_configuration={},
            configuration_snapshot={"capabilities": []},
            change_note="test",
            created_by="test",
            published=True,
        )
    )
    db.add(
        AgentToolAssignment(
            agent_id=agent.id,
            agent_version=1,
            tenant_id="tenant-a",
            tool_name=name,
            assignment_action="execute",
            enabled=True,
            risk_mode="write",
            approval_required=False,
            added_by="test",
        )
    )
    db.add(
        IntegrationAgentAssignment(
            connection_id=connection.id,
            agent_id=agent.id,
            tenant_id="tenant-a",
            capability_names=[name],
            created_by="test",
        )
    )
    db.commit()
    return connection, agent


@pytest.mark.asyncio
async def test_complete_jira_create_golden_semantic_to_plan_pipeline(
    db_session, monkeypatch
) -> None:
    intent_provider = _Provider(
        {
            "intent": "jira.issue.create",
            "domain": "jira",
            "operation": "create",
            "resource": "issue",
            "confidence": 0.99,
            "ambiguous": False,
            "ambiguity_reason": None,
            "entities": {},
            "semantic_hints": [],
            "source": "llm",
            "error_code": None,
        }
    )
    extraction_provider = _Provider(
        {
            "intent": "jira.issue.create",
            "parameters": {
                name: {
                    "name": name,
                    "value": value,
                    "value_type": "string",
                    "source": "user_prompt",
                    "confidence": 1,
                    "explicit": True,
                    "normalized": False,
                    "original_text": None,
                }
                for name, value in {
                    "project_key": "KAN",
                    "issue_type": "Task",
                    "summary": "Testing",
                }.items()
            },
            "unresolved_mentions": [],
            "warnings": [],
            "source": "llm",
            "error_code": None,
        }
    )
    providers = iter([intent_provider, extraction_provider])
    monkeypatch.setattr(
        "app.ai.factory.AIProviderFactory.get_provider", lambda **_: next(providers)
    )

    prompt = "Create Jira Task in project KAN with summary Testing"
    intent = (
        IntentAnalyzer()
        .analyze(
            prompt, provider_name="openai", model="mock", available_domains=["jira"]
        )
        .result
    )
    extraction = (
        ParameterExtractor()
        .extract(
            prompt,
            intent=intent,
            provider_name="openai",
            model="mock",
            schema_definitions=_definition("jira.create_issue"),
        )
        .result
    )
    state = ParameterReconciler().reconcile(intent, extraction)
    schema = RequirementSchemaProvider().get(
        intent.intent, _definition("jira.create_issue")
    )
    requirements = MissingFieldResolver().evaluate(state, schema)
    connection, agent = _inventory(db_session, "jira.create_issue", "action")
    resolution = CapabilityResolver().resolve(
        db_session,
        intent_result=intent,
        parameter_state=state,
        tenant_id="tenant-a",
        permissions={"jira.issue.create"},
    )
    routing = AgentRouter().route(
        db_session,
        capability_resolution=resolution,
        intent_result=intent,
        parameter_state=state,
        tenant_id="tenant-a",
        identity=AgentIdentity(
            actor_id="user-a",
            tenant_id="tenant-a",
            permissions=frozenset({"agents.execute"}),
            groups=frozenset(),
            roles=frozenset(),
        ),
        execution_context={"environment": "production"},
    )
    context = RuntimeContext(
        request_id=uuid4(),
        workflow_id=uuid4(),
        session_id=uuid4(),
        conversation_id=uuid4(),
        tenant_id="tenant-a",
        user_id="user-a",
        goal=prompt,
        trace_id="golden-trace",
        metadata={
            "intent_analysis": intent.model_dump(mode="json"),
            "parameter_state": state.model_dump(mode="json"),
            "capability_resolution": resolution.persisted_dict(),
            "agent_routing": routing.persisted_dict(),
        },
    )
    plan = await CapabilityAwarePlanner().plan(context)

    assert intent.intent == "jira.issue.create"
    assert {key: item.value for key, item in state.parameters.items()} == {
        "project_key": "KAN",
        "issue_type": "Task",
        "summary": "Testing",
    }
    assert requirements.complete is True
    assert resolution.selected.name == "jira.create_issue"
    assert resolution.selected.integration_connection_id == connection.id
    assert routing.selected_agent.agent_id == agent.uuid
    assert len(plan.tasks) == 1
    assert plan.tasks[0].task_type == "ACTION"
    assert plan.tasks[0].implementation_name == "jira.create_issue"
    assert plan.tasks[0].agent_id == agent.uuid
    assert plan.tasks[0].integration_connection_id == connection.id
    assert plan.tasks[0].parameters == {
        "project_key": "KAN",
        "issue_type": "Task",
        "summary": "Testing",
    }
    assert intent_provider.calls == 1
    assert extraction_provider.calls == 1


@pytest.mark.asyncio
async def test_natural_jira_search_resolves_and_plans_read_only(db_session) -> None:
    semantic = {
        "intent": "jira.issue.search",
        "domain": "jira",
        "resource": "issue",
        "operation": "search",
        "confidence": 1,
        "ambiguous": False,
        "ambiguity_reason": None,
        "entities": {},
        "semantic_hints": [],
        "source": "deterministic",
        "error_code": None,
    }
    extraction = {
        "intent": "jira.issue.search",
        "unresolved_mentions": [],
        "warnings": [],
        "source": "llm",
        "error_code": None,
        "parameters": {
            name: {
                "name": name,
                "value": value,
                "value_type": "string",
                "source": "user_prompt",
                "confidence": 1,
                "explicit": True,
            }
            for name, value in {
                "project_key": "KAN",
                "issue_type": "Bug",
                "status": "Open",
                "priority": "High",
                "assignee": "Ahmed",
            }.items()
        },
    }
    state = ParameterReconciler().reconcile(semantic, extraction)
    connection, agent = _inventory(db_session, "jira.search_issues", "tool")
    resolution = CapabilityResolver().resolve(
        db_session,
        intent_result=semantic,
        parameter_state=state,
        tenant_id="tenant-a",
        permissions={"jira.issue.read"},
    )
    routing = AgentRouter().route(
        db_session,
        capability_resolution=resolution,
        intent_result=semantic,
        parameter_state=state,
        tenant_id="tenant-a",
        identity=AgentIdentity(
            actor_id="user-a",
            tenant_id="tenant-a",
            permissions=frozenset({"agents.execute"}),
            groups=frozenset(),
            roles=frozenset(),
        ),
        execution_context={"environment": "production"},
    )
    context = RuntimeContext(
        request_id=uuid4(),
        workflow_id=uuid4(),
        session_id=uuid4(),
        conversation_id=uuid4(),
        tenant_id="tenant-a",
        user_id="user-a",
        goal="Show all open bugs in KAN assigned to Ahmed",
        trace_id="search",
        metadata={
            "intent_analysis": semantic,
            "parameter_state": state.model_dump(mode="json"),
            "capability_resolution": resolution.persisted_dict(),
            "agent_routing": routing.persisted_dict(),
        },
    )
    plan = await CapabilityAwarePlanner().plan(context)
    task = plan.tasks[0]
    assert task.implementation_name == "jira.search_issues"
    assert task.integration_connection_id == connection.id
    assert task.agent_id == agent.uuid
    assert task.side_effect_class == "READ_ONLY"
    assert task.parameters == {
        "project_key": "KAN",
        "issue_type": "Bug",
        "status": "Open",
        "priority": "High",
        "assignee": "Ahmed",
    }
    assert JiraConnector._search_jql(task.parameters) == (
        'project = "KAN" AND issuetype = "Bug" AND status = "Open" '
        'AND priority = "High" AND assignee = "Ahmed"'
    )
