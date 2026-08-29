from __future__ import annotations

import logging
from time import monotonic
from typing import Any, ClassVar, Literal

from jsonschema import ValidationError as JSONSchemaValidationError
from jsonschema import validate as validate_json
from pydantic import BaseModel, ConfigDict, Field

from app.metrics.input_requirement_metrics import (
    INPUT_REQUIREMENT_EVALUATIONS,
    INPUT_REQUIREMENT_LATENCY,
    INPUT_REQUIREMENT_MISSING_FIELDS,
)
from app.runtime.parameter_reconciler import ParameterState, ParameterType

logger = logging.getLogger(__name__)

RequirementReason = Literal["MISSING", "AMBIGUOUS", "INVALID", "NULL_NOT_ALLOWED"]


class InputFieldRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    label: str
    value_type: ParameterType
    required: bool
    description: str | None = None
    options: list[Any] | None = None
    allow_null: bool = False
    validation: dict[str, Any] = Field(default_factory=dict)
    source: str


class InputRequirementSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: str
    fields: dict[str, InputFieldRequirement]
    source: str
    version: str | None = None


class MissingField(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    label: str
    value_type: ParameterType
    reason: RequirementReason
    current_status: str | None = None
    options: list[Any] | None = None
    validation: dict[str, Any] = Field(default_factory=dict)


class InputRequirementResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: str
    satisfied: list[str]
    missing: list[MissingField]
    ambiguous: list[MissingField]
    invalid: list[MissingField]
    complete: bool | None
    schema_available: bool
    schema_source: str | None
    schema_version: str | None = None
    requirement_schema: InputRequirementSchema | None = None

    def unresolved_fields(self) -> list[MissingField]:
        return [*self.missing, *self.ambiguous, *self.invalid]


class RequirementSchemaProvider:
    """Reads exact semantic requirement schemas without resolving capabilities."""

    _INTENT_TO_SCHEMA: ClassVar[dict[str, str]] = {
        "jira.project.search": "jira.get_projects",
        "jira.issue.search": "jira.search_issues",
        "jira.issue.read": "jira.get_issue",
        "jira.issue.comment.read": "jira.get_comments",
        "jira.sprint.health.assess": "jira.get_sprint_health",
        "jira.sprint.search": "jira.get_sprints",
        "jira.release.search": "jira.get_versions",
        "jira.release.issue.search": "jira.get_version_issues",
        "jira.issue.create_metadata.read": "jira.get_create_metadata",
        "jira.issue.transition.read": "jira.get_transitions",
        "jira.issue.create": "jira.create_issue",
        "deployment.report.generate": "deployment_report",
    }

    @classmethod
    def supported_intents(cls) -> list[str]:
        """Return the migrated semantic intents with deterministic input contracts."""
        return sorted(cls._INTENT_TO_SCHEMA)

    def get(
        self,
        intent: str | None,
        definitions: list[dict[str, Any]],
        *,
        dynamic_schema: dict[str, Any] | None = None,
    ) -> InputRequirementSchema | None:
        schema_name = self._INTENT_TO_SCHEMA.get(intent or "")
        if not schema_name:
            return None
        function = next(
            (
                item.get("function") or {}
                for item in definitions
                if (item.get("function") or {}).get("name") == schema_name
            ),
            None,
        )
        if function is None:
            function = self._connector_contract(schema_name)
        if function is None:
            return None
        base = function.get("parameters") or {}
        effective = self._merge_schemas(base, dynamic_schema)
        fields: dict[str, InputFieldRequirement] = {}
        required = set(effective.get("required") or [])
        for name, definition in (effective.get("properties") or {}).items():
            json_types = definition.get("type", "string")
            nullable = False
            if isinstance(json_types, list):
                nullable = "null" in json_types
                json_types = next(
                    (item for item in json_types if item != "null"), "null"
                )
            nullable = nullable or bool(definition.get("nullable", False))
            value_type: ParameterType = (
                json_types
                if json_types
                in {"string", "integer", "number", "boolean", "array", "object", "null"}
                else "string"
            )
            fields[name] = InputFieldRequirement(
                name=name,
                label=definition.get("title") or name.replace("_", " ").title(),
                value_type=value_type,
                required=name in required,
                description=definition.get("description"),
                options=definition.get("enum"),
                allow_null=nullable,
                validation={
                    key: definition[key]
                    for key in (
                        "type",
                        "format",
                        "minLength",
                        "maxLength",
                        "minimum",
                        "maximum",
                        "minItems",
                        "maxItems",
                        "enum",
                        "items",
                    )
                    if key in definition
                },
                source="dynamic_integration_metadata"
                if dynamic_schema and name in (dynamic_schema.get("properties") or {})
                else "tool_schema",
            )
        return InputRequirementSchema(
            intent=intent or "",
            fields=fields,
            source="tool_schema+dynamic_integration_metadata"
            if dynamic_schema
            else "tool_schema",
            version=function.get("version"),
        )

    @staticmethod
    def _connector_contract(schema_name: str) -> dict[str, Any] | None:
        """Read implemented connector schemas without selecting an installed capability."""
        from app.integrations.jira import CAPABILITIES

        definition = next(
            (item for item in CAPABILITIES if item.name == schema_name), None
        )
        if definition is None:
            return None
        return {
            "name": definition.name,
            "parameters": definition.input_schema,
            "version": definition.version,
        }

    @staticmethod
    def _merge_schemas(
        base: dict[str, Any], dynamic: dict[str, Any] | None
    ) -> dict[str, Any]:
        if not dynamic:
            return base
        return {
            **base,
            "properties": {
                **(base.get("properties") or {}),
                **(dynamic.get("properties") or {}),
            },
            "required": list(
                dict.fromkeys(
                    [*(base.get("required") or []), *(dynamic.get("required") or [])]
                )
            ),
        }


class MissingFieldResolver:
    """Evaluates required fields from canonical state without AI or external calls."""

    def evaluate(
        self,
        state: ParameterState | dict[str, Any],
        schema: InputRequirementSchema | None,
        *,
        execution_id: str | None = None,
    ) -> InputRequirementResult:
        started = monotonic()
        parameter_state = (
            state
            if isinstance(state, ParameterState)
            else ParameterState.model_validate(state)
        )
        if schema is None:
            result = InputRequirementResult(
                intent=parameter_state.intent or "",
                satisfied=[],
                missing=[],
                ambiguous=[],
                invalid=[],
                complete=None,
                schema_available=False,
                schema_source=None,
                schema_version=None,
                requirement_schema=None,
            )
            self._observe(result, started, execution_id)
            return result
        satisfied: list[str] = []
        missing: list[MissingField] = []
        ambiguous: list[MissingField] = []
        invalid: list[MissingField] = []
        for name, requirement in schema.fields.items():
            if not requirement.required:
                continue
            parameter = parameter_state.parameters.get(name)
            if parameter is None or parameter.status == "UNRESOLVED":
                missing.append(self._field(requirement, "MISSING", parameter))
                continue
            if parameter.status == "AMBIGUOUS":
                field = self._field(requirement, "AMBIGUOUS", parameter)
                alternatives = [
                    parameter.value,
                    *(item.value for item in parameter.alternatives),
                ]
                field.options = list(dict.fromkeys(alternatives))
                ambiguous.append(field)
                continue
            if parameter.status == "INVALID":
                invalid.append(self._field(requirement, "INVALID", parameter))
                continue
            if parameter.value is None:
                if requirement.allow_null:
                    satisfied.append(name)
                else:
                    invalid.append(
                        self._field(requirement, "NULL_NOT_ALLOWED", parameter)
                    )
                continue
            try:
                validation = dict(requirement.validation)
                if validation:
                    validate_json(parameter.value, validation)
            except JSONSchemaValidationError:
                invalid.append(self._field(requirement, "INVALID", parameter))
                continue
            satisfied.append(name)
        result = InputRequirementResult(
            intent=schema.intent,
            satisfied=satisfied,
            missing=missing,
            ambiguous=ambiguous,
            invalid=invalid,
            complete=not (missing or ambiguous or invalid),
            schema_available=True,
            schema_source=schema.source,
            schema_version=schema.version,
            requirement_schema=schema,
        )
        self._observe(result, started, execution_id)
        return result

    @staticmethod
    def _field(requirement, reason, parameter) -> MissingField:
        return MissingField(
            name=requirement.name,
            label=requirement.label,
            value_type=requirement.value_type,
            reason=reason,
            current_status=parameter.status if parameter else None,
            options=requirement.options,
            validation=requirement.validation,
        )

    @staticmethod
    def _observe(result, started, execution_id) -> None:
        elapsed = monotonic() - started
        outcome = (
            "unavailable"
            if not result.schema_available
            else "complete"
            if result.complete
            else "incomplete"
        )
        INPUT_REQUIREMENT_EVALUATIONS.labels(
            outcome, result.schema_source or "none"
        ).inc()
        for field in result.unresolved_fields():
            INPUT_REQUIREMENT_MISSING_FIELDS.labels(field.reason).inc()
        INPUT_REQUIREMENT_LATENCY.observe(elapsed)
        logger.info(
            "Input requirements evaluated",
            extra={
                "execution_id": execution_id,
                "intent": result.intent,
                "schema_source": result.schema_source,
                "schema_version": result.schema_version,
                "satisfied_count": len(result.satisfied),
                "missing_count": len(result.missing),
                "ambiguous_count": len(result.ambiguous),
                "invalid_count": len(result.invalid),
                "complete": result.complete,
                "latency_ms": round(elapsed * 1000, 2),
            },
        )


requirement_schema_provider = RequirementSchemaProvider()
missing_field_resolver = MissingFieldResolver()
