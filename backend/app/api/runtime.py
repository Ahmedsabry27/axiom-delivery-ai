import json
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.agents.application_service import AgentIdentity
from app.auth.dependencies import get_current_user
from app.database.dependencies import get_db
from app.models.runtime_execution import (
    RuntimeContinuation,
    RuntimeExecution,
    RuntimeExecutionEvent,
)
from app.services.runtime_execution_service import (
    InvalidRuntimeTransitionError,
    runtime_execution_service,
)

router = APIRouter(prefix="/api/runtime", tags=["Runtime"])


def _tenant_id(user: dict) -> str:
    return str(user.get("custom:tenant_id", "default"))


class ContinueRequest(BaseModel):
    continuation_id: UUID
    values: dict = Field(default_factory=dict)
    message: str | None = Field(default=None, min_length=1, max_length=8000)


def _runtime_event_cursor(after_sequence: int | None, last_event_id: str | None) -> int:
    """Resolve the cursor; query parameter deterministically takes precedence."""
    if after_sequence is not None:
        return after_sequence
    if last_event_id in (None, ""):
        return 0
    try:
        cursor = int(last_event_id)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="Invalid Last-Event-ID") from exc
    if cursor < 0:
        raise HTTPException(status_code=400, detail="Invalid Last-Event-ID")
    return cursor


def _runtime_response(db: Session, execution: RuntimeExecution) -> dict:
    execution = runtime_execution_service.expire_continuations(db, execution)
    continuation = (
        db.query(RuntimeContinuation)
        .filter(
            RuntimeContinuation.execution_id == execution.id,
            RuntimeContinuation.status == "pending",
            RuntimeContinuation.consumed_at.is_(None),
        )
        .order_by(RuntimeContinuation.created_at.desc())
        .first()
    )
    continuation_payload = None
    if continuation is not None:
        schema = continuation.schema or {}
        continuation_payload = {
            "kind": continuation.kind,
            "continuation_id": str(continuation.id),
            "fields": schema.get("fields", []),
            "requested_fields": schema.get(
                "requested_fields",
                [field.get("name") for field in schema.get("fields", [])],
            ),
            "intent": schema.get("intent"),
            "capability": schema.get("capability"),
            "known_values": {
                key: value
                for key, value in (continuation.known_values or {}).items()
                if not key.startswith("_")
            },
            "required_role": continuation.required_role,
            "title": (
                "Approval required"
                if continuation.kind == "approval"
                else schema.get("title", "Additional information required")
            ),
            "description": (
                "A governed action requires approval."
                if continuation.kind == "approval"
                else schema.get(
                    "description",
                    "Provide the unresolved values needed to continue this plan.",
                )
            ),
            **(
                {"validation_feedback": schema["validation_feedback"]}
                if schema.get("validation_feedback") is not None
                else {}
            ),
            **(
                {"parameter_state_version": schema["parameter_state_version"]}
                if schema.get("parameter_state_version") is not None
                else {}
            ),
        }
    last_sequence = (
        db.query(RuntimeExecutionEvent.sequence)
        .filter(RuntimeExecutionEvent.execution_id == execution.id)
        .order_by(RuntimeExecutionEvent.sequence.desc())
        .limit(1)
        .scalar()
        or 0
    )
    now = datetime.now(UTC).replace(tzinfo=None)
    is_stale = bool(
        execution.status == "RUNNING"
        and execution.lease_expires_at is not None
        and execution.lease_expires_at < now
    )
    heartbeat_age_seconds = (
        max(0.0, (now - execution.heartbeat_at).total_seconds())
        if execution.heartbeat_at is not None
        else None
    )
    return {
        "execution_id": str(execution.id),
        "workflow_id": str(execution.workflow_id),
        "status": execution.status,
        "state_version": execution.state_version,
        "last_sequence": last_sequence,
        "agent": execution.agent,
        "attempt": execution.attempt,
        "is_stale": is_stale,
        "heartbeat_age_seconds": heartbeat_age_seconds,
        "agent_id": execution.selected_agent_id,
        "provider": execution.provider_name,
        "model": execution.model_name,
        "duration_ms": execution.duration_ms,
        "token_usage": execution.token_usage,
        "estimated_cost": execution.estimated_cost,
        "metadata": execution.runtime_metadata,
        "started_at": execution.started_at,
        "deadline_at": execution.deadline_at,
        "finished_at": execution.completed_at,
        "error": execution.error,
        "error_code": (execution.runtime_metadata or {}).get("error_code"),
        "result_message": execution.result_message,
        "continuation": continuation_payload,
    }


