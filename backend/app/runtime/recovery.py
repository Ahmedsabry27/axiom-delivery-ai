from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import or_

from app.audit.events import append_audit_event
from app.core.config import settings
from app.database.models.agent_execution import AgentExecution
from app.database.models.tool import ToolDefinition, ToolExecution
from app.database.session import SessionLocal
from app.metrics.runtime_metrics import (
    RUNTIME_RECOVERIES,
    RUNTIME_RECOVERY_FAILURES,
    RUNTIME_STALE,
)
from app.models.runtime_execution import RuntimeExecution
from app.runtime.leases import claim_locked_execution, utcnow

if TYPE_CHECKING:
    from app.services.runtime_execution_service import RuntimeExecutionService

logger = logging.getLogger(__name__)


class RuntimeRecoveryService:
    """Conservatively reclaim or terminalize executions abandoned by a worker."""

    def __init__(self, runtime_service: RuntimeExecutionService) -> None:
        self.runtime_service = runtime_service
        self._loop_task: asyncio.Task[None] | None = None

    def find_stale_execution_ids(self) -> list[str]:
        with SessionLocal() as db:
            rows = (
                db.query(RuntimeExecution.id)
                .filter(
                    RuntimeExecution.status == "RUNNING",
                    or_(
                        RuntimeExecution.lease_owner.is_(None),
                        RuntimeExecution.lease_expires_at.is_(None),
                        RuntimeExecution.lease_expires_at < utcnow(),
                    ),
                )
                .order_by(RuntimeExecution.lease_expires_at)
                .limit(settings.RUNTIME_RECOVERY_BATCH_SIZE)
                .all()
            )
            return [str(row[0]) for row in rows]

    async def reconcile_once(self) -> int:
        recovered = 0
        for execution_id in self.find_stale_execution_ids():
            RUNTIME_STALE.inc()
            if await self.reconcile_execution(execution_id):
                recovered += 1
        return recovered

    async def reconcile_execution(self, execution_id: str) -> bool:

        execution_uuid = UUID(execution_id)
        with SessionLocal() as db:
            record = (
                db.query(RuntimeExecution)
                .filter(RuntimeExecution.id == execution_uuid)
                .with_for_update(skip_locked=True)
                .one_or_none()
            )
            now = utcnow()
            if (
                record is None
                or record.status != "RUNNING"
                or (
                    record.lease_owner is not None
                    and record.lease_expires_at is not None
                    and record.lease_expires_at >= now
                )
            ):
                return False
            previous_owner = record.lease_owner

            if record.deadline_at is not None and record.deadline_at <= now:
                self.runtime_service.transition_execution(
                    record.id,
                    "TIMED_OUT",
                    expected_statuses={"RUNNING"},
                    error_code="RUNTIME_TIMEOUT",
                    error_message="Runtime execution deadline exceeded during recovery",
                    event_type="runtime.timed_out",
                    db=db,
                    commit=False,
                )
                db.commit()
                RUNTIME_RECOVERY_FAILURES.labels(code="RUNTIME_TIMEOUT").inc()
                return True

            if (record.attempt or 1) >= settings.RUNTIME_MAX_RECOVERY_ATTEMPTS:
                self.runtime_service.transition_execution(
                    record.id,
                    "FAILED",
                    expected_statuses={"RUNNING"},
                    error_code="RECOVERY_ATTEMPTS_EXHAUSTED",
                    error_message="Runtime recovery attempts were exhausted",
                    event_type="runtime.recovery_exhausted",
                    db=db,
                    commit=False,
                )
                db.commit()
                RUNTIME_RECOVERY_FAILURES.labels(
                    code="RECOVERY_ATTEMPTS_EXHAUSTED"
                ).inc()
                return True

            agents = (
                db.query(AgentExecution)
                .filter(AgentExecution.runtime_execution_id == str(record.id))
                .with_for_update()
                .all()
            )
            correlations = [
                str(record.workflow_id),
                *[row.correlation_id for row in agents],
            ]
            tool_ids = {
                item for row in agents for item in (row.tool_execution_ids or [])
            }
            tools = (
                db.query(ToolExecution)
                .filter(
                    or_(
                        ToolExecution.correlation_id.in_(correlations),
                        ToolExecution.id.in_(tool_ids) if tool_ids else False,
                    )
                )
                .with_for_update()
                .all()
            )

            if any(tool.status == "timed_out" for tool in tools):
                target, code, message = (
                    "TIMED_OUT",
                    "CHILD_EXECUTION_TIMEOUT",
                    "A required tool timed out before worker loss",
                )
            elif any(tool.status == "failed" for tool in tools) or any(
                agent.status == "failed" for agent in agents
            ):
                target, code, message = (
                    "FAILED",
                    "CHILD_EXECUTION_FAILED",
                    "A required child failed before worker loss",
                )
            else:
                target = code = message = None
            if target:
                self.runtime_service.transition_execution(
                    record.id,
                    target,
                    expected_statuses={"RUNNING"},
                    error_code=code,
                    error_message=message,
                    db=db,
                    commit=False,
                )
                db.commit()
                RUNTIME_RECOVERY_FAILURES.labels(code=code).inc()
                return True

            definitions = {
                item.name: item
                for item in db.query(ToolDefinition)
                .filter(ToolDefinition.tenant_id == record.tenant_id)
                .all()
            }
            running_tools = [tool for tool in tools if tool.status == "running"]
            unsafe = [
                tool
                for tool in running_tools
                if definitions.get(tool.tool_name) is None
                or definitions[tool.tool_name].risk_level != "read"
            ]
            if unsafe:
                self.runtime_service.transition_execution(
                    record.id,
                    "FAILED",
                    expected_statuses={"RUNNING"},
                    error_code="RECOVERY_UNCERTAIN_EXTERNAL_ACTION",
                    error_message="External action outcome is unknown after worker loss; it was not replayed",
                    event_type="runtime.recovery_failed",
                    event_payload={"unsafe_tools": [tool.tool_name for tool in unsafe]},
                    db=db,
                    commit=False,
                )
                db.commit()
                RUNTIME_RECOVERY_FAILURES.labels(
                    code="RECOVERY_UNCERTAIN_EXTERNAL_ACTION"
                ).inc()
                return True

            succeeded_writes = [
                tool
                for tool in tools
                if tool.status == "succeeded"
                and definitions.get(tool.tool_name) is not None
                and definitions[tool.tool_name].risk_level != "read"
            ]
            if succeeded_writes:
                result = succeeded_writes[-1].output_summary
                completed_at = datetime.now(UTC)
                for agent in agents:
                    if agent.status in {"queued", "running"}:
                        agent.status = "succeeded"
                        agent.current_phase = "succeeded"
                        agent.completed_at = completed_at
                self.runtime_service.transition_execution(
                    record.id,
                    "COMPLETED",
                    expected_statuses={"RUNNING"},
                    result_message=str(result)
                    if result is not None
                    else "External action completed successfully.",
                    event_type="runtime.completed",
                    event_payload={
                        "recovered_from_persisted_child": succeeded_writes[-1].id
                    },
                    db=db,
                    commit=False,
                )
                db.commit()
                return True

            for tool in running_tools:
                tool.status = "failed"
                tool.finished_at = datetime.now(UTC)
                tool.error_code = "WORKER_LOSS_RETRY"
                tool.error_message = (
                    "Read-only tool attempt abandoned after worker loss"
                )
            for agent in agents:
                if agent.status in {"queued", "running"}:
                    agent.status = "failed"
                    agent.current_phase = "failed"
                    agent.completed_at = datetime.now(UTC)
                    agent.error_code = "WORKER_LOSS_RETRY"
                    agent.safe_error_message = (
                        "Agent attempt abandoned after worker loss"
                    )

            attempt = claim_locked_execution(
                record,
                worker_id=self.runtime_service.worker_id,
                recovery=True,
            )
            record.state_version = (record.state_version or 0) + 1
            self.runtime_service._append_runtime_event_locked(
                db,
                record,
                {
                    "type": "runtime.recovered",
                    "name": "Runtime Recovered",
                    "description": "Stale execution ownership was reclaimed",
                    "status": "running",
                    "aggregate_status": "RUNNING",
                    "component_type": "runtime",
                    "component_id": str(record.id),
                    "component_status": "RUNNING",
                    "final": False,
                    "previous_lease_owner": previous_owner,
                    "new_lease_owner": self.runtime_service.worker_id,
                    "attempt": attempt,
                    "reason": "lease_expired",
                },
            )
            append_audit_event(
                db,
                tenant_id=record.tenant_id,
                actor_id="runtime-recovery",
                action="runtime.recovered",
                target_type="runtime_execution",
                target_id=str(record.id),
                correlation_id=str(record.workflow_id),
                metadata={
                    "previous_lease_owner": previous_owner,
                    "new_lease_owner": self.runtime_service.worker_id,
                    "attempt": attempt,
                    "reason": "lease_expired",
                },
            )
            db.commit()
            db.refresh(record)

        self.runtime_service.launch_recovered_execution(record)
        RUNTIME_RECOVERIES.inc()
        logger.info(
            "Runtime execution reclaimed",
            extra={
                "execution_id": execution_id,
                "worker_id": self.runtime_service.worker_id,
                "attempt": attempt,
            },
        )
        return True

    async def run_forever(self) -> None:
        while True:
            try:
                await self.reconcile_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Runtime recovery sweep failed")
            await asyncio.sleep(settings.RUNTIME_RECOVERY_INTERVAL_SECONDS)

    async def start(self) -> None:
        if self._loop_task is not None and not self._loop_task.done():
            return
        await self.reconcile_once()
        self._loop_task = asyncio.create_task(self.run_forever())

    async def stop(self) -> None:
        if self._loop_task is None:
            return
        self._loop_task.cancel()
        await asyncio.gather(self._loop_task, return_exceptions=True)
        self._loop_task = None
