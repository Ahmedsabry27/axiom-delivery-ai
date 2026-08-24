import pytest

from app.runtime.intent_analyzer import IntentResult
from app.runtime.parameter_reconciler import (
    CanonicalParameter,
    ParameterCandidate,
    ParameterReconciler,
    ParameterState,
)
from app.services.runtime_execution_service import RuntimeExecutionService


def intent(
    name="jira.issue.create",
    domain="jira",
    operation="create",
    resource="issue",
):
    return IntentResult(
        intent=name,
        domain=domain,
        operation=operation,
        resource=resource,
        confidence=0.95,
        ambiguous=False,
    )


def extracted(name, value, *, source="user_prompt", confidence=0.99, explicit=True):
    if value is None:
        value_type = "null"
    elif isinstance(value, bool):
        value_type = "boolean"
    elif isinstance(value, int):
        value_type = "integer"
    elif isinstance(value, float):
        value_type = "number"
    elif isinstance(value, list):
        value_type = "array"
    else:
        value_type = "string"
    return {
        "name": name,
        "value": value,
        "value_type": value_type,
        "source": source,
        "confidence": confidence,
        "explicit": explicit,
        "normalized": False,
        "original_text": None,
    }


def extraction(parameters=None, intent_name="jira.issue.create", **overrides):
    return {
        "intent": intent_name,
        "parameters": parameters or {},
        "unresolved_mentions": [],
        "warnings": [],
        "source": "llm",
        "error_code": None,
        **overrides,
    }


def candidate(
    name,
    value,
    *,
    source="conversation_context",
    confidence=0.9,
    explicit=True,
    domain="jira",
    collection_mode="replace",
    ordinal=None,
    value_type=None,
):
    return ParameterCandidate(
        name=name,
        value=value,
        value_type=value_type or extracted(name, value)["value_type"],
        source=source,
        confidence=confidence,
        explicit=explicit,
        domain=domain,
        collection_mode=collection_mode,
        ordinal=ordinal,
    )


def values(state):
    return {name: parameter.value for name, parameter in state.parameters.items()}


def test_current_prompt_overrides_context_and_preserves_alternative():
    state = ParameterReconciler().reconcile(
        intent(),
        extraction(
            {
                "project_key": extracted("project_key", "OPS"),
                "issue_type": extracted("issue_type", "Task"),
                "summary": extracted("summary", "Cleanup"),
            }
        ),
        additional_candidates=[candidate("project_key", "KAN")],
    )
    assert values(state) == {
        "issue_type": "Task",
        "project_key": "OPS",
        "summary": "Cleanup",
    }
    project = state.parameters["project_key"]
    assert project.source == "user_prompt"
    assert project.explicit is True
    assert [item.value for item in project.alternatives] == ["KAN"]


def test_relevant_context_fills_omitted_project():
    state = ParameterReconciler().reconcile(
        intent(),
        extraction(
            {
                "issue_type": extracted("issue_type", "Task"),
                "summary": extracted("summary", "Cleanup"),
            }
        ),
        additional_candidates=[candidate("project_key", "KAN")],
    )
    assert state.parameters["project_key"].value == "KAN"
    assert state.parameters["project_key"].source == "conversation_context"


def test_explicit_current_value_beats_inference_and_default():
    state = ParameterReconciler().reconcile(
        intent(),
        extraction({"priority": extracted("priority", "Low")}),
        additional_candidates=[
            candidate(
                "priority",
                "High",
                source="model_inference",
                confidence=0.99,
                explicit=False,
            )
        ],
        configured_defaults=[
            candidate(
                "priority",
                "Medium",
                source="workspace_default",
                confidence=1,
                explicit=False,
            )
        ],
    )
    assert state.parameters["priority"].value == "Low"


def test_safe_semantic_enum_case_is_normalized_but_human_text_is_preserved():
    state = ParameterReconciler().reconcile(
        intent(),
        extraction(
            {
                "priority": extracted("priority", "HIGH"),
                "summary": extracted("summary", "Payment API timeout"),
            }
        ),
    )
    assert state.parameters["priority"].value == "High"
    assert state.parameters["summary"].value == "Payment API timeout"


