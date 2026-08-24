from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.api.tools import identity
from app.audit.events import append_audit_event
from app.auth.dependencies import get_current_user
from app.database.dependencies import get_db
from app.database.models.governance_workflow import (
    ApprovalRequest,
    ClarificationRequest,
)
from app.governance.clarifications import consume_clarification
from app.governance.workflows import decide_approval
from app.tool_sdk.errors import ToolSDKError
from app.tool_sdk.service import executor

router = APIRouter(prefix="/api/v1", tags=["Approval and Clarification"])
Database = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[dict, Depends(get_current_user)]


class DecisionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(default="", max_length=500)


class ResumePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    resume_token: str = Field(min_length=20, max_length=256)
    input: dict = Field(default_factory=dict)


class ClarificationResumePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    resume_token: str = Field(min_length=20, max_length=256)
    response: dict = Field(default_factory=dict)


def _approval_item(row: ApprovalRequest) -> dict:
    return {
        "id": row.id,
        "tool": row.tool_name,
        "version": row.tool_version,
        "discovery_id": row.discovery_id,
        "conversation_id": row.conversation_id,
        "requester_id": row.requester_id,
        "required_approver_role": row.required_approver_role,
        "required_approver_group": row.required_approver_group,
        "risk_level": row.risk_level,
        "environment": row.environment,
        "safe_action_summary": row.safe_action_summary,
        "status": row.status,
        "created_at": row.created_at.isoformat(),
        "expires_at": row.expires_at.isoformat(),
        "approver_id": row.approver_id,
        "decision": row.decision,
        "decision_reason": row.decision_reason,
        "decided_at": row.decided_at.isoformat() if row.decided_at else None,
        "consumed_at": row.consumed_at.isoformat() if row.consumed_at else None,
        "revoked_at": row.revoked_at.isoformat() if row.revoked_at else None,
    }


def _get(db: Session, request_id: str, tenant_id: str) -> ApprovalRequest:
    row = (
        db.query(ApprovalRequest).filter_by(id=request_id, tenant_id=tenant_id).first()
    )
    if not row:
        raise HTTPException(
            404,
            {"code": "APPROVAL_NOT_FOUND", "message": "Approval request was not found"},
        )
    return row


