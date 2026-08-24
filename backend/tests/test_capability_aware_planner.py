from __future__ import annotations

from copy import deepcopy
from uuid import uuid4

import pytest

from app.planners.capability_aware_planner import (
    CapabilityAwarePlanner,
    ExecutionPlanValidator,
    PlanInputBindingError,
    PlanPreconditionError,
    PlanValidationError,
)
from app.runtime.context import RuntimeContext


def _context(
    *, capability_type: str = "action", implementation: str = "jira.create_issue"
) -> RuntimeContext:
    semantic = (
        "jira.issue.create" if "create" in implementation else "jira.issue.search"
    )
    selected = {
        "capability_id": "cap-jira",
        "semantic_capability": semantic,
        "name": implementation,
        "display_name": implementation,
        "capability_type": capability_type,
        "integration_connection_id": "conn-jira",
        "input_schema": {
            "type": "object",
            "properties": {
                "project": {"type": "string"},
                "summary": {"type": "string"},
                "assignee": {"type": ["string", "null"]},
            },
            "required": ["project", "summary"],
            "additionalProperties": False,
        },
        "output_schema": {"type": "object"},
        "parameter_bindings": {
            "project_key": "project",
            "summary": "summary",
            "assignee": "assignee",
        },
        "risk_level": "write" if capability_type == "action" else "read",
        "approval_required": False,
        "version": "1",
    }
    return RuntimeContext(
        request_id=uuid4(),
        workflow_id=uuid4(),
        session_id=uuid4(),
        conversation_id=uuid4(),
        tenant_id="tenant-a",
        user_id="user-a",
        goal="Create Jira issue",
        trace_id="trace-a",
        metadata={
            "intent_analysis": {
                "status": "RESOLVED",
                "intent": semantic,
                "domain": "jira",
            },
            "parameter_state": {
                "version": 4,
                "parameters": {
                    "project_key": {"status": "RESOLVED", "value": "KAN"},
                    "summary": {"status": "RESOLVED", "value": "Test issue"},
                    "assignee": {"status": "RESOLVED", "value": None},
                    "unused": {"status": "UNRESOLVED", "value": "ignored"},
                },
            },
            "capability_resolution": {"status": "RESOLVED", "selected": selected},
            "agent_routing": {
                "status": "RESOLVED",
                "selection_mode": "automatic",
                "selected_agent": {
                    "agent_id": "agent-jira",
                    "agent_name": "Jira Agent",
                    "agent_slug": "jira-agent",
                    "published_version": 7,
                    "model_provider": "bedrock",
                    "model": "model-a",
                },
            },
        },
    )


@pytest.mark.asyncio
async def test_builds_one_exact_jira_action_with_alias_and_explicit_null() -> None:
    context = _context()
    plan = await CapabilityAwarePlanner().plan(context)

    assert len(plan.tasks) == 1
    task = plan.tasks[0]
    assert task.task_type == "ACTION"
    assert task.capability_id == "cap-jira"
    assert task.implementation_name == "jira.create_issue"
    assert task.agent_id == "agent-jira"
    assert task.agent_version == 7
    assert task.integration_connection_id == "conn-jira"
    assert task.parameters == {
        "project": "KAN",
        "summary": "Test issue",
        "assignee": None,
    }
    assert task.side_effect_class == "NON_IDEMPOTENT_WRITE"
    assert task.retry_policy["automatic"] is False
    assert "general-execution" not in repr(plan)


@pytest.mark.asyncio
async def test_read_tool_is_read_only_and_retryable() -> None:
    context = _context(capability_type="tool", implementation="jira.search_issues")
    plan = await CapabilityAwarePlanner().plan(context)
    assert plan.tasks[0].task_type == "TOOL"
    assert plan.tasks[0].implementation_name == "jira.search_issues"
    assert plan.tasks[0].side_effect_class == "READ_ONLY"
    assert plan.tasks[0].retry_policy == {"max_attempts": 2, "automatic": True}


@pytest.mark.asyncio
async def test_workflow_identity_is_preserved() -> None:
    context = _context(capability_type="workflow", implementation="deployment_report")
    selected = context.metadata["capability_resolution"]["selected"]
    selected["semantic_capability"] = "deployment.report.generate"
    plan = await CapabilityAwarePlanner().plan(context)
    assert plan.tasks[0].task_type == "WORKFLOW"
    assert plan.tasks[0].implementation_name == "deployment_report"


@pytest.mark.asyncio
async def test_required_binding_failure_fails_closed() -> None:
    context = _context()
    context.metadata["parameter_state"]["parameters"]["summary"]["status"] = (
        "UNRESOLVED"
    )
    with pytest.raises(PlanInputBindingError):
        await CapabilityAwarePlanner().plan(context)


@pytest.mark.asyncio
async def test_schema_validation_failure_fails_closed() -> None:
    context = _context()
    context.metadata["parameter_state"]["parameters"]["summary"]["value"] = 42
    with pytest.raises(PlanInputBindingError):
        await CapabilityAwarePlanner().plan(context)


@pytest.mark.asyncio
async def test_missing_authoritative_input_prevents_planning() -> None:
    context = _context()
    del context.metadata["agent_routing"]
    with pytest.raises(PlanPreconditionError):
        await CapabilityAwarePlanner().plan(context)


@pytest.mark.asyncio
async def test_plan_is_deterministic_except_for_generated_ids() -> None:
    context = _context()
    first = await CapabilityAwarePlanner().plan(context)
    second = await CapabilityAwarePlanner().plan(context)
    assert first.input_fingerprint == second.input_fingerprint
    assert first.tasks[0].parameters == second.tasks[0].parameters
    assert first.tasks[0].implementation_name == second.tasks[0].implementation_name


@pytest.mark.asyncio
async def test_validator_rejects_capability_agent_and_connection_drift() -> None:
    context = _context()
    planner = CapabilityAwarePlanner()
    plan = await planner.plan(context)
    resolution = context.metadata["capability_resolution"]
    routing = context.metadata["agent_routing"]
    for field, value in (
        ("capability_id", "wrong-capability"),
        ("agent_id", "wrong-agent"),
        ("integration_connection_id", "wrong-connection"),
    ):
        candidate = deepcopy(plan)
        setattr(candidate.tasks[0], field, value)
        with pytest.raises(PlanValidationError):
            ExecutionPlanValidator().validate(
                candidate, capability_resolution=resolution, agent_routing=routing
            )


@pytest.mark.asyncio
async def test_validator_rejects_dependency_cycle() -> None:
    context = _context()
    plan = await CapabilityAwarePlanner().plan(context)
    plan.tasks[0].depends_on = [plan.tasks[0].id]
    with pytest.raises(PlanValidationError):
        ExecutionPlanValidator().validate(
            plan,
            capability_resolution=context.metadata["capability_resolution"],
            agent_routing=context.metadata["agent_routing"],
        )
