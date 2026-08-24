from __future__ import annotations

from app.contracts.audit import (
    AuditEntry,
    AuditLevel,
)


class AuditService:
    """
    Records workflow execution history.

    This implementation stores audit entries in memory.

    Future versions should persist them using
    an AuditRepository.
    """

    def __init__(self) -> None:
        self._entries: list[AuditEntry] = []

    async def info(
        self,
        workflow_id: str,
        event: str,
        message: str,
        task_id: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> None:

        self._entries.append(
            AuditEntry(
                workflow_id=workflow_id,
                task_id=task_id,
                event=event,
                message=message,
                level=AuditLevel.INFO,
                metadata=metadata or {},
            )
        )

    async def warning(
        self,
        workflow_id: str,
        event: str,
        message: str,
        task_id: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> None:

        self._entries.append(
            AuditEntry(
                workflow_id=workflow_id,
                task_id=task_id,
                event=event,
                message=message,
                level=AuditLevel.WARNING,
                metadata=metadata or {},
            )
        )

    async def error(
        self,
        workflow_id: str,
        event: str,
        message: str,
        task_id: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> None:

        self._entries.append(
            AuditEntry(
                workflow_id=workflow_id,
                task_id=task_id,
                event=event,
                message=message,
                level=AuditLevel.ERROR,
                metadata=metadata or {},
            )
        )

    async def history(
        self,
        workflow_id: str,
    ) -> list[AuditEntry]:
        """
        Return the audit history for a workflow.
        """

        return [entry for entry in self._entries if entry.workflow_id == workflow_id]

    async def all(
        self,
    ) -> list[AuditEntry]:
        """
        Return every audit entry.
        """

        return list(self._entries)

    async def clear(
        self,
    ) -> None:
        """
        Clear the audit log.

        Primarily intended for testing.
        """

        self._entries.clear()
