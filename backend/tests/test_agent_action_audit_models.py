from app.database.models import (
    Action,
    Agent,
    AuditLog,
)


def test_agent_model():

    agent = Agent(
        name="default-agent",
        status="READY",
        health="HEALTHY",
    )

    assert agent.name == "default-agent"


def test_action_model():

    action = Action(
        name="generate-report",
        type="REPORT",
    )

    assert action.type == "REPORT"


def test_audit_model():

    audit = AuditLog(
        tenant_id="tenant1",
        user_id="user1",
        event_type="AGENT_STARTED",
        entity="agent",
        entity_id="default-agent",
    )

    assert audit.event_type == "AGENT_STARTED"
