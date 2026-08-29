from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.agents.execution_service import AgentExecutionService
from app.ai.governed_provider import authorized_provider_invocation
from app.ai.models import AIResponse, AIUsage
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


def test_json_schema_union_type_is_normalized_for_parameter_reconciliation():
    assert RuntimeExecutionService._expected_parameter_type(
        ["string", "null"]
    ) == "string"
    assert RuntimeExecutionService._expected_parameter_type(["null"]) is None
    assert RuntimeExecutionService._expected_parameter_type("array") == "array"


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


@pytest.mark.parametrize(
    ("intent", "expected"),
    [
        ({"intent": None, "error_code": "INTENT_ANALYSIS_FAILED"}, True),
        ({"intent": "general.assistance", "error_code": None}, True),
        ({"intent": "unknown.request", "error_code": None}, False),
        ({"intent": "jira.project.search", "error_code": None}, False),
        ({"intent": "jira.issue.search", "error_code": None}, False),
        ({"intent": "jira.issue.read", "error_code": None}, False),
        ({"intent": "jira.issue.create", "error_code": None}, False),
    ],
)
def test_non_action_intents_use_direct_copilot_response(intent, expected):
    assert RuntimeExecutionService._requires_direct_response(intent) is expected


def test_jira_project_results_are_rendered_for_chat():
    message = AgentExecutionService._tool_result_message(
        "jira.get_projects",
        {"values": [{"key": "KAN", "name": "Kanban Delivery"}]},
    )
    assert "1 Jira project" in message
    assert "**KAN** — Kanban Delivery" in message


def test_jira_planned_releases_are_rendered_instead_of_issues():
    message = AgentExecutionService._tool_result_message(
        "jira.get_versions",
        {
            "releases": [
                {
                    "name": "SOAI 1.0",
                    "project_key": "SOAI",
                    "release_date": "2026-09-30",
                    "overdue": False,
                    "browse_url": "https://jira.example/releases/10",
                }
            ]
        },
    )

    assert "1 planned Jira release" in message
    assert "[SOAI 1.0](https://jira.example/releases/10)" in message
    assert "SOAI · 2026-09-30" in message


def test_jira_issue_results_render_requested_assignee_table():
    message = AgentExecutionService._tool_result_message(
        "jira.search_issues",
        {
            "issues": [
                {
                    "key": "SOAI-4",
                    "fields": {
                        "summary": "Complete security controls",
                        "issuetype": {"name": "Story"},
                        "status": {"name": "In Progress"},
                        "assignee": {"displayName": "Ahmed Sabry"},
                    },
                },
                {
                    "key": "SOAI-3",
                    "fields": {
                        "summary": "Validate operational workflow",
                        "issuetype": {"name": "Story"},
                        "status": {"name": "In Progress"},
                        "assignee": None,
                    },
                },
            ]
        },
        {
            "format": "auto",
            "fields": ["key", "summary", "assignee"],
            "include_count": True,
        },
    )

    assert "I found 2 Jira issue(s)" in message
    assert "| Key | Summary | Assignee |" in message
    assert "| SOAI-4 | Complete security controls | Ahmed Sabry |" in message
    assert "| SOAI-3 | Validate operational workflow | Unassigned |" in message


def test_jira_issue_description_renders_atlassian_document_format():
    message = AgentExecutionService._tool_result_message(
        "jira.get_issue",
        {
            "key": "AIGOV-6",
            "fields": {
                "summary": "Evaluate runtime policy before execution",
                "description": {
                    "type": "doc",
                    "version": 1,
                    "content": [
                        {
                            "type": "paragraph",
                            "content": [
                                {
                                    "type": "text",
                                    "text": "Outcome: runtime policy is evaluated.",
                                }
                            ],
                        }
                    ],
                },
            },
        },
        {
            "format": "auto",
            "fields": ["key", "summary", "description"],
            "include_count": False,
        },
    )

    assert "**AIGOV-6** — Evaluate runtime policy before execution" in message
    assert "**Description**" in message
    assert "Outcome: runtime policy is evaluated." in message


def test_jira_comments_render_author_timestamp_and_adf_text():
    message = AgentExecutionService._tool_result_message(
        "jira.get_comments",
        {
            "issue_key": "AIDP-1",
            "browse_url": "https://jira.example/browse/AIDP-1",
            "comments": [
                {
                    "author": {"displayName": "Ahmed Sabry"},
                    "created": "2026-08-28T12:00:00.000+0000",
                    "body": {
                        "type": "doc",
                        "version": 1,
                        "content": [
                            {
                                "type": "paragraph",
                                "content": [{"type": "text", "text": "Ready to review."}],
                            }
                        ],
                    },
                }
            ],
        },
    )

    assert "1 comment(s) on **AIDP-1**" in message
    assert "**Ahmed Sabry**" in message
    assert "Ready to review." in message
    assert "[Open AIDP-1 in Jira]" in message
    assert "- Status:" not in message