@router.get("/approvals")
def list_approvals(
    db: Database,
    user: CurrentUser,
    status: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    ctx = identity(user)
    query = db.query(ApprovalRequest).filter_by(tenant_id=ctx.tenant_id)
    if (
        "approvals.approve" not in ctx.permissions
        and "tools.admin" not in ctx.permissions
    ):
        query = query.filter_by(requester_id=ctx.actor_id)
    if status:
        query = query.filter_by(status=status)
    total = query.count()
    rows = (
        query.order_by(ApprovalRequest.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "items": [_approval_item(row) for row in rows],
        "total": total,
        "page": page,
    }


@router.get("/approvals/{request_id}")
def get_approval(request_id: str, db: Database, user: CurrentUser):
    ctx = identity(user)
    row = _get(db, request_id, ctx.tenant_id)
    if row.requester_id != ctx.actor_id and not (
        {"approvals.approve", "tools.admin"} & ctx.permissions
    ):
        raise HTTPException(
            403,
            {"code": "PERMISSION_DENIED", "message": "Approval request is not visible"},
        )
    return _approval_item(row)


def _decide(
    request_id: str, payload: DecisionPayload, decision: str, db: Session, user: dict
):
    ctx = identity(user)
    row = _get(db, request_id, ctx.tenant_id)
    try:
        return _approval_item(decide_approval(db, row, ctx, decision, payload.reason))
    except ToolSDKError as exc:
        raise HTTPException(
            exc.status_code, {"code": exc.code, "message": exc.safe_message}
        ) from exc


@router.post("/approvals/{request_id}/approve")
def approve(request_id: str, payload: DecisionPayload, db: Database, user: CurrentUser):
    return _decide(request_id, payload, "approve", db, user)


@router.post("/approvals/{request_id}/deny")
def deny(request_id: str, payload: DecisionPayload, db: Database, user: CurrentUser):
    return _decide(request_id, payload, "deny", db, user)


@router.post("/approvals/{request_id}/revoke")
def revoke(request_id: str, payload: DecisionPayload, db: Database, user: CurrentUser):
    ctx = identity(user)
    row = _get(db, request_id, ctx.tenant_id)
    if (
        "approvals.approve" not in ctx.permissions
        and "tools.admin" not in ctx.permissions
    ):
        raise HTTPException(
            403,
            {"code": "PERMISSION_DENIED", "message": "Caller cannot revoke approvals"},
        )
    now = datetime.now(UTC)
    result = db.execute(
        update(ApprovalRequest)
        .where(
            ApprovalRequest.id == row.id,
            ApprovalRequest.status.in_(["pending", "approved"]),
        )
        .values(
            status="revoked",
            revoked_at=now,
            decision_reason=payload.reason,
            state_version=ApprovalRequest.state_version + 1,
        )
    )
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(
            409,
            {
                "code": "APPROVAL_STATE_CONFLICT",
                "message": "Approval cannot be revoked",
            },
        )
    append_audit_event(
        db,
        tenant_id=ctx.tenant_id,
        actor_id=ctx.actor_id,
        action="approval.revoked",
        target_type="approval_request",
        target_id=row.id,
        correlation_id=ctx.correlation_id,
    )
    db.commit()
    db.refresh(row)
    return _approval_item(row)


@router.post("/approvals/{request_id}/resume")
async def resume(
    request_id: str, payload: ResumePayload, db: Database, user: CurrentUser
):
    ctx = identity(user)
    row = _get(db, request_id, ctx.tenant_id)
    if row.requester_id != ctx.actor_id:
        raise HTTPException(
            403,
            {
                "code": "PERMISSION_DENIED",
                "message": "Only the requester can resume execution",
            },
        )
    try:
        return await executor.execute(
            row.tool_name,
            payload.input,
            ctx.model_copy(
                update={
                    "approval_request_id": row.id,
                    "approval_resume_token": payload.resume_token,
                    "conversation_id": row.conversation_id,
                }
            ),
            db,
            row.tool_version,
        )
    except ToolSDKError as exc:
        raise HTTPException(
            exc.status_code,
            {"code": exc.code, "message": exc.safe_message, "fields": exc.fields},
        ) from exc


def _clarification_item(row: ClarificationRequest) -> dict:
    return {
        "id": row.id,
        "conversation_id": row.conversation_id,
        "discovery_id": row.discovery_id,
        "tool": row.tool_name,
        "version": row.tool_version,
        "candidate_alternatives": row.candidate_alternatives,
        "question": row.question,
        "input_schema": row.input_schema,
        "known_values": row.known_values,
        "missing_fields": row.missing_fields,
        "status": row.status,
        "created_at": row.created_at.isoformat(),
        "expires_at": row.expires_at.isoformat(),
        "consumed_at": row.consumed_at.isoformat() if row.consumed_at else None,
    }


def _get_clarification(
    db: Session, clarification_id: str, tenant_id: str
) -> ClarificationRequest:
    row = (
        db.query(ClarificationRequest)
        .filter_by(id=clarification_id, tenant_id=tenant_id)
        .first()
    )
    if not row:
        raise HTTPException(
            404,
            {
                "code": "CLARIFICATION_NOT_FOUND",
                "message": "Clarification request was not found",
            },
        )
    return row


@router.get("/clarifications/{clarification_id}")
def get_clarification(clarification_id: str, db: Database, user: CurrentUser):
    ctx = identity(user)
    row = _get_clarification(db, clarification_id, ctx.tenant_id)
    if row.requester_id != ctx.actor_id and "tools.admin" not in ctx.permissions:
        raise HTTPException(
            403,
            {
                "code": "PERMISSION_DENIED",
                "message": "Clarification request is not visible",
            },
        )
    return _clarification_item(row)


@router.post("/clarifications/{clarification_id}/cancel")
def cancel_clarification(clarification_id: str, db: Database, user: CurrentUser):
    ctx = identity(user)
    row = _get_clarification(db, clarification_id, ctx.tenant_id)
    if row.requester_id != ctx.actor_id and "tools.admin" not in ctx.permissions:
        raise HTTPException(
            403,
            {
                "code": "PERMISSION_DENIED",
                "message": "Clarification request cannot be cancelled",
            },
        )
    result = db.execute(
        update(ClarificationRequest)
        .where(
            ClarificationRequest.id == row.id,
            ClarificationRequest.status == "waiting_for_input",
        )
        .values(
            status="cancelled", state_version=ClarificationRequest.state_version + 1
        )
    )
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(
            409,
            {
                "code": "CLARIFICATION_STATE_CONFLICT",
                "message": "Clarification cannot be cancelled",
            },
        )
    append_audit_event(
        db,
        tenant_id=ctx.tenant_id,
        actor_id=ctx.actor_id,
        action="clarification.cancelled",
        target_type="clarification_request",
        target_id=row.id,
        correlation_id=ctx.correlation_id,
    )
    db.commit()
    db.refresh(row)
    return _clarification_item(row)


@router.post("/clarifications/{clarification_id}/resume")
async def resume_clarification(
    clarification_id: str,
    payload: ClarificationResumePayload,
    db: Database,
    user: CurrentUser,
):
    ctx = identity(user)
    row = _get_clarification(db, clarification_id, ctx.tenant_id)
    try:
        normalized = consume_clarification(
            db,
            row=row,
            token=payload.resume_token,
            response=payload.response,
            context=ctx,
        )
        # Registry lookup, enabled state, permissions and governance are deliberately re-run.
        return await executor.execute(
            row.tool_name,
            normalized,
            ctx.model_copy(update={"conversation_id": row.conversation_id}),
            db,
            row.tool_version,
        )
    except ToolSDKError as exc:
        raise HTTPException(
            exc.status_code,
            {"code": exc.code, "message": exc.safe_message, "fields": exc.fields},
        ) from exc
