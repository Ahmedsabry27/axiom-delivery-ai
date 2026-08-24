from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, ClassVar

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database.models.agent_execution import AgentContinuation, AgentExecution
from app.database.models.tool import ToolExecution
from app.models.runtime_execution import RuntimeContinuation

if TYPE_CHECKING:
    from app.models.runtime_execution import RuntimeExecution


class ChildOutcome(StrEnum):
    ACTIVE = "active"
    WAITING_FOR_INPUT = "waiting_for_input"
    WAITING_FOR_APPROVAL = "waiting_for_approval"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


AGENT_OUTCOMES = {
    "queued": ChildOutcome.ACTIVE,
    "running": ChildOutcome.ACTIVE,
    "waiting_for_input": ChildOutcome.WAITING_FOR_INPUT,
    "waiting_for_clarification": ChildOutcome.WAITING_FOR_INPUT,
    "waiting_for_approval": ChildOutcome.WAITING_FOR_APPROVAL,
    "succeeded": ChildOutcome.SUCCEEDED,
    "failed": ChildOutcome.FAILED,
    "cancelled": ChildOutcome.CANCELLED,
    # Expiry means the resumable execution exceeded its continuation window.
    "expired": ChildOutcome.TIMED_OUT,
    "timed_out": ChildOutcome.TIMED_OUT,
}

TOOL_OUTCOMES = {
    "running": ChildOutcome.ACTIVE,
    "succeeded": ChildOutcome.SUCCEEDED,
    "failed": ChildOutcome.FAILED,
    "timed_out": ChildOutcome.TIMED_OUT,
    "cancelled": ChildOutcome.CANCELLED,
}


def map_agent_execution_status(status: str) -> ChildOutcome:
    try:
        return AGENT_OUTCOMES[status]
    except KeyError as exc:
        raise ValueError(f"Unknown AgentExecution status: {status}") from exc


def map_tool_execution_status(status: str) -> ChildOutcome:
    try:
        return TOOL_OUTCOMES[status]
    except KeyError as exc:
        raise ValueError(f"Unknown ToolExecution status: {status}") from exc


@dataclass
class ChildExecutionSummary:
    active: int = 0
    waiting_for_input: int = 0
    waiting_for_approval: int = 0
    succeeded: int = 0
    failed: int = 0
    timed_out: int = 0
    cancelled: int = 0
    agent_execution_ids: list[str] | None = None
    tool_execution_ids: list[str] | None = None

    def add(self, outcome: ChildOutcome) -> None:
        setattr(self, outcome.value, getattr(self, outcome.value) + 1)

    def as_dict(self) -> dict:
        return asdict(self)


class RequiredChildStateError(RuntimeError):
    """Raised when required synchronous children forbid parent completion."""


