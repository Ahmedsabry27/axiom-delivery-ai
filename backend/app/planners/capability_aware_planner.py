from __future__ import annotations

import hashlib
import json
from time import monotonic
from typing import Any
from uuid import UUID, uuid4

from jsonschema import ValidationError as JSONSchemaValidationError
from jsonschema import validate as validate_json

from app.contracts.planner import Planner
from app.metrics.planning_metrics import (
    PLANNING_FAILURES,
    PLANNING_LATENCY,
    PLANNING_REQUESTS,
    PLANNING_TASKS,
)
from app.runtime.context import RuntimeContext
from app.runtime.execution_plan import ExecutionPlan
from app.runtime.task import Task

DEFAULT_TASK_TIMEOUT_SECONDS = 30
VALID_CAPABILITY_TYPES = {"tool", "action", "workflow", "native", "mcp"}


class PlanningError(ValueError):
    code = "PLANNING_FAILED"


class PlanPreconditionError(PlanningError):
    code = "PLAN_PRECONDITION_FAILED"


class PlanInputBindingError(PlanningError):
    code = "PLAN_INPUT_BINDING_FAILED"


class PlanValidationError(PlanningError):
    code = "PLAN_VALIDATION_FAILED"


class ExecutionPlanValidator:
    """Rejects plan drift and malformed dependency graphs before execution."""

    def validate(
        self,
        plan: ExecutionPlan,
        *,
        capability_resolution: dict[str, Any],
        agent_routing: dict[str, Any],
    ) -> None:
        selected_capability = capability_resolution.get("selected") or {}
        selected_agent = agent_routing.get("selected_agent") or {}
        if not plan.tasks or not any(task.required for task in plan.tasks):
            raise PlanValidationError("Plan requires at least one required task")
        ids = [task.id for task in plan.tasks]
        if len(ids) != len(set(ids)):
            raise PlanValidationError("Plan task IDs must be unique")
        known = set(ids)
        for task in plan.tasks:
            if task.task_type.lower() not in VALID_CAPABILITY_TYPES:
                raise PlanValidationError("Plan contains an invalid capability type")
            if not task.capability_id or not task.implementation_name:
                raise PlanValidationError(
                    "Executable task capability identity is missing"
                )
            if task.capability_id != selected_capability.get("capability_id"):
                raise PlanValidationError(
                    "Plan capability differs from resolved capability"
                )
            if task.implementation_name != selected_capability.get("name"):
                raise PlanValidationError(
                    "Plan implementation differs from resolved capability"
                )
            if task.agent_id != selected_agent.get("agent_id"):
                raise PlanValidationError("Plan agent differs from routed agent")
            if task.integration_connection_id != selected_capability.get(
                "integration_connection_id"
            ):
                raise PlanValidationError(
                    "Plan connection differs from resolved connection"
                )
            if any(dependency not in known for dependency in task.depends_on):
                raise PlanValidationError("Plan contains an unknown dependency")
        self._validate_acyclic(plan.tasks)

    @staticmethod
    def _validate_acyclic(tasks: list[Task]) -> None:
        graph = {task.id: set(task.depends_on) for task in tasks}
        visiting: set[UUID] = set()
        visited: set[UUID] = set()

        def visit(node: UUID) -> None:
            if node in visiting:
                raise PlanValidationError("Plan dependency graph contains a cycle")
            if node in visited:
                return
            visiting.add(node)
            for dependency in graph[node]:
                visit(dependency)
            visiting.remove(node)
            visited.add(node)

        for task_id in graph:
            visit(task_id)


