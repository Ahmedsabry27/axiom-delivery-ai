from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.database.models.audit import AuditLog


class AuditRepository:
    """
    Persistence layer for audit logs.
    """

    def __init__(
        self,
        db: Session,
    ):

        self._db = db

    def create_log(
        self,
        event_type: str,
        entity: str,
        entity_id: str,
        user_id: str | None = None,
        tenant_id: str | None = None,
    ) -> AuditLog:

        log = AuditLog(
            event_type=event_type,
            entity=entity,
            entity_id=entity_id,
            user_id=user_id,
            tenant_id=tenant_id,
            timestamp=datetime.now(UTC),
        )

        self._db.add(log)

        self._db.commit()

        self._db.refresh(log)

        return log

    def get_logs(
        self,
        entity: str | None = None,
    ) -> list[AuditLog]:

        query = self._db.query(AuditLog)

        if entity:
            query = query.filter(AuditLog.entity == entity)

        return query.all()
