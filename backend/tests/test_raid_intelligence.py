from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.auth.dependencies import get_current_user
from app.database.dependencies import get_db
from app.database.models.audit import AuditLog
from app.database.models.delivery import (
    DeliveryEvidence,
    DeliveryPortfolio,
    DeliveryProgramme,
    DeliveryProject,
    DeliveryRAIDItem,
    DeliverySprint,
    DeliveryTeam,
    ProposedAction,
)
from app.delivery.copilot_service import DeliveryCopilotService
from app.delivery.raid_intelligence import (
    RAIDValidationError,
    attention,
    duplicate_similarity,
    exposure,
    hygiene_findings,
    validate_transition,
)
from app.delivery.raid_repository import RAIDConflictError, RAIDRepository
from app.delivery.read_service import DeliveryReadService
from app.main import app
from app.models.conversation import Conversation


def hierarchy(db, tenant: str = "tenant-a"):
    portfolio = DeliveryPortfolio(
        tenant_id=tenant, name="Synthetic Portfolio", status="ACTIVE"
    )
    db.add(portfolio)
    db.flush()
    programme = DeliveryProgramme(
        tenant_id=tenant,
        name="Synthetic Programme",
        portfolio_id=portfolio.id,
        status="ACTIVE",
    )
    db.add(programme)
    db.flush()
    project = DeliveryProject(
        tenant_id=tenant,
        name="Synthetic Project",
        programme_id=programme.id,
        status="ACTIVE",
    )
    db.add(project)
    db.flush()
    team = DeliveryTeam(
        tenant_id=tenant, name="Phoenix", project_id=project.id, status="ACTIVE"
    )
    db.add(team)
    db.flush()
    sprint = DeliverySprint(
        tenant_id=tenant,
        name="Sprint 24",
        project_id=project.id,
        team_id=team.id,
        goal="Ship fictional payments",
        status="ACTIVE",
        start_date=date.today() - timedelta(days=4),
        end_date=date.today() + timedelta(days=6),
    )
    db.add(sprint)
    db.flush()
    return portfolio, programme, project, team, sprint


def risk_values(project_id: str, **overrides):
    values = {
        "item_type": "RISK",
        "name": "Payment API delay",
        "description": "Fictional provider capacity may delay the payment API.",
        "project_id": project_id,
        "probability": "ALMOST_CERTAIN",
        "impact": "CRITICAL",
        "residual_probability": "ALMOST_CERTAIN",
        "residual_impact": "CRITICAL",
        "owner_id": "owner-1",
        "review_date": date.today() + timedelta(days=3),
        "due_date": date.today() + timedelta(days=5),
        "mitigation_plan": "Review provider capacity daily.",
    }
    values.update(overrides)
    return values


def test_deterministic_scoring_missing_data_attention_hygiene_and_duplicates():
    assert exposure("ALMOST_CERTAIN", "CRITICAL").value == 25
    assert exposure("ALMOST_CERTAIN", "CRITICAL").band == "CRITICAL"
    assert exposure(None, "CRITICAL").band == "UNKNOWN"
    item = DeliveryRAIDItem(
        tenant_id="tenant-a",
        project_id="project",
        item_type="RISK",
        name="Payment API delay",
        description="Delay",
        status="OPEN",
        probability="LIKELY",
        impact="CRITICAL",
        exposure_band="CRITICAL",
        due_date=date.today() - timedelta(days=1),
        review_date=date.today() - timedelta(days=1),
        identified_at=datetime.now(UTC) - timedelta(days=40),
    )
    scored = attention(item)
    assert scored.value == 100
    assert "Missing owner +15" in scored.reasons
    findings = hygiene_findings(item, evidence_count=0)
    assert {finding["findingType"] for finding in findings} >= {
        "UNOWNED",
        "MISSING_MITIGATION",
        "MISSING_EVIDENCE",
        "OVERDUE",
    }
    similarity, reasons = duplicate_similarity(
        {"title": "Payment api delay", "project_id": "project"}, item
    )
    assert similarity >= 0.8 and "Similar normalized title" in reasons


def test_lifecycle_validates_transitions_closure_notes_and_completion_evidence():
    validate_transition("RISK", "IDENTIFIED", "ASSESSED")
    with pytest.raises(RAIDValidationError, match="Invalid"):
        validate_transition("RISK", "IDENTIFIED", "MITIGATING")
    with pytest.raises(RAIDValidationError, match="note"):
        validate_transition("RISK", "IDENTIFIED", "CLOSED")
    with pytest.raises(RAIDValidationError, match="evidence"):
        validate_transition(
            "ACTION",
            "IN_PROGRESS",
            "COMPLETED",
            note="Done",
            completion_evidence_required=True,
        )