def test_unscoped_default_is_not_applied_across_domains():
    deployment = intent(
        "deployment.report.generate", "deployment", "generate", "report"
    )
    state = ParameterReconciler().reconcile(
        deployment,
        extraction(intent_name="deployment.report.generate"),
        configured_defaults=[
            {
                "name": "project_key",
                "value": "KAN",
                "value_type": "string",
                "source": "workspace_default",
                "confidence": 1,
                "explicit": False,
                "domain": None,
            }
        ],
    )
    assert state.parameters == {}


def test_explicit_null_clears_context_and_default():
    state = ParameterReconciler().reconcile(
        intent(),
        extraction({"assignee": extracted("assignee", None)}),
        additional_candidates=[candidate("assignee", "Ahmed")],
        configured_defaults=[
            candidate(
                "assignee", "Default User", source="integration_default", explicit=False
            )
        ],
        expected_types={"assignee": "string"},
    )
    assignee = state.parameters["assignee"]
    assert assignee.value is None
    assert assignee.value_type == "null"
    assert assignee.explicit is True


def test_equal_strength_conflict_is_ambiguous_not_arbitrarily_resolved():
    state = ParameterReconciler().reconcile(
        intent(),
        extraction(),
        additional_candidates=[
            candidate("project_key", "KAN", source="user_prompt", confidence=1),
            candidate("project_key", "OPS", source="user_prompt", confidence=1),
        ],
    )
    project = state.parameters["project_key"]
    assert project.status == "AMBIGUOUS"
    assert project.conflict is True
    assert {project.value, *(item.value for item in project.alternatives)} == {
        "KAN",
        "OPS",
    }
    assert len(state.conflicts) == 1


def test_same_turn_correction_uses_later_ordinal():
    state = ParameterReconciler().reconcile(
        intent(),
        extraction(),
        additional_candidates=[
            candidate(
                "project_key", "KAN", source="user_prompt", confidence=1, ordinal=1
            ),
            candidate(
                "project_key", "OPS", source="user_prompt", confidence=1, ordinal=2
            ),
        ],
    )
    assert state.parameters["project_key"].value == "OPS"
    assert state.parameters["project_key"].status == "RESOLVED"


def test_inferred_value_is_resolved_when_no_stronger_candidate_exists():
    state = ParameterReconciler().reconcile(
        intent(),
        extraction(
            {
                "issue_type": extracted("issue_type", "Bug"),
                "summary": extracted(
                    "summary",
                    "Login returns 500",
                    source="model_inference",
                    confidence=0.82,
                    explicit=False,
                ),
            }
        ),
    )
    assert state.parameters["summary"].status == "RESOLVED"
    assert state.parameters["summary"].explicit is False


def test_weak_inference_is_omitted_with_warning():
    state = ParameterReconciler().reconcile(
        intent(),
        extraction(
            {
                "priority": extracted(
                    "priority",
                    "High",
                    source="model_inference",
                    confidence=0.35,
                    explicit=False,
                )
            }
        ),
    )
    assert "priority" not in state.parameters
    assert any("Weak inferred" in warning for warning in state.warnings)


def test_cross_domain_context_is_excluded():
    deployment = intent(
        "deployment.report.generate", "deployment", "generate", "report"
    )
    state = ParameterReconciler().reconcile(
        deployment,
        extraction(
            {"release_version": extracted("release_version", "2.4")},
            intent_name="deployment.report.generate",
        ),
        additional_candidates=[candidate("project_key", "KAN", domain="jira")],
    )
    assert values(state) == {"release_version": "2.4"}


def test_domain_relevant_context_is_reused():
    search = intent("jira.issue.search", "jira", "search", "issue")
    state = ParameterReconciler().reconcile(
        search,
        extraction(
            {"status": extracted("status", "Open")},
            intent_name="jira.issue.search",
        ),
        additional_candidates=[candidate("project_key", "KAN", domain="jira")],
    )
    assert values(state) == {"project_key": "KAN", "status": "Open"}


def existing_labels(labels):
    return ParameterState(
        intent="jira.issue.create",
        parameters={
            "labels": CanonicalParameter(
                name="labels",
                value=labels,
                value_type="array",
                source="user_prompt",
                confidence=1,
                explicit=True,
                status="RESOLVED",
            )
        },
    )


def test_array_add_merges_only_with_explicit_add_semantics():
    state = ParameterReconciler().reconcile(
        intent(),
        extraction(),
        existing_state=existing_labels(["backend"]),
        additional_candidates=[
            candidate(
                "labels",
                ["urgent"],
                source="user_prompt",
                confidence=1,
                collection_mode="add",
                value_type="array",
            )
        ],
    )
    assert state.parameters["labels"].value == ["backend", "urgent"]


