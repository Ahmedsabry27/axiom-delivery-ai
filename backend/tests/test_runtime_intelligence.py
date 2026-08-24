from types import SimpleNamespace

import pytest

from app.ai.models import AIResponse
from app.integrations.jira import CAPABILITIES
from app.runtime.intelligence import CapabilityIntelligence, reconcile_parameters
from app.services.runtime_execution_service import RuntimeExecutionService


def definitions(*items):
    return [
        {
            "type": "function",
            "function": {
                "name": item.name,
                "description": item.description,
                "parameters": getattr(item, "input_schema", None) or item.parameters,
            },
        }
        for item in items
    ]


def fallback(prompt, items=CAPABILITIES):
    catalog = CapabilityIntelligence._catalog(definitions(*items))
    return CapabilityIntelligence.fallback(prompt, catalog)


def test_jira_create_extracts_all_parameters():
    result = fallback(
        "CREATE JIRA TICKET IN PROJECT KAN TYPE TASK WITH THE SUMMARY TESTING"
    )
    assert result.selected_tool == "jira.create_issue"
    assert result.entities == {
        "project_key": "KAN",
        "issue_type": "Task",
        "summary": "TESTING",
    }


def test_jira_create_does_not_request_known_fields():
    result = fallback("Create Task in KAN called Payment failure")
    create = next(
        item
        for item in definitions(*CAPABILITIES)
        if item["function"]["name"] == "jira.create_issue"
    )
    resolved, trace = reconcile_parameters(
        create["function"]["parameters"],
        prompt_values=result.entities,
        collected_values={},
    )
    assert RuntimeExecutionService._required_fields("", resolved, [create]) == []
    assert set(trace) == {"project_key", "issue_type", "summary"}


def test_jira_create_requests_only_missing_fields():
    result = fallback("Create Jira ticket in KAN")
    create = next(
        item
        for item in definitions(*CAPABILITIES)
        if item["function"]["name"] == "jira.create_issue"
    )
    missing = RuntimeExecutionService._required_fields("", result.entities, [create])
    assert [field["name"] for field in missing] == ["issue_type", "summary"]


def test_lowercase_enterprise_identifier_is_normalized_by_schema():
    create = next(
        item
        for item in definitions(*CAPABILITIES)
        if item["function"]["name"] == "jira.create_issue"
    )
    resolved, trace = reconcile_parameters(
        create["function"]["parameters"],
        prompt_values={"project_key": "kan"},
        collected_values={},
    )
    assert resolved["project_key"] == "KAN"
    assert trace["project_key"]["value"] == "KAN"


def test_parameter_reconciliation_preserves_explicit_values():
    schema = next(
        item.input_schema for item in CAPABILITIES if item.name == "jira.create_issue"
    )
    resolved, trace = reconcile_parameters(
        schema,
        prompt_values={"project_key": "KAN"},
        collected_values={
            "project_key": "OLD",
            "issue_type": "Task",
            "summary": "Testing",
        },
        context_values={"project_key": "DEFAULT"},
    )
    assert resolved["project_key"] == "KAN"
    assert trace["project_key"]["source"] == "user_prompt"


def test_pending_input_accepts_natural_language_and_preserves_values():
    schema = next(
        item.input_schema for item in CAPABILITIES if item.name == "jira.create_issue"
    )
    extracted = CapabilityIntelligence._extract_schema_values(
        "KAN, Task, summary is Authentication failure", schema
    )
    resolved, _ = reconcile_parameters(
        schema,
        prompt_values={},
        collected_values=extracted,
        context_values={"description": "Keep the prior description"},
    )
    assert resolved["project_key"] == "KAN"
    assert resolved["issue_type"] == "Task"
    assert resolved["summary"] == "Authentication failure"
    assert resolved["description"] == "Keep the prior description"


def test_jira_report_not_routed_to_deployment_report():
    from app.tool_sdk.builtin_tools import DeploymentReportTool

    result = fallback(
        "Generate Jira report", [*CAPABILITIES, DeploymentReportTool().metadata]
    )
    assert result.domain == "jira"
    assert result.selected_tool != "deployment_report"
    assert result.ambiguous is True


def test_deployment_report_still_routes_correctly():
    from app.tool_sdk.builtin_tools import DeploymentReportTool

    result = fallback("Generate deployment report", [DeploymentReportTool().metadata])
    assert result.selected_tool == "deployment_report"
    assert result.domain == "deployment_report"


def test_planner_never_selects_unknown_capability():
    result = fallback("Use imaginary.super_tool to do something")
    assert result.selected_tool is None


