from __future__ import annotations

from app.contracts.audit import AuditEntry
from app.persistence.audit_repository import AuditRepository


class InMemoryAuditRepository(AuditRepository):
    """
    In-memory implementation of AuditRepository.

    Intended for development and testing.
    """

    def __init__(self) -> None:
        self._entries: dict[str, AuditEntry] = {}

    async def save(
        self,
        entry: AuditEntry,
    ) -> None:

        self._entries[entry.id] = entry

    async def get(
        self,
        entry_id: str,
    ) -> AuditEntry | None:

        return self._entries.get(entry_id)

    async def list_by_workflow(
        self,
        workflow_id: str,
    ) -> list[AuditEntry]:

        return sorted(
            (
                entry
                for entry in self._entries.values()
                if entry.workflow_id == workflow_id
            ),
            key=lambda x: x.created_at,
        )

    async def list_all(
        self,
    ) -> list[AuditEntry]:

        return sorted(
            self._entries.values(),
            key=lambda x: x.created_at,
        )

    async def delete(
        self,
        entry_id: str,
    ) -> None:

        self._entries.pop(entry_id, None)

    async def clear(
        self,
    ) -> None:

        self._entries.clear()
