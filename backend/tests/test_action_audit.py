from datetime import UTC, datetime

from app.actions.models.action_audit import (
    ActionAuditRecord,
)
from app.actions.services.action_audit_service import (
    ActionAuditService,
)


def test_create_audit_record():

    service = ActionAuditService()

    record = ActionAuditRecord(
        action_name="deploy-release",
        user_id="user1",
        execution_id="exec-001",
        status="SUCCESS",
        timestamp=datetime.now(UTC),
    )

    service.record(record)

    records = service.get_records()

    assert len(records) == 1

    assert records[0].action_name == "deploy-release"


def test_find_action_audit():

    service = ActionAuditService()

    service.record(
        ActionAuditRecord(
            action_name="restart-service",
            user_id="user1",
            execution_id="exec-002",
            status="SUCCESS",
            timestamp=datetime.now(UTC),
        )
    )

    result = service.find_by_action("restart-service")

    assert len(result) == 1


def test_failed_action_audit():

    service = ActionAuditService()

    service.record(
        ActionAuditRecord(
            action_name="database-migration",
            user_id="admin",
            execution_id="exec-003",
            status="FAILED",
            timestamp=datetime.now(UTC),
            error="Connection timeout",
        )
    )

    record = service.get_records()[0]

    assert record.status == "FAILED"

    assert record.error == "Connection timeout"
