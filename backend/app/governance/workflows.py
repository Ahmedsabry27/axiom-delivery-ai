from __future__ import annotations

import hashlib
import json
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.audit.events import append_audit_event
from app.contracts.tool_models import ExecutionContext
from app.database.models.governance_workflow import ApprovalRequest
from app.database.models.tool_discovery import ToolGovernancePolicy
from app.tool_sdk.errors import PermissionDeniedError, UnsafeOperationError, redact


def fingerprint(value: Any) -> str:
    safe = redact(value)
    encoded = json.dumps(safe, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode()).hexdigest()


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def utc(value: datetime) -> datetime:
    """Normalize database timestamps; SQLite drops timezone metadata."""
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def create_approval(
    db: Session,
    *,
    tool,
    normalized_input: dict,
    context: ExecutionContext,
    policy_ids: list[str],
    ttl_minutes: int = 30,
) -> tuple[ApprovalRequest, str]:
    policy = None
    if policy_ids:
        policy = (
            db.query(ToolGovernancePolicy)
            .filter_by(id=policy_ids[0], tenant_id=context.tenant_id)
            .first()
        )
    input_hash = fingerprint(normalized_input)
    existing = (
        db.query(ApprovalRequest)
        .filter_by(
            tenant_id=context.tenant_id,
            tool_name=tool.name,
            tool_version=tool.metadata.version,
            requester_id=context.actor_id,
            input_fingerprint=input_hash,
            status="pending",
        )
        .first()
    )
    if existing and utc(existing.expires_at) > datetime.now(UTC):
        # Tokens are intentionally unrecoverable; idempotent retries return no new secret.
        return existing, ""
    token = secrets.token_urlsafe(32)
    actions = policy.actions if policy else {}
    row = ApprovalRequest(
        tenant_id=context.tenant_id,
        tool_name=tool.name,
        tool_version=tool.metadata.version,
        conversation_id=context.conversation_id,
        requester_id=context.actor_id,
        requester_agent_id=context.agent_id,
        policy_id=policy.id if policy else None,
        policy_version=policy.version if policy else None,
        required_approver_role=actions.get("approver_role"),
        required_approver_group=actions.get("approver_group"),
        separation_of_duties=actions.get("separation_of_duties", True),
        risk_level=tool.metadata.risk_level.value,
        environment=context.environment,
        safe_action_summary={"tool": tool.name, "version": tool.metadata.version},
        input_fingerprint=input_hash,
        expires_at=datetime.now(UTC) + timedelta(minutes=ttl_minutes),
        resume_token_hash=hash_token(token),
        audit_metadata={"policy_ids": policy_ids},
    )
    db.add(row)
    db.flush()
    append_audit_event(
        db,
        tenant_id=context.tenant_id,
        actor_id=context.actor_id,
        action="approval.created",
        target_type="approval_request",
        target_id=row.id,
        correlation_id=context.correlation_id,
        after={"status": row.status, "tool": row.tool_name},
    )
    db.commit()
    return row, token


def decide_approval(
    db: Session,
    row: ApprovalRequest,
    context: ExecutionContext,
    decision: str,
    reason: str,
) -> ApprovalRequest:
    if row.tenant_id != context.tenant_id:
        raise PermissionDeniedError("Approval request was not found")
    if (
        "approvals.approve" not in context.permissions
        and "tools.admin" not in context.permissions
    ):
        raise PermissionDeniedError("Caller cannot decide approval requests")
    if row.required_approver_role and row.required_approver_role not in context.roles:
        raise PermissionDeniedError("Caller does not have the required approver role")
    if (
        row.required_approver_group
        and row.required_approver_group not in context.groups
    ):
        raise PermissionDeniedError(
            "Caller does not belong to the required approver group"
        )
    if row.separation_of_duties and row.requester_id == context.actor_id:
        raise PermissionDeniedError("Requester cannot approve this request")
    now = datetime.now(UTC)
    if utc(row.expires_at) <= now:
        row.status = "expired"
        db.commit()
        raise UnsafeOperationError("Approval request has expired")
    if row.status != "pending":
        raise UnsafeOperationError("Approval request is no longer pending")
    result = db.execute(
        update(ApprovalRequest)
        .where(ApprovalRequest.id == row.id, ApprovalRequest.status == "pending")
        .values(
            status="approved" if decision == "approve" else "denied",
            approver_id=context.actor_id,
            decision=decision,
            decision_reason=reason[:500],
            decided_at=now,
            state_version=ApprovalRequest.state_version + 1,
        )
    )
    if result.rowcount != 1:
        db.rollback()
        raise UnsafeOperationError("Approval request was decided concurrently")
    append_audit_event(
        db,
        tenant_id=context.tenant_id,
        actor_id=context.actor_id,
        action="approval.denied" if decision == "deny" else "approval.approved",
        target_type="approval_request",
        target_id=row.id,
        correlation_id=context.correlation_id,
        after={"decision": decision},
    )
    db.commit()
    db.refresh(row)
    return row


def consume_approval(
    db: Session,
    *,
    request_id: str | None,
    token: str | None,
    tool,
    normalized_input: dict,
    context: ExecutionContext,
    policy_ids: list[str],
) -> ApprovalRequest:
    if not request_id or not token:
        row, issued_token = create_approval(
            db,
            tool=tool,
            normalized_input=normalized_input,
            context=context,
            policy_ids=policy_ids,
        )
        fields = [{"field": "approval_request_id", "message": row.id}]
        if issued_token:
            fields.append({"field": "resume_token", "message": issued_token})
        raise UnsafeOperationError("Tool execution requires approval", fields=fields)
    row = (
        db.query(ApprovalRequest)
        .filter_by(id=request_id, tenant_id=context.tenant_id)
        .first()
    )
    now = datetime.now(UTC)
    valid = (
        row
        and row.status == "approved"
        and utc(row.expires_at) > now
        and row.consumed_at is None
        and secrets.compare_digest(row.resume_token_hash, hash_token(token))
        and row.tool_name == tool.name
        and row.tool_version == tool.metadata.version
        and row.input_fingerprint == fingerprint(normalized_input)
    )
    if not valid:
        raise UnsafeOperationError("Approval evidence is invalid or no longer usable")
    if row.policy_id:
        policy = (
            db.query(ToolGovernancePolicy)
            .filter_by(id=row.policy_id, tenant_id=context.tenant_id)
            .first()
        )
        if (
            not policy
            or policy.version != row.policy_version
            or row.policy_id not in policy_ids
        ):
            raise UnsafeOperationError("Approval policy binding is no longer valid")
    result = db.execute(
        update(ApprovalRequest)
        .where(
            ApprovalRequest.id == row.id,
            ApprovalRequest.status == "approved",
            ApprovalRequest.consumed_at.is_(None),
        )
        .values(
            status="consumed",
            consumed_at=now,
            state_version=ApprovalRequest.state_version + 1,
        )
    )
    if result.rowcount != 1:
        db.rollback()
        raise UnsafeOperationError("Approval evidence has already been consumed")
    append_audit_event(
        db,
        tenant_id=context.tenant_id,
        actor_id=context.actor_id,
        action="approval.consumed",
        target_type="approval_request",
        target_id=row.id,
        correlation_id=context.correlation_id,
    )
    db.commit()
    db.refresh(row)
    return row
