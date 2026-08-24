from __future__ import annotations

import logging
from time import monotonic
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from app.metrics.reconciliation_metrics import (
    PARAMETER_RECONCILIATION_CONFLICTS,
    PARAMETER_RECONCILIATION_LATENCY,
    PARAMETER_RECONCILIATIONS,
)
from app.runtime.intent_analyzer import IntentResult
from app.runtime.parameter_extractor import (
    ExtractedParameter,
    ParameterExtractionResult,
    ParameterType,
    _canonical_name,
    _value_type,
)

logger = logging.getLogger(__name__)

ParameterStatus = Literal["RESOLVED", "AMBIGUOUS", "INVALID", "UNRESOLVED"]
CandidateSource = Literal[
    "user_prompt",
    "structured_input",
    "conversation_context",
    "runtime_state",
    "intent_analysis",
    "integration_default",
    "workspace_default",
    "model_inference",
]

INFERENCE_MIN_CONFIDENCE = 0.75

_SOURCE_PRECEDENCE: dict[str, int] = {
    "user_prompt": 800,
    "structured_input": 700,
    "conversation_context": 600,
    "runtime_state": 500,
    "intent_analysis": 400,
    "integration_default": 300,
    "workspace_default": 200,
    "model_inference": 100,
}


class ParameterCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    value: Any
    value_type: ParameterType
    source: CandidateSource
    confidence: float = Field(ge=0.0, le=1.0)
    explicit: bool
    original_text: str | None = None
    domain: str | None = None
    collection_mode: Literal["replace", "add"] = "replace"
    ordinal: int | None = None

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: Any) -> str:
        if not isinstance(value, str):
            raise TypeError("candidate name must be a string")
        return _canonical_name(value)


class ParameterConflict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    reason: str
    candidates: list[ParameterCandidate]


class CanonicalParameter(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    value: Any
    value_type: ParameterType
    source: CandidateSource
    confidence: float = Field(ge=0.0, le=1.0)
    explicit: bool
    status: ParameterStatus
    validated: bool = False
    original_text: str | None = None
    alternatives: list[ParameterCandidate] = Field(default_factory=list)
    conflict: bool = False
    conflict_reason: str | None = None


class ParameterState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: str | None
    parameters: dict[str, CanonicalParameter]
    conflicts: list[ParameterConflict] = Field(default_factory=list)
    unresolved_mentions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    version: int = Field(default=1, ge=1)


def _candidate_from_extracted(
    parameter: ExtractedParameter, domain: str
) -> ParameterCandidate:
    source: CandidateSource = parameter.source
    return ParameterCandidate(
        name=parameter.name,
        value=parameter.value,
        value_type=parameter.value_type,
        source=source,
        confidence=parameter.confidence,
        explicit=parameter.explicit,
        original_text=parameter.original_text,
        domain=domain,
    )


def _normalize_value(
    name: str, value: Any, expected_type: ParameterType | None
) -> tuple[Any, ParameterType]:
    if expected_type == "integer" and isinstance(value, str):
        stripped = value.strip()
        if stripped.lstrip("+-").isdigit():
            return int(stripped), "integer"
    if expected_type == "number" and isinstance(value, str):
        try:
            return float(value.strip()), "number"
        except ValueError:
            pass
    if expected_type == "boolean" and isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "yes", "include", "included"}:
            return True, "boolean"
        if lowered in {"false", "no", "exclude", "excluded"}:
            return False, "boolean"
    if isinstance(value, str) and expected_type == "string":
        if name == "status" and value.strip().lower() in {
            "succeeded",
            "partial",
            "failed",
        }:
            return value.strip().lower(), "string"
        if name in {"priority", "status", "issue_type"}:
            return value.strip().title(), "string"
        return value, "string"
    if isinstance(value, str) and name in {"priority", "status", "issue_type"}:
        return value.strip().title(), "string"
    return value, _value_type(value)


