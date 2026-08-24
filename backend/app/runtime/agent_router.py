from __future__ import annotations

import logging
from time import monotonic
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.agents.application_service import AgentIdentity
from app.database.models.agent import Agent, AgentVersion
from app.database.models.agent_assignment import (
    AgentAccessAssignment,
    AgentToolAssignment,
)
from app.database.models.integration import IntegrationAgentAssignment
from app.metrics.agent_routing_metrics import (
    AGENT_ROUTING,
    AGENT_ROUTING_AMBIGUOUS,
    AGENT_ROUTING_INCOMPATIBLE,
    AGENT_ROUTING_LATENCY,
    AGENT_ROUTING_RESOLVED,
    AGENT_ROUTING_UNAVAILABLE,
)
from app.runtime.capability_resolver import CapabilityResolutionResult
from app.runtime.intent_analyzer import IntentResult
from app.runtime.parameter_reconciler import ParameterState

logger = logging.getLogger(__name__)

RoutingStatus = Literal[
    "RESOLVED",
    "EXPLICIT_SELECTED",
    "AMBIGUOUS",
    "UNAVAILABLE",
    "UNHEALTHY",
    "UNAUTHORIZED",
    "INCOMPATIBLE",
]


class AgentDescriptor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_id: str
    internal_id: int
    slug: str
    name: str
    lifecycle_status: str
    operational_health: str
    published_version: int | None
    owner_id: str | None
    tenant_id: str
    model_provider: str | None
    model: str | None
    model_configuration: dict[str, Any] = Field(default_factory=dict)
    environment_restrictions: list[str] = Field(default_factory=list)
    semantic_capabilities: list[str] = Field(default_factory=list)
    tool_names: list[str] = Field(default_factory=list)
    integration_connection_ids: list[str] = Field(default_factory=list)
    integration_capability_names: list[str] = Field(default_factory=list)
    is_default: bool = False
    priority: int = 0
    access_allowed: bool = False
    runtime_loadable: bool = False


class AgentCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent_id: str
    agent_slug: str
    agent_name: str
    eligible: bool
    score: float
    capability_match: bool
    connection_match: bool
    environment_match: bool
    permission_match: bool
    health_match: bool
    rejection_reasons: list[str] = Field(default_factory=list)
    reason_codes: list[str] = Field(default_factory=list)
    model_provider: str | None = None
    model: str | None = None
    published_version: int | None = None
    model_configuration: dict[str, Any] = Field(default_factory=dict)
    assigned_tools: list[str] = Field(default_factory=list)
    semantic_capabilities: list[str] = Field(default_factory=list)
    priority: int = 0
    is_default: bool = False


class AgentRoutingResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: RoutingStatus
    selected_agent: AgentCandidate | None = None
    candidates: list[AgentCandidate] = Field(default_factory=list)
    selection_mode: Literal["user_selected", "automatic", "default_fallback"]
    confidence: float = 0
    reason_code: str | None = None
    resolved_capability_id: str
    semantic_capability: str
    implementation_name: str
    integration_connection_id: str | None = None

    def persisted_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="json")


