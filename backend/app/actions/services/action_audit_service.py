from __future__ import annotations

from app.actions.models.action_audit import (
    ActionAuditRecord,
)


class ActionAuditService:
    """
    Stores action execution history.
    """

    def __init__(self):

        self._records: list[ActionAuditRecord] = []

    def record(
        self,
        audit: ActionAuditRecord,
    ) -> None:

        self._records.append(audit)

    def get_records(
        self,
    ) -> list[ActionAuditRecord]:

        return self._records

    def find_by_action(
        self,
        action_name: str,
    ) -> list[ActionAuditRecord]:

        return [record for record in self._records if record.action_name == action_name]
