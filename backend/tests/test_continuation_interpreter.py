import json

import pytest

from app.ai.models import AIResponse
from app.runtime.continuation_interpreter import ContinuationInterpreter

FIELDS = [
    {
        "name": "issue_type",
        "label": "Issue Type",
        "type": "select",
        "required": True,
        "options": ["Task", "Bug"],
        "validation": {"type": "string", "enum": ["Task", "Bug"]},
    },
    {
        "name": "summary",
        "label": "Summary",
        "type": "text",
        "required": True,
        "options": [],
        "validation": {"type": "string", "minLength": 1},
    },
]


class StubProvider:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def ask(self, messages):
        self.calls.append(messages)
        return AIResponse(text=json.dumps(self.payload), model="test-model")


def llm_result(values=None, **overrides):
    return {
        "values": values or {},
        "unresolved_fields": [],
        "invalid_fields": [],
        "user_cancelled": False,
        "intent_changed": False,
        "new_message": None,
        "warnings": [],
        "error_code": None,
        **overrides,
    }


def value(name, item, value_type="string"):
    return {
        "name": name,
        "value": item,
        "value_type": value_type,
        "confidence": 0.95,
        "explicit": True,
    }


def test_structured_submission_is_deterministic_and_scoped(monkeypatch):
    monkeypatch.setattr(
        "app.runtime.continuation_interpreter.AIProviderFactory.get_provider",
        lambda **_: pytest.fail("structured input must not call an AI provider"),
    )
    result = ContinuationInterpreter().interpret_structured(
        {"issue_type": "Task", "summary": "Testing", "project_key": "OPS"},
        FIELDS,
    )
    assert {name: item.value for name, item in result.values.items()} == {
        "issue_type": "Task",
        "summary": "Testing",
    }


def test_single_select_is_case_normalized_without_model(monkeypatch):
    monkeypatch.setattr(
        "app.runtime.continuation_interpreter.AIProviderFactory.get_provider",
        lambda **_: pytest.fail("single select must be deterministic"),
    )
    result = ContinuationInterpreter().interpret_natural_language(
        "bug",
        [FIELDS[0]],
        intent="jira.issue.create",
        provider_name="openai",
        model="test",
    )
    assert result.values["issue_type"].value == "Bug"


@pytest.mark.parametrize(
    ("field", "reply", "expected"),
    [
        ({"name": "count", "type": "integer", "required": True}, "25", 25),
        ({"name": "include_closed", "type": "boolean", "required": True}, "no", False),
        (
            {
                "name": "date_from",
                "type": "date",
                "required": True,
                "validation": {"type": "string", "format": "date"},
            },
            "2026-08-01",
            "2026-08-01",
        ),
        (
            {"name": "labels", "type": "multiselect", "required": True},
            "backend, urgent",
            ["backend", "urgent"],
        ),
        (
            {
                "name": "summary",
                "type": "text",
                "required": True,
                "validation": {"type": "string", "minLength": 1},
            },
            "Payment API timeout",
            "Payment API timeout",
        ),
    ],
)
def test_single_field_types_are_parsed_deterministically(field, reply, expected):
    result = ContinuationInterpreter().interpret_natural_language(
        reply,
        [field],
        intent="generic.operation",
        provider_name="bedrock",
        model="test",
    )
    assert result.values[field["name"]].value == expected


def test_invalid_select_remains_unresolved():
    result = ContinuationInterpreter().interpret_natural_language(
        "Incident",
        [FIELDS[0]],
        intent="jira.issue.create",
        provider_name="openai",
        model="test",
    )
    assert result.values == {}
    assert result.invalid_fields == ["issue_type"]


def test_multi_field_natural_language_uses_provider_neutral_contract(monkeypatch):
    provider = StubProvider(
        llm_result(
            values={
                "issue_type": value("issue_type", "Task"),
                "summary": value("summary", "Login failure"),
                "project_key": value("project_key", "SHOULD_BE_IGNORED"),
            }
        )
    )
    monkeypatch.setattr(
        "app.runtime.continuation_interpreter.AIProviderFactory.get_provider",
        lambda **_: provider,
    )
    result = ContinuationInterpreter().interpret_natural_language(
        "Task, summary is Login failure",
        FIELDS,
        intent="jira.issue.create",
        provider_name="bedrock",
        model="test",
        known_parameters=["project_key"],
    )
    assert {name: item.value for name, item in result.values.items()} == {
        "issue_type": "Task",
        "summary": "Login failure",
    }
    prompt = json.loads(provider.calls[0][1].content)
    assert prompt["known_parameter_names"] == ["project_key"]


@pytest.mark.parametrize(
    "reply", ["cancel", "never mind", "stop this", "don't create it"]
)
def test_explicit_cancel_is_not_parsed_as_a_value(reply):
    result = ContinuationInterpreter().interpret_natural_language(
        reply,
        FIELDS,
        intent="jira.issue.create",
        provider_name="openai",
        model="test",
    )
    assert result.user_cancelled is True
    assert result.values == {}


def test_intent_change_is_detected_conservatively():
    result = ContinuationInterpreter().interpret_natural_language(
        "Instead show open Jira bugs",
        FIELDS,
        intent="jira.issue.create",
        provider_name="openai",
        model="test",
    )
    assert result.intent_changed is True
    assert result.new_message == "Instead show open Jira bugs"


@pytest.mark.parametrize(
    "reply",
    [
        "Create a Jira ticket",
        "Show open Jira bugs",
        "Generate deployment report for release 2.4",
        "What is edge computing?",
        "Forget that and show open bugs in KAN",
    ],
)
def test_strong_natural_commands_are_new_requests_before_single_field_mapping(reply):
    result = ContinuationInterpreter().interpret_natural_language(
        reply,
        [{"name": "summary", "type": "text", "required": True}],
        intent="jira.issue.create",
        provider_name="openai",
        model="test",
    )
    assert result.intent_changed is True
    assert result.new_message == reply
    assert result.values == {}


def test_create_prefixed_free_text_remains_a_summary_answer():
    result = ContinuationInterpreter().interpret_natural_language(
        "Create endpoint returns HTTP 500",
        [{"name": "summary", "type": "text", "required": True}],
        intent="jira.issue.create",
        provider_name="openai",
        model="test",
    )
    assert result.intent_changed is False
    assert result.values["summary"].value == "Create endpoint returns HTTP 500"


def test_malformed_provider_output_is_nonterminal_fallback(monkeypatch):
    monkeypatch.setattr(
        "app.runtime.continuation_interpreter.AIProviderFactory.get_provider",
        lambda **_: StubProvider("not-json"),
    )
    result = ContinuationInterpreter().interpret_natural_language(
        "some response",
        FIELDS,
        intent="jira.issue.create",
        provider_name="openai",
        model="test",
    )
    assert result.error_code == "CONTINUATION_INTERPRETATION_FAILED"
    assert result.unresolved_fields == ["issue_type", "summary"]