def test_array_replace_does_not_union():
    state = ParameterReconciler().reconcile(
        intent(),
        extraction(),
        existing_state=existing_labels(["backend", "urgent"]),
        additional_candidates=[
            candidate(
                "labels",
                ["frontend"],
                source="user_prompt",
                confidence=1,
                collection_mode="replace",
                value_type="array",
            )
        ],
    )
    assert state.parameters["labels"].value == ["frontend"]


def test_schema_type_hint_normalizes_integer_string():
    state = ParameterReconciler().reconcile(
        intent(),
        extraction(),
        configured_defaults=[
            candidate(
                "max_results",
                "25",
                source="integration_default",
                explicit=False,
                value_type="string",
            )
        ],
        expected_types={"max_results": "integer"},
    )
    assert state.parameters["max_results"].value == 25
    assert state.parameters["max_results"].value_type == "integer"


def test_incompatible_type_is_ignored_without_crashing():
    state = ParameterReconciler().reconcile(
        intent(),
        extraction({"max_results": extracted("max_results", 25)}),
        additional_candidates=[
            candidate(
                "max_results",
                ["twenty-five"],
                source="user_prompt",
                confidence=0.8,
                value_type="array",
            )
        ],
        expected_types={"max_results": "integer"},
    )
    assert state.parameters["max_results"].value == 25
    assert any("Incompatible" in warning for warning in state.warnings)


def test_malformed_extracted_candidate_preserves_valid_candidates():
    state = ParameterReconciler().reconcile(
        intent(),
        extraction(
            {
                "project_key": extracted("project_key", "KAN"),
                "bad": {"name": "bad", "value": [], "value_type": "string"},
            }
        ),
    )
    assert values(state) == {"project_key": "KAN"}
    assert any("Invalid extracted" in warning for warning in state.warnings)


@pytest.mark.parametrize(
    ("parameters", "expected"),
    [
        ({}, {}),
        ({"project_key": extracted("project_key", "KAN")}, {"project_key": "KAN"}),
        (
            {
                "project_key": extracted("project_key", "KAN"),
                "issue_type": extracted("issue_type", "Task"),
                "summary": extracted("summary", "Testing"),
            },
            {"project_key": "KAN", "issue_type": "Task", "summary": "Testing"},
        ),
    ],
)
def test_empty_partial_and_complete_states_have_no_missing_field_logic(
    parameters, expected
):
    state = ParameterReconciler().reconcile(intent(), extraction(parameters))
    assert values(state) == expected
    assert not hasattr(state, "missing_fields")
    assert all(item.status == "RESOLVED" for item in state.parameters.values())


@pytest.mark.asyncio
async def test_runtime_persists_emits_and_reuses_parameter_state(monkeypatch):
    service = RuntimeExecutionService()
    reconciled = ParameterState(
        intent="jira.issue.create",
        parameters={
            "project_key": CanonicalParameter(
                name="project_key",
                value="KAN",
                value_type="string",
                source="user_prompt",
                confidence=1,
                explicit=True,
                status="RESOLVED",
            )
        },
    )
    calls = []
    monkeypatch.setattr(
        "app.services.runtime_execution_service.parameter_reconciler.reconcile",
        lambda *args, **kwargs: calls.append((args, kwargs)) or reconciled,
    )
    persisted = []
    events = []
    monkeypatch.setattr(
        service,
        "_merge_runtime_metadata",
        lambda execution_id, values: persisted.append(values),
    )

    async def capture_event(execution_id, event):
        events.append(event)

    monkeypatch.setattr(service, "publish_event", capture_event)
    structured_intent = intent().model_dump(mode="json")
    first = await service._reconcile_parameters_once(
        "execution-1",
        structured_intent=structured_intent,
        parameter_extraction=extraction(),
        schema_definitions=[],
        runtime_metadata={},
    )
    second = await service._reconcile_parameters_once(
        "execution-1",
        structured_intent=structured_intent,
        parameter_extraction=extraction(),
        schema_definitions=[],
        runtime_metadata={"parameter_state": first},
    )
    assert first == second
    assert first["version"] == 1
    assert len(calls) == 1
    assert persisted == [{"parameter_state": first}]
    assert [event["type"] for event in events] == ["parameter_reconciliation.completed"]