def test_repository_crud_filters_history_evidence_tenant_and_concurrency(db_session):
    _, _, project_a, _, sprint_a = hierarchy(db_session, "tenant-a")
    _, _, project_b, _, _ = hierarchy(db_session, "tenant-b")
    evidence_a = DeliveryEvidence(
        tenant_id="tenant-a",
        entity_type="SPRINT",
        entity_id=sprint_a.id,
        source_type="STATUS_UPDATE",
        source_system="MANUAL",
        source_record_id="risk-a",
        title="Provider delay evidence",
    )
    evidence_b = DeliveryEvidence(
        tenant_id="tenant-b",
        entity_type="PROJECT",
        entity_id=project_b.id,
        source_type="STATUS_UPDATE",
        source_system="MANUAL",
        source_record_id="risk-b",
        title="Other tenant evidence",
    )
    db_session.add_all((evidence_a, evidence_b))
    db_session.flush()
    repo = RAIDRepository(db_session, "tenant-a", "owner-1")
    risk = repo.create(
        risk_values(project_a.id, sprint_id=sprint_a.id, reference="R-031")
    )
    repo.link_evidence(risk.id, evidence_a.id)
    db_session.commit()
    assert risk.exposure_score == 25
    assert risk.residual_exposure_score == 25
    assert repo.get(risk.id).reference == "R-031"
    assert repo.list(filters={"search": "Payment"})[1] == 1
    assert (
        repo.list(filters={"item_type": "RISK", "sprint_id": sprint_a.id})[0][0].id
        == risk.id
    )
    with pytest.raises(RAIDValidationError, match="inaccessible"):
        repo.link_evidence(risk.id, evidence_b.id)
    with pytest.raises(RAIDConflictError):
        repo.update(risk.id, {"priority": "HIGH"}, expected_version=99)
    risk = repo.transition(
        risk.id, "ASSESSED", expected_version=risk.version, note=None
    )
    review = repo.review(
        risk.id,
        "Exposure remains material.",
        date.today() + timedelta(days=7),
        expected_version=risk.version,
    )
    db_session.commit()
    assert review.note.startswith("Exposure")
    assert {row.event_type for row in repo.history(risk.id)} >= {
        "CREATED",
        "EVIDENCE_LINKED",
        "STATUS_TRANSITION",
        "REVIEWED",
    }
    assert RAIDRepository(db_session, "tenant-b", "owner-2").get(risk.id) is None


def test_authenticated_api_candidate_human_review_proposal_copilot_and_negative_tenant(
    db_session,
):
    _, _, project, _, sprint = hierarchy(db_session, "tenant-a")
    _, _, other_project, _, _ = hierarchy(db_session, "tenant-b")
    evidence = DeliveryEvidence(
        tenant_id="tenant-a",
        entity_type="SPRINT",
        entity_id=sprint.id,
        source_type="STATUS_UPDATE",
        source_system="MANUAL",
        source_record_id="payment-delay",
        title="Payment provider status",
        summary="Capacity remains constrained.",
    )
    other_evidence = DeliveryEvidence(
        tenant_id="tenant-b",
        entity_type="PROJECT",
        entity_id=other_project.id,
        source_type="STATUS_UPDATE",
        source_system="MANUAL",
        source_record_id="private-risk",
        title="Tenant B confidential title",
    )
    conversation = Conversation(
        title="RAID review", tenant_id="tenant-a", user_id="owner-1"
    )
    db_session.add_all((evidence, other_evidence, conversation))
    db_session.commit()
    identity = {"sub": "owner-1", "custom:tenant_id": "tenant-a", "permissions": []}
    app.dependency_overrides[get_current_user] = lambda: identity
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        client = TestClient(app)
        created = client.post(
            "/api/raid",
            json={
                **_json_dates(
                    risk_values(project.id, sprint_id=sprint.id, reference="R-031")
                ),
                "evidence_ids": [evidence.id],
            },
        )
        assert created.status_code == 201, created.text
        risk = created.json()["item"]
        assert risk["reference"] == "R-031" and risk["evidenceCount"] == 1
        assert client.get("/api/raid/summary").json()["criticalRisks"] == 1
        assert len(client.get("/api/raid/heatmap").json()["cells"]) == 25
        assert (
            client.get("/api/raid", params={"search": "confidential"}).json()["total"]
            == 0
        )
        assert (
            client.post(
                f"/api/raid/{risk['id']}/evidence",
                json={"evidence_id": other_evidence.id},
            ).status_code
            == 422
        )
        candidate = client.post(
            "/api/raid/detected",
            json={
                "candidate_type": "RISK",
                "title": "Payment API capacity concern",
                "description": "Persisted sprint evidence indicates delivery uncertainty.",
                "confidence": 0.86,
                "evidence_ids": [evidence.id],
                "affected_entities": [{"type": "SPRINT", "id": sprint.id}],
                "suggested_owner": "owner-1",
                "suggested_due_date": (date.today() + timedelta(days=8)).isoformat(),
                "suggested_probability": "LIKELY",
                "suggested_impact": "HIGH",
                "project_id": project.id,
                "limitations": ["Single reporting period"],
            },
        )
        assert candidate.status_code == 201, candidate.text
        candidate_id = candidate.json()["candidate"]["id"]
        accepted = client.post(
            f"/api/raid/detected/{candidate_id}/accept",
            json={
                "project_id": project.id,
                "review_date": (date.today() + timedelta(days=7)).isoformat(),
            },
        )
        assert accepted.status_code == 201, accepted.text
        accepted_item = accepted.json()["item"]
        assert (
            accepted.json()["humanReviewed"] is True
            and accepted_item["evidenceCount"] == 1
        )
        proposal = client.post(
            f"/api/raid/{accepted_item['id']}/proposals",
            json={
                "action_type": "DRAFT_ESCALATION",
                "content": "Review the fictional provider risk at the programme checkpoint.",
                "status": "PROPOSED",
                "evidence_ids": [evidence.id],
            },
        )
        assert (
            proposal.status_code == 201 and proposal.json()["externalWrites"] is False
        )
        copilot = client.post(
            "/api/raid/copilot",
            json={
                "conversation_id": str(conversation.id),
                "question": "What is the evidence for this risk?",
                "raid_id": accepted_item["id"],
            },
        )
        assert copilot.status_code == 200, copilot.text
        assert copilot.json()["evidence"][0]["id"] == evidence.id
        assert copilot.json()["externalWrites"] is False
        assert (
            db_session.scalar(
                select(ProposedAction).where(
                    ProposedAction.raid_id == accepted_item["id"]
                )
            )
            is not None
        )
        assert db_session.scalars(
            select(AuditLog).where(
                AuditLog.tenant_id == "tenant-a",
                AuditLog.correlation_id == proposal.json()["traceId"],
            )
        ).all()

        identity.update({"sub": "owner-2", "custom:tenant_id": "tenant-b"})
        assert client.get(f"/api/raid/{risk['id']}").status_code == 404
        assert (
            client.get("/api/raid", params={"search": "Payment API delay"}).json()[
                "total"
            ]
            == 0
        )
        cross_accept = client.post(
            f"/api/raid/detected/{candidate_id}/accept",
            json={
                "project_id": other_project.id,
                "review_date": date.today().isoformat(),
            },
        )
        assert cross_accept.status_code == 404
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_db, None)


