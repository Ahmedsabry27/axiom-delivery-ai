from app.database.models.delivery import (
    CopilotFeedback,
    DeliveryEvidence,
    DeliveryPortfolio,
    ProposedAction,
)
from app.delivery.repositories import (
    EvidenceRepository,
    FeedbackRepository,
    ProposedActionRepository,
    TenantRepository,
)


def test_tenant_repository_does_not_leak_direct_ids(db_session):
    TenantRepository(db_session, DeliveryPortfolio, "tenant-a").add(
        DeliveryPortfolio(tenant_id="tenant-a", name="A")
    )
    record = DeliveryPortfolio(tenant_id="tenant-b", name="B")
    TenantRepository(db_session, DeliveryPortfolio, "tenant-b").add(record)
    db_session.commit()
    assert (
        TenantRepository(db_session, DeliveryPortfolio, "tenant-a").get(record.id)
        is None
    )


def test_cross_tenant_add_and_evidence_reference_are_rejected(db_session):
    repo = TenantRepository(db_session, DeliveryPortfolio, "tenant-a")
    try:
        repo.add(DeliveryPortfolio(tenant_id="tenant-b", name="Wrong"))
        raise AssertionError()
    except ValueError:
        pass
    evidence = DeliveryEvidence(
        tenant_id="tenant-b",
        entity_type="Sprint",
        entity_id="s1",
        source_type="record",
        source_system="MANUAL",
        source_record_id="x",
        title="Private",
    )
    EvidenceRepository(db_session, "tenant-b").add(evidence)
    db_session.commit()
    try:
        EvidenceRepository(db_session, "tenant-a").require_authorized_ids([evidence.id])
        raise AssertionError()
    except ValueError:
        pass


def test_feedback_and_proposed_actions_are_restart_durable(db_session):
    feedback = CopilotFeedback(
        tenant_id="tenant-a",
        conversation_id="c1",
        message_id="m1",
        feedback_type="Helpful",
        user_id="u1",
    )
    FeedbackRepository(db_session, "tenant-a").add(feedback)
    action = ProposedAction(
        tenant_id="tenant-a",
        conversation_id="c1",
        action_type="ESCALATION",
        content="Review blocker",
        created_by="u1",
    )
    ProposedActionRepository(db_session, "tenant-a").add(action)
    db_session.commit()
    db_session.expire_all()
    assert (
        FeedbackRepository(db_session, "tenant-a").get(feedback.id).feedback_type
        == "Helpful"
    )
    assert (
        ProposedActionRepository(db_session, "tenant-a")
        .get(action.id)
        .approval_required
        is True
    )
