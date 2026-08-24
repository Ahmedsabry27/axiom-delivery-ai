from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.database.session import SessionLocal
from app.integrations.jira import CAPABILITIES
from app.models.runtime_execution import (
    RuntimeContinuation,
    RuntimeExecution,
    RuntimeExecutionEvent,
)
from app.runtime.input_requirements import (
    MissingFieldResolver,
    RequirementSchemaProvider,
)
from app.runtime.parameter_reconciler import (
    CanonicalParameter,
    ParameterCandidate,
    ParameterState,
)
from app.services.runtime_execution_service import (
    ContinuationSchemaMismatchError,
    RuntimeExecutionService,
    SemanticConsistencyError,
)
from app.tool_sdk.builtin_tools import DeploymentReportTool


def definitions(*items):
    return [
        {
            "type": "function",
            "function": {
                "name": item.name,
                "description": item.description,
                "parameters": getattr(item, "input_schema", None) or item.parameters,
                "version": getattr(item, "version", None),
            },
        }
        for item in items
    ]


JIRA_CREATE = next(item for item in CAPABILITIES if item.name == "jira.create_issue")
KNOWN_DEFINITIONS = definitions(JIRA_CREATE, DeploymentReportTool().metadata)


def parameter(
    name,
    value,
    *,
    status="RESOLVED",
    value_type=None,
    alternatives=None,
    validated=False,
):
    if value_type is None:
        value_type = (
            "null"
            if value is None
            else "boolean"
            if isinstance(value, bool)
            else "integer"
            if isinstance(value, int)
            else "array"
            if isinstance(value, list)
            else "string"
        )
    return CanonicalParameter(
        name=name,
        value=value,
        value_type=value_type,
        source="user_prompt",
        confidence=1,
        explicit=True,
        status=status,
        validated=validated,
        alternatives=alternatives or [],
        conflict=status == "AMBIGUOUS",
        conflict_reason="conflict" if status == "AMBIGUOUS" else None,
    )


def state(parameters, intent="jira.issue.create"):
    return ParameterState(intent=intent, parameters=parameters)


def jira_schema():
    schema = RequirementSchemaProvider().get("jira.issue.create", KNOWN_DEFINITIONS)
    assert schema is not None
    return schema


@pytest.mark.parametrize(
    ("parameters", "satisfied", "missing"),
    [
        (
            {
                "project_key": parameter("project_key", "KAN"),
                "issue_type": parameter("issue_type", "Task"),
                "summary": parameter("summary", "Testing"),
            },
            ["project_key", "issue_type", "summary"],
            [],
        ),
        (
            {"project_key": parameter("project_key", "KAN", validated=False)},
            ["project_key"],
            ["issue_type", "summary"],
        ),
        (
            {"issue_type": parameter("issue_type", "Bug")},
            ["issue_type"],
            ["project_key", "summary"],
        ),
        (
            {"summary": parameter("summary", "Payment failure")},
            ["summary"],
            ["project_key", "issue_type"],
        ),
        ({}, [], ["project_key", "issue_type", "summary"]),
        (
            {
                "project_key": parameter("project_key", "KAN"),
                "issue_type": parameter("issue_type", "Task"),
            },
            ["project_key", "issue_type"],
            ["summary"],
        ),
    ],
)
def test_jira_required_minus_satisfied_is_exact(parameters, satisfied, missing):
    result = MissingFieldResolver().evaluate(state(parameters), jira_schema())
    assert result.satisfied == satisfied
    assert [field.name for field in result.missing] == missing
    assert result.complete is (not missing)


def test_jira_create_requirements_use_implemented_contract_without_visible_tool():
    schema = RequirementSchemaProvider().get("jira.issue.create", [])
    result = MissingFieldResolver().evaluate(state({}), schema)
    assert result.complete is False
    assert [field.name for field in result.missing] == [
        "project_key",
        "issue_type",
        "summary",
    ]
    assert result.requirement_schema.intent == "jira.issue.create"


def test_optional_jira_fields_do_not_block_completion():
    result = MissingFieldResolver().evaluate(
        state(
            {
                "project_key": parameter("project_key", "KAN"),
                "issue_type": parameter("issue_type", "Task"),
                "summary": parameter("summary", "Testing"),
            }
        ),
        jira_schema(),
    )
    assert result.complete is True
    assert not {"description", "priority", "assignee", "labels"} & {
        field.name for field in result.unresolved_fields()
    }


def test_ambiguous_required_field_preserves_alternatives_as_options():
    alternatives = [
        ParameterCandidate(
            name="project_key",
            value="OPS",
            value_type="string",
            source="user_prompt",
            confidence=1,
            explicit=True,
            domain="jira",
        )
    ]
    result = MissingFieldResolver().evaluate(
        state(
            {
                "project_key": parameter(
                    "project_key", "KAN", status="AMBIGUOUS", alternatives=alternatives
                ),
                "issue_type": parameter("issue_type", "Task"),
                "summary": parameter("summary", "Cleanup"),
            }
        ),
        jira_schema(),
    )
    assert result.complete is False
    assert result.missing == []
    assert [field.name for field in result.ambiguous] == ["project_key"]
    assert result.ambiguous[0].options == ["KAN", "OPS"]