class RuntimeChildReconciler:
    """Reconcile required synchronous children owned by one RuntimeExecution."""

    _NONTERMINAL_AGENT: ClassVar[set[str]] = {
        "queued",
        "running",
        "waiting_for_input",
        "waiting_for_clarification",
        "waiting_for_approval",
    }

    @staticmethod
    def _children(
        db: Session, runtime: RuntimeExecution
    ) -> tuple[list[AgentExecution], list[ToolExecution]]:
        agents = (
            db.query(AgentExecution)
            .filter(AgentExecution.runtime_execution_id == str(runtime.id))
            .order_by(AgentExecution.id)
            .with_for_update()
            .all()
        )
        correlations = [
            str(runtime.workflow_id),
            *[row.correlation_id for row in agents],
        ]
        tool_ids = {item for row in agents for item in (row.tool_execution_ids or [])}
        tools = (
            db.query(ToolExecution)
            .filter(
                or_(
                    ToolExecution.correlation_id.in_(correlations),
                    ToolExecution.id.in_(tool_ids) if tool_ids else False,
                )
            )
            .order_by(ToolExecution.id)
            .with_for_update()
            .all()
        )
        return agents, tools

    @staticmethod
    def _summary(
        agents: list[AgentExecution], tools: list[ToolExecution]
    ) -> ChildExecutionSummary:
        summary = ChildExecutionSummary(
            agent_execution_ids=[row.id for row in agents],
            tool_execution_ids=[row.id for row in tools],
        )
        for row in agents:
            if row.error_code == "WORKER_LOSS_RETRY":
                continue
            summary.add(map_agent_execution_status(row.status))
        for row in tools:
            if row.error_code == "WORKER_LOSS_RETRY":
                continue
            summary.add(map_tool_execution_status(row.status))
        return summary

    def reconcile(
        self, db: Session, runtime: RuntimeExecution, target_status: str
    ) -> ChildExecutionSummary:
        agents, tools = self._children(db, runtime)
        before = self._summary(agents, tools)

        if target_status == "COMPLETED":
            if any(
                getattr(before, name)
                for name in (
                    "active",
                    "waiting_for_input",
                    "waiting_for_approval",
                    "failed",
                    "timed_out",
                    "cancelled",
                )
            ):
                raise RequiredChildStateError(
                    "Required synchronous child executions did not all succeed"
                )
            return before

        if target_status not in {"FAILED", "CANCELLED", "TIMED_OUT"}:
            return before

        now = datetime.now(UTC)
        child_target = {
            "FAILED": "failed",
            "CANCELLED": "cancelled",
            "TIMED_OUT": "timed_out",
        }[target_status]
        for agent in agents:
            if agent.status not in self._NONTERMINAL_AGENT:
                continue
            agent.status = child_target
            agent.current_phase = child_target
            agent.completed_at = now
            if child_target == "cancelled":
                agent.cancelled_at = now
            if child_target == "failed":
                agent.error_code = agent.error_code or "PARENT_RUNTIME_FAILED"
                agent.safe_error_message = (
                    agent.safe_error_message or "Parent runtime execution failed"
                )
            elif child_target == "timed_out":
                agent.error_code = agent.error_code or "PARENT_RUNTIME_TIMEOUT"
                agent.safe_error_message = (
                    agent.safe_error_message or "Parent runtime execution timed out"
                )
            started = agent.started_at
            if started:
                started = started if started.tzinfo else started.replace(tzinfo=UTC)
                agent.duration_ms = round((now - started).total_seconds() * 1000, 2)

        agent_ids = [row.id for row in agents]
        if agent_ids:
            continuations = (
                db.query(AgentContinuation)
                .filter(
                    AgentContinuation.execution_id.in_(agent_ids),
                    AgentContinuation.status == "pending",
                )
                .order_by(AgentContinuation.id)
                .with_for_update()
                .all()
            )
            for continuation in continuations:
                continuation.status = "cancelled"
                continuation.cancelled_at = now

        runtime_continuations = (
            db.query(RuntimeContinuation)
            .filter(
                RuntimeContinuation.execution_id == runtime.id,
                RuntimeContinuation.status == "pending",
            )
            .order_by(RuntimeContinuation.id)
            .with_for_update()
            .all()
        )
        for continuation in runtime_continuations:
            continuation.status = "cancelled"
            continuation.consumed_at = now.replace(tzinfo=None)

        for tool in tools:
            if tool.status != "running":
                continue
            tool.status = child_target
            tool.finished_at = now
            tool.error_code = {
                "FAILED": "PARENT_RUNTIME_FAILED",
                "CANCELLED": "EXECUTION_CANCELLED",
                "TIMED_OUT": "EXECUTION_TIMEOUT",
            }[target_status]
            tool.error_message = {
                "FAILED": "Parent runtime execution failed",
                "CANCELLED": "Execution was cancelled",
                "TIMED_OUT": "Parent runtime execution timed out",
            }[target_status]
            started = tool.started_at
            if started:
                started = started if started.tzinfo else started.replace(tzinfo=UTC)
                tool.duration_ms = round((now - started).total_seconds() * 1000, 2)

        db.flush()
        return self._summary(agents, tools)


runtime_child_reconciler = RuntimeChildReconciler()
