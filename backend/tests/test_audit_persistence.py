from app.audit.services.audit_repository import AuditRepository


def test_create_audit_log(
    db_session,
):

    repository = AuditRepository(db_session)

    log = repository.create_log(
        event_type="WORKFLOW_STARTED",
        entity="workflow",
        entity_id="123",
    )

    assert log.id is not None
    assert log.event_type == "WORKFLOW_STARTED"
    assert log.entity == "workflow"


def test_filter_audit_logs(
    db_session,
):

    repository = AuditRepository(db_session)

    repository.create_log(
        "ACTION_EXECUTED",
        "action",
        "10",
    )

    logs = repository.get_logs("action")

    assert len(logs) == 1
    assert logs[0].entity == "action"