@pytest.mark.parametrize("status", ["INVALID", "UNRESOLVED"])
def test_invalid_and_unresolved_required_fields_do_not_satisfy(status):
    result = MissingFieldResolver().evaluate(
        state({"summary": parameter("summary", "bad", status=status)}),
        jira_schema(),
    )
    target = result.invalid if status == "INVALID" else result.missing
    assert "summary" in [field.name for field in target]
    assert result.complete is False


def generic_schema(properties, required):
    definition = {
        "type": "function",
        "function": {
            "name": "deployment_report",
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }
    return RequirementSchemaProvider().get("deployment.report.generate", [definition])


def test_empty_string_invalid_but_false_and_zero_are_satisfied():
    schema = generic_schema(
        {
            "summary": {"type": "string", "minLength": 1},
            "include_closed": {"type": "boolean"},
            "offset": {"type": "integer", "minimum": 0},
        },
        ["summary", "include_closed", "offset"],
    )
    result = MissingFieldResolver().evaluate(
        state(
            {
                "summary": parameter("summary", ""),
                "include_closed": parameter("include_closed", False),
                "offset": parameter("offset", 0),
            },
            "deployment.report.generate",
        ),
        schema,
    )
    assert set(result.satisfied) == {"include_closed", "offset"}
    assert [field.name for field in result.invalid] == ["summary"]


@pytest.mark.parametrize(("nullable", "complete"), [(True, True), (False, False)])
def test_explicit_null_follows_schema_nullability(nullable, complete):
    schema = generic_schema(
        {
            "assignee": {
                "type": ["string", "null"] if nullable else "string",
                "nullable": nullable,
            }
        },
        ["assignee"],
    )
    result = MissingFieldResolver().evaluate(
        state(
            {"assignee": parameter("assignee", None)},
            "deployment.report.generate",
        ),
        schema,
    )
    assert result.complete is complete
    if not nullable:
        assert result.invalid[0].reason == "NULL_NOT_ALLOWED"


def test_required_array_obeys_min_items():
    schema = generic_schema(
        {"labels": {"type": "array", "items": {"type": "string"}, "minItems": 1}},
        ["labels"],
    )
    result = MissingFieldResolver().evaluate(
        state({"labels": parameter("labels", [])}, "deployment.report.generate"),
        schema,
    )
    assert [field.name for field in result.invalid] == ["labels"]


def test_dynamic_requirements_are_merged_iteratively():
    provider = RequirementSchemaProvider()
    base = provider.get("jira.issue.create", KNOWN_DEFINITIONS)
    initial = MissingFieldResolver().evaluate(
        state(
            {
                "project_key": parameter("project_key", "KAN"),
                "issue_type": parameter("issue_type", "Task"),
                "summary": parameter("summary", "Testing"),
            }
        ),
        base,
    )
    assert initial.complete is True
    dynamic = provider.get(
        "jira.issue.create",
        KNOWN_DEFINITIONS,
        dynamic_schema={
            "type": "object",
            "properties": {
                "customfield_123": {
                    "type": "string",
                    "title": "Business Service",
                    "minLength": 1,
                }
            },
            "required": ["customfield_123"],
        },
    )
    second = MissingFieldResolver().evaluate(
        state(
            {
                "project_key": parameter("project_key", "KAN"),
                "issue_type": parameter("issue_type", "Task"),
                "summary": parameter("summary", "Testing"),
            }
        ),
        dynamic,
    )
    assert [field.name for field in second.missing] == ["customfield_123"]
    assert second.missing[0].label == "Business Service"


def test_no_schema_returns_controlled_unknown_completeness():
    schema = RequirementSchemaProvider().get("sap.work_order.create", KNOWN_DEFINITIONS)
    result = MissingFieldResolver().evaluate(state({}, "sap.work_order.create"), schema)
    assert result.schema_available is False
    assert result.complete is None
    assert result.unresolved_fields() == []


def test_jira_report_never_uses_deployment_report_schema():
    assert (
        RequirementSchemaProvider().get("jira.report.generate", KNOWN_DEFINITIONS)
        is None
    )


def test_deployment_partial_asks_only_for_actual_missing_fields():
    schema = RequirementSchemaProvider().get(
        "deployment.report.generate", KNOWN_DEFINITIONS
    )
    result = MissingFieldResolver().evaluate(
        state(
            {
                "release_version": parameter("release_version", "2.4"),
                "environment": parameter("environment", "production"),
            },
            "deployment.report.generate",
        ),
        schema,
    )
    assert [field.name for field in result.missing] == ["project_name", "status"]


@pytest.mark.asyncio
async def test_runtime_persists_emits_and_reuses_evaluation(monkeypatch):
    service = RuntimeExecutionService()
    parameter_state = state({"project_key": parameter("project_key", "KAN")})
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
    first = await service._evaluate_input_requirements_once(
        str(uuid4()),
        parameter_state=parameter_state.model_dump(mode="json"),
        schema_definitions=KNOWN_DEFINITIONS,
        runtime_metadata={},
    )
    second = await service._evaluate_input_requirements_once(
        str(uuid4()),
        parameter_state=parameter_state.model_dump(mode="json"),
        schema_definitions=KNOWN_DEFINITIONS,
        runtime_metadata={"input_requirements": first},
    )
    assert first == second
    assert first["parameter_state_version"] == 1
    assert len(persisted) == 1
    assert [event["type"] for event in events] == ["input_requirements.evaluated"]


def test_generic_required_input_fields_contain_only_unresolved_fields():
    result = (
        MissingFieldResolver()
        .evaluate(
            state({"project_key": parameter("project_key", "KAN")}), jira_schema()
        )
        .model_dump(mode="json")
    )
    fields = RuntimeExecutionService._requirement_fields(result)
    assert [field["name"] for field in fields] == ["issue_type", "summary"]
    assert [field["label"] for field in fields] == ["Issue Type", "Summary"]


def test_semantic_identity_drift_fails_closed():
    with pytest.raises(SemanticConsistencyError):
        RuntimeExecutionService._assert_semantic_consistency(
            {
                "intent_analysis": {"intent": "jira.issue.create"},
                "parameter_state": {"intent": "jira.issue.create"},
                "input_requirements": {"intent": "jira.report.generate"},
            },
            continuation_intent="jira.issue.create",
            execution_id="safe-test-id",
        )


def test_continuation_field_drift_fails_before_persistence():
    requirements = (
        MissingFieldResolver()
        .evaluate(state({}), jira_schema())
        .model_dump(mode="json")
    )
    execution = RuntimeExecution(
        id=uuid4(),
        conversation_id=uuid4(),
        workflow_id=uuid4(),
        user_id="requirements-user",
        tenant_id="requirements-tenant",
        status="RUNNING",
        runtime_metadata={
            "intent_analysis": {"intent": "jira.issue.create"},
            "parameter_state": {"intent": "jira.issue.create"},
            "input_requirements": requirements,
        },
    )
    with pytest.raises(ContinuationSchemaMismatchError):
        RuntimeExecutionService._build_input_continuation(
            execution,
            [
                {
                    "name": "report_scope",
                    "label": "Jira report scope",
                    "type": "text",
                    "required": True,
                }
            ],
            {},
            parameter_state_version=1,
            input_requirements=requirements,
        )


@pytest.mark.asyncio
async def test_waiting_transition_is_durable_releases_lease_and_deduplicates(
    monkeypatch,
):
    service = RuntimeExecutionService()
    execution_id = uuid4()
    with SessionLocal() as db:
        db.add(
            RuntimeExecution(
                id=execution_id,
                conversation_id=uuid4(),
                workflow_id=uuid4(),
                user_id="requirements-user",
                tenant_id="requirements-tenant",
                status="RUNNING",
                started_at=datetime.now(UTC).replace(tzinfo=None),
                lease_owner=service.worker_id,
                lease_expires_at=(datetime.now(UTC) + timedelta(minutes=5)).replace(
                    tzinfo=None
                ),
                heartbeat_at=datetime.now(UTC).replace(tzinfo=None),
                attempt=1,
                runtime_metadata={
                    "parameter_state": {"version": 1},
                    "intent_analysis": {"intent": "jira.issue.create"},
                },
                steps=[],
                token_usage={},
            )
        )
        db.commit()
    service._owned_attempts[str(execution_id)] = 1
    published = []

    async def capture(execution_id_value, event):
        published.append((execution_id_value, event))

    monkeypatch.setattr(service._tracker, "publish", capture)
    requirements = {"intent": "jira.issue.create", "parameter_state_version": 1}
    fields = [
        {"name": "issue_type", "label": "Issue Type", "type": "text", "required": True},
        {"name": "summary", "label": "Summary", "type": "text", "required": True},
    ]
    await service._pause_for_input(
        str(execution_id),
        fields,
        {"project_key": "KAN"},
        parameter_state_version=1,
        input_requirements=requirements,
    )
    await service._pause_for_input(
        str(execution_id),
        fields,
        {"project_key": "KAN"},
        parameter_state_version=1,
        input_requirements=requirements,
    )

    with SessionLocal() as db:
        record = db.get(RuntimeExecution, execution_id)
        continuations = (
            db.query(RuntimeContinuation)
            .filter_by(execution_id=execution_id, status="pending")
            .all()
        )
        lifecycle = (
            db.query(RuntimeExecutionEvent)
            .filter_by(
                execution_id=execution_id, event_type="runtime.waiting_for_input"
            )
            .all()
        )
        assert record.status == "WAITING_FOR_INPUT"
        assert record.lease_owner is None
        assert record.lease_expires_at is None
        assert len(continuations) == 1
        assert continuations[0].schema["parameter_state_version"] == 1
        assert continuations[0].schema["input_requirements"] == requirements
        assert len(lifecycle) == 1
    assert len(published) == 1