def test_capability_resolution_cannot_override_structured_intent(monkeypatch):
    class Provider:
        def ask(self, messages):
            assert "Do not reclassify" in messages[1].content
            return AIResponse(
                text='{"intent":"wrong.value","domain":"deployment","operation":"delete","resource":"everything","entities":{},"confidence":0.9,"required_capabilities":["jira.create_issue"],"selected_tool":"jira.create_issue","ambiguous":false}'
            )

    monkeypatch.setattr(
        "app.runtime.intelligence.AIProviderFactory.get_provider",
        lambda **_: Provider(),
    )
    semantic = {
        "intent": "jira.issue.create",
        "domain": "jira",
        "operation": "create",
        "resource": "issue",
        "ambiguous": False,
    }
    result = CapabilityIntelligence().analyze(
        "Create a ticket",
        definitions(*CAPABILITIES),
        provider_name="openai",
        model="test",
        semantic_intent=semantic,
    )
    assert result.intent == "jira.issue.create"
    assert (result.domain, result.operation, result.resource) == (
        "jira",
        "create",
        "issue",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("inputs", "expected"),
    [
        ({}, ["project_key", "issue_type", "summary"]),
        ({"project_key": "KAN"}, ["issue_type", "summary"]),
        ({"project_key": "KAN", "issue_type": "Task"}, ["summary"]),
    ],
)
async def test_jira_flow_requests_all_and_only_missing_base_schema_fields(
    monkeypatch, inputs, expected
):
    service = RuntimeExecutionService()
    create = next(item for item in CAPABILITIES if item.name == "jira.create_issue")
    monkeypatch.setattr(
        "app.services.runtime_execution_service.tool_registry.get",
        lambda name: SimpleNamespace(
            metadata=SimpleNamespace(
                name=create.name,
                description=create.description,
                parameters=create.input_schema,
            )
        ),
    )

    async def no_step(*args, **kwargs):
        return None

    async def metadata(*args, **kwargs):
        return {
            "issue_types": [
                {"id": "10008", "name": "Task"},
                {"id": "10011", "name": "Bug"},
            ],
            "selected_issue_type": {"id": "10008", "name": "Task"},
            "fields": [],
        }

    captured = []

    async def pause(execution_id, fields, known):
        captured.extend(fields)

    monkeypatch.setattr(service, "publish_step", no_step)
    monkeypatch.setattr(service, "_execute_runtime_tool", metadata)
    monkeypatch.setattr(service, "_pause_for_input", pause)
    await service._execute_jira_create_flow(
        "runtime-1",
        SimpleNamespace(),
        SimpleNamespace(),
        {"tools.admin"},
        "default",
        inputs,
        __import__("datetime").datetime.now(__import__("datetime").UTC),
    )
    assert [field["name"] for field in captured] == expected
    if inputs.get("project_key") and "issue_type" in expected:
        issue_type = next(field for field in captured if field["name"] == "issue_type")
        assert issue_type["type"] == "select"
        assert [option["value"] for option in issue_type["options"]] == ["Task", "Bug"]


@pytest.mark.asyncio
async def test_dynamic_jira_required_field_creates_second_input_stage(monkeypatch):
    service = RuntimeExecutionService()
    create = next(item for item in CAPABILITIES if item.name == "jira.create_issue")
    monkeypatch.setattr(
        "app.services.runtime_execution_service.tool_registry.get",
        lambda name: SimpleNamespace(
            metadata=SimpleNamespace(
                name=create.name,
                description=create.description,
                parameters=create.input_schema,
            )
        ),
    )

    async def no_step(*args, **kwargs):
        return None

    async def metadata(*args, **kwargs):
        return {
            "issue_types": [{"id": "10008", "name": "Task"}],
            "selected_issue_type": {"id": "10008", "name": "Task"},
            "fields": [
                {
                    "fieldId": "customfield_123",
                    "name": "Business Service",
                    "required": True,
                    "hasDefaultValue": False,
                }
            ],
        }

    captured = []

    async def pause(execution_id, fields, known):
        captured.extend(fields)

    monkeypatch.setattr(service, "publish_step", no_step)
    monkeypatch.setattr(service, "_execute_runtime_tool", metadata)
    monkeypatch.setattr(service, "_pause_for_input", pause)
    await service._execute_jira_create_flow(
        "runtime-1",
        SimpleNamespace(),
        SimpleNamespace(),
        {"tools.admin"},
        "default",
        {"project_key": "KAN", "issue_type": "Task", "summary": "Testing"},
        __import__("datetime").datetime.now(__import__("datetime").UTC),
    )
    assert [(field["name"], field["label"]) for field in captured] == [
        ("customfield_123", "Business Service")
    ]
