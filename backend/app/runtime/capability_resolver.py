from __future__ import annotations

import logging
from time import monotonic
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.database.models.action import Action
from app.database.models.integration import (
    IntegrationAgentAssignment,
    IntegrationCapability,
    IntegrationConnection,
)
from app.database.models.mcp import MCPCapability, MCPServer
from app.database.models.tool import ToolDefinition
from app.metrics.capability_resolution_metrics import (
    CAPABILITY_RESOLUTION_AMBIGUOUS,
    CAPABILITY_RESOLUTION_LATENCY,
    CAPABILITY_RESOLUTION_UNAUTHORIZED,
    CAPABILITY_RESOLUTION_UNAVAILABLE,
    CAPABILITY_RESOLUTION_UNHEALTHY,
    CAPABILITY_RESOLUTIONS,
)
from app.runtime.intent_analyzer import IntentResult
from app.runtime.parameter_reconciler import ParameterState

logger = logging.getLogger(__name__)

ResolutionStatus = Literal[
    "RESOLVED", "AMBIGUOUS", "UNAVAILABLE", "UNAUTHORIZED", "UNHEALTHY"
]
CapabilityType = Literal["tool", "action", "workflow", "native", "mcp"]

# Explicit compatibility bridge for catalog entries that predate semantic metadata.
LEGACY_SEMANTIC_CAPABILITIES: dict[str, str] = {
    "jira.get_projects": "jira.project.search",
    "jira.search_issues": "jira.issue.search",
    "jira.get_issue": "jira.issue.read",
    "jira.get_create_metadata": "jira.issue.create_metadata.read",
    "jira.get_transitions": "jira.issue.transition.read",
    "jira.create_issue": "jira.issue.create",
    "jira.update_issue": "jira.issue.update",
    "jira.add_comment": "jira.issue.comment",
    "jira.assign_issue": "jira.issue.assign",
    "jira.transition_issue": "jira.issue.transition",
    "deployment_report": "deployment.report.generate",
}

_WRITE_OPERATIONS = {"create", "update", "comment", "assign", "transition", "delete"}


class CapabilityDescriptor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capability_id: str
    semantic_capability: str
    name: str
    display_name: str
    capability_type: CapabilityType
    domain: str
    resource: str
    operation: str
    provider: str | None = None
    source: str
    enabled: bool
    healthy: bool
    tenant_id: str | None = None
    integration_connection_id: str | None = None
    integration_connection_name: str | None = None
    integration_connection_display_name: str | None = None
    connection_default: bool = False
    permissions: list[str] = Field(default_factory=list)
    input_schema: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None
    risk_level: str | None = None
    approval_required: bool = False
    version: str | None = None
    eligible_agent_ids: list[str] = Field(default_factory=list)


class CapabilityCandidate(CapabilityDescriptor):
    score: float = 0
    eligible: bool = False
    rejection_reasons: list[str] = Field(default_factory=list)
    authorized: bool = False
    input_compatible: bool = False
    parameter_bindings: dict[str, str] = Field(default_factory=dict)
    explicit_connection_match: bool = False


class CapabilityResolutionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    intent: str | None
    status: ResolutionStatus
    selected: CapabilityCandidate | None = None
    candidates: list[CapabilityCandidate] = Field(default_factory=list)
    required_semantic_capability: str | None
    confidence: float = 0
    reason_code: str | None = None

    def persisted_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class CapabilityResolutionError(RuntimeError):
    """Technical inventory failure, distinct from a valid unavailable result."""