class ParameterReconciler:
    """Deterministically chooses canonical values without external validation."""

    def reconcile(
        self,
        intent: IntentResult | dict[str, Any],
        extraction: ParameterExtractionResult | dict[str, Any],
        *,
        additional_candidates: list[ParameterCandidate | dict[str, Any]] | None = None,
        existing_state: ParameterState | dict[str, Any] | None = None,
        configured_defaults: list[ParameterCandidate | dict[str, Any]] | None = None,
        expected_types: dict[str, ParameterType] | None = None,
        execution_id: str | None = None,
    ) -> ParameterState:
        started = monotonic()
        intent_result = (
            intent
            if isinstance(intent, IntentResult)
            else IntentResult.model_validate(
                {
                    key: value
                    for key, value in intent.items()
                    if key in IntentResult.model_fields
                }
            )
        )
        input_warnings: list[str] = []
        if isinstance(extraction, ParameterExtractionResult):
            extraction_result = extraction
        else:
            valid_parameters: dict[str, ExtractedParameter] = {}
            raw_parameters = extraction.get("parameters", {})
            if isinstance(raw_parameters, dict):
                for name, raw in raw_parameters.items():
                    try:
                        valid_parameters[name] = (
                            raw
                            if isinstance(raw, ExtractedParameter)
                            else ExtractedParameter.model_validate(raw)
                        )
                    except ValidationError:
                        input_warnings.append(
                            f"Invalid extracted candidate ignored for {_canonical_name(str(name))}."
                        )
            else:
                input_warnings.append(
                    "Invalid extracted parameter collection was ignored."
                )
            extraction_result = ParameterExtractionResult(
                intent=extraction.get("intent", intent_result.intent),
                parameters=valid_parameters,
                unresolved_mentions=extraction.get("unresolved_mentions", []),
                warnings=extraction.get("warnings", []),
                source=extraction.get("source", "fallback"),
                error_code=extraction.get("error_code"),
            )
        domain = intent_result.domain
        warnings = [*extraction_result.warnings, *input_warnings]
        candidates: list[ParameterCandidate] = [
            _candidate_from_extracted(parameter, domain)
            for parameter in extraction_result.parameters.values()
        ]
        for raw in additional_candidates or []:
            try:
                candidate = (
                    raw
                    if isinstance(raw, ParameterCandidate)
                    else ParameterCandidate.model_validate(raw)
                )
            except ValidationError:
                warnings.append("An invalid parameter candidate was ignored.")
                continue
            if candidate.domain and candidate.domain != domain:
                continue
            candidates.append(candidate)
        for raw in configured_defaults or []:
            try:
                candidate = (
                    raw
                    if isinstance(raw, ParameterCandidate)
                    else ParameterCandidate.model_validate(raw)
                )
            except ValidationError:
                warnings.append("An invalid configured default was ignored.")
                continue
            # Defaults without a declared semantic domain are unsafe to reuse.
            if candidate.domain != domain:
                continue
            candidates.append(candidate)
        prior_version = 0
        if existing_state:
            state = (
                existing_state
                if isinstance(existing_state, ParameterState)
                else ParameterState.model_validate(existing_state)
            )
            if state.intent == intent_result.intent:
                prior_version = state.version
                for parameter in state.parameters.values():
                    candidates.append(
                        ParameterCandidate(
                            name=parameter.name,
                            value=parameter.value,
                            value_type=parameter.value_type,
                            source="runtime_state",
                            confidence=parameter.confidence,
                            explicit=parameter.explicit,
                            original_text=parameter.original_text,
                            domain=domain,
                        )
                    )

        grouped: dict[str, list[ParameterCandidate]] = {}
        for candidate in candidates:
            if (
                candidate.source == "model_inference"
                and not candidate.explicit
                and candidate.confidence < INFERENCE_MIN_CONFIDENCE
            ):
                warnings.append(
                    f"Weak inferred candidate omitted for {candidate.name}."
                )
                continue
            expected = (expected_types or {}).get(candidate.name)
            value, value_type = _normalize_value(
                candidate.name, candidate.value, expected
            )
            if (
                candidate.value is not None
                and expected
                and value_type != expected
                and not (expected == "number" and value_type == "integer")
            ):
                warnings.append(f"Incompatible candidate ignored for {candidate.name}.")
                continue
            grouped.setdefault(candidate.name, []).append(
                candidate.model_copy(update={"value": value, "value_type": value_type})
            )

        parameters: dict[str, CanonicalParameter] = {}
        conflicts: list[ParameterConflict] = []
        for name in sorted(grouped):
            canonical, conflict = self._resolve_group(name, grouped[name])
            parameters[name] = canonical
            if conflict:
                conflicts.append(conflict)

        elapsed = monotonic() - started
        PARAMETER_RECONCILIATIONS.labels("conflict" if conflicts else "success").inc()
        PARAMETER_RECONCILIATION_CONFLICTS.inc(len(conflicts))
        PARAMETER_RECONCILIATION_LATENCY.observe(elapsed)
        logger.info(
            "Parameter reconciliation completed",
            extra={
                "execution_id": execution_id,
                "intent": intent_result.intent,
                "candidate_count": len(candidates),
                "resolved_count": sum(
                    item.status == "RESOLVED" for item in parameters.values()
                ),
                "conflict_count": len(conflicts),
                "parameter_state_version": prior_version + 1,
                "latency_ms": round(elapsed * 1000, 2),
            },
        )
        return ParameterState(
            intent=intent_result.intent,
            parameters=parameters,
            conflicts=conflicts,
            unresolved_mentions=extraction_result.unresolved_mentions,
            warnings=warnings,
            version=prior_version + 1,
        )

    @staticmethod
    def _resolve_group(
        name: str, candidates: list[ParameterCandidate]
    ) -> tuple[CanonicalParameter, ParameterConflict | None]:
        ranked = sorted(
            candidates,
            key=lambda item: (
                _SOURCE_PRECEDENCE[item.source],
                int(item.explicit),
                item.confidence,
                item.ordinal if item.ordinal is not None else -1,
            ),
            reverse=True,
        )
        winner = ranked[0]
        same_strength = [
            item
            for item in ranked
            if _SOURCE_PRECEDENCE[item.source] == _SOURCE_PRECEDENCE[winner.source]
            and item.explicit == winner.explicit
            and item.confidence == winner.confidence
        ]
        values = {repr(item.value) for item in same_strength}
        if len(values) > 1:
            ordered = [item for item in same_strength if item.ordinal is not None]
            if len(ordered) == len(same_strength) and len(
                {item.ordinal for item in ordered}
            ) == len(ordered):
                winner = max(ordered, key=lambda item: item.ordinal or 0)
            else:
                reason = "Equally authoritative candidates contain different values."
                conflict = ParameterConflict(
                    name=name, reason=reason, candidates=same_strength
                )
                return CanonicalParameter(
                    name=name,
                    value=winner.value,
                    value_type=winner.value_type,
                    source=winner.source,
                    confidence=winner.confidence,
                    explicit=winner.explicit,
                    status="AMBIGUOUS",
                    alternatives=[item for item in ranked if item is not winner],
                    conflict=True,
                    conflict_reason=reason,
                    original_text=winner.original_text,
                ), conflict

        if winner.collection_mode == "add" and winner.value_type == "array":
            prior = next(
                (item for item in ranked[1:] if item.value_type == "array"), None
            )
            if prior:
                winner = winner.model_copy(
                    update={"value": list(dict.fromkeys([*prior.value, *winner.value]))}
                )
        return CanonicalParameter(
            name=name,
            value=winner.value,
            value_type=winner.value_type,
            source=winner.source,
            confidence=winner.confidence,
            explicit=winner.explicit,
            status="RESOLVED",
            validated=False,
            original_text=winner.original_text,
            alternatives=[item for item in ranked if item is not winner],
        ), None


parameter_reconciler = ParameterReconciler()