class CapabilityAwarePlanner(Planner):
    """Builds a minimal executable plan only from authoritative upstream state."""

    def __init__(self, validator: ExecutionPlanValidator | None = None) -> None:
        self.validator = validator or ExecutionPlanValidator()

    async def plan(self, context: RuntimeContext) -> ExecutionPlan:
        started = monotonic()
        metadata = context.metadata
        intent = metadata.get("intent_analysis")
        state = metadata.get("parameter_state")
        capability = metadata.get("capability_resolution")
        routing = metadata.get("agent_routing")
        if not all(
            isinstance(item, dict) for item in (intent, state, capability, routing)
        ):
            PLANNING_FAILURES.labels("precondition").inc()
            raise PlanPreconditionError("Authoritative planning inputs are missing")
        if capability.get("status") != "RESOLVED" or not capability.get("selected"):
            raise PlanPreconditionError("Capability must be resolved before planning")
        if routing.get("status") not in {
            "RESOLVED",
            "EXPLICIT_SELECTED",
        } or not routing.get("selected_agent"):
            raise PlanPreconditionError("Agent must be resolved before planning")
        selected = capability["selected"]
        routed = routing["selected_agent"]
        parameters, warnings = self._bind_parameters(state, selected)
        task_type = str(selected.get("capability_type") or "").lower()
        side_effect = self._side_effect(selected)
        task = Task(
            id=uuid4(),
            name=self._task_name(selected),
            description=f"Invoke registered capability {selected['name']}",
            agent=routed.get("agent_slug"),
            agent_id=routed.get("agent_id"),
            agent_version=routed.get("published_version"),
            required_capabilities=[selected.get("semantic_capability")],
            required_tools=[selected.get("name")],
            tool=selected.get("name"),
            task_type=task_type.upper(),
            capability_id=selected.get("capability_id"),
            semantic_capability=selected.get("semantic_capability"),
            implementation_name=selected.get("name"),
            integration_connection_id=selected.get("integration_connection_id"),
            parameters=parameters,
            required=True,
            timeout_seconds=int(
                selected.get("timeout_seconds") or DEFAULT_TASK_TIMEOUT_SECONDS
            ),
            retry_count=1 if side_effect == "READ_ONLY" else 0,
            retry_policy={
                "max_attempts": 2 if side_effect == "READ_ONLY" else 1,
                "automatic": side_effect == "READ_ONLY",
            },
            side_effect_class=side_effect,
            expected_output_schema=selected.get("output_schema"),
            requires_approval=bool(selected.get("approval_required")),
            metadata={
                "risk_level": selected.get("risk_level"),
                "reason_codes": [
                    "PRIMARY_CAPABILITY_TASK",
                    "PARAMETER_BOUND",
                    "EXPLICIT_AGENT"
                    if routing.get("selection_mode") == "user_selected"
                    else "AUTOMATIC_AGENT",
                ],
                "binding_warnings": warnings,
                "tenant_id": context.tenant_id,
                "user_id": context.user_id,
                "execution_id": str(context.request_id),
                "workflow_id": str(context.workflow_id),
                "provider": routed.get("model_provider"),
                "model": routed.get("model"),
            },
        )
        fingerprint = self._fingerprint(intent, state, selected, routed)
        plan = ExecutionPlan(
            goal=context.goal,
            tasks=[task],
            execution_id=context.request_id,
            intent=intent.get("intent"),
            version=1,
            root_task_ids=[task.id],
            status="VALIDATED",
            metadata={
                "capability_id": selected.get("capability_id"),
                "agent_id": routed.get("agent_id"),
                "connection_id": selected.get("integration_connection_id"),
                "capability_type": task_type,
            },
            input_fingerprint=fingerprint,
            required_capabilities=[selected.get("semantic_capability")],
            agent_requirements={task.name: [selected.get("semantic_capability")]},
            estimated_duration_seconds=float(task.timeout_seconds),
            estimated_cost=0,
        )
        try:
            self.validator.validate(
                plan, capability_resolution=capability, agent_routing=routing
            )
        except PlanValidationError:
            PLANNING_FAILURES.labels("validation").inc()
            raise
        elapsed = monotonic() - started
        domain = str(intent.get("domain") or "unknown")
        PLANNING_REQUESTS.labels(domain, task_type, "success").inc()
        PLANNING_TASKS.labels(task_type).inc(len(plan.tasks))
        PLANNING_LATENCY.observe(elapsed)
        return plan

    @staticmethod
    def _bind_parameters(
        state: dict[str, Any], selected: dict[str, Any]
    ) -> tuple[dict[str, Any], list[str]]:
        schema = selected.get("input_schema") or {}
        properties = schema.get("properties") or {}
        bindings = selected.get("parameter_bindings") or {}
        bound: dict[str, Any] = {}
        warnings: list[str] = []
        for canonical, parameter in (state.get("parameters") or {}).items():
            if parameter.get("status") != "RESOLVED":
                continue
            target = bindings.get(canonical)
            if not target and canonical in properties:
                target = canonical
            if not target or (properties and target not in properties):
                warnings.append(f"UNBOUND_OPTIONAL_PARAMETER:{canonical}")
                continue
            bound[target] = parameter.get("value")
        required = set(schema.get("required") or [])
        missing = sorted(required - set(bound))
        if missing:
            PLANNING_FAILURES.labels("binding").inc()
            raise PlanInputBindingError(
                f"Required capability inputs could not be bound: {', '.join(missing)}"
            )
        try:
            validate_json(bound, schema or {"type": "object"})
        except JSONSchemaValidationError as exc:
            PLANNING_FAILURES.labels("binding").inc()
            raise PlanInputBindingError(
                f"Capability input validation failed: {exc.message}"
            ) from exc
        return bound, warnings

    @staticmethod
    def _side_effect(selected: dict[str, Any]) -> str:
        if selected.get("capability_type") in {"tool", "native", "mcp"}:
            return "READ_ONLY"
        if selected.get("idempotent") is True:
            return "IDEMPOTENT_WRITE"
        if selected.get("capability_type") == "action":
            return "NON_IDEMPOTENT_WRITE"
        return "UNKNOWN"

    @staticmethod
    def _task_name(selected: dict[str, Any]) -> str:
        display = selected.get("display_name") or selected.get("name") or "Capability"
        return " ".join(
            part.capitalize() for part in str(display).replace("_", " ").split()
        )

    @staticmethod
    def _fingerprint(
        intent: dict[str, Any],
        state: dict[str, Any],
        capability: dict[str, Any],
        agent: dict[str, Any],
    ) -> str:
        payload = {
            "intent": intent.get("intent"),
            "parameter_state_version": state.get("version"),
            "capability_id": capability.get("capability_id"),
            "capability_version": capability.get("version"),
            "connection_id": capability.get("integration_connection_id"),
            "agent_id": agent.get("agent_id"),
            "agent_version": agent.get("published_version"),
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


capability_aware_planner = CapabilityAwarePlanner()
