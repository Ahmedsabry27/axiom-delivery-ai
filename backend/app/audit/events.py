from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from app.database.models.audit import AuditLog
from app.tool_sdk.errors import redact


def _safe(value: Any) -> dict | None:
    if value is None:
        return None
    safe = redact(value)
    if isinstance(safe, dict):
        return safe
    return {"value": safe}


def append_audit_event(
    db: Session,
    *,
    tenant_id: str,
    actor_id: str,
    action: str,
    target_type: str,
    target_id: str,
    correlation_id: str | None = None,
    before: Any = None,
    after: Any = None,
    metadata: Any = None,
    trace_id: str | None = None,
    actor_type: str = "user",
    result: str = "SUCCESS",
    policy_id: str | None = None,
    policy_version: int | None = None,
    agent_id: str | None = None,
    model_id: str | None = None,
    provider: str | None = None,
    tool_id: str | None = None,
    execution_id: str | None = None,
    approval_id: str | None = None,
    severity: str = "INFO",
) -> AuditLog:
    """Append a sanitized event without committing the caller's transaction."""
    now = datetime.now(UTC)
    event_id = str(uuid4())
    safe_before = _safe(before)
    safe_after = _safe(after)
    safe_metadata = _safe(metadata)
    previous = (
        db.query(AuditLog)
        .filter(AuditLog.tenant_id == tenant_id, AuditLog.integrity_hash.is_not(None))
        .order_by(AuditLog.id.desc())
        .with_for_update()
        .first()
    )
    previous_hash = previous.integrity_hash if previous else "0" * 64
    canonical = json.dumps(
        {
            "action": action,
            "actor_id": actor_id,
            "actor_type": actor_type,
            "after": safe_after,
            "before": safe_before,
            "correlation_id": correlation_id,
            "event_id": event_id,
            "metadata": safe_metadata,
            "result": result,
            "severity": severity,
            "target_id": target_id,
            "target_type": target_type,
            "tenant_id": tenant_id,
            "timestamp": now.isoformat(),
            "trace_id": trace_id or correlation_id,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    integrity_hash = hashlib.sha256((previous_hash + canonical).encode()).hexdigest()
    event = AuditLog(
        tenant_id=tenant_id,
        user_id=actor_id,
        event_type=action,
        entity=target_type,
        entity_id=target_id,
        timestamp=now,
        actor_id=actor_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        correlation_id=correlation_id,
        before_summary=safe_before,
        after_summary=safe_after,
        metadata_json=safe_metadata,
        created_at=now,
        event_id=event_id,
        trace_id=trace_id or correlation_id,
        actor_type=actor_type,
        result=result,
        policy_id=policy_id,
        policy_version=policy_version,
        agent_id=agent_id,
        model_id=model_id,
        provider=provider,
        tool_id=tool_id,
        execution_id=execution_id,
        approval_id=approval_id,
        severity=severity,
        previous_hash=previous_hash,
        integrity_hash=integrity_hash,
        canonical_payload=canonical,
    )
    db.add(event)
    return event
