from __future__ import annotations

import asyncio
import random
import time
from datetime import UTC, datetime
from uuid import uuid4

from prometheus_client import Counter, Gauge, Histogram
from sqlalchemy.orm import Session

from app.contracts.tool_models import ExecutionContext, ExecutionEnvelope, ToolError
from app.database.models.tool import ToolExecution
from app.database.models.tool_discovery import ToolMarketplaceProfile
from app.logging.logger import logger
from app.tool_sdk.errors import (
    PermissionDeniedError,
    ToolDisabledError,
    ToolSDKError,
    ToolTimeoutError,
    redact,
)
from app.tool_sdk.schema import validate_and_default

EXECUTIONS = Counter("tool_execution_total", "Tool executions", ["tool", "status"])
DURATION = Histogram(
    "tool_execution_duration_seconds", "Tool execution duration", ["tool"]
)
FAILURES = Counter("tool_failure_total", "Tool failures", ["tool", "code"])
REGISTRY_SIZE = Gauge("tool_registry_size", "Registered tool versions")


class ToolExecutor:
    def __init__(self, registry):
        self.registry = registry
        REGISTRY_SIZE.set(len(registry.list()))

    async def execute(
        self, name, input_data, context: ExecutionContext, db: Session, version=None
    ):
        tool = self.registry.get(name, version)
        meta = tool.metadata
        if not self.registry.is_enabled(tool):
            raise ToolDisabledError(f"Tool '{name}' is disabled")
        missing = set(meta.permissions) - context.permissions
        if missing and "tools.admin" not in context.permissions:
            raise PermissionDeniedError(
                "Caller does not have the required tool permission",
                fields=[
                    {"field": "permissions", "message": p} for p in sorted(missing)
                ],
            )
        normalized = validate_and_default(meta.parameters, input_data)
        profile = (
            db.query(ToolMarketplaceProfile)
            .filter_by(
                tenant_id=context.tenant_id,
                tool_name=name,
                tool_version=meta.version,
            )
            .first()
        )
        if profile:
            from app.tool_discovery.governance import evaluate
            from app.tool_discovery.intent import extract_intent

            policy = evaluate(
                db,
                tool,
                context,
                extract_intent(
                    name.replace("_", " "),
                    context.environment,
                    context.data_classification,
                ),
                profile,
            )
            if policy.decision == "deny":
                raise PermissionDeniedError(policy.safe_explanation)
            if policy.decision == "approval_required":
                from app.governance.workflows import consume_approval

                consume_approval(
                    db,
                    request_id=context.approval_request_id,
                    token=context.approval_resume_token,
                    tool=tool,
                    normalized_input=normalized,
                    context=context,
                    policy_ids=policy.policy_ids,
                )
            if (
                context.max_cost is not None
                and profile.estimated_cost is not None
                and profile.estimated_cost > context.max_cost
            ):
                raise PermissionDeniedError("Tool exceeds the execution cost limit")
        if len(str(normalized).encode()) > 256_000:
            from app.tool_sdk.errors import InvalidToolInputError

            raise InvalidToolInputError("Tool input exceeds 256 KB")
        if context.idempotency_key:
            prior = (
                db.query(ToolExecution)
                .filter_by(
                    tenant_id=context.tenant_id,
                    tool_name=name,
                    idempotency_key=context.idempotency_key,
                )
                .first()
            )
            if prior and prior.status == "succeeded":
                return self._envelope(prior, meta, prior.output_summary, None)
        row = ToolExecution(
            id=str(uuid4()),
            tenant_id=context.tenant_id,
            tool_name=name,
            tool_version=meta.version,
            actor_id=context.actor_id,
            agent_id=context.agent_id,
            status="running",
            correlation_id=context.correlation_id,
            trace_id=context.trace_id,
            input_summary=redact(normalized),
            idempotency_key=context.idempotency_key,
        )
        db.add(row)
        db.commit()
        started = time.perf_counter()
        attempt = 0
        try:
            while True:
                attempt += 1
                try:
                    result = await asyncio.wait_for(
                        tool.execute(
                            normalized, context.model_copy(update={"db_session": db})
                        ),
                        timeout=meta.timeout_seconds,
                    )
                    break
                except asyncio.TimeoutError as exc:
                    raise ToolTimeoutError(
                        f"Tool exceeded its {meta.timeout_seconds}s timeout"
                    ) from exc
                except ToolSDKError as exc:
                    if not exc.retryable or attempt >= meta.retry_policy.max_attempts:
                        raise
                    await asyncio.sleep(
                        meta.retry_policy.base_delay_seconds * (2 ** (attempt - 1))
                        + random.uniform(0, 0.1)
                    )
            if not result.success:
                raise ToolSDKError(
                    result.error.message if result.error else "Tool failed"
                )
            if meta.output_schema:
                validate_and_default(meta.output_schema, result.data, output=True)
            safe = redact(result.data)
            if len(str(safe).encode()) > 1_000_000:
                safe = {"truncated": True, "preview": str(safe)[:50_000]}
            self._finish(
                db,
                row,
                "succeeded",
                started,
                output=safe,
                retries=attempt - 1,
                provider_request_id=result.provider_request_id,
            )
            EXECUTIONS.labels(name, "succeeded").inc()
            DURATION.labels(name).observe((row.duration_ms or 0) / 1000)
            logger.info(
                "Tool execution succeeded",
                extra={
                    "execution_id": row.id,
                    "tool": name,
                    "version": meta.version,
                    "correlation_id": context.correlation_id,
                    "duration_ms": row.duration_ms,
                },
            )
            return self._envelope(row, meta, safe, None)
        except asyncio.CancelledError:
            self._finish(
                db,
                row,
                "cancelled",
                started,
                code="EXECUTION_CANCELLED",
                message="Execution was cancelled",
            )
            raise
        except ToolSDKError as exc:
            status = "timed_out" if exc.code == "EXECUTION_TIMEOUT" else "failed"
            self._finish(
                db,
                row,
                status,
                started,
                code=exc.code,
                message=exc.safe_message,
                retries=attempt - 1,
            )
            EXECUTIONS.labels(name, status).inc()
            FAILURES.labels(name, exc.code).inc()
            logger.warning(
                "Tool execution failed",
                extra={
                    "execution_id": row.id,
                    "tool": name,
                    "correlation_id": context.correlation_id,
                    "error_code": exc.code,
                },
            )
            return self._envelope(
                row,
                meta,
                None,
                ToolError(
                    code=exc.code,
                    message=exc.safe_message,
                    retryable=exc.retryable,
                    fields=exc.fields,
                ),
            )
        except Exception:  # noqa: BLE001 -- executor boundary records sanitized plugin failures
            self._finish(
                db,
                row,
                "failed",
                started,
                code="TOOL_EXECUTION_FAILED",
                message="The tool could not complete the request",
                retries=attempt - 1,
            )
            EXECUTIONS.labels(name, "failed").inc()
            FAILURES.labels(name, "TOOL_EXECUTION_FAILED").inc()
            logger.exception(
                "Unexpected tool execution failure",
                extra={"execution_id": row.id, "tool": name},
            )
            return self._envelope(
                row,
                meta,
                None,
                ToolError(
                    code="TOOL_EXECUTION_FAILED",
                    message="The tool could not complete the request",
                ),
            )

    @staticmethod
    def _finish(
        db,
        row,
        status,
        started,
        output=None,
        code=None,
        message=None,
        retries=0,
        provider_request_id=None,
    ):
        db.refresh(row)
        if row.status in {"cancelled", "timed_out"}:
            # A parent cancellation/timeout won a race while the connector was
            # in flight. Preserve the first terminal child outcome; external
            # side effects, if any, are not claimed to have been rolled back.
            return
        row.status = status
        row.finished_at = datetime.now(UTC)
        row.duration_ms = round((time.perf_counter() - started) * 1000, 2)
        row.output_summary = output
        row.error_code = code
        row.error_message = message
        row.retry_count = retries
        row.provider_request_id = provider_request_id
        from app.audit.events import append_audit_event

        append_audit_event(
            db,
            tenant_id=row.tenant_id,
            actor_id=row.actor_id,
            action="tool.execution.completed",
            target_type="tool_execution",
            target_id=row.id,
            correlation_id=row.correlation_id,
            after={"status": status, "tool": row.tool_name, "error_code": code},
        )
        db.commit()
        db.refresh(row)

    @staticmethod
    def _envelope(row, meta, data, error):
        return ExecutionEnvelope(
            execution_id=row.id,
            tool={"name": meta.name, "version": meta.version},
            status=row.status,
            data=data,
            error=error,
            meta={
                "duration_ms": row.duration_ms,
                "correlation_id": row.correlation_id,
                "provider_request_id": row.provider_request_id,
            },
        )