class CapabilityResolver:
    """Deterministically resolves semantic intent against tenant catalog state."""

    def resolve(
        self,
        db: Session,
        *,
        intent_result: IntentResult | dict[str, Any],
        parameter_state: ParameterState | dict[str, Any],
        tenant_id: str,
        permissions: set[str],
        execution_context: dict[str, Any] | None = None,
        execution_id: str | None = None,
    ) -> CapabilityResolutionResult:
        started = monotonic()
        try:
            intent = (
                intent_result
                if isinstance(intent_result, IntentResult)
                else IntentResult.model_validate(
                    {
                        key: value
                        for key, value in intent_result.items()
                        if key in IntentResult.model_fields
                    }
                )
            )
            state = (
                parameter_state
                if isinstance(parameter_state, ParameterState)
                else ParameterState.model_validate(parameter_state)
            )
            context = execution_context or {}
            inventory = self._inventory(db, tenant_id)
            candidates = [
                self._evaluate(item, intent, state, permissions, context)
                for item in inventory
                if item.semantic_capability == intent.intent
            ]
            result = self._select(intent, candidates, context)
        except Exception as exc:
            if isinstance(exc, CapabilityResolutionError):
                raise
            raise CapabilityResolutionError(
                "Capability inventory lookup failed"
            ) from exc
        elapsed = monotonic() - started
        selected_type = result.selected.capability_type if result.selected else "none"
        CAPABILITY_RESOLUTIONS.labels(
            intent.domain, intent.operation, result.status, selected_type
        ).inc()
        CAPABILITY_RESOLUTION_LATENCY.observe(elapsed)
        status_metrics = {
            "UNAVAILABLE": CAPABILITY_RESOLUTION_UNAVAILABLE,
            "AMBIGUOUS": CAPABILITY_RESOLUTION_AMBIGUOUS,
            "UNAUTHORIZED": CAPABILITY_RESOLUTION_UNAUTHORIZED,
            "UNHEALTHY": CAPABILITY_RESOLUTION_UNHEALTHY,
        }
        if result.status in status_metrics:
            status_metrics[result.status].inc()
        logger.info(
            "Capability resolution completed",
            extra={
                "execution_id": execution_id,
                "intent": intent.intent,
                "domain": intent.domain,
                "required_semantic_capability": intent.intent,
                "candidate_count": len(result.candidates),
                "eligible_count": sum(item.eligible for item in result.candidates),
                "resolution_status": result.status,
                "selected_capability_id": (
                    result.selected.capability_id if result.selected else None
                ),
                "selected_type": selected_type,
                "integration_connection_id": (
                    result.selected.integration_connection_id
                    if result.selected
                    else None
                ),
                "latency_ms": round(elapsed * 1000, 2),
            },
        )
        return result

    def _inventory(self, db: Session, tenant_id: str) -> list[CapabilityDescriptor]:
        connections = {
            row.id: row
            for row in db.query(IntegrationConnection)
            .filter_by(tenant_id=tenant_id)
            .all()
        }
        assignments: dict[str, list[str]] = {}
        for row in db.query(IntegrationAgentAssignment).filter_by(tenant_id=tenant_id):
            assignments.setdefault(row.connection_id, []).append(str(row.agent_id))
        descriptors: list[CapabilityDescriptor] = []
        backed_names: set[tuple[str, str]] = set()
        for capability in db.query(IntegrationCapability).filter_by(
            tenant_id=tenant_id
        ):
            connection = connections.get(capability.connection_id)
            semantic = self.semantic_for(capability.external_name)
            if not semantic:
                continue
            backed_names.add((capability.connection_id, capability.external_name))
            required = self._integration_permissions(db, capability, tenant_id)
            descriptors.append(
                self._descriptor(
                    capability_id=capability.id,
                    semantic=semantic,
                    name=capability.external_name,
                    display_name=capability.display_name,
                    capability_type=self._capability_type(
                        capability.capability_type, capability.external_name
                    ),
                    provider=connection.connector_type if connection else None,
                    source="integration_capability",
                    enabled=bool(
                        capability.enabled
                        and capability.provisioned
                        and connection
                        and connection.enabled
                        and connection.status in {"connected", "active"}
                    ),
                    healthy=bool(connection and connection.health_status == "healthy"),
                    tenant_id=tenant_id,
                    connection=connection,
                    permissions=required,
                    input_schema=capability.input_schema,
                    output_schema=capability.output_schema,
                    risk_level=capability.risk_level,
                    approval_required=capability.approval_required,
                    version=capability.version,
                    eligible_agent_ids=assignments.get(capability.connection_id, []),
                )
            )
        for tool in db.query(ToolDefinition).filter(
            (ToolDefinition.tenant_id == tenant_id)
            | (
                (ToolDefinition.tenant_id == "default")
                & (ToolDefinition.registration_source == "native")
            )
        ):
            if (
                tool.integration_connection_id
                and (tool.integration_connection_id, tool.name) in backed_names
            ):
                continue
            semantic = self.semantic_for(tool.name, tool.tags)
            if not semantic:
                continue
            connection = connections.get(tool.integration_connection_id)
            source_type = str(tool.registration_source or "").lower()
            kind: CapabilityType = (
                "mcp"
                if "mcp" in source_type
                else "native"
                if source_type == "native"
                else "tool"
            )
            descriptors.append(
                self._descriptor(
                    capability_id=tool.id,
                    semantic=semantic,
                    name=tool.name,
                    display_name=tool.display_name,
                    capability_type=kind,
                    provider=tool.provider,
                    source=f"tool_definition:{tool.registration_source}",
                    enabled=bool(tool.enabled and tool.active and not tool.deprecated),
                    healthy=(
                        connection.health_status == "healthy" if connection else True
                    ),
                    tenant_id=tenant_id,
                    connection=connection,
                    permissions=list(tool.permissions or []),
                    input_schema=tool.input_schema,
                    output_schema=tool.output_schema,
                    risk_level=tool.risk_level,
                    version=tool.version,
                )
            )
        for action in db.query(Action).filter_by(tenant_id=tenant_id):
            if (
                action.integration_connection_id
                and (action.integration_connection_id, action.name) in backed_names
            ):
                continue
            semantic = self.semantic_for(action.name)
            if not semantic:
                continue
            connection = connections.get(action.integration_connection_id)
            descriptors.append(
                self._descriptor(
                    capability_id=f"action:{action.id}",
                    semantic=semantic,
                    name=action.name,
                    display_name=action.display_name or action.name,
                    capability_type="action",
                    provider=action.provider,
                    source="action_definition",
                    enabled=action.status == "ENABLED",
                    healthy=(
                        connection.health_status == "healthy" if connection else True
                    ),
                    tenant_id=tenant_id,
                    connection=connection,
                    permissions=list((action.permissions or {}).get("required", [])),
                    risk_level=action.risk_level,
                    approval_required=action.approval_required,
                )
            )
        servers = {
            row.id: row for row in db.query(MCPServer).filter_by(tenant_id=tenant_id)
        }
        for capability in db.query(MCPCapability).filter_by(tenant_id=tenant_id):
            semantic = (capability.safe_metadata or {}).get(
                "semantic_capability"
            ) or self.semantic_for(capability.internal_name)
            if not semantic:
                continue
            server = servers.get(capability.server_id)
            descriptors.append(
                self._descriptor(
                    capability_id=capability.id,
                    semantic=semantic,
                    name=capability.internal_name,
                    display_name=capability.display_name,
                    capability_type="mcp",
                    provider=(server.slug if server else "mcp"),
                    source="mcp_capability",
                    enabled=bool(
                        capability.enabled
                        and capability.approved
                        and not capability.missing
                        and server
                        and server.enabled
                        and server.deleted_at is None
                    ),
                    healthy=bool(server and server.health_status == "healthy"),
                    tenant_id=tenant_id,
                    permissions=[capability.permission],
                    input_schema=capability.schema_json,
                    output_schema=None,
                    risk_level=capability.risk_level,
                    approval_required=capability.approval_policy == "required",
                )
            )
        return descriptors

    @staticmethod
    def semantic_for(name: str, tags: list[Any] | None = None) -> str | None:
        for tag in tags or []:
            if isinstance(tag, str) and tag.startswith("semantic:"):
                return tag.removeprefix("semantic:")
        return LEGACY_SEMANTIC_CAPABILITIES.get(name)

    @staticmethod
    def _descriptor(
        *, semantic: str, connection=None, **kwargs
    ) -> CapabilityDescriptor:
        parts = semantic.split(".")
        configuration = connection.configuration or {} if connection else {}
        safe_metadata = connection.safe_metadata or {} if connection else {}
        return CapabilityDescriptor(
            semantic_capability=semantic,
            domain=parts[0] if parts else "unknown",
            resource=parts[1] if len(parts) > 1 else "unknown",
            operation=parts[-1] if parts else "unknown",
            integration_connection_id=connection.id if connection else None,
            integration_connection_name=connection.name if connection else None,
            integration_connection_display_name=(
                connection.display_name if connection else None
            ),
            connection_default=bool(
                configuration.get("is_default") or safe_metadata.get("is_default")
            ),
            **kwargs,
        )

    @staticmethod
    def _integration_permissions(
        db: Session, capability: IntegrationCapability, tenant_id: str
    ) -> list[str]:
        action = (
            db.query(Action)
            .filter_by(
                tenant_id=tenant_id,
                integration_connection_id=capability.connection_id,
                name=capability.external_name,
            )
            .first()
        )
        if action:
            return list((action.permissions or {}).get("required", []))
        tool = (
            db.query(ToolDefinition)
            .filter_by(
                tenant_id=tenant_id,
                integration_connection_id=capability.connection_id,
                name=capability.external_name,
            )
            .first()
        )
        return list(tool.permissions or []) if tool else []

    @staticmethod
    def _capability_type(raw: str, name: str) -> CapabilityType:
        if raw in {"workflow", "native", "mcp"}:
            return raw
        semantic = LEGACY_SEMANTIC_CAPABILITIES.get(name, "")
        operation = semantic.rsplit(".", 1)[-1]
        return "action" if raw == "action" or operation in _WRITE_OPERATIONS else "tool"

    def _evaluate(
        self,
        item: CapabilityDescriptor,
        intent: IntentResult,
        state: ParameterState,
        permissions: set[str],
        context: dict[str, Any],
    ) -> CapabilityCandidate:
        reasons: list[str] = []
        authorized = (
            not item.permissions
            or "tools.admin" in permissions
            or set(item.permissions).issubset(permissions)
        )
        if not item.enabled:
            reasons.append("DISABLED")
        if (
            item.source == "integration_capability"
            and not item.integration_connection_id
        ):
            reasons.append("INTEGRATION_CONNECTION_MISSING")
        if not authorized:
            reasons.append("UNAUTHORIZED")
        if item.integration_connection_id and not item.healthy:
            reasons.append("UNHEALTHY")
        if intent.operation in _WRITE_OPERATIONS and item.capability_type == "tool":
            reasons.append("OPERATION_TYPE_MISMATCH")
        if (
            intent.operation not in _WRITE_OPERATIONS
            and item.capability_type == "action"
        ):
            reasons.append("OPERATION_TYPE_MISMATCH")
        bindings, compatible, coverage = self._bindings(item.input_schema, state)
        if not compatible:
            reasons.append("INPUT_SCHEMA_INCOMPATIBLE")
        hint = self._connection_hint(state, context)
        explicit_match = bool(hint and self._matches_connection(item, hint))
        if hint and item.integration_connection_id and not explicit_match:
            reasons.append("CONNECTION_MISMATCH")
        pinned_tools = set(context.get("selected_agent_tools") or [])
        if context.get("selected_agent_id") and item.name not in pinned_tools:
            reasons.append("SELECTED_AGENT_INCOMPATIBLE")
        score = (
            100
            + coverage * 10
            + (20 if explicit_match else 0)
            + (5 if item.connection_default else 0)
        )
        return CapabilityCandidate(
            **item.model_dump(),
            score=score,
            eligible=not reasons,
            rejection_reasons=reasons,
            authorized=authorized,
            input_compatible=compatible,
            parameter_bindings=bindings,
            explicit_connection_match=explicit_match,
        )

    @staticmethod
    def _bindings(
        schema: dict[str, Any] | None, state: ParameterState
    ) -> tuple[dict[str, str], bool, float]:
        if not schema or not schema.get("properties"):
            return {}, True, 0
        properties = schema.get("properties") or {}
        aliases = schema.get("x-parameter-aliases") or {}
        bindings: dict[str, str] = {}
        resolved = {
            name: item
            for name, item in state.parameters.items()
            if item.status == "RESOLVED"
        }
        for canonical in resolved:
            target = canonical if canonical in properties else aliases.get(canonical)
            if target in properties:
                bindings[canonical] = target
        required = set(schema.get("required") or [])
        bound_targets = set(bindings.values())
        compatible = required.issubset(bound_targets)
        coverage = len(bindings) / max(1, len(resolved))
        return bindings, compatible, coverage

    @staticmethod
    def _connection_hint(state: ParameterState, context: dict[str, Any]) -> str | None:
        for key in ("integration_connection_id", "connection_id", "connection_name"):
            value = context.get(key)
            if value:
                return str(value)
            parameter = state.parameters.get(key)
            if parameter and parameter.status == "RESOLVED" and parameter.value:
                return str(parameter.value)
        return None

    @staticmethod
    def _matches_connection(item: CapabilityDescriptor, hint: str) -> bool:
        normalized = hint.strip().casefold()
        return normalized in {
            str(item.integration_connection_id or "").casefold(),
            str(item.integration_connection_name or "").casefold(),
            str(item.integration_connection_display_name or "").casefold(),
        }

    @staticmethod
    def _select(
        intent: IntentResult,
        candidates: list[CapabilityCandidate],
        context: dict[str, Any],
    ) -> CapabilityResolutionResult:
        eligible = [item for item in candidates if item.eligible]
        if not candidates:
            return CapabilityResolutionResult(
                intent=intent.intent,
                status="UNAVAILABLE",
                candidates=[],
                required_semantic_capability=intent.intent,
                reason_code="NO_REGISTERED_CAPABILITY",
            )
        if not eligible:
            reason_set = {
                reason for item in candidates for reason in item.rejection_reasons
            }
            targeted = [item for item in candidates if item.explicit_connection_match]
            defaulted = [item for item in candidates if item.connection_default]
            protected = targeted or (
                defaulted if intent.operation in _WRITE_OPERATIONS else []
            )
            status: ResolutionStatus = (
                "UNHEALTHY"
                if protected
                and any("UNHEALTHY" in item.rejection_reasons for item in protected)
                else "UNAUTHORIZED"
                if reason_set == {"UNAUTHORIZED"}
                else "UNHEALTHY"
                if "UNHEALTHY" in reason_set and not (reason_set - {"UNHEALTHY"})
                else "UNAVAILABLE"
            )
            return CapabilityResolutionResult(
                intent=intent.intent,
                status=status,
                candidates=candidates,
                required_semantic_capability=intent.intent,
                reason_code=next(iter(sorted(reason_set)), "NO_ELIGIBLE_CAPABILITY"),
            )
        if intent.operation in _WRITE_OPERATIONS:
            targeted = [item for item in candidates if item.explicit_connection_match]
            defaulted = [item for item in candidates if item.connection_default]
            protected = targeted or defaulted
            if protected and not any(item.eligible for item in protected):
                unhealthy = any(
                    "UNHEALTHY" in item.rejection_reasons for item in protected
                )
                return CapabilityResolutionResult(
                    intent=intent.intent,
                    status="UNHEALTHY" if unhealthy else "UNAVAILABLE",
                    candidates=candidates,
                    required_semantic_capability=intent.intent,
                    reason_code=(
                        "TARGET_CONNECTION_UNHEALTHY"
                        if unhealthy
                        else "TARGET_CONNECTION_UNAVAILABLE"
                    ),
                )
        eligible.sort(key=lambda item: item.score, reverse=True)
        top_score = eligible[0].score
        top = [item for item in eligible if item.score == top_score]
        if len(top) > 1:
            return CapabilityResolutionResult(
                intent=intent.intent,
                status="AMBIGUOUS",
                candidates=candidates,
                required_semantic_capability=intent.intent,
                confidence=0.5,
                reason_code="MULTIPLE_EQUIVALENT_CAPABILITIES",
            )
        selected = top[0]
        return CapabilityResolutionResult(
            intent=intent.intent,
            status="RESOLVED",
            selected=selected,
            candidates=candidates,
            required_semantic_capability=intent.intent,
            confidence=min(1, intent.confidence),
            reason_code=None,
        )


capability_resolver = CapabilityResolver()