def test_jira_issue_link_renders_clickable_browse_url():
    message = AgentExecutionService._tool_result_message(
        "jira.get_issue",
        {
            "key": "AIGOV-6",
            "fields": {"summary": "Evaluate runtime policy before execution"},
            "browse_url": "https://jira.example/browse/AIGOV-6",
        },
        {
            "format": "auto",
            "fields": ["key", "link"],
            "include_count": False,
        },
    )

    assert message == (
        "**AIGOV-6**\n\n"
        "[Open AIGOV-6 in Jira](https://jira.example/browse/AIGOV-6)"
    )


@pytest.mark.asyncio
async def test_direct_response_completes_with_provider_answer(monkeypatch):
    service = RuntimeExecutionService()
    events = []
    completed = []

    async def publish_step(*args, **kwargs):
        events.append(("step", args, kwargs))

    async def publish_event(*args, **kwargs):
        events.append(("event", args, kwargs))

    monkeypatch.setattr(service, "publish_step", publish_step)
    monkeypatch.setattr(service, "publish_event", publish_event)
    monkeypatch.setattr(
        service,
        "_generate_response",
        lambda *_args: AIResponse(
            text="Copilot answer",
            model="amazon.nova-lite-v1:0",
            latency_seconds=0.01,
            usage=AIUsage(prompt_tokens=10, completion_tokens=4, total_tokens=14),
        ),
    )
    monkeypatch.setattr(
        service,
        "_complete_execution",
        lambda *args, **kwargs: completed.append((args, kwargs)),
    )
    execution = SimpleNamespace(
        conversation_id="conversation-1",
        user_id="user-1",
        tenant_id="tenant-1",
        runtime_metadata={},
    )

    await service._execute_direct_response(
        "execution-1",
        execution,
        "Hello",
        "bedrock",
        "amazon.nova-lite-v1:0",
        datetime.now(UTC),
    )

    assert any(event[0] == "event" for event in events)
    assert completed[0][1]["status"] == "COMPLETED"
    assert completed[0][1]["message"] == "Copilot answer"


def test_generate_response_does_not_reserve_twice_inside_authorized_runtime(
    monkeypatch,
):
    captured = {}

    class Database:
        def close(self):
            return None

    monkeypatch.setattr(
        "app.services.runtime_execution_service.SessionLocal", Database
    )
    monkeypatch.setattr(
        "app.services.runtime_execution_service.settings.BUDGET_ENFORCEMENT_ENABLED",
        True,
    )

    def ask(**kwargs):
        captured.update(kwargs)
        return AIResponse(text="ok", model="approved-model")

    monkeypatch.setattr(
        "app.services.runtime_execution_service.chat_service.ask", ask
    )
    with authorized_provider_invocation():
        RuntimeExecutionService._generate_response(
            "conversation-1",
            "user-1",
            "hello",
            "bedrock",
            "approved-model",
            "tenant-1",
            "execution-1",
            {},
        )

    assert captured["budget_context"] is None


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
        ({}, ["project_key"]),
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


@pytest.mark.asyncio
async def test_jira_create_pauses_for_approval_before_external_write(monkeypatch):
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

    calls = []

    async def execute_tool(*args, **kwargs):
        calls.append(args[5])
        if args[5] == "jira.get_create_metadata":
            return {
                "selected_issue_type": {"id": "10008", "name": "Task"},
                "fields": [],
            }
        raise AssertionError("Jira create must not run before approval")

    approvals = []

    async def pause_for_approval(execution_id, inputs, **details):
        approvals.append((inputs, details))

    monkeypatch.setattr(service, "publish_step", no_step)
    monkeypatch.setattr(service, "_execute_runtime_tool", execute_tool)
    monkeypatch.setattr(service, "_pause_for_approval", pause_for_approval)
    monkeypatch.setattr(service, "_runtime_metadata", lambda execution_id: {})

    await service._execute_jira_create_flow(
        "runtime-1",
        SimpleNamespace(),
        SimpleNamespace(),
        {"tools.admin"},
        "default",
        {"project_key": "KAN", "issue_type": "Task", "summary": "Testing"},
        __import__("datetime").datetime.now(__import__("datetime").UTC),
    )

    assert calls == ["jira.get_create_metadata"]
    assert approvals[0][0]["project_key"] == "KAN"
    assert approvals[0][1]["action"] == "jira.create_issue"


def test_jira_create_rejects_cross_conversation_project_and_summary(monkeypatch):
    service = RuntimeExecutionService()
    monkeypatch.setattr(service, "_runtime_metadata", lambda execution_id: {})
    monkeypatch.setattr(service, "_merge_runtime_metadata", lambda *args: None)
    state = {
        "intent": "jira.issue.create",
        "parameters": {
            "project_key": {
                "name": "project_key",
                "value": "KAN",
                "source": "conversation_context",
                "original_text": "KAN",
            },
            "issue_type": {
                "name": "issue_type",
                "value": "Task",
                "source": "user_prompt",
                "original_text": "ticket",
            },
            "summary": {
                "name": "summary",
                "value": "Agent routing verification",
                "source": "user_prompt",
                "original_text": "Agent routing verification",
            },
        },
        "warnings": [],
    }

    sanitized = service._enforce_explicit_jira_create_inputs(
        "runtime-1", "Create Jira ticket", state
    )

    assert set(sanitized["parameters"]) == {"issue_type"}
    assert "project_key" in sanitized["warnings"][-1]
    assert "summary" in sanitized["warnings"][-1]
