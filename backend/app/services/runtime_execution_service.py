from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import AsyncGenerator
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from time import monotonic
from typing import Any, ClassVar
from uuid import UUID, uuid4

from jsonschema import ValidationError as JSONSchemaValidationError
from jsonschema import validate as validate_json
from sqlalchemy import case, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.actions.examples.report_action import GenerateDeploymentReportAction
from app.actions.registry import ActionRegistry
from app.actions.services.action_executor import ActionExecutor
from app.agents.application_service import AgentIdentity, agent_application_service
from app.agents.execution_service import ExecutionRequest, agent_execution_service
from app.ai.exceptions import (
    AIAuthenticationError,
    AIConnectionError,
    AIProviderError,
    AIRateLimitError,
    AITimeoutError,
)
from app.audit.events import append_audit_event
from app.contracts.tool_models import ExecutionContext as ToolExecutionContext
from app.core.config import settings
from app.database.models.agent import Agent, AgentVersion
from app.database.models.agent_assignment import (
    AgentKnowledgeAssignment,
    AgentToolAssignment,
)
from app.database.models.governance import GovernedModel, ModelPrice, UsageRecord
from app.database.models.tool import ToolDefinition, ToolExecution
from app.database.session import SessionLocal
from app.events.runtime_events import (
    PlanningCompleted,
    PlanningFailed,
    PlanningStarted,
    TaskCompleted,
    TaskFailed,
    TaskStarted,
    WorkflowCompleted,
    WorkflowFailed,
    WorkflowStarted,
)
from app.metrics.continuation_metrics import (
    CONTINUATION_INTERPRETATION_FAILURES,
    CONTINUATION_LATENCY,
    CONTINUATION_RESPONSES,
    CONTINUATION_ROUNDS,
)
from app.metrics.input_requirement_metrics import INPUT_REQUIREMENT_WAITS
from app.metrics.runtime_metrics import (
    RUNTIME_ACTIVE,
    RUNTIME_DURATION,
    RUNTIME_EVENT_APPEND_FAILURE,
    RUNTIME_EVENT_APPEND_RETRY,
    RUNTIME_EVENT_COUNTER_DRIFT_DETECTED,
    RUNTIME_EVENT_COUNTER_RECONCILED,
    RUNTIME_EVENT_SEQUENCE_CONFLICT,
    RUNTIME_EXECUTIONS,
    RUNTIME_LEASE_LOST,
)
from app.models.runtime_execution import (
    RuntimeContinuation,
    RuntimeExecution,
    RuntimeExecutionEvent,
)
from app.planners.capability_aware_planner import (
    PlanningError,
    capability_aware_planner,
)
from app.runtime.agent_router import agent_router
from app.runtime.capability_resolver import (
    CapabilityResolutionError,
    capability_resolver,
)
from app.runtime.child_reconciliation import (
    RequiredChildStateError,
    runtime_child_reconciler,
)
from app.runtime.context import RuntimeContext
from app.runtime.continuation_interpreter import continuation_interpreter
from app.runtime.execution_tracker import ExecutionTracker
from app.runtime.input_requirements import (
    InputRequirementSchema,
    missing_field_resolver,
    requirement_schema_provider,
)
from app.runtime.intelligence import (
    CapabilityIntelligence,
    IntentAnalysis,
    reconcile_parameters,
)
from app.runtime.intent_analyzer import intent_analyzer
from app.runtime.leases import (
    RuntimeLeaseLostError,
    assert_execution_lease,
    claim_execution,
    claim_locked_execution,
    get_runtime_worker_id,
    renew_execution_lease,
)
from app.runtime.parameter_extractor import parameter_extractor
from app.runtime.parameter_reconciler import ParameterCandidate, parameter_reconciler
from app.services.chat_service import chat_service
from app.services.runtime_service import get_runtime
from app.tool_sdk.agent import authorized_model_tools
from app.tool_sdk.service import executor as tool_executor
from app.tool_sdk.service import registry as tool_registry

logger = logging.getLogger(__name__)


class InvalidRuntimeTransitionError(RuntimeError):
    """Raised when a RuntimeExecution lifecycle transition is not permitted."""


class SemanticConsistencyError(ValueError):
    """Raised when persisted intelligence stages disagree on semantic identity."""

    code = "SEMANTIC_CONSISTENCY_FAILED"


class ContinuationSchemaMismatchError(SemanticConsistencyError):
    """Raised before persistence when continuation fields are not canonical."""

    code = "CONTINUATION_SCHEMA_MISMATCH"