@router.get("")
def get_conversation_runtime(
    conversation_id: UUID,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    execution = (
        db.query(RuntimeExecution)
        .filter_by(
            conversation_id=conversation_id,
            user_id=user["sub"],
            tenant_id=_tenant_id(user),
        )
        .order_by(RuntimeExecution.started_at.desc())
        .first()
    )
    if execution is None:
        raise HTTPException(status_code=404, detail="Execution not found")
    return _runtime_response(db, execution)


@router.get("/{execution_id}")
def get_runtime_execution(
    execution_id: UUID,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    execution = runtime_execution_service.get_for_user(
        db, execution_id, user["sub"], _tenant_id(user)
    )
    if execution is None:
        raise HTTPException(status_code=404, detail="Execution not found")
    return _runtime_response(db, execution)


@router.post("/{execution_id}/continue")
async def continue_runtime_execution(
    execution_id: UUID,
    payload: ContinueRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    try:
        execution = await runtime_execution_service.continue_execution(
            db,
            execution_id=execution_id,
            user_id=user["sub"],
            continuation_id=payload.continuation_id,
            values=payload.values,
            message=payload.message,
            action="input",
            resume_identity=AgentIdentity.from_claims(user),
            tenant_id=_tenant_id(user),
        )
    except (ValueError, InvalidRuntimeTransitionError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if execution is None:
        raise HTTPException(status_code=404, detail="Execution not found")
    if execution.id != execution_id:
        return {
            "outcome": "new_request",
            "cancelled_execution_id": str(execution_id),
            "execution": _runtime_response(db, execution),
        }
    return {
        "execution_id": str(execution.id),
        "workflow_id": str(execution.workflow_id),
        "status": execution.status,
    }


@router.post("/{execution_id}/approve")
async def approve_runtime_execution(
    execution_id: UUID,
    payload: ContinueRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    try:
        execution = await runtime_execution_service.continue_execution(
            db,
            execution_id=execution_id,
            user_id=user["sub"],
            continuation_id=payload.continuation_id,
            values=payload.values,
            action="approve",
            resume_identity=AgentIdentity.from_claims(user),
        )
    except (ValueError, InvalidRuntimeTransitionError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if execution is None:
        raise HTTPException(status_code=404, detail="Execution not found")
    return {
        "execution_id": str(execution.id),
        "workflow_id": str(execution.workflow_id),
        "status": execution.status,
    }


@router.post("/{execution_id}/deny")
async def deny_runtime_execution(
    execution_id: UUID,
    payload: ContinueRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    try:
        execution = await runtime_execution_service.continue_execution(
            db,
            execution_id=execution_id,
            user_id=user["sub"],
            continuation_id=payload.continuation_id,
            values=payload.values,
            action="deny",
            resume_identity=AgentIdentity.from_claims(user),
        )
    except (ValueError, InvalidRuntimeTransitionError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if execution is None:
        raise HTTPException(status_code=404, detail="Execution not found")
    return {"execution_id": str(execution.id), "status": execution.status}


@router.post("/cancel/{execution_id}")
async def cancel_runtime_execution(
    execution_id: UUID,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    try:
        execution = await runtime_execution_service.cancel(
            db,
            execution_id=execution_id,
            user_id=user["sub"],
            tenant_id=_tenant_id(user),
        )
    except InvalidRuntimeTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if execution is None:
        raise HTTPException(status_code=404, detail="Execution not found")
    return {"execution_id": str(execution.id), "status": execution.status}


@router.get("/events/{execution_id}")
async def runtime_events_stream(
    execution_id: UUID,
    after_sequence: int | None = Query(default=None, ge=0),
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    execution = runtime_execution_service.get_for_user(
        db, execution_id, user["sub"], _tenant_id(user)
    )
    if execution is None:
        raise HTTPException(status_code=404, detail="Execution not found")
    workflow_id = str(execution.workflow_id)
    # Query cursor takes precedence when both are supplied. A malformed standard
    # header is rejected instead of silently replaying the entire execution.
    cursor = _runtime_event_cursor(after_sequence, last_event_id)
    # Do not retain the request dependency session for the lifetime of the stream.
    db.close()

    async def event_generator():
        async for event in runtime_execution_service.stream(
            str(execution_id), after_sequence=cursor
        ):
            if event.get("type") == "heartbeat":
                yield ": heartbeat\n\n"
                continue
            payload = {
                **event,
                "execution_id": str(execution_id),
                "workflow_id": workflow_id,
            }
            sequence = payload.get("sequence")
            event_id = f"id: {sequence}\n" if sequence is not None else ""
            yield (f"{event_id}event: runtime_event\ndata: {json.dumps(payload)}\n\n")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
