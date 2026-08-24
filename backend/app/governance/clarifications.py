from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.audit.events import append_audit_event
from app.contracts.tool_models import ExecutionContext
from app.database.models.governance_workflow import ClarificationRequest
from app.governance.workflows import hash_token, utc
from app.tool_sdk.errors import PermissionDeniedError, UnsafeOperationError
from app.tool_sdk.schema import validate_and_default


def create_clarification(
    db: Session,
    *,
    discovery_id: str,
    tool,
    context: ExecutionContext,
    known_values: dict,
    missing_fields: list[str],
    alternatives: list[dict],
    ttl_minutes: int = 30,
) -> tuple[ClarificationRequest, str]:
    token = secrets.token_urlsafe(32)
    safe_alternatives = [
        {
            "tool_name": item["tool_name"],
            "version": item["version"],
            "display_name": item["display_name"],
        }
        for item in alternatives[:5]
    ]
    row = ClarificationRequest(
        tenant_id=context.tenant_id,
        conversation_id=context.conversation_id,
        discovery_id=discovery_id,
        tool_name=tool.name,
        tool_version=tool.metadata.version,
        candidate_alternatives=safe_alternatives,
        question="Provide the required fields to continue.",
        input_schema=tool.metadata.parameters,
        known_values=known_values,
        missing_fields=missing_fields,
        expires_at=datetime.now(UTC) + timedelta(minutes=ttl_minutes),
        resume_token_hash=hash_token(token),
        requester_id=context.actor_id,
        audit_metadata={"correlation_id": context.correlation_id},
    )
    db.add(row)
    db.flush()
    append_audit_event(
        db,
        tenant_id=context.tenant_id,
        actor_id=context.actor_id,
        action="clarification.created",
        target_type="clarification_request",
        target_id=row.id,
        correlation_id=context.correlation_id,
        after={
            "status": row.status,
            "tool": row.tool_name,
            "missing_fields": missing_fields,
        },
    )
    return row, token


def consume_clarification(
    db: Session,
    *,
    row: ClarificationRequest,
    token: str,
    response: dict,
    context: ExecutionContext,
) -> dict:
    if row.tenant_id != context.tenant_id or row.requester_id != context.actor_id:
        raise PermissionDeniedError("Clarification request was not found")
    now = datetime.now(UTC)
    if utc(row.expires_at) <= now:
        row.status = "expired"
        db.commit()
        raise UnsafeOperationError("Clarification request has expired")
    if row.status != "waiting_for_input" or not secrets.compare_digest(
        row.resume_token_hash, hash_token(token)
    ):
        raise UnsafeOperationError(
            "Clarification evidence is invalid or no longer usable"
        )
    unknown = set(response) - set(row.missing_fields)
    if unknown:
        raise UnsafeOperationError(
            "Response attempted to change fields outside the clarification"
        )
    merged = {**row.known_values, **response}
    normalized = validate_and_default(row.input_schema, merged)
    result = db.execute(
        update(ClarificationRequest)
        .where(
            ClarificationRequest.id == row.id,
            ClarificationRequest.status == "waiting_for_input",
        )
        .values(
            status="consumed",
            user_response=response,
            consumed_at=now,
            state_version=ClarificationRequest.state_version + 1,
        )
    )
    if result.rowcount != 1:
        db.rollback()
        raise UnsafeOperationError("Clarification response has already been consumed")
    append_audit_event(
        db,
        tenant_id=context.tenant_id,
        actor_id=context.actor_id,
        action="clarification.consumed",
        target_type="clarification_request",
        target_id=row.id,
        correlation_id=context.correlation_id,
        after={"status": "consumed", "submitted_fields": sorted(response)},
    )
    db.commit()
    return normalized