def test_explicit_permission_set_rejects_unauthorized_mutation(db_session):
    _, _, project, _, _ = hierarchy(db_session)
    item = RAIDRepository(db_session, "tenant-a", "owner-1").create(
        risk_values(project.id)
    )
    db_session.commit()
    app.dependency_overrides[get_current_user] = lambda: {
        "sub": "reader",
        "custom:tenant_id": "tenant-a",
        "permissions": ["raid.read"],
    }
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        response = TestClient(app).post(
            f"/api/raid/{item.id}/transition",
            json={"expected_version": item.version, "status": "ASSESSED"},
        )
        assert response.status_code == 403
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_db, None)


def test_critical_sprint_risk_propagates_to_command_my_day_sprint_and_copilot(
    db_session,
):
    _, _, project, _, sprint = hierarchy(db_session)
    evidence = DeliveryEvidence(
        tenant_id="tenant-a",
        entity_type="SPRINT",
        entity_id=sprint.id,
        source_type="STATUS_UPDATE",
        source_system="MANUAL",
        source_record_id="critical-sprint-risk",
        title="Critical synthetic sprint risk evidence",
    )
    conversation = Conversation(
        title="Cross-module RAID", tenant_id="tenant-a", user_id="owner-1"
    )
    db_session.add_all((evidence, conversation))
    db_session.flush()
    repository = RAIDRepository(db_session, "tenant-a", "owner-1")
    risk = repository.create(
        risk_values(project.id, sprint_id=sprint.id, reference="R-031")
    )
    repository.link_evidence(risk.id, evidence.id)
    db_session.commit()

    read_service = DeliveryReadService(db_session, "tenant-a", "owner-1")
    command = read_service.command_center()
    my_day = read_service.my_day()
    sprint_detail = read_service.sprint_detail(sprint.id)
    answer = DeliveryCopilotService(db_session, "tenant-a", "owner-1").raid_insight(
        str(conversation.id), "What threatens this sprint?", risk.id
    )

    assert any(item["id"] == risk.id for item in command["attentionItems"])
    assert any(item["id"] == risk.id for item in my_day["items"])
    assert sprint_detail is not None
    goal_confidence = next(
        dimension
        for dimension in sprint_detail["healthDimensions"]
        if dimension["name"] == "goal_confidence"
    )
    assert goal_confidence["score"] == 30
    assert sprint_detail["raidItems"][0]["reference"] == "R-031"
    assert answer["topItems"][0]["id"] == risk.id
    assert answer["evidence"][0]["id"] == evidence.id


def _json_dates(values):
    return {
        key: value.isoformat() if isinstance(value, (date, datetime)) else value
        for key, value in values.items()
    }
