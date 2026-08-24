from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.api.runtime import _runtime_response
from app.models.runtime_execution import RuntimeContinuation, RuntimeExecution


def test_runtime_response_exposes_active_input_continuation(db_session):
    execution = RuntimeExecution(
        id=uuid4(),
        workflow_id=uuid4(),
        conversation_id=uuid4(),
        user_id="user-1",
        tenant_id="tenant-1",
        status="WAITING_FOR_INPUT",
    )
    continuation = RuntimeContinuation(
        id=uuid4(),
        execution_id=execution.id,
        tenant_id="tenant-1",
        kind="input",
        schema={"fields": [{"name": "project_key", "required": True}]},
        known_values={"summary": "Production issue", "_resume_token": "private"},
        expires_at=datetime.now(UTC).replace(tzinfo=None) + timedelta(hours=1),
    )
    db_session.add_all([execution, continuation])
    db_session.commit()

    payload = _runtime_response(db_session, execution)

    assert payload["continuation"] == {
        "kind": "input",
        "continuation_id": str(continuation.id),
        "fields": [{"name": "project_key", "required": True}],
        "requested_fields": ["project_key"],
        "intent": None,
        "capability": None,
        "known_values": {"summary": "Production issue"},
        "required_role": None,
        "title": "Additional information required",
        "description": "Provide the unresolved values needed to continue this plan.",
    }
    assert payload["state_version"] == execution.state_version
    assert payload["last_sequence"] == 0
    assert payload["attempt"] == 1
    assert payload["is_stale"] is False
