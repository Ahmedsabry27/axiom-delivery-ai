from __future__ import annotations

from abc import ABC, abstractmethod

from app.contracts.audit import AuditEntry


class AuditRepository(ABC):
    """
    Repository abstraction for workflow audit records.

    Implementations may persist audit entries to:

    - SQL Server
    - PostgreSQL
    - Azure Cosmos DB
    - MongoDB
    - Amazon DynamoDB
    - Elasticsearch

    The runtime should depend only on this interface.
    """

    @abstractmethod
    async def save(
        self,
        entry: AuditEntry,
    ) -> None:
        """
        Persist an audit entry.
        """
        raise NotImplementedError

    @abstractmethod
    async def get(
        self,
        entry_id: str,
    ) -> AuditEntry | None:
        """
        Retrieve an audit entry by its identifier.
        """
        raise NotImplementedError

    @abstractmethod
    async def list_by_workflow(
        self,
        workflow_id: str,
    ) -> list[AuditEntry]:
        """
        Return all audit entries for a workflow.
        """
        raise NotImplementedError

    @abstractmethod
    async def list_all(
        self,
    ) -> list[AuditEntry]:
        """
        Return all audit entries.
        """
        raise NotImplementedError

    @abstractmethod
    async def delete(
        self,
        entry_id: str,
    ) -> None:
        """
        Delete an audit entry.
        """
        raise NotImplementedError

    @abstractmethod
    async def clear(
        self,
    ) -> None:
        """
        Remove all audit entries.

        Primarily intended for testing.
        """
        raise NotImplementedError