class AgentRouter:
    """Routes an already-resolved capability to persisted executable agents."""

    def route(
        self,
        db: Session,
        *,
        capability_resolution: CapabilityResolutionResult | dict[str, Any],
        intent_result: IntentResult | dict[str, Any],
        parameter_state: ParameterState | dict[str, Any],
        tenant_id: str,
        identity: AgentIdentity,
        execution_context: dict[str, Any] | None = None,
        explicit_agent_id: str | None = None,
        execution_id: str | None = None,
    ) -> AgentRoutingResult:
        started = monotonic()
        capability = (
            capability_resolution
            if isinstance(capability_resolution, CapabilityResolutionResult)
            else CapabilityResolutionResult.model_validate(capability_resolution)
        )
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
        if capability.status != "RESOLVED" or capability.selected is None:
            raise ValueError("Agent routing requires a resolved capability")
        # Validate the state contract even though routing deliberately does not score it.
        if not isinstance(parameter_state, ParameterState):
            ParameterState.model_validate(parameter_state)
        context = execution_context or {}
        descriptors = self._inventory(db, tenant_id, identity)
        if explicit_agent_id:
            requested = [
                item
                for item in descriptors
                if explicit_agent_id
                in {item.agent_id, item.slug, str(item.internal_id)}
            ]
            candidates = [
                self._evaluate(item, capability, context, explicit=True)
                for item in requested
            ]
            result = self._explicit_result(capability, candidates)
        else:
            candidates = [
                self._evaluate(item, capability, context, explicit=False)
                for item in descriptors
            ]
            result = self._automatic_result(capability, candidates)
        elapsed = monotonic() - started
        AGENT_ROUTING.labels(result.selection_mode, result.status, intent.domain).inc()
        AGENT_ROUTING_LATENCY.observe(elapsed)
        if result.status in {"RESOLVED", "EXPLICIT_SELECTED"}:
            AGENT_ROUTING_RESOLVED.inc()
        elif result.status == "AMBIGUOUS":
            AGENT_ROUTING_AMBIGUOUS.inc()
        elif result.status == "INCOMPATIBLE":
            AGENT_ROUTING_INCOMPATIBLE.inc()
        else:
            AGENT_ROUTING_UNAVAILABLE.inc()
        selected = result.selected_agent
        logger.info(
            "Agent routing completed",
            extra={
                "execution_id": execution_id,
                "capability_id": capability.selected.capability_id,
                "semantic_capability": capability.selected.semantic_capability,
                "selection_mode": result.selection_mode,
                "candidate_count": len(result.candidates),
                "eligible_count": sum(item.eligible for item in result.candidates),
                "selected_agent_id": selected.agent_id if selected else None,
                "provider": selected.model_provider if selected else None,
                "model": selected.model if selected else None,
                "routing_status": result.status,
                "latency_ms": round(elapsed * 1000, 2),
            },
        )
        return result

    def _inventory(
        self, db: Session, tenant_id: str, identity: AgentIdentity
    ) -> list[AgentDescriptor]:
        rows = (
            db.query(Agent)
            .filter(Agent.tenant_id == tenant_id, Agent.deleted_at.is_(None))
            .all()
        )
        descriptors: list[AgentDescriptor] = []
        for row in rows:
            version = None
            if row.published_version is not None:
                version = (
                    db.query(AgentVersion)
                    .filter_by(
                        agent_id=row.id,
                        tenant_id=tenant_id,
                        version=row.published_version,
                        published=True,
                    )
                    .first()
                )
            snapshot = version.configuration_snapshot or {} if version else {}
            planner = version.planner_configuration or {} if version else {}
            limits = version.execution_limits or {} if version else {}
            capabilities = self._capability_names(
                snapshot.get("capabilities") or planner.get("capabilities") or []
            )
            tools = (
                db.query(AgentToolAssignment)
                .filter_by(
                    agent_id=row.id,
                    tenant_id=tenant_id,
                    enabled=True,
                    assignment_action="execute",
                )
                .all()
            )
            tools = [
                item
                for item in tools
                if item.agent_version in {None, row.published_version}
            ]
            integration_assignments = (
                db.query(IntegrationAgentAssignment)
                .filter_by(agent_id=row.id, tenant_id=tenant_id)
                .all()
            )
            model_configuration = (
                dict(version.model_configuration or {}) if version else {}
            )
            provider = (
                str(
                    model_configuration.get("provider")
                    or row.model_configuration_ref
                    or ""
                )
                .strip()
                .lower()
                or None
            )
            model = str(model_configuration.get("model") or "").strip() or None
            descriptors.append(
                AgentDescriptor(
                    agent_id=row.uuid,
                    internal_id=row.id,
                    slug=row.slug,
                    name=row.name,
                    lifecycle_status=row.lifecycle_status,
                    operational_health=row.operational_health.lower(),
                    published_version=row.published_version,
                    owner_id=row.owner_id,
                    tenant_id=row.tenant_id,
                    model_provider=provider,
                    model=model,
                    model_configuration=model_configuration,
                    environment_restrictions=list(
                        row.environment_restrictions
                        or limits.get("environment_restrictions")
                        or []
                    ),
                    semantic_capabilities=capabilities,
                    tool_names=sorted({item.tool_name for item in tools}),
                    integration_connection_ids=sorted(
                        {item.connection_id for item in integration_assignments}
                    ),
                    integration_capability_names=sorted(
                        {
                            name
                            for item in integration_assignments
                            for name in (item.capability_names or [])
                        }
                    ),
                    is_default=bool(
                        planner.get("is_default") or snapshot.get("is_default")
                    ),
                    priority=int(planner.get("routing_priority", 0) or 0),
                    access_allowed=self._access_allowed(db, row, identity),
                    runtime_loadable=bool(
                        version and version.instructions.strip() and provider and model
                    ),
                )
            )
        return descriptors

    @staticmethod
    def _capability_names(values: list[Any]) -> list[str]:
        names = []
        for value in values:
            if isinstance(value, dict):
                name = value.get("semantic_capability") or value.get("name")
            else:
                name = value
            if name:
                names.append(str(name))
        return sorted(set(names))

    @staticmethod
    def _access_allowed(db: Session, row: Agent, identity: AgentIdentity) -> bool:
        subjects = {(identity.subject_type, identity.actor_id)}
        subjects.update(("group", item) for item in identity.groups)
        subjects.update(("role", item) for item in identity.roles)
        matching = [
            item
            for item in db.query(AgentAccessAssignment).filter_by(
                agent_id=row.id, tenant_id=row.tenant_id, action="execute"
            )
            if (item.subject_type, item.subject_id) in subjects
        ]
        if any(not item.enabled for item in matching):
            return False
        return bool(
            row.owner_id == identity.actor_id
            or identity.allows("agents.execute")
            or any(item.enabled for item in matching)
        )

    @staticmethod
    def _evaluate(
        item: AgentDescriptor,
        capability: CapabilityResolutionResult,
        context: dict[str, Any],
        *,
        explicit: bool,
    ) -> AgentCandidate:
        selected = capability.selected
        assert selected is not None
        implementation_match = selected.name in item.tool_names
        semantic_match = selected.semantic_capability in item.semantic_capabilities
        integration_capability_match = (
            selected.name in item.integration_capability_names
        )
        authoritative_ids = set(selected.eligible_agent_ids)
        authoritative_match = (
            not authoritative_ids or str(item.internal_id) in authoritative_ids
        )
        capability_match = bool(
            authoritative_match
            and (implementation_match or semantic_match or integration_capability_match)
        )
        connection_match = bool(
            not selected.integration_connection_id
            or selected.integration_connection_id in item.integration_connection_ids
        )
        environment = str(context.get("environment") or "production").lower()
        environment_match = bool(
            not item.environment_restrictions
            or environment
            in {str(value).lower() for value in item.environment_restrictions}
        )
        health_match = item.operational_health not in {"unhealthy", "error", "offline"}
        reasons: list[str] = []
        if item.lifecycle_status != "enabled" or item.published_version is None:
            reasons.append("NOT_PUBLISHED")
        if not health_match:
            reasons.append("UNHEALTHY")
        if not capability_match:
            reasons.append("CAPABILITY_MISMATCH")
        if not connection_match:
            reasons.append("CONNECTION_MISMATCH")
        if not environment_match:
            reasons.append("ENVIRONMENT_RESTRICTED")
        if not item.access_allowed:
            reasons.append("AGENT_PERMISSION_DENIED")
        if not item.runtime_loadable:
            reasons.append("AGENT_RUNTIME_UNAVAILABLE")
        if explicit and reasons:
            reasons.append("EXPLICIT_SELECTION_INCOMPATIBLE")
        reason_codes = []
        if capability_match:
            reason_codes.append(
                "IMPLEMENTATION_EXACT_MATCH"
                if implementation_match
                else "SEMANTIC_CAPABILITY_EXACT_MATCH"
            )
        if selected.integration_connection_id and connection_match:
            reason_codes.append("CONNECTION_MATCH")
        if item.operational_health == "healthy":
            reason_codes.append("HEALTHY")
        elif health_match:
            reason_codes.append("HEALTH_UNKNOWN")
        if item.lifecycle_status == "enabled" and item.published_version is not None:
            reason_codes.append("PUBLISHED")
        score = (
            (
                120
                if implementation_match or integration_capability_match
                else 100
                if semantic_match
                else 0
            )
            + (30 if selected.integration_connection_id and connection_match else 0)
            + (20 if item.operational_health == "healthy" else 5 if health_match else 0)
            + item.priority * 10
            - (1 if item.is_default else 0)
        )
        return AgentCandidate(
            agent_id=item.agent_id,
            agent_slug=item.slug,
            agent_name=item.name,
            eligible=not reasons,
            score=score,
            capability_match=capability_match,
            connection_match=connection_match,
            environment_match=environment_match,
            permission_match=item.access_allowed,
            health_match=health_match,
            rejection_reasons=reasons,
            reason_codes=reason_codes,
            model_provider=item.model_provider,
            model=item.model,
            published_version=item.published_version,
            model_configuration=item.model_configuration,
            assigned_tools=item.tool_names,
            semantic_capabilities=item.semantic_capabilities,
            priority=item.priority,
            is_default=item.is_default,
        )

    @staticmethod
    def _base_result(
        capability: CapabilityResolutionResult, **kwargs
    ) -> AgentRoutingResult:
        selected = capability.selected
        assert selected is not None
        return AgentRoutingResult(
            resolved_capability_id=selected.capability_id,
            semantic_capability=selected.semantic_capability,
            implementation_name=selected.name,
            integration_connection_id=selected.integration_connection_id,
            **kwargs,
        )

    def _explicit_result(
        self, capability: CapabilityResolutionResult, candidates: list[AgentCandidate]
    ) -> AgentRoutingResult:
        if not candidates:
            return self._base_result(
                capability,
                status="UNAVAILABLE",
                candidates=[],
                selection_mode="user_selected",
                reason_code="SELECTED_AGENT_NOT_FOUND",
            )
        candidate = candidates[0]
        if candidate.eligible:
            return self._base_result(
                capability,
                status="EXPLICIT_SELECTED",
                selected_agent=candidate,
                candidates=candidates,
                selection_mode="user_selected",
                confidence=1,
            )
        if "UNHEALTHY" in candidate.rejection_reasons:
            status: RoutingStatus = "UNHEALTHY"
            reason = "AGENT_UNHEALTHY"
        elif candidate.rejection_reasons == [
            "AGENT_PERMISSION_DENIED",
            "EXPLICIT_SELECTION_INCOMPATIBLE",
        ]:
            status, reason = "UNAUTHORIZED", "AGENT_PERMISSION_DENIED"
        else:
            status, reason = "INCOMPATIBLE", "SELECTED_AGENT_INCOMPATIBLE"
        return self._base_result(
            capability,
            status=status,
            candidates=candidates,
            selection_mode="user_selected",
            reason_code=reason,
        )

    def _automatic_result(
        self, capability: CapabilityResolutionResult, candidates: list[AgentCandidate]
    ) -> AgentRoutingResult:
        eligible = [item for item in candidates if item.eligible]
        if not eligible:
            unhealthy = any(
                item.capability_match and "UNHEALTHY" in item.rejection_reasons
                for item in candidates
            )
            unauthorized = any(
                item.capability_match
                and "AGENT_PERMISSION_DENIED" in item.rejection_reasons
                for item in candidates
            )
            return self._base_result(
                capability,
                status="UNHEALTHY"
                if unhealthy
                else "UNAUTHORIZED"
                if unauthorized
                else "UNAVAILABLE",
                candidates=candidates,
                selection_mode="automatic",
                reason_code="AGENT_UNHEALTHY"
                if unhealthy
                else "AGENT_PERMISSION_DENIED"
                if unauthorized
                else "AGENT_UNAVAILABLE",
            )
        eligible.sort(key=lambda item: item.score, reverse=True)
        top = [item for item in eligible if item.score == eligible[0].score]
        if len(top) > 1:
            return self._base_result(
                capability,
                status="AMBIGUOUS",
                candidates=candidates,
                selection_mode="automatic",
                confidence=0.5,
                reason_code="MULTIPLE_EQUIVALENT_AGENTS",
            )
        selected = top[0]
        mode = "default_fallback" if selected.is_default else "automatic"
        return self._base_result(
            capability,
            status="RESOLVED",
            selected_agent=selected,
            candidates=candidates,
            selection_mode=mode,
            confidence=1 if len(eligible) == 1 else 0.9,
        )


agent_router = AgentRouter()