class RuntimeExecutionService:
    """Bridges the reusable runtime EventBus to durable SSE executions."""

    def __init__(self) -> None:
        self._runtime = get_runtime()
        self._tracker = ExecutionTracker()
        self._workflow_to_execution: dict[str, str] = {}
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._heartbeat_tasks: dict[str, asyncio.Task[None]] = {}
        self._owned_attempts: dict[str, int] = {}
        self.worker_id = get_runtime_worker_id()
        self._subscriptions_registered = False

        registry = ActionRegistry()
        registry.register(GenerateDeploymentReportAction())
        self._action_executor = ActionExecutor(registry)
        self._register_event_subscriptions()

    _VALID_TRANSITIONS: ClassVar[dict[str, set[str]]] = {
        "PENDING": {"RUNNING", "CANCELLED"},
        "RUNNING": {
            "WAITING_FOR_INPUT",
            "WAITING_FOR_APPROVAL",
            "COMPLETED",
            "FAILED",
            "CANCELLED",
            "TIMED_OUT",
        },
        "WAITING_FOR_INPUT": {"RUNNING", "CANCELLED", "TIMED_OUT"},
        "WAITING_FOR_APPROVAL": {"RUNNING", "FAILED", "CANCELLED", "TIMED_OUT"},
        "COMPLETED": set(),
        "FAILED": set(),
        "CANCELLED": set(),
        "TIMED_OUT": set(),
    }

    _TERMINAL_STATUSES: ClassVar[set[str]] = {
        "COMPLETED",
        "FAILED",
        "CANCELLED",
        "TIMED_OUT",
    }
    _LIFECYCLE_EVENT_TYPES: ClassVar[dict[tuple[str, str], str]] = {
        ("PENDING", "RUNNING"): "runtime.started",
        ("RUNNING", "WAITING_FOR_INPUT"): "runtime.waiting_for_input",
        ("RUNNING", "WAITING_FOR_APPROVAL"): "runtime.waiting_for_approval",
        ("WAITING_FOR_INPUT", "RUNNING"): "runtime.resumed",
        ("WAITING_FOR_APPROVAL", "RUNNING"): "runtime.resumed",
    }
    _TERMINAL_EVENT_TYPES: ClassVar[dict[str, str]] = {
        "COMPLETED": "runtime.completed",
        "FAILED": "runtime.failed",
        "CANCELLED": "runtime.cancelled",
        "TIMED_OUT": "runtime.timed_out",
    }

    def _refresh_active_metric(self) -> None:
        RUNTIME_ACTIVE.set(len(getattr(self, "_owned_attempts", {})))

    def transition_execution(
        self,
        execution_id: str | UUID,
        target_status: str,
        *,
        expected_statuses: set[str] | None = None,
        reason: str | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
        metadata: dict[str, Any] | None = None,
        agent: str | None = None,
        result_message: str | None = None,
        event_type: str | None = None,
        event_name: str | None = None,
        event_payload: dict[str, Any] | None = None,
        component_type: str = "runtime",
        component_id: str | None = None,
        worker_id: str | None = None,
        ownership_attempt: int | None = None,
        db: Session | None = None,
        commit: bool = True,
    ) -> RuntimeExecution:
        """Atomically apply the canonical public RuntimeExecution transition."""
        owns_session = db is None
        session = db or SessionLocal()
        execution_uuid = (
            execution_id if isinstance(execution_id, UUID) else UUID(execution_id)
        )
        try:
            record = (
                session.query(RuntimeExecution)
                .filter(RuntimeExecution.id == execution_uuid)
                .with_for_update()
                .one_or_none()
            )
            if record is None:
                raise LookupError(f"Runtime execution '{execution_uuid}' was not found")

            if worker_id is not None:
                assert_execution_lease(
                    record,
                    worker_id=worker_id,
                    attempt=ownership_attempt or -1,
                )

            current = record.status
            if target_status == current:
                # Same-state requests are deliberately side-effect free, including
                # repeated terminal notifications from concurrent completion paths.
                # Child reconciliation is still allowed to repair an older leaked
                # child without changing parent timestamps or adding an audit row.
                if target_status in self._TERMINAL_STATUSES:
                    runtime_child_reconciler.reconcile(session, record, target_status)
                    self._ensure_terminal_event_locked(session, record)
                    if commit:
                        session.commit()
                        session.refresh(record)
                return record

            if expected_statuses is not None and current not in expected_statuses:
                logger.warning(
                    "Runtime transition rejected because current state was unexpected",
                    extra={
                        "execution_id": str(execution_uuid),
                        "current_status": current,
                        "target_status": target_status,
                        "expected_statuses": sorted(expected_statuses),
                    },
                )
                raise InvalidRuntimeTransitionError(
                    f"Runtime execution is {current}; expected one of {sorted(expected_statuses)}"
                )
            if target_status not in self._VALID_TRANSITIONS.get(current, set()):
                logger.warning(
                    "Invalid runtime transition rejected",
                    extra={
                        "execution_id": str(execution_uuid),
                        "current_status": current,
                        "target_status": target_status,
                    },
                )
                raise InvalidRuntimeTransitionError(
                    f"Invalid runtime transition: {current} -> {target_status}"
                )

            now = datetime.now(UTC).replace(tzinfo=None)
            child_summary = None
            if target_status in self._TERMINAL_STATUSES:
                try:
                    child_summary = runtime_child_reconciler.reconcile(
                        session, record, target_status
                    )
                except RequiredChildStateError:
                    logger.warning(
                        "Runtime completion rejected by required child state",
                        extra={
                            "execution_id": str(execution_uuid),
                            "current_status": current,
                            "target_status": target_status,
                        },
                    )
                    raise
            record.status = target_status
            record.state_version = (record.state_version or 0) + 1
            if current == "PENDING" and target_status == "RUNNING":
                record.started_at = record.started_at or now
                timeout_seconds = int(
                    (record.runtime_metadata or {}).get(
                        "runtime_timeout_seconds", settings.RUNTIME_TIMEOUT_SECONDS
                    )
                )
                record.deadline_at = record.deadline_at or (
                    now + timedelta(seconds=max(1, timeout_seconds))
                )
            if target_status == "RUNNING":
                record.waiting_reason = None
            elif target_status in {"WAITING_FOR_INPUT", "WAITING_FOR_APPROVAL"}:
                record.waiting_reason = reason or record.waiting_reason

            if agent is not None:
                record.agent = agent
            if metadata:
                record.runtime_metadata = {
                    **(record.runtime_metadata or {}),
                    **metadata,
                }

            if target_status in self._TERMINAL_STATUSES:
                record.completed_at = record.completed_at or now
                if record.started_at is not None and record.duration_ms is None:
                    record.duration_ms = round(
                        (record.completed_at - record.started_at).total_seconds()
                        * 1000,
                        2,
                    )
                if target_status == "COMPLETED":
                    if result_message is not None:
                        record.result_message = result_message
                    record.error = None
                else:
                    if error_message is not None:
                        record.error = error_message
                    if target_status == "CANCELLED" and record.error is None:
                        record.result_message = (
                            result_message or "Execution cancelled by user."
                        )
                    elif result_message is not None:
                        record.result_message = result_message
                if error_code:
                    record.runtime_metadata = {
                        **(record.runtime_metadata or {}),
                        "error_code": error_code,
                    }

            if target_status in {
                "WAITING_FOR_INPUT",
                "WAITING_FOR_APPROVAL",
                *self._TERMINAL_STATUSES,
            }:
                record.lease_owner = None
                record.lease_expires_at = None
                record.heartbeat_at = None

            lifecycle_type = event_type or self._event_type_for_transition(
                current, target_status
            )
            lifecycle_payload = {
                **(event_payload or {}),
                "type": lifecycle_type,
                "name": event_name or self._event_name_for_status(target_status),
                "description": (event_payload or {}).get("description")
                or reason
                or error_message
                or self._event_description_for_status(target_status),
                "status": target_status.lower(),
                "aggregate_status": target_status,
                "component_type": component_type,
                "component_id": component_id or str(record.id),
                "component_status": target_status,
                "final": target_status in self._TERMINAL_STATUSES,
                "execution_id": str(record.id),
                "workflow_id": str(record.workflow_id),
                "agent": record.agent,
                "agent_id": record.selected_agent_id,
                "provider": record.provider_name,
                "model": record.model_name,
                "duration_ms": record.duration_ms,
            }
            if result_message is not None:
                lifecycle_payload["message"] = result_message
            if error_message is not None:
                lifecycle_payload["error"] = error_message
            if error_code is not None:
                lifecycle_payload["error_code"] = error_code
            self._append_runtime_event_locked(session, record, lifecycle_payload)

            audit_action = (
                "runtime.started"
                if target_status == "RUNNING" and current == "PENDING"
                else f"runtime.{target_status.lower()}"
            )
            append_audit_event(
                session,
                tenant_id=record.tenant_id,
                actor_id=record.user_id,
                action=audit_action,
                target_type="runtime_execution",
                target_id=str(record.id),
                correlation_id=str(record.workflow_id),
                metadata={
                    "from_status": current,
                    "to_status": target_status,
                    "reason": reason,
                    "agent_id": record.selected_agent_id,
                    "provider": record.provider_name,
                    "model": record.model_name,
                    "duration_ms": record.duration_ms,
                    "error": record.error,
                    "children": child_summary.as_dict() if child_summary else None,
                },
            )
            if target_status in self._TERMINAL_STATUSES:
                self._record_usage_locked(session, record)
            if commit:
                session.commit()
                session.refresh(record)
            else:
                session.flush()
            if target_status in self._TERMINAL_STATUSES:
                RUNTIME_EXECUTIONS.labels(status=target_status.lower()).inc()
                if record.duration_ms is not None:
                    RUNTIME_DURATION.observe(record.duration_ms / 1000)
            if target_status in {
                "WAITING_FOR_INPUT",
                "WAITING_FOR_APPROVAL",
                *self._TERMINAL_STATUSES,
            }:
                getattr(self, "_owned_attempts", {}).pop(str(record.id), None)
                self._refresh_active_metric()
            logger.info(
                "Runtime state transitioned",
                extra={
                    "execution_id": str(record.id),
                    "workflow_id": str(record.workflow_id),
                    "worker_id": worker_id,
                    "attempt": record.attempt,
                    "from_status": current,
                    "to_status": target_status,
                    "event_sequence": record.last_event_sequence,
                },
            )
            return record
        except Exception:
            if owns_session or commit:
                session.rollback()
            raise
        finally:
            if owns_session:
                session.close()

    @classmethod
    def _event_type_for_transition(cls, source: str, target: str) -> str:
        return (
            cls._TERMINAL_EVENT_TYPES.get(target)
            or cls._LIFECYCLE_EVENT_TYPES[(source, target)]
        )

    @staticmethod
    def _record_usage_locked(db: Session, record: RuntimeExecution) -> None:
        """Persist one tenant-scoped usage record without inventing unavailable values."""
        if (
            db.query(UsageRecord.id)
            .filter_by(tenant_id=record.tenant_id, execution_id=str(record.id))
            .first()
        ):
            return
        usage = record.token_usage or {}
        model = (
            db.query(GovernedModel)
            .filter(
                GovernedModel.provider_model_id == record.model_name,
                GovernedModel.status == "ACTIVE",
                (GovernedModel.tenant_id == record.tenant_id)
                | (GovernedModel.tenant_id.is_(None)),
            )
            .order_by(GovernedModel.tenant_id.desc())
            .first()
        )
        now = datetime.now(UTC)
        price = None
        if model is not None:
            price = (
                db.query(ModelPrice)
                .filter(
                    ModelPrice.model_id == model.id,
                    ModelPrice.effective_from <= now,
                    (ModelPrice.effective_until.is_(None))
                    | (ModelPrice.effective_until > now),
                )
                .order_by(ModelPrice.version.desc())
                .first()
            )
        input_tokens = usage.get("input_tokens") or usage.get("prompt_tokens")
        output_tokens = usage.get("output_tokens") or usage.get("completion_tokens")
        input_cost = output_cost = total_cost = None
        if price is not None and input_tokens is not None and output_tokens is not None:
            million = Decimal(1_000_000)
            input_cost = (
                Decimal(input_tokens) * price.input_cost_per_million / million
            ).quantize(Decimal("0.00000001"))
            output_cost = (
                Decimal(output_tokens) * price.output_cost_per_million / million
            ).quantize(Decimal("0.00000001"))
            total_cost = input_cost + output_cost
        db.add(
            UsageRecord(
                tenant_id=record.tenant_id,
                trace_id=str(record.workflow_id),
                execution_id=str(record.id),
                user_id=record.user_id,
                agent_id=record.selected_agent_id,
                model_id=model.id if model else (record.model_name or "unregistered"),
                provider=record.provider_name or "unknown",
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cached_input_tokens=usage.get("cached_input_tokens"),
                reasoning_tokens=usage.get("reasoning_tokens"),
                tool_calls=int(usage.get("tool_calls") or 0),
                latency_ms=int(record.duration_ms)
                if record.duration_ms is not None
                else None,
                status=record.status,
                price_version=price.version if price else None,
                input_cost=input_cost,
                output_cost=output_cost,
                total_cost=total_cost,
                currency=price.currency if price else None,
                cost_estimated=False if total_cost is not None else None,
                started_at=record.started_at or now,
                completed_at=record.completed_at,
            )
        )

    @staticmethod
    def _event_name_for_status(status: str) -> str:
        return {
            "RUNNING": "Runtime Started",
            "WAITING_FOR_INPUT": "Required Information",
            "WAITING_FOR_APPROVAL": "Approval Required",
            "COMPLETED": "Result Generated",
            "FAILED": "Runtime Execution",
            "CANCELLED": "Runtime Cancelled",
            "TIMED_OUT": "Runtime Timed Out",
        }[status]

    @staticmethod
    def _event_description_for_status(status: str) -> str:
        return {
            "RUNNING": "Runtime execution started",
            "WAITING_FOR_INPUT": "Runtime is waiting for required information",
            "WAITING_FOR_APPROVAL": "Runtime is waiting for approval",
            "COMPLETED": "Runtime execution completed",
            "FAILED": "Runtime execution failed",
            "CANCELLED": "Runtime execution was cancelled",
            "TIMED_OUT": "Runtime execution timed out",
        }[status]

    def _register_event_subscriptions(self) -> None:
        if self._subscriptions_registered:
            return

        event_bus = self._runtime._event_bus
        for event_type in (
            PlanningStarted,
            PlanningCompleted,
            PlanningFailed,
            WorkflowStarted,
            WorkflowCompleted,
            WorkflowFailed,
            TaskStarted,
            TaskCompleted,
            TaskFailed,
        ):
            event_bus.subscribe(event_type, self._handle_runtime_event)
        self._subscriptions_registered = True

    async def start(
        self,
        db: Session,
        *,
        user_id: str,
        message: str,
        conversation_id: UUID,
        permissions: set[str] | None = None,
        tenant_id: str = "default",
        provider_name: str | None = None,
        model: str | None = None,
        agent_id: str | None = None,
        identity: Any | None = None,
        workspace_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> RuntimeExecution:
        resolved_provider = self._resolve_provider_name(provider_name)
        resolved_model = self._resolve_model(
            provider_name=resolved_provider,
            model=model,
        )

        execution = RuntimeExecution(
            id=uuid4(),
            workflow_id=uuid4(),
            conversation_id=conversation_id,
            user_id=user_id,
            goal=message,
            status="PENDING",
            started_at=None,
            steps=[],
            tenant_id=tenant_id,
            selected_agent_id=None,
            agent=None,
            provider_name=resolved_provider,
            model_name=resolved_model,
            workspace_id=workspace_id,
            runtime_metadata={
                **(metadata or {}),
                "request": {
                    "agent_id": agent_id,
                    "provider": provider_name,
                    "model": model,
                },
                "resolved": {"provider": resolved_provider, "model": resolved_model},
                "selection_mode": "user_selected" if agent_id else "automatic",
                "selected_agent": None,
                "agent_candidates": [],
                "permissions": sorted(permissions or set()),
                "identity": {
                    "actor_id": identity.actor_id if identity else user_id,
                    "tenant_id": identity.tenant_id if identity else tenant_id,
                    "permissions": sorted(identity.permissions)
                    if identity
                    else sorted(permissions or set()),
                    "groups": sorted(identity.groups) if identity else [],
                    "roles": sorted(identity.roles) if identity else [],
                    "subject_type": identity.subject_type if identity else "user",
                },
            },
        )
        db.add(execution)
        from app.services.conversation_service import conversation_service

        conversation_service.save_user_message(db, conversation_id, message)
        db.commit()
        db.refresh(execution)
        RUNTIME_EXECUTIONS.labels(status="pending").inc()

        execution = claim_execution(
            db,
            execution.id,
            worker_id=self.worker_id,
            expected_status="PENDING",
        )
        if execution is None:
            raise RuntimeError("Runtime execution could not be claimed")
        execution = self.transition_execution(
            execution.id,
            "RUNNING",
            expected_statuses={"PENDING"},
            worker_id=self.worker_id,
            ownership_attempt=execution.attempt,
            db=db,
        )

        execution_id = str(execution.id)
        self._owned_attempts[execution_id] = execution.attempt
        self._refresh_active_metric()
        logger.info(
            "Runtime execution claimed",
            extra={
                "execution_id": execution_id,
                "workflow_id": str(execution.workflow_id),
                "worker_id": self.worker_id,
                "attempt": execution.attempt,
                "lease_expires_at": execution.lease_expires_at,
            },
        )
        self._workflow_to_execution[str(execution.workflow_id)] = execution_id
        self._tasks[execution_id] = asyncio.create_task(
            self._execute_with_deadline(
                execution,
                message,
                permissions or set(),
                tenant_id,
                resolved_provider,
                resolved_model,
                None,
                {},
            )
        )
        return execution

    async def _execute_with_deadline(self, execution: RuntimeExecution, *args) -> None:
        execution_id = str(execution.id)
        attempt = self._owned_attempts.get(execution_id, execution.attempt)
        heartbeat = asyncio.create_task(self._heartbeat(execution_id, attempt))
        self._heartbeat_tasks[execution_id] = heartbeat
        deadline = execution.deadline_at
        budget_context = None
        usage: dict[str, int] = {}
        provider_invoked = False
        try:
            from contextlib import nullcontext

            from app.ai.governed_provider import authorized_provider_invocation
            from app.governance.budget_enforcement import (
                BudgetEnforcementError,
                budget_enforcement_service,
            )

            if settings.BUDGET_ENFORCEMENT_ENABLED:
                budget_context = self._budget_context(
                    execution,
                    str(args[0]) if args else execution.goal or "",
                    str(args[4]) if len(args) > 4 else execution.model_name or "",
                )
                with SessionLocal() as budget_db:
                    reservation = budget_enforcement_service.reserve(
                        budget_db, budget_context
                    )
                    selected_provider = reservation.model.provider
                    selected_model = reservation.model.provider_model_id
                routed_args = list(args)
                routed_args[3] = selected_provider
                routed_args[4] = selected_model
                args = tuple(routed_args)
            invocation = (
                authorized_provider_invocation(usage)
                if budget_context is not None
                else nullcontext()
            )
            with invocation:
                provider_invoked = budget_context is not None
                if deadline is None:
                    await self._execute(execution, *args)
                else:
                    remaining = (
                        deadline - datetime.now(UTC).replace(tzinfo=None)
                    ).total_seconds()
                    if remaining <= 0:
                        await self._timeout_execution(
                            execution_id,
                            "RUNTIME_TIMEOUT",
                            "Runtime execution deadline exceeded",
                        )
                    else:
                        try:
                            await asyncio.wait_for(
                                self._execute(execution, *args), timeout=remaining
                            )
                        except TimeoutError:
                            await self._timeout_execution(
                                execution_id,
                                "RUNTIME_TIMEOUT",
                                "Runtime execution deadline exceeded",
                            )
            if budget_context is not None:
                with SessionLocal() as budget_db:
                    if usage:
                        budget_enforcement_service.settle(
                            budget_db, budget_context, usage
                        )
                    else:
                        budget_enforcement_service.release(
                            budget_db, budget_context, "NO_PROVIDER_USAGE"
                        )
        except BudgetEnforcementError as exc:
            reason = ", ".join(exc.decision.get("reason_codes", ["BUDGET_BLOCKED"]))
            try:
                self.transition_execution(
                    execution_id,
                    "FAILED",
                    expected_statuses={"RUNNING"},
                    error_code="BUDGET_ENFORCEMENT_BLOCKED",
                    error_message=reason,
                    metadata={"budget_decision": exc.decision},
                    worker_id=self.worker_id,
                    ownership_attempt=attempt,
                )
            except (InvalidRuntimeTransitionError, RuntimeLeaseLostError):
                pass
        except Exception:
            if budget_context is not None:
                with SessionLocal() as budget_db:
                    if provider_invoked and usage:
                        budget_enforcement_service.settle(
                            budget_db, budget_context, usage
                        )
                    else:
                        budget_enforcement_service.release(
                            budget_db, budget_context, "RUNTIME_FAILED_BEFORE_USAGE"
                        )
            raise
        finally:
            heartbeat.cancel()
            await asyncio.gather(heartbeat, return_exceptions=True)
            self._heartbeat_tasks.pop(execution_id, None)
            self._owned_attempts.pop(execution_id, None)
            self._refresh_active_metric()

    def launch_recovered_execution(self, execution: RuntimeExecution) -> None:
        """Restart only a recovery-classified execution from its durable request."""
        execution_id = str(execution.id)
        metadata = dict(execution.runtime_metadata or {})
        inputs = dict(metadata.get("inputs") or {})
        selected = metadata.get("selected_agent")
        self._owned_attempts[execution_id] = execution.attempt
        self._refresh_active_metric()
        self._workflow_to_execution[str(execution.workflow_id)] = execution_id
        self._tasks[execution_id] = asyncio.create_task(
            self._execute_with_deadline(
                execution,
                execution.goal or "",
                set(metadata.get("permissions", [])),
                execution.tenant_id,
                execution.provider_name or settings.AI_PROVIDER,
                execution.model_name
                or self._resolve_model(
                    provider_name=execution.provider_name or settings.AI_PROVIDER,
                    model=None,
                ),
                selected,
                inputs,
            )
        )

    async def _heartbeat(self, execution_id: str, attempt: int) -> None:
        while True:
            await asyncio.sleep(settings.RUNTIME_HEARTBEAT_SECONDS)
            renewed = False
            for retry in range(3):
                try:
                    with SessionLocal() as db:
                        renewed = renew_execution_lease(
                            db,
                            execution_id,
                            worker_id=self.worker_id,
                            attempt=attempt,
                        )
                    break
                except Exception:
                    logger.exception(
                        "Runtime heartbeat failed",
                        extra={
                            "execution_id": execution_id,
                            "worker_id": self.worker_id,
                            "attempt": attempt,
                            "retry": retry + 1,
                        },
                    )
                    await asyncio.sleep(min(1, settings.RUNTIME_HEARTBEAT_SECONDS / 3))
            if not renewed:
                RUNTIME_LEASE_LOST.inc()
                logger.warning(
                    "Runtime lease lost",
                    extra={
                        "execution_id": execution_id,
                        "worker_id": self.worker_id,
                        "attempt": attempt,
                    },
                )
                task = self._tasks.get(execution_id)
                if task is not None and task is not asyncio.current_task():
                    task.cancel()
                return

    def _assert_local_ownership(self, execution_id: str) -> None:
        attempt = getattr(self, "_owned_attempts", {}).get(execution_id)
        if attempt is None:
            return
        with SessionLocal() as db:
            record = db.get(RuntimeExecution, UUID(execution_id))
            if record is None:
                raise RuntimeLeaseLostError("Runtime execution no longer exists")
            assert_execution_lease(
                record,
                worker_id=self.worker_id,
                attempt=attempt,
            )

    async def _timeout_execution(
        self, execution_id: str, code: str, message: str
    ) -> None:
        try:
            record = self.transition_execution(
                execution_id,
                "TIMED_OUT",
                error_code=code,
                error_message=message,
                metadata={
                    "timeout": {
                        "component": "runtime",
                        "timed_out_at": datetime.now(UTC).isoformat(),
                    }
                },
                worker_id=self.worker_id,
                ownership_attempt=self._owned_attempts.get(execution_id),
            )
        except (InvalidRuntimeTransitionError, RuntimeLeaseLostError):
            return
        await self.publish_step(
            execution_id,
            "Runtime Execution",
            message,
            "failed",
            final=True,
            message=message,
            duration_ms=record.duration_ms,
            error=message,
            error_code=code,
            terminal_status="TIMED_OUT",
        )

    @staticmethod
    def _select_agent(
        db: Session,
        *,
        tenant_id: str,
        goal: str,
        requested_agent_id: str | None,
        identity: AgentIdentity | None = None,
    ) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
        query = db.query(Agent).filter(
            Agent.tenant_id == tenant_id,
            Agent.lifecycle_status == "enabled",
            Agent.deleted_at.is_(None),
            Agent.published_version.is_not(None),
        )
        rows = query.all()
        if requested_agent_id:
            rows = [
                row
                for row in rows
                if requested_agent_id in {row.uuid, row.slug, str(row.id)}
            ]
            if not rows:
                raise ValueError("Selected agent is unavailable or not authorized")

        intent = RuntimeExecutionService._classify_intent(goal)
        permitted = set(identity.permissions) if identity else {"tools.admin"}
        capability_definitions = authorized_model_tools(permissions=permitted)
        capability_analysis = CapabilityIntelligence.fallback(
            goal, CapabilityIntelligence._catalog(capability_definitions)
        )
        terms = {
            part.strip(".,!?()[]").lower() for part in goal.split() if len(part) > 2
        }
        terms.add(intent["intent"].replace("_", " "))
        candidates: list[dict[str, Any]] = []
        for row in rows:
            if row.operational_health in {"unhealthy", "error", "offline"}:
                continue
            if identity is not None:
                try:
                    agent_application_service.resolve_runtime(db, identity, row.uuid)
                except Exception:
                    logger.debug(
                        "Skipping an unavailable runtime agent candidate",
                        extra={"agent_id": row.uuid},
                        exc_info=True,
                    )
                    continue
            version = (
                db.query(AgentVersion)
                .filter_by(
                    agent_id=row.id, version=row.published_version, published=True
                )
                .first()
            )
            if version is None:
                continue
            snapshot = version.configuration_snapshot or {}
            capabilities = snapshot.get(
                "capabilities"
            ) or row.planner_configuration.get("capabilities", [])
            tools = (
                db.query(AgentToolAssignment)
                .filter_by(agent_id=row.id, tenant_id=tenant_id, enabled=True)
                .all()
            )
            knowledge = (
                db.query(AgentKnowledgeAssignment)
                .filter_by(agent_id=row.id, tenant_id=tenant_id, enabled=True)
                .all()
            )
            searchable = " ".join(
                [
                    row.name,
                    row.description,
                    row.slug,
                    str(snapshot.get("instructions", "")),
                    str(snapshot.get("tags", "")),
                    str(snapshot.get("planner_configuration", "")),
                    str(snapshot.get("environment_restrictions", "")),
                    *map(str, capabilities),
                    *[item.tool_name for item in tools],
                    *[str(item.knowledge_source_id) for item in knowledge],
                ]
            ).lower()
            matches = sum(1 for term in terms if term in searchable)
            capability_matches = sum(
                1
                for capability in capabilities
                if any(term in str(capability).lower() for term in terms)
            )
            tool_matches = sum(
                1
                for item in tools
                if any(term in item.tool_name.lower() for term in terms)
            )
            resolved_tool_match = bool(
                capability_analysis.selected_tool
                and any(
                    item.tool_name == capability_analysis.selected_tool
                    for item in tools
                )
            )
            confidence = min(
                0.99,
                0.15
                + matches * 0.08
                + capability_matches * 0.15
                + tool_matches * 0.2
                + (0.55 if resolved_tool_match else 0),
            )
            candidate = {
                "agent_id": row.uuid,
                "name": row.name,
                "slug": row.slug,
                "capabilities": capabilities,
                "provider": (version.model_configuration or {}).get(
                    "provider", "openai"
                ),
                "model": (version.model_configuration or {}).get("model"),
                "confidence": round(1.0 if requested_agent_id else confidence, 2),
                "reason": "User selected this published agent"
                if requested_agent_id
                else (
                    "Owns the resolved registered capability and matches the request"
                    if resolved_tool_match
                    else "Matches the request intent, published capabilities, and assigned resources"
                    if matches
                    else "Eligible published agent"
                ),
                "model_configuration": version.model_configuration or {},
                "published_version": row.published_version,
                "tools": [item.tool_name for item in tools],
                "knowledge_source_count": len(knowledge),
            }
            candidates.append(candidate)
        candidates.sort(key=lambda item: item["confidence"], reverse=True)
        if requested_agent_id:
            return (candidates[0] if candidates else None), candidates
        selected = (
            candidates[0]
            if candidates
            and candidates[0]["confidence"] >= settings.AUTO_AGENT_MIN_CONFIDENCE
            else None
        )
        return selected, candidates

    @staticmethod
    def _resolve_provider_name(
        provider_name: str | None,
    ) -> str:
        provider = (provider_name or settings.AI_PROVIDER).strip().lower()

        if provider not in {"openai", "bedrock"}:
            raise ValueError(f"Unsupported AI provider: {provider}")

        return provider

    @staticmethod
    def _resolve_model(
        *,
        provider_name: str,
        model: str | None,
    ) -> str:
        if model and model.strip():
            return model.strip()

        if provider_name == "openai":
            return settings.OPENAI_MODEL

        if provider_name == "bedrock":
            return settings.BEDROCK_MODEL_ID

        raise ValueError(f"Unsupported AI provider: {provider_name}")

    def get_for_user(
        self,
        db: Session,
        execution_id: UUID,
        user_id: str,
        tenant_id: str | None = None,
    ) -> RuntimeExecution | None:
        query = db.query(RuntimeExecution).filter(
            RuntimeExecution.id == execution_id,
            RuntimeExecution.user_id == user_id,
        )
        if tenant_id is not None:
            query = query.filter(RuntimeExecution.tenant_id == tenant_id)
        return query.first()

    def expire_continuations(
        self, db: Session, execution: RuntimeExecution
    ) -> RuntimeExecution:
        if execution.status not in {"WAITING_FOR_INPUT", "WAITING_FOR_APPROVAL"}:
            return execution
        now = datetime.now(UTC).replace(tzinfo=None)
        continuation = (
            db.query(RuntimeContinuation)
            .filter(
                RuntimeContinuation.execution_id == execution.id,
                RuntimeContinuation.status == "pending",
                RuntimeContinuation.expires_at <= now,
            )
            .order_by(RuntimeContinuation.id)
            .with_for_update()
            .first()
        )
        if continuation is None:
            return execution
        code = (
            "APPROVAL_EXPIRED"
            if continuation.kind == "approval"
            else "CONTINUATION_EXPIRED"
        )
        execution = self.transition_execution(
            execution.id,
            "TIMED_OUT",
            expected_statuses={execution.status},
            error_code=code,
            error_message="Approval expired"
            if continuation.kind == "approval"
            else "Required input expired",
            metadata={
                "timeout": {
                    "component": "continuation",
                    "operation": continuation.kind,
                    "timed_out_at": datetime.now(UTC).isoformat(),
                }
            },
            db=db,
            commit=False,
        )
        continuation.status = "expired"
        continuation.consumed_at = now
        db.commit()
        db.refresh(execution)
        return execution

    @staticmethod
    def _runtime_metadata(execution_id: str) -> dict[str, Any]:
        db = SessionLocal()
        try:
            record = db.get(RuntimeExecution, UUID(execution_id))
            return dict(record.runtime_metadata or {}) if record else {}
        finally:
            db.close()

    @staticmethod
    def _matching_tool(
        message: str,
        tool_definitions: list[dict[str, Any]] | None = None,
        preferred: str | None = None,
    ) -> dict[str, Any] | None:
        if preferred:
            for definition in tool_definitions or []:
                function = definition.get("function") or {}
                if function.get("name") == preferred:
                    return function
        terms = {
            word.strip(".,!?()[]").lower() for word in message.split() if len(word) > 2
        }
        candidates = []
        for definition in tool_definitions or []:
            function = definition.get("function") or {}
            searchable = (
                f"{function.get('name', '')} {function.get('description', '')}".lower()
            )
            score = sum(1 for term in terms if term in searchable)
            if score:
                candidates.append((score, function))
        if not candidates:
            return None
        return max(candidates, key=lambda item: item[0])[1]

    @classmethod
    def _required_fields(
        cls,
        message: str,
        supplied: dict[str, Any],
        tool_definitions: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        """Derive missing fields from the best matching authorized tool JSON schema."""
        functions = [(item.get("function") or {}) for item in (tool_definitions or [])]
        function = (
            functions[0]
            if len(functions) == 1
            else cls._matching_tool(message, tool_definitions)
        )
        if function is None:
            return []
        schema = function.get("parameters") or {}
        properties = schema.get("properties") or {}
        fields = []
        for name in schema.get("required", []):
            if supplied.get(name) not in (None, "", []):
                continue
            item = properties.get(name, {})
            kind = item.get("type", "string")
            if kind == "string":
                kind = item.get("format", "text")
            if item.get("enum"):
                kind = "select"
            fields.append(
                {
                    "name": name,
                    "label": item.get("title") or name.replace("_", " ").title(),
                    "type": kind,
                    "required": True,
                    "options": item.get("enum", []),
                    "description": item.get("description"),
                    "tool": function.get("name"),
                }
            )
        return fields

    @staticmethod
    def _is_jira_create_request(message: str) -> bool:
        lowered = message.lower()
        return (
            "jira" in lowered
            and any(word in lowered for word in ("create", "add", "open"))
            and any(
                word in lowered for word in ("ticket", "issue", "bug", "task", "story")
            )
        )

    async def _execute_runtime_tool(
        self,
        execution_id: str,
        execution: RuntimeExecution,
        context: RuntimeContext,
        permissions: set[str],
        tenant_id: str,
        tool_name: str,
        inputs: dict[str, Any],
        *,
        stage: str = "default",
    ):
        tool = tool_registry.get(tool_name)
        category = "action" if str(tool.metadata.risk_level) != "read" else "tool"
        step_id = f"{category}:{tool_name}:{stage}"
        await self.publish_event(
            execution_id,
            {
                "type": f"{category}_started",
                "name": tool_name,
                "step_id": step_id,
                "description": f"Executing authorized {category}",
                "status": "running",
            },
        )
        tool_db = SessionLocal()
        try:
            self._assert_local_ownership(execution_id)
            envelope = await tool_executor.execute(
                tool_name,
                inputs,
                ToolExecutionContext(
                    actor_id=execution.user_id,
                    permissions=permissions,
                    tenant_id=tenant_id,
                    conversation_id=str(execution.conversation_id),
                    correlation_id=str(execution.workflow_id),
                    trace_id=context.trace_id,
                    idempotency_key=f"runtime:{execution_id}:{tool_name}:{stage}",
                ),
                tool_db,
            )
        except asyncio.CancelledError:
            await self.publish_event(
                execution_id,
                {
                    "type": f"{category}_cancelled",
                    "name": tool_name,
                    "step_id": step_id,
                    "description": f"{category.title()} execution was cancelled",
                    "status": "cancelled",
                    "error_code": "EXECUTION_CANCELLED",
                    "component_type": category,
                    "component_status": "CANCELLED",
                },
            )
            raise
        except Exception as exc:
            timed_out = isinstance(exc, (AITimeoutError, TimeoutError))
            await self.publish_event(
                execution_id,
                {
                    "type": f"{category}_{'timed_out' if timed_out else 'failed'}",
                    "name": tool_name,
                    "step_id": step_id,
                    "description": getattr(exc, "safe_message", None)
                    or "The tool could not complete the request",
                    "status": "timed_out" if timed_out else "failed",
                    "error_code": getattr(exc, "code", "TOOL_EXECUTION_FAILED"),
                    "component_type": category,
                    "component_status": "TIMED_OUT" if timed_out else "FAILED",
                },
            )
            raise
        finally:
            tool_db.close()
        if envelope.status != "succeeded":
            timed_out = envelope.status == "timed_out"
            await self.publish_event(
                execution_id,
                {
                    "type": f"{category}_{'timed_out' if timed_out else 'failed'}",
                    "name": tool_name,
                    "step_id": step_id,
                    "description": envelope.error.message
                    if envelope.error
                    else f"{category.title()} failed",
                    "status": "timed_out" if timed_out else "failed",
                    "duration_ms": envelope.meta.get("duration_ms"),
                    "error_code": envelope.error.code
                    if envelope.error
                    else "TOOL_EXECUTION_FAILED",
                    "tool_execution_id": envelope.execution_id,
                    "component_type": category,
                    "component_id": envelope.execution_id,
                    "component_status": "TIMED_OUT" if timed_out else "FAILED",
                },
            )
            if envelope.status == "timed_out":
                raise AITimeoutError(
                    envelope.error.message
                    if envelope.error
                    else "Tool execution timed out"
                )
            raise RuntimeError(
                envelope.error.message
                if envelope.error
                else f"{category.title()} execution failed"
            )
        await self.publish_event(
            execution_id,
            {
                "type": f"{category}_completed",
                "name": tool_name,
                "step_id": step_id,
                "description": f"Authorized {category} completed",
                "status": "completed",
                "duration_ms": envelope.meta.get("duration_ms"),
                "result_summary": envelope.data,
                "tool_execution_id": envelope.execution_id,
                "component_type": category,
                "component_id": envelope.execution_id,
                "component_status": "COMPLETED",
            },
        )
        return envelope.data

    async def _execute_jira_create_flow(
        self,
        execution_id: str,
        execution: RuntimeExecution,
        context: RuntimeContext,
        permissions: set[str],
        tenant_id: str,
        inputs: dict[str, Any],
        started_at: datetime,
        agent_name: str = "Governed Integration Runtime",
    ) -> None:
        await self.publish_step(
            execution_id,
            "Agent Selected",
            "Published agent owning the resolved Jira capability selected",
            "completed",
            agent=agent_name,
        )
        await self.publish_step(
            execution_id,
            "Planner",
            "Resolving Jira project, issue type, and create fields",
            "completed",
            agent=agent_name,
        )
        create_tool = tool_registry.get("jira.create_issue")
        create_definition = {
            "type": "function",
            "function": {
                "name": create_tool.metadata.name,
                "description": create_tool.metadata.description,
                "parameters": create_tool.metadata.parameters,
            },
        }
        base_missing = self._required_fields("", inputs, [create_definition])
        if not inputs.get("project_key"):
            await self._pause_for_input(execution_id, base_missing, inputs)
            return
        metadata_inputs = {"project_key": inputs["project_key"]}
        if inputs.get("issue_type_id"):
            metadata_inputs["issue_type_id"] = inputs["issue_type_id"]
        elif inputs.get("issue_type"):
            metadata_inputs["issue_type"] = inputs["issue_type"]
        metadata = await self._execute_runtime_tool(
            execution_id,
            execution,
            context,
            permissions,
            tenant_id,
            "jira.get_create_metadata",
            metadata_inputs,
            stage=str(
                inputs.get("issue_type_id") or inputs.get("issue_type") or "issue-types"
            ),
        )
        if not inputs.get("issue_type") and not inputs.get("issue_type_id"):
            options = [
                {"label": item["name"], "value": item["name"]}
                for item in metadata.get("issue_types", [])
                if item.get("name")
            ]
            if not options:
                raise RuntimeError("No Jira issue types are available for this project")
            enriched = []
            for field in base_missing:
                if field["name"] == "issue_type":
                    field = {
                        **field,
                        "type": "select",
                        "options": options,
                        "description": "Issue type available in this Jira project",
                    }
                enriched.append(field)
            await self._pause_for_input(execution_id, enriched, inputs)
            return
        selected = metadata.get("selected_issue_type") or {}
        inputs = {
            **inputs,
            "issue_type": selected.get("name") or inputs.get("issue_type"),
            "issue_type_id": selected.get("id") or inputs.get("issue_type_id"),
        }
        missing = self._required_fields("", inputs, [create_definition])
        ignored = {"project", "issuetype", "summary", "reporter"}
        for field in metadata.get("fields", []):
            field_id = field.get("fieldId") or field.get("key")
            if (
                not field_id
                or field_id in ignored
                or not field.get("required")
                or field.get("hasDefaultValue")
            ):
                continue
            if inputs.get(field_id) in (None, "", []):
                allowed = field.get("allowedValues") or []
                options = [
                    {
                        "label": str(item.get("name") or item.get("value") or item),
                        "value": str(item.get("id") or item.get("value") or item),
                    }
                    for item in allowed
                ]
                missing.append(
                    {
                        "name": field_id,
                        "label": field.get("name") or field_id,
                        "type": "select" if options else "text",
                        "required": True,
                        "options": options,
                        "description": f"Required by Jira for {inputs['issue_type']}",
                    }
                )
        if missing:
            await self._pause_for_input(execution_id, missing, inputs)
            return
        known = {
            "project_key",
            "issue_type",
            "issue_type_id",
            "summary",
            "description",
            "priority",
            "assignee",
            "labels",
        }
        action_inputs = {
            key: value
            for key, value in inputs.items()
            if key in known and value not in (None, "", [])
        }
        action_inputs["jira_fields"] = {
            key: value
            for key, value in inputs.items()
            if key not in known and value not in (None, "", [])
        }
        issue = await self._execute_runtime_tool(
            execution_id,
            execution,
            context,
            permissions,
            tenant_id,
            "jira.create_issue",
            action_inputs,
            stage="create",
        )
        issue_key = issue.get("key")
        message = f"Created Jira issue {issue_key}." + (
            f" {issue.get('browse_url')}" if issue.get("browse_url") else ""
        )
        duration_ms = round((datetime.now(UTC) - started_at).total_seconds() * 1000, 2)
        self._complete_execution(
            execution_id,
            status="COMPLETED",
            agent=agent_name,
            message=message,
            duration_ms=duration_ms,
        )
        await self.publish_event(
            execution_id,
            {
                "type": "completed",
                "name": "Result Generated",
                "step_id": "result-generation",
                "description": "Jira issue created successfully",
                "status": "completed",
                "agent": agent_name,
                "duration_ms": duration_ms,
                "message": message,
                "final": True,
            },
        )

    async def _pause_for_input(
        self,
        execution_id: str,
        fields: list[dict[str, Any]],
        known_values: dict[str, Any],
        *,
        parameter_state_version: int | None = None,
        input_requirements: dict[str, Any] | None = None,
        canonical_metadata: dict[str, Any] | None = None,
    ) -> None:
        # Make the observable WAITING state and its canonical interpretation one
        # transaction boundary. Readers must never see a continuation before the
        # intent/parameter metadata used to create it is durable.
        canonical_metadata = canonical_metadata or self._runtime_metadata(execution_id)
        db = SessionLocal()
        created = False
        try:
            record = db.get(RuntimeExecution, UUID(execution_id))
            if record is None:
                return
            field_names = [field["name"] for field in fields]
            existing = (
                db.query(RuntimeContinuation)
                .filter_by(execution_id=record.id, kind="input", status="pending")
                .order_by(RuntimeContinuation.created_at.desc())
                .first()
            )
            if (
                existing is not None
                and existing.schema.get("parameter_state_version")
                == parameter_state_version
                and [field.get("name") for field in existing.schema.get("fields", [])]
                == field_names
            ):
                return
            continuation = self._build_input_continuation(
                record,
                fields,
                known_values,
                parameter_state_version=parameter_state_version or 1,
                input_requirements=input_requirements or {},
            )
            db.add(continuation)
            self.transition_execution(
                record.id,
                "WAITING_FOR_INPUT",
                expected_statuses={"RUNNING"},
                reason="required_input",
                worker_id=self.worker_id,
                ownership_attempt=self._owned_attempts.get(execution_id),
                metadata={
                    key: canonical_metadata[key]
                    for key in (
                        "intent_analysis",
                        "parameter_extraction",
                        "parameter_state",
                        "input_requirements",
                    )
                    if key in canonical_metadata
                },
                db=db,
                commit=False,
            )
            record.current_step = "Collect Information"
            required_input_event = self._append_runtime_event_locked(
                db,
                record,
                self._required_input_event(
                    continuation,
                    continuation.schema["fields"],
                    known_values,
                ),
            )
            db.commit()
            created = True
        finally:
            db.close()
        if not created:
            return
        INPUT_REQUIREMENT_WAITS.inc()
        # Downstream delivery happens only after the state, continuation and
        # required-input event have committed as one durable unit.
        await self._tracker.publish(execution_id, required_input_event)

    @staticmethod
    def _build_input_continuation(
        record: RuntimeExecution,
        fields: list[dict[str, Any]],
        known_values: dict[str, Any],
        *,
        parameter_state_version: int,
        input_requirements: dict[str, Any],
    ) -> RuntimeContinuation:
        properties: dict[str, Any] = {}
        required: list[str] = []
        for field in fields:
            definition = dict(field.get("validation") or {})
            if not definition:
                definition["type"] = {
                    "text": "string",
                    "textarea": "string",
                    "select": "string",
                    "integer": "integer",
                    "number": "number",
                    "boolean": "boolean",
                    "multiselect": "array",
                    "date": "string",
                }.get(field.get("type", "text"), "string")
            if field.get("options"):
                definition["enum"] = [
                    option.get("value") if isinstance(option, dict) else option
                    for option in field["options"]
                ]
            properties[field["name"]] = definition
            if field.get("required"):
                required.append(field["name"])
        intent_name = RuntimeExecutionService._assert_semantic_consistency(
            dict(record.runtime_metadata or {}),
            continuation_intent=input_requirements.get("intent"),
            execution_id=str(record.id),
        )
        unresolved = [
            *input_requirements.get("missing", []),
            *input_requirements.get("ambiguous", []),
            *input_requirements.get("invalid", []),
        ]
        expected_fields = [item["name"] for item in unresolved]
        actual_fields = [field["name"] for field in fields]
        if unresolved and (
            len(actual_fields) != len(set(actual_fields))
            or set(actual_fields) != set(expected_fields)
        ):
            raise ContinuationSchemaMismatchError(
                "Continuation fields do not match canonical input requirements"
            )
        title, description = RuntimeExecutionService._continuation_prompt(
            intent_name, fields
        )
        metadata = dict(record.runtime_metadata or {})
        capability = (
            (metadata.get("capability_resolution") or {}).get("selected") or {}
        ).get("name")
        return RuntimeContinuation(
            execution_id=record.id,
            tenant_id=record.tenant_id,
            kind="input",
            schema={
                "type": "object",
                "properties": properties,
                "required": required,
                "additionalProperties": True,
                "fields": fields,
                "requested_fields": actual_fields,
                "plan_id": metadata.get("plan_id"),
                "intent": intent_name,
                "capability": capability,
                "parameter_state_version": parameter_state_version,
                "input_requirements": input_requirements,
                "title": title,
                "description": description,
            },
            known_values=known_values,
            expires_at=datetime.now(UTC).replace(tzinfo=None) + timedelta(hours=24),
        )

    async def _publish_required_input(
        self,
        execution_id: str,
        continuation: RuntimeContinuation,
        fields: list[dict[str, Any]],
        known_values: dict[str, Any],
    ) -> None:
        await self.publish_event(
            execution_id,
            self._required_input_event(continuation, fields, known_values),
        )

    def _required_input_event(
        self,
        continuation: RuntimeContinuation,
        fields: list[dict[str, Any]],
        known_values: dict[str, Any],
    ) -> dict[str, Any]:
        intent_name = continuation.schema.get("intent") or ""
        title, description = self._continuation_prompt(intent_name, fields)
        return {
            "type": "required_input",
            "name": "Additional Information Required",
            "step_id": "required-information",
            "title": title,
            "description": description,
            "status": "waiting",
            "continuation_id": str(continuation.id),
            "fields": fields,
            "known_values": known_values,
            "intent": intent_name,
            "parameter_state_version": continuation.schema.get(
                "parameter_state_version"
            ),
            "final": False,
        }

    @staticmethod
    def _continuation_prompt(
        intent_name: str | None, fields: list[dict[str, Any]]
    ) -> tuple[str, str]:
        parts = (intent_name or "").split(".")
        domain = parts[0].title() if parts and parts[0] else ""
        resource = parts[1].replace("_", " ").title() if len(parts) > 1 else ""
        labels = [field["label"] for field in fields]
        if len(labels) == 1:
            description = f"Please provide {labels[0]}."
        elif labels:
            description = f"I still need {', '.join(labels[:-1])} and {labels[-1]}."
        else:
            description = "Please provide the unresolved values needed to continue."
        title = (
            f"{domain} {resource} details required"
            if domain and resource
            else "Additional information required"
        )
        return title, description

    @staticmethod
    def _assert_semantic_consistency(
        metadata: dict[str, Any],
        *,
        continuation_intent: str | None = None,
        execution_id: str | None = None,
    ) -> str:
        """Fail closed when authoritative intelligence identities diverge."""
        selected = (metadata.get("capability_resolution") or {}).get("selected") or {}
        identities = {
            "intent_analysis": (metadata.get("intent_analysis") or {}).get("intent"),
            "parameter_state": (metadata.get("parameter_state") or {}).get("intent"),
            "input_requirements": (metadata.get("input_requirements") or {}).get(
                "intent"
            ),
            "continuation": continuation_intent,
            "capability_resolution": selected.get("semantic_capability"),
        }
        populated = {key: value for key, value in identities.items() if value}
        unique = set(populated.values())
        if len(unique) != 1:
            logger.error(
                "Runtime semantic identities disagree",
                extra={
                    "execution_id": execution_id,
                    "semantic_identities": populated,
                    "error_code": SemanticConsistencyError.code,
                },
            )
            raise SemanticConsistencyError(
                "Runtime semantic state is inconsistent; continuation was not applied"
            )
        if not unique:
            raise SemanticConsistencyError(
                "Runtime semantic identity is missing; continuation was not applied"
            )
        return next(iter(unique))

    async def _pause_for_approval(
        self, execution_id: str, inputs: dict[str, Any]
    ) -> None:
        db = SessionLocal()
        try:
            record = db.get(RuntimeExecution, UUID(execution_id))
            if record is None:
                return
            continuation = RuntimeContinuation(
                execution_id=record.id,
                tenant_id=record.tenant_id,
                kind="approval",
                schema={"type": "approval", "action": "send_email"},
                known_values=inputs,
                required_role="runtime.approver",
                expires_at=datetime.now(UTC).replace(tzinfo=None) + timedelta(hours=4),
            )
            db.add(continuation)
            self.transition_execution(
                record.id,
                "WAITING_FOR_APPROVAL",
                expected_statuses={"RUNNING"},
                reason="approval_required",
                worker_id=self.worker_id,
                ownership_attempt=self._owned_attempts.get(execution_id),
                db=db,
                commit=False,
            )
            record.current_step = "Approval Check"
            db.commit()
            continuation_id = str(continuation.id)
        finally:
            db.close()
        await self.publish_event(
            execution_id,
            {
                "type": "approval_required",
                "name": "Send report approval",
                "description": "Sending the generated report is a governed business action.",
                "status": "waiting",
                "continuation_id": continuation_id,
                "action": "send_email",
                "risk": "medium",
                "business_impact": "Sends report data to external recipients",
                "required_role": "runtime.approver",
                "requested_parameters": {"recipients": inputs.get("recipients")},
                "summary": "Approve sending the deployment report to the confirmed recipients.",
                "final": False,
            },
        )

    async def continue_execution(
        self,
        db: Session,
        *,
        execution_id: UUID,
        user_id: str,
        continuation_id: UUID,
        values: dict[str, Any],
        action: str = "input",
        message: str | None = None,
        resume_identity: AgentIdentity | None = None,
        tenant_id: str | None = None,
    ) -> RuntimeExecution | None:
        if resume_identity is not None and action in {"approve", "deny"}:
            record = (
                db.query(RuntimeExecution)
                .filter_by(id=execution_id, tenant_id=resume_identity.tenant_id)
                .with_for_update()
                .first()
            )
        else:
            record = (
                db.query(RuntimeExecution)
                .filter(
                    RuntimeExecution.id == execution_id,
                    RuntimeExecution.user_id == user_id,
                    *(
                        [RuntimeExecution.tenant_id == tenant_id]
                        if tenant_id is not None
                        else []
                    ),
                )
                .with_for_update()
                .first()
            )
        if record is None:
            return None
        expected_status = (
            "WAITING_FOR_APPROVAL"
            if action in {"approve", "deny"}
            else "WAITING_FOR_INPUT"
        )
        if record.status != expected_status:
            raise ValueError(f"Execution is not in {expected_status} state")
        continuation = (
            db.query(RuntimeContinuation)
            .filter_by(id=continuation_id, execution_id=execution_id, status="pending")
            .with_for_update()
            .first()
        )
        if continuation is not None and continuation.expires_at < datetime.now(
            UTC
        ).replace(tzinfo=None):
            self.expire_continuations(db, record)
            raise ValueError("Continuation is invalid or expired")
        if continuation is None:
            raise ValueError("Continuation is invalid or expired")
        metadata = dict(record.runtime_metadata or {})
        if (
            action == "input"
            and continuation.kind == "input"
            and isinstance(metadata.get("parameter_state"), dict)
            and continuation.schema.get("parameter_state_version") is not None
        ):
            return await self._continue_canonical_input(
                db,
                record=record,
                continuation=continuation,
                values=values,
                message=message,
                user_id=user_id,
                resume_identity=resume_identity,
            )
        ownership_attempt = claim_locked_execution(record, worker_id=self.worker_id)
        execution_key = str(record.id)
        self._owned_attempts[execution_key] = ownership_attempt
        self._refresh_active_metric()
        agent_execution_id = continuation.schema.get("agent_execution_id")
        if agent_execution_id:
            metadata = dict(record.runtime_metadata or {})
            identity = resume_identity or self._identity(metadata)
            token = continuation.known_values.get("_resume_token")
            if not token:
                raise ValueError("Continuation cannot be resumed")
            result = await agent_execution_service.resume(
                db,
                execution_id=agent_execution_id,
                token=token,
                response=values,
                identity=identity,
                action=action,
            )
            continuation.status = "consumed"
            continuation.response = values
            continuation.consumed_at = datetime.now(UTC).replace(tzinfo=None)
            self.transition_execution(
                record.id,
                "RUNNING",
                expected_statuses={expected_status},
                worker_id=self.worker_id,
                ownership_attempt=ownership_attempt,
                db=db,
                commit=False,
            )
            db.commit()
            await self.publish_event(
                str(record.id),
                {
                    "type": "step",
                    "name": "Required Information",
                    "step_id": "required-information",
                    "description": "Submitted information was validated",
                    "status": "completed",
                },
            )
            await self.publish_event(
                str(record.id),
                {
                    "type": "step",
                    "name": "Runtime Resumed",
                    "step_id": "runtime-resumed",
                    "description": "Governed continuation accepted",
                    "status": "completed",
                },
            )
            await self._map_agent_result(
                str(record.id), record, metadata.get("selected_agent") or {}, result
            )
            return record
        fields = continuation.schema.get("fields", [])
        if set(values) == {"natural_language"} and isinstance(
            values.get("natural_language"), str
        ):
            pending_schema = {
                "type": "object",
                "properties": continuation.schema.get("properties", {}),
                "required": continuation.schema.get("required", []),
                "additionalProperties": False,
            }
            text = values["natural_language"].strip()
            extracted = CapabilityIntelligence._extract_schema_values(
                text, pending_schema
            )
            if len(fields) == 1 and not extracted:
                extracted[fields[0]["name"]] = text
            values = extracted
        missing = [
            field["name"]
            for field in fields
            if field.get("required") and values.get(field["name"]) in (None, "", [])
        ]
        if missing:
            raise ValueError(f"Missing required values: {', '.join(missing)}")
        if not agent_execution_id:
            try:
                validate_json(
                    {**continuation.known_values, **values},
                    {k: v for k, v in continuation.schema.items() if k != "fields"},
                )
            except JSONSchemaValidationError as exc:
                raise ValueError(f"Invalid continuation input: {exc.message}") from exc
        continuation.status = "consumed"
        continuation.response = values
        continuation.consumed_at = datetime.now(UTC).replace(tzinfo=None)
        self.transition_execution(
            record.id,
            "RUNNING",
            expected_statuses={expected_status},
            worker_id=self.worker_id,
            ownership_attempt=ownership_attempt,
            db=db,
            commit=False,
        )
        metadata = dict(record.runtime_metadata or {})
        metadata["inputs"] = {**continuation.known_values, **values}
        if continuation.kind == "approval":
            metadata["approval_granted"] = True
        record.runtime_metadata = metadata
        db.commit()
        append_audit_event(
            db,
            tenant_id=record.tenant_id,
            actor_id=user_id,
            action="runtime.input_provided",
            target_type="runtime_execution",
            target_id=str(record.id),
            correlation_id=str(record.workflow_id),
            metadata={
                "continuation_id": str(continuation.id),
                "fields": sorted(values),
            },
        )
        db.commit()
        await self.publish_event(
            str(record.id),
            {
                "type": "step",
                "name": "Required Information",
                "step_id": "required-information",
                "description": "Submitted information was validated",
                "status": "completed",
                "final": False,
            },
        )
        await self.publish_event(
            str(record.id),
            {
                "type": "step",
                "name": "Runtime Resumed",
                "step_id": "runtime-resumed",
                "description": "Execution resumed from the blocked plan step",
                "status": "completed",
                "final": False,
            },
        )
        selected = metadata.get("selected_agent")
        self._workflow_to_execution[str(record.workflow_id)] = execution_key
        self._tasks[execution_key] = asyncio.create_task(
            self._execute_with_deadline(
                record,
                record.goal or "",
                set(metadata.get("permissions", [])),
                record.tenant_id,
                record.provider_name or settings.AI_PROVIDER,
                record.model_name
                or self._resolve_model(
                    provider_name=record.provider_name or settings.AI_PROVIDER,
                    model=None,
                ),
                selected,
                metadata["inputs"],
            )
        )
        return record

    async def _continue_canonical_input(
        self,
        db: Session,
        *,
        record: RuntimeExecution,
        continuation: RuntimeContinuation,
        values: dict[str, Any],
        message: str | None,
        user_id: str,
        resume_identity: AgentIdentity | None,
    ) -> RuntimeExecution:
        """Apply form or natural-language input to the same canonical execution."""
        started = monotonic()
        metadata = dict(record.runtime_metadata or {})
        previous_state = metadata["parameter_state"]
        stored_requirements = continuation.schema.get("input_requirements") or {}
        schema_payload = stored_requirements.get("requirement_schema")
        fields = continuation.schema.get("fields", [])
        mode = "natural_language" if message is not None else "structured"
        if message is not None:
            interpreted = await asyncio.to_thread(
                continuation_interpreter.interpret_natural_language,
                message,
                fields,
                intent=previous_state.get("intent"),
                provider_name=record.provider_name or settings.AI_PROVIDER,
                model=record.model_name
                or self._resolve_model(
                    provider_name=record.provider_name or settings.AI_PROVIDER,
                    model=None,
                ),
                known_parameters=list(previous_state.get("parameters", {})),
            )
        else:
            interpreted = continuation_interpreter.interpret_structured(values, fields)

        if interpreted.user_cancelled or interpreted.intent_changed:
            old_execution_id = record.id
            old_intent = (
                continuation.schema.get("intent")
                or previous_state.get("intent")
                or (metadata.get("intent_analysis") or {}).get("intent")
            )
            conversation_id = record.conversation_id
            tenant_id = record.tenant_id
            provider_name = record.provider_name
            model_name = record.model_name
            workspace_id = record.workspace_id
            permissions = set(metadata.get("permissions", []))
            continuation.status = "cancelled"
            continuation.consumed_at = datetime.now(UTC).replace(tzinfo=None)
            reason = (
                "intent_changed" if interpreted.intent_changed else "user_cancelled"
            )
            record = self.transition_execution(
                record.id,
                "CANCELLED",
                expected_statuses={"WAITING_FOR_INPUT"},
                reason=reason,
                result_message="Execution cancelled by user.",
                event_payload={
                    "continuation_id": str(continuation.id),
                    "intent_changed": interpreted.intent_changed,
                    "submission_type": mode,
                },
                db=db,
                commit=False,
            )
            if interpreted.intent_changed:
                append_audit_event(
                    db,
                    tenant_id=tenant_id,
                    actor_id=user_id,
                    action="runtime.continuation.intent_changed",
                    target_type="runtime_execution",
                    target_id=str(old_execution_id),
                    correlation_id=str(record.workflow_id),
                    metadata={
                        "continuation_id": str(continuation.id),
                        "old_intent": old_intent,
                        "new_request_detected": True,
                        "handoff_outcome": "old_execution_cancelled",
                    },
                )
            db.commit()
            CONTINUATION_RESPONSES.labels(mode, "cancelled").inc()
            CONTINUATION_ROUNDS.labels("cancelled").inc()
            CONTINUATION_LATENCY.observe(monotonic() - started)
            if interpreted.intent_changed:
                new_message = (interpreted.new_message or message or "").strip()
                if not new_message:
                    raise ValueError("A new request message is required for handoff")
                return await self.start(
                    db,
                    user_id=user_id,
                    message=new_message,
                    conversation_id=conversation_id,
                    permissions=permissions,
                    tenant_id=tenant_id,
                    provider_name=provider_name,
                    model=model_name,
                    identity=resume_identity,
                    workspace_id=workspace_id,
                    metadata={
                        "continuation_handoff": {
                            "cancelled_execution_id": str(old_execution_id),
                            "old_intent": old_intent,
                        }
                    },
                )
            return record

        # Legacy/inconsistent state may always be abandoned above, but applying
        # an answer remains fail-closed against the persisted semantic contract.
        authoritative_intent = self._assert_semantic_consistency(
            metadata,
            continuation_intent=continuation.schema.get("intent"),
            execution_id=str(record.id),
        )
        schema_intent = (schema_payload or {}).get("intent")
        if schema_intent and schema_intent != authoritative_intent:
            logger.error(
                "Continuation requirement schema has a different semantic identity",
                extra={
                    "execution_id": str(record.id),
                    "continuation_id": str(continuation.id),
                    "authoritative_intent": authoritative_intent,
                    "schema_intent": schema_intent,
                    "error_code": SemanticConsistencyError.code,
                },
            )
            raise SemanticConsistencyError(
                "Runtime semantic state is inconsistent; continuation was not applied"
            )
        expected_version = continuation.schema.get("parameter_state_version")
        if previous_state.get("version") != expected_version:
            raise ValueError(
                "Continuation is stale because the parameter state has changed"
            )

        if not interpreted.values:
            continuation.schema = {
                **continuation.schema,
                "validation_feedback": {
                    "unresolved_fields": interpreted.unresolved_fields,
                    "invalid_fields": interpreted.invalid_fields,
                    "warnings": interpreted.warnings,
                    "error_code": interpreted.error_code,
                },
            }
            db.commit()
            if interpreted.error_code:
                CONTINUATION_INTERPRETATION_FAILURES.inc()
            CONTINUATION_RESPONSES.labels(mode, "invalid").inc()
            CONTINUATION_ROUNDS.labels("still_waiting").inc()
            CONTINUATION_LATENCY.observe(monotonic() - started)
            await self.publish_event(
                str(record.id),
                {
                    "type": "continuation.response_received",
                    "name": "Continuation Response",
                    "description": "The response did not resolve a requested field",
                    "status": "waiting",
                    "invalid_fields": interpreted.invalid_fields,
                    "unresolved_fields": interpreted.unresolved_fields,
                    "error_code": interpreted.error_code,
                    "final": False,
                },
            )
            return record

        intent_analysis = metadata.get("intent_analysis") or {}
        domain = str(intent_analysis.get("domain") or "unknown")
        candidates = [
            ParameterCandidate(
                name=name,
                value=item.value,
                value_type=item.value_type,
                source="structured_input",
                confidence=item.confidence,
                explicit=True,
                domain=domain,
            )
            for name, item in interpreted.values.items()
        ]
        extraction = {
            "intent": previous_state.get("intent"),
            "parameters": {},
            "unresolved_mentions": [],
            "warnings": interpreted.warnings,
            "source": "llm",
            "error_code": None,
        }
        next_state = parameter_reconciler.reconcile(
            intent_analysis,
            extraction,
            additional_candidates=candidates,
            existing_state=previous_state,
            execution_id=str(record.id),
        )
        schema = (
            InputRequirementSchema.model_validate(schema_payload)
            if schema_payload
            else None
        )
        requirements = missing_field_resolver.evaluate(
            next_state, schema, execution_id=str(record.id)
        )
        requirement_payload = requirements.model_dump(mode="json")
        requirement_payload["parameter_state_version"] = next_state.version
        continuation.status = "consumed"
        continuation.response = {
            name: item.value for name, item in interpreted.values.items()
        }
        continuation.consumed_at = datetime.now(UTC).replace(tzinfo=None)
        canonical_values = {
            name: item.value
            for name, item in next_state.parameters.items()
            if item.status == "RESOLVED"
        }
        metadata = {
            **metadata,
            "parameter_state": next_state.model_dump(mode="json"),
            "input_requirements": requirement_payload,
            "inputs": canonical_values,
        }
        record.runtime_metadata = metadata

        next_continuation = None
        if requirements.complete is False:
            next_fields = self._requirement_fields(requirement_payload)
            next_continuation = self._build_input_continuation(
                record,
                next_fields,
                canonical_values,
                parameter_state_version=next_state.version,
                input_requirements=requirement_payload,
            )
            db.add(next_continuation)
            db.query(RuntimeContinuation).filter(
                RuntimeContinuation.execution_id == record.id,
                RuntimeContinuation.kind == "input",
                RuntimeContinuation.status == "pending",
                RuntimeContinuation.id != continuation.id,
            ).update(
                {
                    "status": "superseded",
                    "consumed_at": datetime.now(UTC).replace(tzinfo=None),
                },
                synchronize_session=False,
            )
            record.current_step = "Collect Information"
        else:
            ownership_attempt = claim_locked_execution(record, worker_id=self.worker_id)
            execution_key = str(record.id)
            self._owned_attempts[execution_key] = ownership_attempt
            self._refresh_active_metric()
            self.transition_execution(
                record.id,
                "RUNNING",
                expected_statuses={"WAITING_FOR_INPUT"},
                worker_id=self.worker_id,
                ownership_attempt=ownership_attempt,
                db=db,
                commit=False,
            )
        db.commit()

        await self.publish_event(
            str(record.id),
            {
                "type": "continuation.response_received",
                "name": "Continuation Response",
                "description": "Requested information was received",
                "status": "completed",
                "submission_type": mode,
                "updated_fields": sorted(interpreted.values),
                "final": False,
            },
        )
        await self.publish_event(
            str(record.id),
            {
                "type": "parameter_reconciliation.updated",
                "name": "Parameter State Updated",
                "description": "Continuation values merged into canonical state",
                "status": "completed",
                "parameter_state_version": next_state.version,
                "updated_fields": sorted(interpreted.values),
                "remaining_missing_count": len(requirements.unresolved_fields()),
                "final": False,
            },
        )
        await self.publish_event(
            str(record.id),
            {
                "type": "input_requirements.evaluated",
                "name": "Input Requirements",
                "description": "Input requirements re-evaluated",
                "status": "completed",
                "complete": requirements.complete,
                "missing": [item.name for item in requirements.missing],
                "ambiguous": [item.name for item in requirements.ambiguous],
                "invalid": [item.name for item in requirements.invalid],
                "final": False,
            },
        )
        if next_continuation is not None:
            await self._publish_required_input(
                str(record.id), next_continuation, next_fields, canonical_values
            )
            outcome = "still_waiting"
        else:
            selected = metadata.get("selected_agent")
            execution_key = str(record.id)
            self._workflow_to_execution[str(record.workflow_id)] = execution_key
            self._tasks[execution_key] = asyncio.create_task(
                self._execute_with_deadline(
                    record,
                    record.goal or "",
                    set(metadata.get("permissions", [])),
                    record.tenant_id,
                    record.provider_name or settings.AI_PROVIDER,
                    record.model_name
                    or self._resolve_model(
                        provider_name=record.provider_name or settings.AI_PROVIDER,
                        model=None,
                    ),
                    selected,
                    canonical_values,
                )
            )
            outcome = "complete"
        CONTINUATION_RESPONSES.labels(mode, outcome).inc()
        CONTINUATION_ROUNDS.labels(outcome).inc()
        CONTINUATION_LATENCY.observe(monotonic() - started)
        return record

    async def cancel(
        self,
        db: Session,
        *,
        execution_id: UUID,
        user_id: str,
        tenant_id: str | None = None,
    ) -> RuntimeExecution | None:
        """Cancel an owned execution and notify every connected SSE consumer."""
        execution = self.get_for_user(db, execution_id, user_id, tenant_id)
        if execution is None:
            return None
        if execution.status in self._TERMINAL_STATUSES:
            return execution

        execution_key = str(execution_id)
        execution = self.transition_execution(
            execution_id,
            "CANCELLED",
            expected_statuses={
                "PENDING",
                "RUNNING",
                "WAITING_FOR_INPUT",
                "WAITING_FOR_APPROVAL",
            },
            reason="user_cancelled",
            result_message="Execution cancelled by user.",
            db=db,
            commit=False,
        )
        if db is not None:
            db.query(RuntimeContinuation).filter_by(
                execution_id=execution_id, status="pending"
            ).update(
                {
                    "status": "cancelled",
                    "consumed_at": datetime.now(UTC).replace(tzinfo=None),
                }
            )
            db.commit()
            db.refresh(execution)
        await self.publish_step(
            execution_key,
            name="Runtime Execution",
            description="Execution cancelled by user",
            status="cancelled",
            final=True,
            message="Execution cancelled by user.",
            duration_ms=execution.duration_ms,
        )
        task = self._tasks.get(execution_key)
        if task is not None and not task.done():
            task.cancel()
        return execution

    async def _execute(
        self,
        execution: RuntimeExecution,
        message: str,
        permissions: set[str],
        tenant_id: str,
        provider_name: str,
        model: str,
        selected_agent: dict[str, Any] | None,
        supplied_inputs: dict[str, Any],
    ) -> None:
        """Run outside the request lifecycle using a fresh database session."""
        execution_id = str(execution.id)
        started_at = datetime.now(UTC)
        visible_tool_definitions = authorized_model_tools(permissions=permissions)
        context = RuntimeContext(
            request_id=uuid4(),
            workflow_id=execution.workflow_id,
            session_id=uuid4(),
            conversation_id=execution.conversation_id,
            tenant_id=tenant_id,
            user_id=execution.user_id,
            goal=message,
            trace_id=str(uuid4()),
            available_agents=[selected_agent["slug"]]
            if selected_agent
            else ["default-agent"],
            available_tools=[
                item["function"]["name"] for item in visible_tool_definitions
            ],
            metadata={
                "tool_definitions": visible_tool_definitions,
                "ai_provider": provider_name,
                "ai_model": model,
                "inputs": supplied_inputs,
            },
        )

        try:
            await self.publish_step(
                execution_id,
                name="Request Received",
                description="User prompt received",
                status="completed",
                provider=provider_name,
                model=model,
            )
            if selected_agent:
                await self.publish_step(
                    execution_id,
                    name="Agent Selected",
                    description=selected_agent["reason"],
                    status="completed",
                    agent=selected_agent["name"],
                    agent_id=selected_agent["agent_id"],
                    confidence=selected_agent["confidence"],
                    selection_mode=(
                        self._runtime_metadata(execution_id).get("selection_mode")
                        or "automatic"
                    ),
                    selection_reason=selected_agent["reason"],
                    capabilities=selected_agent.get("capabilities", []),
                    assigned_tools=selected_agent.get("tools", []),
                    knowledge_source_count=selected_agent.get(
                        "knowledge_source_count", 0
                    ),
                    candidates=[
                        {k: v for k, v in item.items() if k != "model_configuration"}
                        for item in self._runtime_metadata(execution_id).get(
                            "agent_candidates", []
                        )
                    ],
                    provider=provider_name,
                    model=model,
                )
            conversation_context = await asyncio.to_thread(
                self._load_conversation_context,
                execution.conversation_id,
                execution.user_id,
            )
            if (
                conversation_context
                and conversation_context[-1].get("role") == "user"
                and conversation_context[-1].get("content", "").strip()
                == message.strip()
            ):
                # The API persists the current message before runtime startup. It is
                # request input, not prior conversation context.
                conversation_context = conversation_context[:-1]
            await self.publish_step(
                execution_id,
                name="Conversation API",
                description="Conversation context loaded",
                status="completed",
            )

            runtime_metadata = self._runtime_metadata(execution_id)
            structured_analysis = await self._classify_intent_once(
                execution_id,
                message,
                provider_name=provider_name,
                model=model,
                conversation_context=conversation_context,
                visible_tool_definitions=visible_tool_definitions,
                runtime_metadata=runtime_metadata,
            )
            parameter_extraction = await self._extract_parameters_once(
                execution_id,
                message,
                structured_intent=structured_analysis,
                provider_name=provider_name,
                model=model,
                conversation_context=conversation_context,
                schema_definitions=visible_tool_definitions,
                runtime_metadata=runtime_metadata,
            )
            parameter_state = await self._reconcile_parameters_once(
                execution_id,
                structured_intent=structured_analysis,
                parameter_extraction=parameter_extraction,
                schema_definitions=visible_tool_definitions,
                runtime_metadata=runtime_metadata,
            )
            input_requirements = await self._evaluate_input_requirements_once(
                execution_id,
                parameter_state=parameter_state,
                schema_definitions=visible_tool_definitions,
                runtime_metadata=runtime_metadata,
            )
            context = replace(
                context,
                metadata={
                    **context.metadata,
                    "intent_analysis": structured_analysis,
                    "extracted_parameters": parameter_extraction,
                    "parameter_state": parameter_state,
                    "input_requirements": input_requirements,
                },
            )
            if input_requirements.get("complete") is not True:
                if not input_requirements.get("schema_available"):
                    self.transition_execution(
                        execution_id,
                        "FAILED",
                        expected_statuses={"RUNNING"},
                        error_code="INPUT_REQUIREMENT_SCHEMA_UNAVAILABLE",
                        error_message="Canonical input requirements could not be resolved.",
                        result_message="The request could not be matched to a supported input contract.",
                        worker_id=self.worker_id,
                        ownership_attempt=self._owned_attempts.get(execution_id),
                    )
                    return
                await self._pause_for_input(
                    execution_id,
                    self._requirement_fields(input_requirements),
                    {
                        name: item.get("value")
                        for name, item in parameter_state.get("parameters", {}).items()
                        if item.get("status") == "RESOLVED"
                    },
                    parameter_state_version=parameter_state.get("version", 1),
                    input_requirements=input_requirements,
                    canonical_metadata={
                        "intent_analysis": structured_analysis,
                        "parameter_extraction": parameter_extraction,
                        "parameter_state": parameter_state,
                        "input_requirements": input_requirements,
                    },
                )
                return
            try:
                capability_resolution = await self._resolve_capability_once(
                    execution_id,
                    structured_intent=structured_analysis,
                    parameter_state=parameter_state,
                    permissions=permissions,
                    selected_agent=selected_agent,
                )
            except CapabilityResolutionError:
                self.transition_execution(
                    execution_id,
                    "FAILED",
                    expected_statuses={"RUNNING"},
                    error_code="CAPABILITY_RESOLUTION_FAILED",
                    error_message="Capability resolution could not be completed.",
                    result_message="The available platform capabilities could not be checked.",
                    worker_id=self.worker_id,
                    ownership_attempt=self._owned_attempts.get(execution_id),
                )
                return
            if capability_resolution.get("status") != "RESOLVED":
                resolution_status = capability_resolution.get("status", "UNAVAILABLE")
                safe_messages = {
                    "UNAUTHORIZED": "You don't have permission to perform this action.",
                    "UNHEALTHY": "The required integration is currently unavailable.",
                    "AMBIGUOUS": "Multiple capabilities are available; a specific connection is required.",
                    "UNAVAILABLE": "No enabled capability is currently available for this request.",
                }
                self.transition_execution(
                    execution_id,
                    "FAILED",
                    expected_statuses={"RUNNING"},
                    error_code=f"CAPABILITY_{resolution_status}",
                    error_message=safe_messages.get(
                        resolution_status, "The requested capability is unavailable."
                    ),
                    result_message=safe_messages.get(
                        resolution_status, "The requested capability is unavailable."
                    ),
                    worker_id=self.worker_id,
                    ownership_attempt=self._owned_attempts.get(execution_id),
                )
                return
            agent_routing = await self._route_agent_once(
                execution_id,
                capability_resolution=capability_resolution,
                structured_intent=structured_analysis,
                parameter_state=parameter_state,
            )
            if agent_routing.get("status") not in {"RESOLVED", "EXPLICIT_SELECTED"}:
                routing_status = agent_routing.get("status", "UNAVAILABLE")
                if routing_status == "INCOMPATIBLE":
                    error_code = "SELECTED_AGENT_INCOMPATIBLE"
                    safe_message = (
                        "The selected agent cannot perform the requested action."
                    )
                elif routing_status == "UNHEALTHY":
                    error_code = "AGENT_UNHEALTHY"
                    safe_message = "The required agent is currently unavailable."
                elif routing_status == "AMBIGUOUS":
                    error_code = "AGENT_AMBIGUOUS"
                    safe_message = "Multiple equally suitable agents are available."
                elif routing_status == "UNAUTHORIZED":
                    error_code = "AGENT_UNAUTHORIZED"
                    safe_message = "You don't have permission to use an eligible agent."
                else:
                    error_code = "AGENT_UNAVAILABLE"
                    safe_message = "No eligible agent is currently available to perform this action."
                self.transition_execution(
                    execution_id,
                    "FAILED",
                    expected_statuses={"RUNNING"},
                    error_code=error_code,
                    error_message=safe_message,
                    result_message=safe_message,
                    worker_id=self.worker_id,
                    ownership_attempt=self._owned_attempts.get(execution_id),
                )
                return
            routed = agent_routing.get("selected_agent") or {}
            selected_agent = {
                "agent_id": routed.get("agent_id"),
                "name": routed.get("agent_name"),
                "slug": routed.get("agent_slug"),
                "capabilities": routed.get("semantic_capabilities", []),
                "provider": routed.get("model_provider"),
                "model": routed.get("model"),
                "confidence": agent_routing.get("confidence", 1),
                "reason": ", ".join(routed.get("reason_codes", [])),
                "model_configuration": routed.get("model_configuration", {}),
                "published_version": routed.get("published_version"),
                "tools": routed.get("assigned_tools", []),
                "knowledge_source_count": 0,
            }
            provider_name = routed.get("model_provider") or provider_name
            model = routed.get("model") or model
            execution.selected_agent_id = selected_agent["agent_id"]
            execution.agent = selected_agent["name"]
            execution.provider_name = provider_name
            execution.model_name = model
            context = replace(
                context,
                available_agents=[selected_agent["slug"]],
                metadata={
                    **context.metadata,
                    "selected_agent": selected_agent,
                    "agent_routing": agent_routing,
                    "ai_provider": provider_name,
                    "ai_model": model,
                    "capability_resolution": capability_resolution,
                },
            )
            try:
                execution_plan = await self._plan_execution_once(
                    execution_id,
                    context=replace(context, request_id=execution.id),
                    structured_intent=structured_analysis,
                    parameter_state=parameter_state,
                    capability_resolution=capability_resolution,
                    agent_routing=agent_routing,
                )
            except PlanningError as exc:
                self.transition_execution(
                    execution_id,
                    "FAILED",
                    expected_statuses={"RUNNING"},
                    error_code=exc.code,
                    error_message="An executable plan could not be created.",
                    result_message="The request could not be planned safely.",
                    worker_id=self.worker_id,
                    ownership_attempt=self._owned_attempts.get(execution_id),
                )
                return

            primary_task = execution_plan["tasks"][0]
            implementation_name = primary_task["implementation_name"]
            resolved_inputs = dict(primary_task["parameters"])
            context = replace(
                context,
                metadata={
                    **context.metadata,
                    "structured_intent": structured_analysis,
                    "inputs": resolved_inputs,
                    "permissions": sorted(permissions),
                    "execution_plan": execution_plan,
                },
            )
            if implementation_name == "jira.create_issue":
                await self._execute_jira_create_flow(
                    execution_id,
                    execution,
                    context,
                    permissions,
                    tenant_id,
                    resolved_inputs,
                    started_at,
                    selected_agent.get("name") or "Governed Integration Runtime",
                )
                return
            await self._execute_managed_agent(
                execution_id,
                execution,
                message,
                resolved_inputs,
                selected_agent,
                implementation_name,
            )
            return

            stored_intent = runtime_metadata.get("intent") or {}
            resolved_capability = capability_resolution.get("selected") or {}
            if resolved_capability.get("name"):
                analysis = IntentAnalysis(
                    intent=structured_analysis.get("intent", "general.assistance"),
                    domain=structured_analysis.get("domain", "general"),
                    operation=structured_analysis.get("operation", "respond"),
                    resource=structured_analysis.get("resource", "unknown"),
                    entities=structured_analysis.get("entities") or {},
                    confidence=structured_analysis.get("confidence", 1),
                    required_capabilities=[resolved_capability["name"]],
                    selected_tool=resolved_capability["name"],
                    ambiguous=False,
                )
            elif stored_intent.get("selected_tool") and not stored_intent.get(
                "ambiguous"
            ):
                analysis = IntentAnalysis(
                    intent=stored_intent.get("intent", "general.assistance"),
                    domain=stored_intent.get("domain", "general"),
                    operation=stored_intent.get("operation", "respond"),
                    resource=stored_intent.get("resource", "unknown"),
                    entities=stored_intent.get("entities") or {},
                    confidence=stored_intent.get("confidence", 0.5),
                    required_capabilities=stored_intent.get("required_capabilities")
                    or [],
                    selected_tool=stored_intent.get("selected_tool"),
                    ambiguous=stored_intent.get("ambiguous", False),
                )
            else:
                analysis_request = message
                if supplied_inputs:
                    import json

                    analysis_request += "\nUser clarification: " + json.dumps(
                        supplied_inputs, default=str
                    )
                analysis = await asyncio.to_thread(
                    CapabilityIntelligence().analyze,
                    analysis_request,
                    visible_tool_definitions,
                    provider_name=provider_name,
                    model=model,
                    semantic_intent=(
                        structured_analysis
                        if structured_analysis.get("source") != "fallback"
                        else None
                    ),
                )
            planned_function = self._matching_tool(
                message, visible_tool_definitions, analysis.selected_tool
            )
            schema = (planned_function or {}).get("parameters") or {"properties": {}}
            resolved_inputs, parameter_trace = reconcile_parameters(
                schema,
                prompt_values=analysis.entities,
                collected_values=supplied_inputs,
            )
            analysis.entities = resolved_inputs
            intent = analysis.safe_dict()
            missing_parameter_names = [
                key
                for key in schema.get("required", [])
                if resolved_inputs.get(key) in (None, "", [])
            ]
            context = replace(
                context,
                metadata={
                    **context.metadata,
                    "structured_intent": intent,
                    "inputs": resolved_inputs,
                    "permissions": sorted(permissions),
                },
            )
            self._merge_runtime_metadata(
                execution_id,
                {
                    "intent": intent,
                    "inputs": resolved_inputs,
                    "legacy_parameter_state": parameter_trace,
                },
            )
            await self.publish_step(
                execution_id,
                name="Intent Analysis",
                description=f"{intent['intent'].replace('_', ' ').replace('.', ' ').title()} identified",
                status="completed",
                intent=intent,
                extracted_parameters=parameter_trace,
                required_capabilities=intent.get("required_capabilities", []),
                missing_parameters=missing_parameter_names,
            )

            if analysis.selected_tool == "jira.create_issue":
                await self._execute_jira_create_flow(
                    execution_id,
                    execution,
                    context,
                    permissions,
                    tenant_id,
                    resolved_inputs,
                    started_at,
                    (selected_agent or {}).get("name")
                    or "Governed Integration Runtime",
                )
                return

            if selected_agent:
                assigned_names = set(selected_agent.get("tools", []))
                assigned_definitions = [
                    item
                    for item in visible_tool_definitions
                    if (item.get("function") or {}).get("name") in assigned_names
                ]
                preflight_missing = self._required_fields(
                    message, resolved_inputs, assigned_definitions
                )
                if preflight_missing:
                    planned_tool = self._matching_tool(
                        message, assigned_definitions, analysis.selected_tool
                    )
                    await self.publish_step(
                        execution_id,
                        "Planner",
                        "Resolving published agent dependencies",
                        "running",
                        agent=selected_agent["name"],
                    )
                    await self.publish_step(
                        execution_id,
                        "Planner",
                        "Execution plan created with unresolved required inputs",
                        "completed",
                        agent=selected_agent["name"],
                        plan={
                            "plan_id": str(uuid4()),
                            "goal": message,
                            "steps": [
                                {
                                    "id": f"tool:{planned_tool['name']}",
                                    "name": planned_tool["name"],
                                    "type": "tool",
                                    "dependencies": [],
                                    "required": True,
                                    "required_capability": planned_tool.get(
                                        "description"
                                    ),
                                    "resolved_tool": planned_tool["name"],
                                    "status": "waiting_for_input",
                                }
                            ],
                        },
                    )
                    await self._pause_for_input(
                        execution_id, preflight_missing, resolved_inputs
                    )
                    return
                await self._execute_managed_agent(
                    execution_id, execution, message, resolved_inputs, selected_agent
                )
                return

            missing_fields = self._required_fields(
                message,
                resolved_inputs,
                [
                    item
                    for item in visible_tool_definitions
                    if (item.get("function") or {}).get("name")
                    == analysis.selected_tool
                ]
                if analysis.selected_tool
                else visible_tool_definitions,
            )
            planned_tool = self._matching_tool(
                message, visible_tool_definitions, analysis.selected_tool
            )
            await self.publish_step(
                execution_id,
                "Planner",
                "Resolving authorized capabilities and dependencies",
                "running",
            )
            plan_steps = (
                [
                    {
                        "id": f"tool:{planned_tool['name']}",
                        "name": planned_tool["name"],
                        "type": "tool",
                        "dependencies": [],
                        "required": True,
                        "required_capability": planned_tool.get("description"),
                        "resolved_tool": planned_tool["name"],
                        "status": "waiting_for_input" if missing_fields else "pending",
                    }
                ]
                if planned_tool
                else [
                    {
                        "id": "agent-response",
                        "name": "Generate governed response",
                        "type": "agent",
                        "dependencies": [],
                        "required": True,
                        "status": "pending",
                    }
                ]
            )
            await self.publish_step(
                execution_id,
                "Planner",
                "Execution plan created",
                "completed",
                plan={"plan_id": str(uuid4()), "goal": message, "steps": plan_steps},
            )
            if missing_fields:
                await self._pause_for_input(
                    execution_id, missing_fields, resolved_inputs
                )
                return

            if planned_tool:
                tool_name = planned_tool["name"]
                tool = tool_registry.get(tool_name)
                category = (
                    "action" if str(tool.metadata.risk_level) != "read" else "tool"
                )
                await self.publish_event(
                    execution_id,
                    {
                        "type": f"{category}_started",
                        "name": tool_name,
                        "step_id": f"{category}:{tool_name}",
                        "description": f"Executing authorized {category}",
                        "status": "running",
                    },
                )
                tool_db = SessionLocal()
                envelope = None
                try:
                    self._assert_local_ownership(execution_id)
                    envelope = await tool_executor.execute(
                        tool_name,
                        resolved_inputs,
                        ToolExecutionContext(
                            actor_id=execution.user_id,
                            permissions=permissions,
                            tenant_id=tenant_id,
                            conversation_id=str(execution.conversation_id),
                            correlation_id=str(execution.workflow_id),
                            trace_id=context.trace_id,
                            idempotency_key=f"runtime:{execution_id}:{tool_name}",
                        ),
                        tool_db,
                    )
                except asyncio.CancelledError:
                    await self.publish_event(
                        execution_id,
                        {
                            "type": f"{category}_cancelled",
                            "name": tool_name,
                            "step_id": f"{category}:{tool_name}",
                            "description": f"{category.title()} execution was cancelled",
                            "status": "cancelled",
                            "error_code": "EXECUTION_CANCELLED",
                            "component_type": category,
                            "component_status": "CANCELLED",
                        },
                    )
                    raise
                except Exception as exc:
                    safe_tool_error = (
                        getattr(exc, "safe_message", None)
                        or "The tool could not complete the request"
                    )
                    timed_out = isinstance(exc, (AITimeoutError, TimeoutError))
                    await self.publish_event(
                        execution_id,
                        {
                            "type": f"{category}_{'timed_out' if timed_out else 'failed'}",
                            "name": tool_name,
                            "step_id": f"{category}:{tool_name}",
                            "description": safe_tool_error,
                            "status": "timed_out" if timed_out else "failed",
                            "error_code": getattr(exc, "code", "TOOL_EXECUTION_FAILED"),
                            "component_type": category,
                            "component_status": "TIMED_OUT" if timed_out else "FAILED",
                        },
                    )
                    raise
                finally:
                    tool_db.close()
                if envelope.status != "succeeded":
                    timed_out = envelope.status == "timed_out"
                    await self.publish_event(
                        execution_id,
                        {
                            "type": f"{category}_{'timed_out' if timed_out else 'failed'}",
                            "name": tool_name,
                            "step_id": f"{category}:{tool_name}",
                            "description": envelope.error.message
                            if envelope.error
                            else f"{category.title()} failed",
                            "status": "timed_out" if timed_out else "failed",
                            "duration_ms": envelope.meta.get("duration_ms"),
                            "component_type": category,
                            "component_id": envelope.execution_id,
                            "component_status": "TIMED_OUT" if timed_out else "FAILED",
                        },
                    )
                    if envelope.status == "timed_out":
                        raise AITimeoutError(
                            envelope.error.message
                            if envelope.error
                            else "Tool execution timed out"
                        )
                    raise RuntimeError(
                        envelope.error.message
                        if envelope.error
                        else f"{category.title()} execution failed"
                    )
                await self.publish_event(
                    execution_id,
                    {
                        "type": f"{category}_completed",
                        "name": tool_name,
                        "step_id": f"{category}:{tool_name}",
                        "description": f"Authorized {category} completed",
                        "status": "completed",
                        "duration_ms": envelope.meta.get("duration_ms"),
                        "result_summary": envelope.data,
                    },
                )
                tool_message = (
                    envelope.data.get("report")
                    if isinstance(envelope.data, dict)
                    else str(envelope.data)
                )
                db_message = SessionLocal()
                try:
                    from app.services.conversation_service import conversation_service

                    conversation_service.save_assistant_message(
                        db_message,
                        execution.conversation_id,
                        tool_message,
                        execution_id,
                    )
                finally:
                    db_message.close()
                duration_ms = round(
                    (datetime.now(UTC) - started_at).total_seconds() * 1000, 2
                )
                self._complete_execution(
                    execution_id,
                    status="COMPLETED",
                    agent="Governed Runtime",
                    message=tool_message,
                    duration_ms=duration_ms,
                )
                await self.publish_event(
                    execution_id,
                    {
                        "type": "completed",
                        "name": "Result Generated",
                        "step_id": "result-generation",
                        "description": "Verified tool result delivered",
                        "status": "completed",
                        "duration_ms": duration_ms,
                        "message": tool_message,
                        "final": True,
                    },
                )
                return

            result = await self._runtime.run(context)
            task_results = result.output.get("results", [])
            agent = (
                selected_agent["name"]
                if selected_agent
                else (task_results[0].get("agent") if task_results else "default-agent")
            )

            await self.publish_step(
                execution_id,
                name="Result Generated",
                description="Generating assistant response",
                status="running",
                agent=agent,
            )
            inference_message = message
            if supplied_inputs:
                import json

                inference_message += "\n\nVerified runtime inputs:\n" + json.dumps(
                    supplied_inputs, sort_keys=True, default=str
                )
            response = await asyncio.to_thread(
                self._generate_response,
                execution.conversation_id,
                execution.user_id,
                inference_message,
                provider_name,
                model,
                execution.tenant_id,
                str(execution.id),
                execution.runtime_metadata,
            )
            if self._has_unresolved_business_placeholders(response.text, message):
                raise ValueError(
                    "Generated output contains unresolved business placeholders"
                )
            duration_ms = round(
                (datetime.now(UTC) - started_at).total_seconds() * 1000, 2
            )
            usage = (
                {
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens,
                }
                if response.usage
                else {}
            )
            await self.publish_event(
                execution_id,
                {
                    "type": "metric",
                    "name": "Provider Metrics",
                    "status": "completed",
                    "provider": provider_name,
                    "model": response.model,
                    "metadata": {
                        "duration_ms": duration_ms,
                        "provider_latency_ms": round(
                            response.latency_seconds * 1000, 2
                        ),
                        "token_usage": usage,
                    },
                },
            )
            self._complete_execution(
                execution_id,
                status="COMPLETED",
                agent=agent,
                message=response.text,
                duration_ms=duration_ms,
            )
            await self.publish_step(
                execution_id,
                name="Result Generated",
                description="Response delivered",
                status="completed",
                agent=agent,
                final=True,
                message=response.text,
                response_id=response.response_id,
                duration_ms=duration_ms,
                provider=provider_name,
                model=response.model,
            )
        except asyncio.CancelledError:
            # cancel() already persisted and published the terminal event.
            raise
        except RuntimeLeaseLostError:
            logger.warning(
                "Stale runtime worker stopped without mutating parent state",
                extra={"execution_id": execution_id, "worker_id": self.worker_id},
            )
            return
        except Exception as exc:  # noqa: BLE001 - normalized into a safe runtime failure
            duration_ms = round(
                (datetime.now(UTC) - started_at).total_seconds() * 1000, 2
            )
            safe_error = self._safe_error_message(exc)
            terminal_status = (
                "TIMED_OUT"
                if isinstance(exc, (AITimeoutError, asyncio.TimeoutError))
                else "FAILED"
            )
            self._complete_execution(
                execution_id,
                status=terminal_status,
                duration_ms=duration_ms,
                error=safe_error,
                error_code=self._error_code(exc),
            )
            await self.publish_step(
                execution_id,
                name="Runtime Orchestrator",
                description="Runtime failed during result generation",
                status="failed",
            )
            await self.publish_step(
                execution_id,
                name="Result Generated",
                description=safe_error,
                status="failed",
                final=True,
                message="Axiom Runtime failed.",
                duration_ms=duration_ms,
                error=safe_error,
                terminal_status=terminal_status,
            )
        finally:
            self._tasks.pop(execution_id, None)
            self._workflow_to_execution.pop(str(execution.workflow_id), None)

    @staticmethod
    def _load_conversation_context(
        conversation_id: UUID, user_id: str
    ) -> list[dict[str, Any]]:
        """Load the owned history before planning; ChatService rebuilds it for inference."""
        db = SessionLocal()
        try:
            from app.services.conversation_service import conversation_service

            messages = conversation_service.get_messages(
                db=db, conversation_id=conversation_id, user_id=user_id
            )
            return [
                {"role": message.role, "content": message.content}
                for message in messages
            ]
        finally:
            db.close()

    async def _classify_intent_once(
        self,
        execution_id: str,
        message: str,
        *,
        provider_name: str,
        model: str,
        conversation_context: list[dict[str, Any]],
        visible_tool_definitions: list[dict[str, Any]],
        runtime_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Persist and emit semantic classification once per durable execution."""
        metadata = (
            runtime_metadata
            if runtime_metadata is not None
            else self._runtime_metadata(execution_id)
        )
        existing = metadata.get("intent_analysis")
        if isinstance(existing, dict) and existing:
            return existing
        domain_hints = sorted(
            {
                str((item.get("function") or {}).get("name", "")).split(".", 1)[0]
                for item in visible_tool_definitions
                if (item.get("function") or {}).get("name")
            }
        )
        analyzed = await asyncio.to_thread(
            intent_analyzer.analyze,
            message,
            provider_name=provider_name,
            model=model,
            conversation_context=conversation_context,
            available_domains=domain_hints,
            migrated_intents=requirement_schema_provider.supported_intents(),
        )
        structured_analysis = analyzed.persisted_dict()
        self._merge_runtime_metadata(
            execution_id, {"intent_analysis": structured_analysis}
        )
        await self.publish_event(
            execution_id,
            {
                "type": "intent_analysis.completed",
                "name": "Structured Intent Classification",
                "step_id": "structured-intent-classification",
                "description": "Semantic intent classification completed",
                "status": "completed",
                "intent_analysis": structured_analysis,
                "final": False,
            },
        )
        return structured_analysis

    async def _extract_parameters_once(
        self,
        execution_id: str,
        message: str,
        *,
        structured_intent: dict[str, Any],
        provider_name: str,
        model: str,
        conversation_context: list[dict[str, Any]],
        schema_definitions: list[dict[str, Any]],
        runtime_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Persist and emit typed parameter extraction once per durable execution."""
        metadata = (
            runtime_metadata
            if runtime_metadata is not None
            else self._runtime_metadata(execution_id)
        )
        existing = metadata.get("parameter_extraction")
        if isinstance(existing, dict) and existing:
            return existing
        extracted = await asyncio.to_thread(
            parameter_extractor.extract,
            message,
            intent=structured_intent,
            provider_name=provider_name,
            model=model,
            conversation_context=conversation_context,
            schema_definitions=schema_definitions,
        )
        parameter_extraction = extracted.persisted_dict()
        self._merge_runtime_metadata(
            execution_id, {"parameter_extraction": parameter_extraction}
        )
        await self.publish_event(
            execution_id,
            {
                "type": "parameter_extraction.completed",
                "name": "Parameter Extraction",
                "step_id": "parameter-extraction",
                "description": "Typed parameter extraction completed",
                "status": "completed",
                "parameter_extraction": parameter_extraction,
                "final": False,
            },
        )
        return parameter_extraction

    async def _reconcile_parameters_once(
        self,
        execution_id: str,
        *,
        structured_intent: dict[str, Any],
        parameter_extraction: dict[str, Any],
        schema_definitions: list[dict[str, Any]],
        runtime_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Persist and emit deterministic canonical parameter state once."""
        metadata = (
            runtime_metadata
            if runtime_metadata is not None
            else self._runtime_metadata(execution_id)
        )
        existing = metadata.get("parameter_state")
        if isinstance(existing, dict) and existing.get("version"):
            return existing
        expected_types: dict[str, Any] = {}
        for definition in schema_definitions:
            properties = (
                (definition.get("function") or {}).get("parameters") or {}
            ).get("properties") or {}
            for name, schema in properties.items():
                schema_type = schema.get("type")
                if schema_type in {
                    "string",
                    "integer",
                    "number",
                    "boolean",
                    "array",
                    "object",
                }:
                    expected_types.setdefault(name, schema_type)
        state = parameter_reconciler.reconcile(
            structured_intent,
            parameter_extraction,
            expected_types=expected_types,
            execution_id=execution_id,
        ).model_dump(mode="json")
        self._merge_runtime_metadata(execution_id, {"parameter_state": state})
        resolved_count = sum(
            item.get("status") == "RESOLVED"
            for item in state.get("parameters", {}).values()
        )
        await self.publish_event(
            execution_id,
            {
                "type": "parameter_reconciliation.completed",
                "name": "Parameter Reconciliation",
                "step_id": "parameter-reconciliation",
                "description": "Canonical parameter state resolved",
                "status": "completed",
                "parameter_state": state,
                "parameter_count": len(state.get("parameters", {})),
                "resolved_count": resolved_count,
                "conflict_count": len(state.get("conflicts", [])),
                "final": False,
            },
        )
        return state

    async def _evaluate_input_requirements_once(
        self,
        execution_id: str,
        *,
        parameter_state: dict[str, Any],
        schema_definitions: list[dict[str, Any]],
        runtime_metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Evaluate canonical state against exact semantic requirements once."""
        metadata = (
            runtime_metadata
            if runtime_metadata is not None
            else self._runtime_metadata(execution_id)
        )
        existing = metadata.get("input_requirements")
        if isinstance(existing, dict) and existing.get(
            "parameter_state_version"
        ) == parameter_state.get("version"):
            return existing
        schema = requirement_schema_provider.get(
            parameter_state.get("intent"), schema_definitions
        )
        result = missing_field_resolver.evaluate(
            parameter_state, schema, execution_id=execution_id
        ).model_dump(mode="json")
        result["parameter_state_version"] = parameter_state.get("version", 1)
        self._merge_runtime_metadata(execution_id, {"input_requirements": result})
        await self.publish_event(
            execution_id,
            {
                "type": "input_requirements.evaluated",
                "name": "Input Requirements",
                "step_id": "input-requirements",
                "description": (
                    "All required inputs are resolved"
                    if result.get("complete") is True
                    else "Required inputs were evaluated"
                ),
                "status": "completed",
                "intent": result.get("intent"),
                "schema_source": result.get("schema_source"),
                "complete": result.get("complete"),
                "satisfied_count": len(result.get("satisfied", [])),
                "missing": [item["name"] for item in result.get("missing", [])],
                "ambiguous": [item["name"] for item in result.get("ambiguous", [])],
                "invalid": [item["name"] for item in result.get("invalid", [])],
                "final": False,
            },
        )
        return result

    async def _resolve_capability_once(
        self,
        execution_id: str,
        *,
        structured_intent: dict[str, Any],
        parameter_state: dict[str, Any],
        permissions: set[str],
        selected_agent: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Resolve and persist the executable capability exactly once."""
        existing = self._runtime_metadata(execution_id).get("capability_resolution")
        if isinstance(existing, dict) and existing.get("status"):
            return existing
        db = SessionLocal()
        try:
            record = db.get(RuntimeExecution, UUID(execution_id))
            if record is None:
                raise CapabilityResolutionError("Runtime execution was not found")
            context = {
                key: value
                for key, value in (record.runtime_metadata or {}).items()
                if key
                in {"integration_connection_id", "connection_id", "connection_name"}
            }
            if (
                selected_agent
                and (record.runtime_metadata or {}).get("selection_mode")
                == "user_selected"
            ):
                context.update(
                    {
                        "selected_agent_id": selected_agent.get("agent_id"),
                        "selected_agent_tools": selected_agent.get("tools", []),
                    }
                )
            result = capability_resolver.resolve(
                db,
                intent_result=structured_intent,
                parameter_state=parameter_state,
                tenant_id=record.tenant_id,
                permissions=permissions,
                execution_context=context,
                execution_id=execution_id,
            ).persisted_dict()
            metadata = dict(record.runtime_metadata or {})
            metadata["capability_resolution"] = result
            record.runtime_metadata = metadata
            db.commit()
        finally:
            db.close()
        selected = result.get("selected") or {}
        rejection_counts: dict[str, int] = {}
        for candidate in result.get("candidates", []):
            for reason in candidate.get("rejection_reasons", []):
                rejection_counts[reason] = rejection_counts.get(reason, 0) + 1
        await self.publish_event(
            execution_id,
            {
                "type": "capability_resolution.completed",
                "name": "Capability Resolution",
                "step_id": "capability-resolution",
                "description": "Registered executable capabilities were evaluated",
                "status": "completed",
                "resolution_status": result.get("status"),
                "required_semantic_capability": result.get(
                    "required_semantic_capability"
                ),
                "selected_capability_id": selected.get("capability_id"),
                "selected_capability": selected.get("name"),
                "capability_type": selected.get("capability_type"),
                "provider": selected.get("provider"),
                "integration_connection_id": selected.get("integration_connection_id"),
                "integration_connection_name": selected.get(
                    "integration_connection_display_name"
                ),
                "candidate_count": len(result.get("candidates", [])),
                "rejection_summary": rejection_counts,
                "final": False,
            },
        )
        return result

    async def _route_agent_once(
        self,
        execution_id: str,
        *,
        capability_resolution: dict[str, Any],
        structured_intent: dict[str, Any],
        parameter_state: dict[str, Any],
    ) -> dict[str, Any]:
        """Persist capability-first agent routing and emit its durable event once."""
        existing = self._runtime_metadata(execution_id).get("agent_routing")
        if isinstance(existing, dict) and existing.get("status"):
            return existing
        db = SessionLocal()
        try:
            record = db.get(RuntimeExecution, UUID(execution_id))
            if record is None:
                raise LookupError("Runtime execution was not found")
            metadata = dict(record.runtime_metadata or {})
            identity = self._identity(metadata)
            request = metadata.get("request") or {}
            context = {
                "environment": metadata.get("environment")
                or (metadata.get("inputs") or {}).get("environment")
                or "production"
            }
            result = agent_router.route(
                db,
                capability_resolution=capability_resolution,
                intent_result=structured_intent,
                parameter_state=parameter_state,
                tenant_id=record.tenant_id,
                identity=identity,
                execution_context=context,
                explicit_agent_id=request.get("agent_id"),
                execution_id=execution_id,
            ).persisted_dict()
            selected = result.get("selected_agent") or {}
            legacy_selected = None
            if selected:
                legacy_selected = {
                    "agent_id": selected.get("agent_id"),
                    "name": selected.get("agent_name"),
                    "slug": selected.get("agent_slug"),
                    "capabilities": selected.get("semantic_capabilities", []),
                    "provider": selected.get("model_provider"),
                    "model": selected.get("model"),
                    "confidence": result.get("confidence"),
                    "reason": ", ".join(selected.get("reason_codes", [])),
                    "model_configuration": selected.get("model_configuration", {}),
                    "published_version": selected.get("published_version"),
                    "tools": selected.get("assigned_tools", []),
                    "knowledge_source_count": 0,
                }
                record.selected_agent_id = selected.get("agent_id")
                record.agent = selected.get("agent_name")
                record.provider_name = (
                    selected.get("model_provider") or record.provider_name
                )
                record.model_name = selected.get("model") or record.model_name
            record.runtime_metadata = {
                **metadata,
                "agent_routing": result,
                "selection_mode": result.get("selection_mode"),
                "selected_agent": legacy_selected,
                "agent_candidates": result.get("candidates", []),
                "resolved": {
                    **(metadata.get("resolved") or {}),
                    "provider": selected.get("model_provider") or record.provider_name,
                    "model": selected.get("model") or record.model_name,
                },
            }
            db.commit()
        finally:
            db.close()
        selected = result.get("selected_agent") or {}
        rejection_counts: dict[str, int] = {}
        for candidate in result.get("candidates", []):
            for reason in candidate.get("rejection_reasons", []):
                rejection_counts[reason] = rejection_counts.get(reason, 0) + 1
        await self.publish_event(
            execution_id,
            {
                "type": "agent_routing.completed",
                "name": "Agent Selection",
                "step_id": "agent-routing",
                "description": "Eligible agents were evaluated for the resolved capability",
                "status": "completed",
                "routing_status": result.get("status"),
                "selection_mode": result.get("selection_mode"),
                "agent": selected.get("agent_name"),
                "agent_id": selected.get("agent_id"),
                "provider": selected.get("model_provider"),
                "model": selected.get("model"),
                "resolved_capability_id": result.get("resolved_capability_id"),
                "semantic_capability": result.get("semantic_capability"),
                "candidate_count": len(result.get("candidates", [])),
                "eligible_count": sum(
                    bool(item.get("eligible")) for item in result.get("candidates", [])
                ),
                "reason_codes": selected.get("reason_codes", []),
                "rejection_summary": rejection_counts,
                "final": False,
            },
        )
        return result

    @staticmethod
    def _requirement_fields(result: dict[str, Any]) -> list[dict[str, Any]]:
        fields = []
        unresolved = [
            *result.get("missing", []),
            *result.get("ambiguous", []),
            *result.get("invalid", []),
        ]
        for item in unresolved:
            value_type = item.get("value_type", "string")
            options = item.get("options") or []
            kind = {
                "string": "text",
                "integer": "integer",
                "number": "number",
                "boolean": "boolean",
                "array": "multiselect" if options else "text",
            }.get(value_type, "text")
            if options:
                kind = "select"
            fields.append(
                {
                    "name": item["name"],
                    "label": item["label"],
                    "type": kind,
                    "required": True,
                    "options": options,
                    "description": item.get("reason"),
                    "reason": item.get("reason"),
                    "validation": item.get("validation") or {},
                }
            )
        return fields

    @staticmethod
    def _budget_context(execution: RuntimeExecution, message: str, model: str):
        from app.governance.budget_enforcement import BudgetContext

        runtime_metadata = execution.runtime_metadata or {}
        scope = runtime_metadata.get("scope") or {}
        return BudgetContext(
            tenant_id=execution.tenant_id,
            trace_id=str(execution.id),
            execution_id=str(execution.id),
            idempotency_key=f"runtime:{execution.id}:response",
            model=model,
            programme_id=scope.get("programme_id"),
            project_id=scope.get("project_id"),
            agent_id=(runtime_metadata.get("selected_agent") or {}).get("id"),
            use_case="copilot",
            data_classification=runtime_metadata.get("data_classification", "INTERNAL"),
            region=runtime_metadata.get("region"),
            estimated_input_tokens=max(1, len(message) // 4),
            reserved_output_tokens=min(
                int(runtime_metadata.get("max_output_tokens", 512)), 4096
            ),
            critical=bool(runtime_metadata.get("critical_ai_request", False)),
            override_id=runtime_metadata.get("budget_override_id"),
        )

    @staticmethod
    def _generate_response(
        conversation_id: UUID,
        user_id: str,
        message: str,
        provider_name: str,
        model: str,
        tenant_id: str,
        execution_id: str,
        runtime_metadata: dict[str, Any],
    ):
        db = SessionLocal()
        try:
            budget_context = None
            if settings.BUDGET_ENFORCEMENT_ENABLED:
                from app.governance.budget_enforcement import BudgetContext

                scope = runtime_metadata.get("scope") or {}
                budget_context = BudgetContext(
                    tenant_id=tenant_id,
                    trace_id=execution_id,
                    execution_id=execution_id,
                    idempotency_key=f"runtime:{execution_id}:response",
                    model=model,
                    programme_id=scope.get("programme_id"),
                    project_id=scope.get("project_id"),
                    agent_id=(runtime_metadata.get("selected_agent") or {}).get("id"),
                    use_case="copilot",
                    data_classification=runtime_metadata.get(
                        "data_classification", "INTERNAL"
                    ),
                    region=runtime_metadata.get("region"),
                    estimated_input_tokens=max(1, len(message) // 4),
                    reserved_output_tokens=min(
                        int(runtime_metadata.get("max_output_tokens", 512)), 4096
                    ),
                    critical=bool(runtime_metadata.get("critical_ai_request", False)),
                    override_id=runtime_metadata.get("budget_override_id"),
                )
            return chat_service.ask(
                db=db,
                user_id=user_id,
                message=message,
                conversation_id=conversation_id,
                provider_name=provider_name,
                model=model,
                persist_user=False,
                budget_context=budget_context,
            )
        finally:
            db.close()

    @staticmethod
    def _classify_intent(message: str) -> dict[str, Any]:
        """Produce safe structured classification metadata without model reasoning."""
        words = set(re.findall(r"[a-z0-9_-]+", message.lower()))
        definitions = {
            "deployment_report": {"deployment", "release", "report"},
            "analysis": {"analyze", "analysis", "compare", "risk", "variance"},
            "summarization": {"summarize", "summary", "explain"},
        }
        scored = {
            name: len(words & vocabulary) / len(vocabulary)
            for name, vocabulary in definitions.items()
        }
        intent, score = max(scored.items(), key=lambda item: item[1])
        if score == 0:
            intent, score = "general_assistance", 0.55
        entities: dict[str, Any] = {}
        environment = next(
            (
                value
                for value in ("production", "staging", "development", "dev", "test")
                if value in words
            ),
            None,
        )
        if environment:
            entities["environment"] = environment
        if "last" in words and "week" in words:
            entities["date_range"] = "last_week"
        return {
            "intent": intent,
            "confidence": round(min(0.98, 0.55 + score * 0.4), 2),
            "entities": entities,
        }

    @staticmethod
    def _has_unresolved_business_placeholders(output: str, request: str) -> bool:
        if "template" in request.lower():
            return False
        return bool(
            re.search(
                r"\[(?:project name|version number|date|description|pass/fail|environment|recipient)\]",
                output,
                re.IGNORECASE,
            )
        )

    @staticmethod
    def _identity(metadata: dict[str, Any]) -> AgentIdentity:
        item = metadata.get("identity") or {}
        effective_permissions = set(item.get("permissions", []))
        effective_permissions.update(metadata.get("permissions", []))
        return AgentIdentity(
            actor_id=item.get("actor_id", "unknown"),
            tenant_id=item.get("tenant_id", "default"),
            permissions=frozenset(effective_permissions),
            groups=frozenset(item.get("groups", [])),
            roles=frozenset(item.get("roles", [])),
            subject_type=item.get("subject_type", "user"),
        )

    def _merge_runtime_metadata(
        self, execution_id: str, values: dict[str, Any]
    ) -> None:
        db = SessionLocal()
        try:
            record = db.get(RuntimeExecution, UUID(execution_id))
            if record:
                record.runtime_metadata = {**(record.runtime_metadata or {}), **values}
                db.commit()
        finally:
            db.close()

    async def _execute_managed_agent(
        self,
        execution_id: str,
        execution: RuntimeExecution,
        message: str,
        inputs: dict[str, Any],
        selected: dict[str, Any],
        implementation_name: str,
    ) -> None:
        metadata = self._runtime_metadata(execution_id)
        identity = self._identity(metadata)
        await self.publish_step(
            execution_id,
            "Agent Execution",
            "Executing published agent plan",
            "running",
            agent=selected["name"],
            provider=selected.get("provider"),
            model=selected.get("model"),
        )
        db = SessionLocal()
        try:
            result = await agent_execution_service.start(
                db,
                agent_id=selected["agent_id"],
                request=ExecutionRequest(
                    message=message,
                    inputs=dict(inputs),
                    conversation_id=str(execution.conversation_id),
                    runtime_execution_id=execution_id,
                    selected_tool=implementation_name,
                ),
                identity=identity,
            )
        finally:
            db.close()
        await self._map_agent_result(execution_id, execution, selected, result)

    async def _plan_execution_once(
        self,
        execution_id: str,
        *,
        context: RuntimeContext,
        structured_intent: dict[str, Any],
        parameter_state: dict[str, Any],
        capability_resolution: dict[str, Any],
        agent_routing: dict[str, Any],
    ) -> dict[str, Any]:
        """Create and persist one authoritative plan, or reuse it on recovery."""
        existing = self._runtime_metadata(execution_id).get("execution_plan")
        if isinstance(existing, dict) and existing.get("status") == "VALIDATED":
            return existing
        planning_context = replace(
            context,
            metadata={
                **context.metadata,
                "intent_analysis": structured_intent,
                "parameter_state": parameter_state,
                "capability_resolution": capability_resolution,
                "agent_routing": agent_routing,
            },
        )
        plan = await capability_aware_planner.plan(planning_context)
        serialized = {
            "plan_id": str(plan.plan_id),
            "execution_id": str(plan.execution_id) if plan.execution_id else None,
            "intent": plan.intent,
            "version": plan.version,
            "goal": plan.goal,
            "root_task_ids": [str(item) for item in plan.root_task_ids],
            "status": plan.status,
            "input_fingerprint": plan.input_fingerprint,
            "metadata": plan.metadata,
            "tasks": [
                {
                    "id": str(task.id),
                    "name": task.name,
                    "description": task.description,
                    "task_type": task.task_type,
                    "capability_id": task.capability_id,
                    "semantic_capability": task.semantic_capability,
                    "implementation_name": task.implementation_name,
                    "agent_id": task.agent_id,
                    "agent_version": task.agent_version,
                    "integration_connection_id": task.integration_connection_id,
                    "parameters": task.parameters,
                    "depends_on": [str(item) for item in task.depends_on],
                    "required": task.required,
                    "timeout_seconds": task.timeout_seconds,
                    "retry_policy": task.retry_policy,
                    "side_effect_class": task.side_effect_class,
                    "expected_output_schema": task.expected_output_schema,
                    "requires_approval": task.requires_approval,
                    "metadata": task.metadata,
                }
                for task in plan.tasks
            ],
        }
        self._merge_runtime_metadata(execution_id, {"execution_plan": serialized})
        await self.publish_event(
            execution_id,
            {
                "type": "planning.completed",
                "name": "Planner",
                "step_id": "capability-aware-planner",
                "description": "Executable capability plan validated",
                "status": "completed",
                "plan_id": serialized["plan_id"],
                "plan_version": serialized["version"],
                "task_count": len(serialized["tasks"]),
                "capability_ids": [
                    item["capability_id"] for item in serialized["tasks"]
                ],
                "agent_ids": [item["agent_id"] for item in serialized["tasks"]],
                "dependency_count": sum(
                    len(item["depends_on"]) for item in serialized["tasks"]
                ),
                "side_effect_summary": [
                    item["side_effect_class"] for item in serialized["tasks"]
                ],
                "plan": serialized,
                "final": False,
            },
        )
        return serialized

    async def _persist_agent_continuation(
        self, execution_id: str, result: dict[str, Any], continuation: dict[str, Any]
    ) -> None:
        schema = continuation.get("schema") or {}
        properties = schema.get("properties") or {}
        missing = continuation.get("missing_fields") or []
        fields = []
        for name in missing:
            definition = properties.get(name, {})
            field_type = definition.get("type", "text")
            if field_type == "string":
                field_type = definition.get("format", "text")
            fields.append(
                {
                    "name": name,
                    "label": definition.get("title") or name.replace("_", " ").title(),
                    "type": field_type,
                    "required": name in schema.get("required", []),
                    "options": definition.get("enum", []),
                    "description": definition.get("description"),
                }
            )
        kind = continuation.get("kind", "input")
        db = SessionLocal()
        try:
            record = db.get(RuntimeExecution, UUID(execution_id))
            row = RuntimeContinuation(
                execution_id=record.id,
                tenant_id=record.tenant_id,
                kind=kind,
                schema={
                    "agent_execution_id": result.get("execution_id"),
                    "fields": fields,
                },
                known_values={"_resume_token": continuation.get("resume_token")},
                required_role=continuation.get("required_approver"),
                expires_at=datetime.fromisoformat(str(continuation["expires_at"]))
                if isinstance(continuation.get("expires_at"), str)
                else continuation.get("expires_at")
                or datetime.now(UTC).replace(tzinfo=None) + timedelta(minutes=30),
            )
            db.add(row)
            target_status = (
                "WAITING_FOR_APPROVAL" if kind == "approval" else "WAITING_FOR_INPUT"
            )
            self.transition_execution(
                record.id,
                target_status,
                expected_statuses={"RUNNING"},
                reason=kind,
                db=db,
                commit=False,
            )
            db.commit()
            continuation_id = str(row.id)
        finally:
            db.close()
        if kind == "approval":
            await self.publish_event(
                execution_id,
                {
                    "type": "approval_required",
                    "name": continuation.get("question") or "Approval required",
                    "description": continuation.get("question")
                    or "A governed action requires approval.",
                    "status": "waiting",
                    "continuation_id": continuation_id,
                    "action": continuation.get("tool_name"),
                    "risk": "governed",
                    "required_role": continuation.get("required_approver"),
                    "final": False,
                },
            )
        else:
            await self.publish_event(
                execution_id,
                {
                    "type": "required_input",
                    "name": "Additional Information Required",
                    "description": continuation.get("question")
                    or "Provide the required tool inputs.",
                    "status": "waiting",
                    "continuation_id": continuation_id,
                    "fields": fields,
                    "final": False,
                },
            )

    async def _map_agent_result(
        self,
        execution_id: str,
        execution: RuntimeExecution,
        selected: dict[str, Any],
        result: dict[str, Any],
    ) -> None:
        self._merge_runtime_metadata(
            execution_id, {"agent_execution_id": result.get("execution_id")}
        )
        if result.get("continuation"):
            await self._persist_agent_continuation(
                execution_id, result, result["continuation"]
            )
            return
        db = SessionLocal()
        try:
            ids = result.get("tool_execution_ids") or []
            rows = (
                db.query(ToolExecution).filter(ToolExecution.id.in_(ids)).all()
                if ids
                else []
            )
            for row in rows:
                definition = (
                    db.query(ToolDefinition)
                    .filter_by(
                        tenant_id=row.tenant_id,
                        name=row.tool_name,
                        version=row.tool_version,
                    )
                    .first()
                )
                category = (
                    "action"
                    if definition and definition.risk_level != "read"
                    else "tool"
                )
                await self.publish_event(
                    execution_id,
                    {
                        "type": f"{category}_started",
                        "name": row.tool_name,
                        "description": f"{category.title()} execution started",
                        "status": "running",
                        "tool_execution_id": row.id,
                        "started_at": row.started_at.isoformat(),
                    },
                )
                await self.publish_event(
                    execution_id,
                    {
                        "type": f"{category}_completed"
                        if row.status == "succeeded"
                        else f"{category}_failed",
                        "name": row.tool_name,
                        "description": "Tool execution completed"
                        if row.status == "succeeded"
                        else (row.error_message or "Tool execution failed"),
                        "status": "completed"
                        if row.status == "succeeded"
                        else "failed",
                        "tool_execution_id": row.id,
                        "duration_ms": row.duration_ms,
                        "retry_count": row.retry_count,
                        "result_summary": row.output_summary,
                    },
                )
        finally:
            db.close()
        if result.get("status") in {"failed", "timed_out", "expired"}:
            error = (result.get("error") or {}).get(
                "message"
            ) or "Managed agent execution failed"
            error_code = (result.get("error") or {}).get(
                "code"
            ) or "AGENT_EXECUTION_FAILED"
            await self.publish_step(
                execution_id,
                "Agent Execution",
                error,
                "failed",
                agent=selected.get("name"),
            )
            terminal_status = (
                "TIMED_OUT"
                if result.get("status") in {"timed_out", "expired"}
                else "FAILED"
            )
            self._complete_execution(
                execution_id,
                status=terminal_status,
                agent=selected.get("name"),
                duration_ms=result.get("duration_ms"),
                error=error,
                error_code=error_code,
            )
            await self.publish_event(
                execution_id,
                {
                    "type": "error",
                    "name": "Runtime Execution",
                    "step_id": "runtime",
                    "description": error,
                    "status": "failed",
                    "error": error,
                    "error_code": error_code,
                    "provider": result.get("model_provider"),
                    "model": result.get("model_name"),
                    "message": error,
                    "duration_ms": result.get("duration_ms"),
                    "final": True,
                },
            )
            return
        output = result.get("result") or {}
        message = output.get("message") or "Execution completed."
        if self._has_unresolved_business_placeholders(message, execution.goal or ""):
            error = "The generated result was incomplete and requires verified business data."
            await self.publish_step(
                execution_id,
                "Agent Execution",
                error,
                "failed",
                agent=selected.get("name"),
            )
            self._complete_execution(
                execution_id,
                status="FAILED",
                agent=selected.get("name"),
                duration_ms=result.get("duration_ms"),
                error=error,
                error_code="INVALID_BUSINESS_RESULT",
            )
            await self.publish_event(
                execution_id,
                {
                    "type": "error",
                    "name": "Runtime Execution",
                    "step_id": "runtime",
                    "description": error,
                    "status": "failed",
                    "error": error,
                    "error_code": "OUTPUT_VALIDATION_FAILED",
                    "provider": result.get("model_provider"),
                    "model": result.get("model_name"),
                    "final": True,
                },
            )
            return
        db = SessionLocal()
        try:
            from app.services.conversation_service import conversation_service

            conversation_service.save_assistant_message(
                db, execution.conversation_id, message, execution_id
            )
        finally:
            db.close()
        await self.publish_step(
            execution_id,
            "Agent Execution",
            "Published agent execution completed",
            "completed",
            agent=selected.get("name"),
            provider=result.get("model_provider"),
            model=result.get("model_name"),
        )
        await self.publish_event(
            execution_id,
            {
                "type": "metric",
                "name": "Provider Metrics",
                "step_id": "provider-metrics",
                "status": "completed",
                "metadata": {
                    "token_usage": result.get("token_usage") or {},
                    "duration_ms": result.get("duration_ms"),
                    "estimated_cost": result.get("estimated_cost"),
                    "actual_cost": result.get("actual_cost"),
                },
                "provider": result.get("model_provider"),
                "model": result.get("model_name"),
            },
        )
        for source in output.get("citations") or []:
            await self.publish_event(
                execution_id,
                {
                    "type": "knowledge_retrieval_completed",
                    "name": source.get("name", "Knowledge source"),
                    "description": "Authorized knowledge source retrieved",
                    "status": "completed",
                    "source": source,
                },
            )
        self._complete_execution(
            execution_id,
            status="COMPLETED",
            agent=selected.get("name"),
            message=message,
            duration_ms=result.get("duration_ms"),
        )
        await self.publish_event(
            execution_id,
            {
                "type": "completed",
                "name": "Result Generated",
                "step_id": "result-generation",
                "description": "Managed agent response delivered",
                "status": "completed",
                "agent": selected.get("name"),
                "agent_id": selected.get("agent_id"),
                "provider": result.get("model_provider"),
                "model": result.get("model_name"),
                "duration_ms": result.get("duration_ms"),
                "message": message,
                "final": True,
            },
        )

    @staticmethod
    def _safe_error_message(error: Exception) -> str:
        """Keep provider payloads and credentials out of SSE events and the UI."""
        if isinstance(error, AIAuthenticationError):
            return "AI provider authentication failed. Contact an administrator."
        if isinstance(error, AIRateLimitError):
            return "AI provider rate limit reached. Please try again shortly."
        if isinstance(error, (AIConnectionError, AITimeoutError)):
            return "AI provider is temporarily unavailable. Please try again."
        if isinstance(error, AIProviderError):
            return "AI provider could not generate a response. Please try again."
        return "Runtime execution failed. Please try again or contact an administrator."

    @staticmethod
    def _error_code(error: Exception) -> str:
        if isinstance(error, AIAuthenticationError):
            return "PROVIDER_AUTH_FAILED"
        if isinstance(error, AIRateLimitError):
            return "PROVIDER_RATE_LIMITED"
        if isinstance(error, AITimeoutError):
            return "RUNTIME_TIMEOUT"
        if isinstance(error, AIConnectionError):
            return "PROVIDER_UNAVAILABLE"
        if isinstance(error, AIProviderError):
            return "MODEL_INVOCATION_FAILED"
        return "RUNTIME_EXECUTION_FAILED"

    async def _handle_runtime_event(self, event: Any) -> None:
        payload = event.payload
        execution_id = self._workflow_to_execution.get(payload.get("workflow_id", ""))
        if execution_id is None:
            return

        if isinstance(event, PlanningStarted):
            await self.publish_step(
                execution_id, "Planner", "Creating execution plan", "running"
            )
        elif isinstance(event, PlanningCompleted):
            await self.publish_step(
                execution_id,
                "Planner",
                "Execution plan created",
                "completed",
                plan=payload.get("plan"),
            )
        elif isinstance(event, PlanningFailed):
            await self.publish_step(
                execution_id, "Planner", "Planning failed", "failed"
            )
        elif isinstance(event, WorkflowStarted):
            await self.publish_step(
                execution_id, "Runtime Orchestrator", "Workflow started", "running"
            )
        elif isinstance(event, TaskStarted):
            agent = payload.get("agent") or "default-agent"
            await self.publish_step(
                execution_id,
                "Agent Selected",
                f"Selected {agent}",
                "completed",
                agent=agent,
            )
            await self.publish_step(
                execution_id,
                "Agent Execution",
                "Executing agent workflow",
                "running",
                agent=agent,
            )
        elif isinstance(event, TaskCompleted):
            await self.publish_step(
                execution_id,
                "Agent Execution",
                "Agent workflow completed",
                "completed",
                agent=payload.get("agent"),
            )
        elif isinstance(event, TaskFailed):
            await self.publish_step(
                execution_id,
                "Agent Execution",
                payload.get("error", "Agent failed"),
                "failed",
                agent=payload.get("agent"),
            )
        elif isinstance(event, WorkflowCompleted):
            await self.publish_step(
                execution_id,
                "Runtime Orchestrator",
                "Workflow execution completed",
                "completed",
            )
        elif isinstance(event, WorkflowFailed):
            await self.publish_step(
                execution_id,
                "Runtime Orchestrator",
                "Workflow execution failed",
                "failed",
            )

    async def publish_step(
        self,
        execution_id: str,
        name: str,
        description: str,
        status: str,
        *,
        agent: str | None = None,
        final: bool = False,
        **extra: Any,
    ) -> None:
        event = {
            "type": "completed" if final and status == "completed" else "step",
            "name": name,
            "description": description,
            "status": status,
            "timestamp": datetime.now(UTC).isoformat(),
            "final": final,
            **extra,
        }
        event.setdefault("step_id", self._step_id(name))
        if agent:
            event["agent"] = agent
        await self.publish_event(execution_id, event)

    async def publish_event(self, execution_id: str, event: dict[str, Any]) -> None:
        event.setdefault("timestamp", datetime.now(UTC).isoformat())
        event.setdefault("final", False)
        event = self.append_runtime_event(execution_id, event)
        await self._tracker.publish(execution_id, event)

    @staticmethod
    def _step_id(name: str) -> str:
        return "-".join(part for part in name.lower().replace("/", " ").split() if part)

    def append_runtime_event(
        self, execution_id: str | UUID, event: dict[str, Any]
    ) -> dict[str, Any]:
        """Durably append an informational event under the execution row lock."""
        execution_uuid = (
            execution_id if isinstance(execution_id, UUID) else UUID(execution_id)
        )
        for attempt in range(1, 3):
            db = SessionLocal()
            try:
                record = (
                    db.query(RuntimeExecution)
                    .filter(RuntimeExecution.id == execution_uuid)
                    .with_for_update()
                    .one_or_none()
                )
                if record is None:
                    return event
                ownership_attempt = getattr(self, "_owned_attempts", {}).get(
                    str(record.id)
                )
                if ownership_attempt is not None:
                    assert_execution_lease(
                        record,
                        worker_id=self.worker_id,
                        attempt=ownership_attempt,
                    )
                if record.status in self._TERMINAL_STATUSES:
                    terminal = self._terminal_event_locked(db, record)
                    if terminal is not None:
                        return dict(terminal.payload)
                durable_event = self._append_runtime_event_locked(db, record, event)
                db.commit()
                return durable_event
            except IntegrityError as exc:
                db.rollback()
                if not self._is_runtime_sequence_conflict(exc):
                    RUNTIME_EVENT_APPEND_FAILURE.labels(reason="integrity_error").inc()
                    raise
                RUNTIME_EVENT_SEQUENCE_CONFLICT.inc()
                logger.warning(
                    "Runtime event sequence conflict",
                    extra={
                        "execution_id": str(execution_uuid),
                        "event_type": event.get("type", "step"),
                        "attempt": attempt,
                        "database_dialect": db.bind.dialect.name
                        if db.bind
                        else "unknown",
                        "status": "retrying" if attempt == 1 else "failed",
                    },
                )
                if attempt == 2:
                    RUNTIME_EVENT_APPEND_FAILURE.labels(
                        reason="sequence_conflict"
                    ).inc()
                    raise
                RUNTIME_EVENT_APPEND_RETRY.inc()
            except Exception:
                db.rollback()
                RUNTIME_EVENT_APPEND_FAILURE.labels(reason="append_error").inc()
                raise
            finally:
                db.close()
        raise RuntimeError("runtime event append attempts exhausted")

    @staticmethod
    def _is_runtime_sequence_conflict(exc: IntegrityError) -> bool:
        message = str(exc.orig).lower()
        return "uq_runtime_event_sequence" in message or (
            "runtime_execution_events.execution_id" in message
            and "runtime_execution_events.sequence" in message
        )

    # Compatibility for tests and older internal callers. The implementation is
    # now a canonical locked append rather than the original COUNT(*) writer.
    def _append_step(self, execution_id: str, event: dict[str, Any]) -> dict[str, Any]:
        return self.append_runtime_event(execution_id, event)

    def _append_runtime_event_locked(
        self,
        db: Session,
        record: RuntimeExecution,
        event: dict[str, Any],
    ) -> dict[str, Any]:
        event = dict(event)
        # The parent row is the per-execution serialization point. The increment
        # self-heals a stale counter from committed event history and the event
        # insert shares this transaction, so rollback reverts both.
        db.flush()
        persisted_max = db.execute(
            select(func.coalesce(func.max(RuntimeExecutionEvent.sequence), 0)).where(
                RuntimeExecutionEvent.execution_id == record.id
            )
        ).scalar_one()
        stored_counter = int(record.last_event_sequence or 0)
        max_sequence = (
            select(func.coalesce(func.max(RuntimeExecutionEvent.sequence), 0))
            .where(RuntimeExecutionEvent.execution_id == RuntimeExecution.id)
            .correlate(RuntimeExecution)
            .scalar_subquery()
        )
        sequence = db.execute(
            update(RuntimeExecution)
            .where(RuntimeExecution.id == record.id)
            .values(
                last_event_sequence=case(
                    (
                        RuntimeExecution.last_event_sequence < max_sequence,
                        max_sequence + 1,
                    ),
                    else_=RuntimeExecution.last_event_sequence + 1,
                )
            )
            .returning(RuntimeExecution.last_event_sequence)
            .execution_options(synchronize_session=False)
        ).scalar_one()
        db.refresh(record)
        if stored_counter < persisted_max:
            RUNTIME_EVENT_COUNTER_DRIFT_DETECTED.inc()
            RUNTIME_EVENT_COUNTER_RECONCILED.inc()
            logger.warning(
                "Runtime event counter drift reconciled",
                extra={
                    "execution_id": str(record.id),
                    "event_type": event.get("type", "step"),
                    "stored_counter": stored_counter,
                    "observed_max_sequence": persisted_max,
                    "allocated_sequence": sequence,
                    "database_dialect": db.bind.dialect.name if db.bind else "unknown",
                    "status": "reconciled",
                },
            )
        event.setdefault("timestamp", datetime.now(UTC).isoformat())
        event.setdefault("final", False)
        event.setdefault("aggregate_status", record.status)
        event.setdefault("component_type", "runtime")
        event.setdefault("component_id", str(record.id))
        event.setdefault("component_status", event.get("status") or record.status)
        event.setdefault("execution_id", str(record.id))
        event.setdefault("workflow_id", str(record.workflow_id))
        event["state_version"] = record.state_version or 0

        step_id = event.get("step_id") or self._step_id(
            event.get("name") or event.get("type", "event")
        )
        event["step_id"] = step_id
        self._update_step_projection(record, event)

        event_id = uuid4()
        event["event_id"] = str(event_id)
        event["sequence"] = sequence
        db.add(
            RuntimeExecutionEvent(
                id=event_id,
                execution_id=record.id,
                sequence=sequence,
                state_version=record.state_version or 0,
                event_type=event.get("type", "step"),
                aggregate_status=event.get("aggregate_status"),
                component_type=event.get("component_type"),
                component_id=event.get("component_id"),
                component_status=event.get("component_status"),
                final=bool(event.get("final")),
                name=event.get("name"),
                status=event.get("status"),
                description=event.get("description"),
                payload=event,
            )
        )
        db.flush()
        return event

    @staticmethod
    def check_execution_event_sequence(
        db: Session, execution_id: str | UUID
    ) -> dict[str, Any]:
        """Return a safe, read-only consistency summary for one execution."""
        execution_uuid = (
            execution_id if isinstance(execution_id, UUID) else UUID(execution_id)
        )
        record = db.get(RuntimeExecution, execution_uuid)
        if record is None:
            raise LookupError(f"Runtime execution '{execution_uuid}' was not found")
        event_count, max_sequence, distinct_sequences = db.execute(
            select(
                func.count(RuntimeExecutionEvent.id),
                func.coalesce(func.max(RuntimeExecutionEvent.sequence), 0),
                func.count(func.distinct(RuntimeExecutionEvent.sequence)),
            ).where(RuntimeExecutionEvent.execution_id == execution_uuid)
        ).one()
        duplicate_count = int(event_count) - int(distinct_sequences)
        counter = int(record.last_event_sequence or 0)
        return {
            "execution_id": str(execution_uuid),
            "counter": counter,
            "max_sequence": int(max_sequence),
            "event_count": int(event_count),
            "duplicate_count": duplicate_count,
            "consistent": counter >= int(max_sequence) and duplicate_count == 0,
        }

    @staticmethod
    def _terminal_event_locked(
        db: Session, record: RuntimeExecution
    ) -> RuntimeExecutionEvent | None:
        expected_type = RuntimeExecutionService._TERMINAL_EVENT_TYPES[record.status]
        return (
            db.query(RuntimeExecutionEvent)
            .filter(
                RuntimeExecutionEvent.execution_id == record.id,
                RuntimeExecutionEvent.event_type == expected_type,
                RuntimeExecutionEvent.final.is_(True),
            )
            .one_or_none()
        )

    def _ensure_terminal_event_locked(
        self, db: Session, record: RuntimeExecution
    ) -> dict[str, Any]:
        existing = self._terminal_event_locked(db, record)
        if existing is not None:
            return dict(existing.payload)
        payload = {
            "type": self._TERMINAL_EVENT_TYPES[record.status],
            "name": self._event_name_for_status(record.status),
            "description": record.error
            or self._event_description_for_status(record.status),
            "status": record.status.lower(),
            "aggregate_status": record.status,
            "component_type": "runtime",
            "component_id": str(record.id),
            "component_status": record.status,
            "final": True,
            "message": record.result_message,
            "error": record.error,
            "duration_ms": record.duration_ms,
        }
        return self._append_runtime_event_locked(db, record, payload)

    @staticmethod
    def _update_step_projection(
        record: RuntimeExecution, event: dict[str, Any]
    ) -> None:
        steps = list(record.steps or [])
        step_id = event["step_id"]
        existing_index = next(
            (index for index, step in enumerate(steps) if step.get("id") == step_id),
            None,
        )
        persisted_step = {
            "id": step_id,
            "name": event.get("name") or event.get("type", "Event"),
            "description": event.get("description", ""),
            "status": event.get("status", "running"),
            "timestamp": event["timestamp"],
        }
        if event.get("type") not in {
            "metric",
            "log",
            "heartbeat",
            "knowledge_retrieval_completed",
            "knowledge_retrieval_started",
        }:
            if existing_index is None:
                steps.append(persisted_step)
            else:
                steps[existing_index] = persisted_step
            record.steps = steps
        if event.get("type") == "metric":
            metric = event.get("metadata") or {}
            record.token_usage = metric.get("token_usage") or record.token_usage
            record.estimated_cost = metric.get("estimated_cost", record.estimated_cost)
            record.actual_cost = metric.get("actual_cost", record.actual_cost)
            record.provider_name = event.get("provider") or record.provider_name
            record.model_name = event.get("model") or record.model_name

    def _complete_execution(
        self,
        execution_id: str,
        *,
        status: str,
        agent: str | None = None,
        message: str | None = None,
        duration_ms: float | None = None,
        error: str | None = None,
        error_code: str | None = None,
    ) -> None:
        # duration_ms is retained in the signature for compatibility with callers,
        # but canonical duration is always derived from durable lifecycle timestamps.
        self.transition_execution(
            execution_id,
            status,
            agent=agent,
            result_message=message,
            error_message=error,
            error_code=error_code,
            worker_id=self.worker_id,
            ownership_attempt=self._owned_attempts.get(execution_id),
        )

    async def stream(
        self, execution_id: str, *, after_sequence: int = 0
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Stream durable events after a sequence cursor.

        The process-local tracker only shortens local delivery latency. Every
        iteration rechecks the database, so another backend instance's commits
        are discovered without a tracker notification.
        """
        execution_uuid = UUID(execution_id)
        last_sequence = max(0, after_sequence)
        queue = self._tracker.subscribe(execution_id)
        heartbeat_elapsed = 0.0
        poll_interval = max(0.05, settings.RUNTIME_EVENT_POLL_INTERVAL_SECONDS)
        heartbeat_interval = max(poll_interval, settings.RUNTIME_SSE_HEARTBEAT_SECONDS)
        batch_size = max(1, settings.RUNTIME_EVENT_BATCH_SIZE)
        try:
            while True:
                events, runtime, terminal_sequence = self._read_durable_events(
                    execution_uuid,
                    after_sequence=last_sequence,
                    limit=batch_size,
                )
                for event in events:
                    sequence = int(event.get("sequence") or 0)
                    if sequence <= last_sequence:
                        continue
                    last_sequence = sequence
                    yield event
                    if event.get("final"):
                        return
                if len(events) >= batch_size:
                    continue

                if runtime is None:
                    return
                if runtime["status"] in self._TERMINAL_STATUSES:
                    if (
                        terminal_sequence is not None
                        and terminal_sequence <= last_sequence
                    ):
                        return
                    if terminal_sequence is None:
                        logger.error(
                            "Terminal runtime is missing its durable terminal event",
                            extra={
                                "execution_id": execution_id,
                                "status": runtime["status"],
                            },
                        )
                        yield self._terminal_stream_fallback(runtime)
                        return

                try:
                    await asyncio.wait_for(queue.get(), timeout=poll_interval)
                except TimeoutError:
                    heartbeat_elapsed += poll_interval
                    if heartbeat_elapsed >= heartbeat_interval:
                        heartbeat_elapsed = 0.0
                        yield {"type": "heartbeat"}
                else:
                    heartbeat_elapsed = 0.0
        finally:
            self._tracker.unsubscribe(execution_id, queue)

    @staticmethod
    def _read_durable_events(
        execution_id: UUID, *, after_sequence: int, limit: int
    ) -> tuple[list[dict[str, Any]], dict[str, Any] | None, int | None]:
        """Read one ordered batch using a short-lived database session."""
        db = SessionLocal()
        try:
            rows = (
                db.query(RuntimeExecutionEvent)
                .filter(
                    RuntimeExecutionEvent.execution_id == execution_id,
                    RuntimeExecutionEvent.sequence > after_sequence,
                )
                .order_by(RuntimeExecutionEvent.sequence.asc())
                .limit(limit)
                .all()
            )
            record = db.get(RuntimeExecution, execution_id)
            runtime = None
            terminal_sequence = None
            if record is not None:
                runtime = {
                    "id": str(record.id),
                    "workflow_id": str(record.workflow_id),
                    "status": record.status,
                    "completed_at": record.completed_at,
                    "started_at": record.started_at,
                    "result_message": record.result_message,
                    "duration_ms": record.duration_ms,
                    "agent": record.agent,
                    "error": record.error,
                }
                terminal_sequence = (
                    db.query(RuntimeExecutionEvent.sequence)
                    .filter(
                        RuntimeExecutionEvent.execution_id == execution_id,
                        RuntimeExecutionEvent.final.is_(True),
                        RuntimeExecutionEvent.component_type == "runtime",
                    )
                    .scalar()
                )
            return [dict(row.payload) for row in rows], runtime, terminal_sequence
        finally:
            db.close()

    @staticmethod
    def _terminal_stream_fallback(runtime: dict[str, Any]) -> dict[str, Any]:
        status = runtime["status"]
        occurred_at = runtime["completed_at"] or runtime["started_at"]
        return {
            "type": RuntimeExecutionService._TERMINAL_EVENT_TYPES[status],
            "name": "Result Generated"
            if status == "COMPLETED"
            else "Runtime Execution",
            "description": runtime["error"]
            or RuntimeExecutionService._event_description_for_status(status),
            "status": status.lower(),
            "aggregate_status": status,
            "component_type": "runtime",
            "component_id": runtime["id"],
            "component_status": status,
            "timestamp": occurred_at.isoformat()
            if occurred_at
            else datetime.now(UTC).isoformat(),
            "final": True,
            "message": runtime["result_message"],
            "error": runtime["error"],
            "duration_ms": runtime["duration_ms"],
            "agent": runtime["agent"],
            "execution_id": runtime["id"],
            "workflow_id": runtime["workflow_id"],
            "recovery_fallback": True,
        }


runtime_execution_service = RuntimeExecutionService()

from app.runtime.recovery import RuntimeRecoveryService  # noqa: E402, I001 -- late import breaks a runtime dependency cycle

runtime_recovery_service = RuntimeRecoveryService(runtime_execution_service)
