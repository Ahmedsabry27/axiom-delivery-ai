from __future__ import annotations

import os
import socket
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.runtime_execution import RuntimeExecution


class RuntimeLeaseLostError(RuntimeError):
    """The local worker no longer owns the execution generation."""


_WORKER_ID = f"{socket.gethostname()}:{os.getpid()}:{uuid4().hex[:12]}"


def get_runtime_worker_id() -> str:
    """Return an opaque identity stable for this process lifetime."""
    return _WORKER_ID


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def claim_execution(
    db: Session,
    execution_id: str | UUID,
    *,
    worker_id: str,
    expected_status: str,
    recovery: bool = False,
) -> RuntimeExecution | None:
    """Conditionally acquire one execution; returns None when another worker won."""
    execution_uuid = (
        execution_id if isinstance(execution_id, UUID) else UUID(execution_id)
    )
    now = utcnow()
    conditions = [
        RuntimeExecution.id == execution_uuid,
        RuntimeExecution.status == expected_status,
    ]
    if recovery:
        conditions.extend(
            [
                RuntimeExecution.lease_expires_at.is_not(None),
                RuntimeExecution.lease_expires_at < now,
                RuntimeExecution.attempt < settings.RUNTIME_MAX_RECOVERY_ATTEMPTS,
            ]
        )
    else:
        conditions.append(RuntimeExecution.lease_owner.is_(None))

    values = {
        "lease_owner": worker_id,
        "heartbeat_at": now,
        "lease_expires_at": now + timedelta(seconds=settings.RUNTIME_LEASE_SECONDS),
    }
    if recovery:
        values["attempt"] = RuntimeExecution.attempt + 1
    result = db.execute(update(RuntimeExecution).where(*conditions).values(**values))
    if result.rowcount != 1:
        db.rollback()
        return None
    db.commit()
    return db.get(RuntimeExecution, execution_uuid)


def claim_locked_execution(
    record: RuntimeExecution, *, worker_id: str, recovery: bool = False
) -> int:
    """Claim a row already locked by the caller and return its fencing generation."""
    now = utcnow()
    if record.lease_owner is not None and not recovery:
        raise RuntimeLeaseLostError("Runtime execution is already owned")
    if recovery:
        record.attempt = (record.attempt or 1) + 1
    record.lease_owner = worker_id
    record.heartbeat_at = now
    record.lease_expires_at = now + timedelta(seconds=settings.RUNTIME_LEASE_SECONDS)
    return record.attempt or 1


def renew_execution_lease(
    db: Session,
    execution_id: str | UUID,
    *,
    worker_id: str,
    attempt: int,
) -> bool:
    execution_uuid = (
        execution_id if isinstance(execution_id, UUID) else UUID(execution_id)
    )
    now = utcnow()
    result = db.execute(
        update(RuntimeExecution)
        .where(
            RuntimeExecution.id == execution_uuid,
            RuntimeExecution.status == "RUNNING",
            RuntimeExecution.lease_owner == worker_id,
            RuntimeExecution.attempt == attempt,
            RuntimeExecution.lease_expires_at >= now,
        )
        .values(
            heartbeat_at=now,
            lease_expires_at=now + timedelta(seconds=settings.RUNTIME_LEASE_SECONDS),
        )
    )
    db.commit()
    return result.rowcount == 1


def assert_execution_lease(
    record: RuntimeExecution, *, worker_id: str, attempt: int
) -> None:
    if (
        record.lease_owner != worker_id
        or record.attempt != attempt
        or record.lease_expires_at is None
        or record.lease_expires_at < utcnow()
    ):
        raise RuntimeLeaseLostError("Runtime execution lease is no longer owned")
