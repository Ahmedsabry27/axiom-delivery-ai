from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.auth.dependencies import get_current_user
from app.database.dependencies import get_db
from app.database.models.audit import AuditLog
from app.database.models.delivery import (
    CopilotResponseEvidence,
    DeliveryCopilotResponse,
    DeliveryDependency,
    DeliveryEvidence,
    DeliveryMilestone,
    DeliveryPortfolio,
    DeliveryProgramme,
    DeliveryProject,
    DeliveryRecommendation,
    DeliveryRelease,
    DeliverySprint,
    DeliveryTeam,
    DeliveryWorkItem,
)
from app.delivery.read_service import DeliveryReadService
from app.delivery.repositories import DependencyRepository, MilestoneRepository
from app.main import app
from app.models.conversation import Conversation
from app.models.message import Message


def hierarchy(db, tenant="tenant-a"):
    portfolio = DeliveryPortfolio(tenant_id=tenant, name="Portfolio", status="ACTIVE")
    db.add(portfolio)
    db.flush()
    programme = DeliveryProgramme(
        tenant_id=tenant, name="Programme", portfolio_id=portfolio.id, status="ACTIVE"
    )
    db.add(programme)
    db.flush()
    project = DeliveryProject(
        tenant_id=tenant, name="Payments", programme_id=programme.id, status="ACTIVE"
    )
    db.add(project)
    db.flush()
    team = DeliveryTeam(
        tenant_id=tenant, name="Phoenix", project_id=project.id, status="ACTIVE"
    )
    db.add(team)
    db.flush()
    release = DeliveryRelease(
        tenant_id=tenant, name="Release 4", project_id=project.id, status="ACTIVE"
    )
    db.add(release)
    db.flush()
    sprint = DeliverySprint(
        tenant_id=tenant,
        name="Sprint 24",
        project_id=project.id,
        team_id=team.id,
        goal="Ship authentication",
        status="ACTIVE",
        start_date=date.today() - timedelta(days=5),
        end_date=date.today() + timedelta(days=5),
        original_committed_points=10,
        completed_original_points=9,
        completed_points=9,
    )
    db.add(sprint)
    db.flush()
    return project, release, sprint


def test_dependency_milestone_lifecycle_and_cross_module_propagation(db_session):
    project, release, sprint = hierarchy(db_session)
    milestone = DeliveryMilestone(
        tenant_id="tenant-a",
        name="MVP",
        project_id=project.id,
        release_id=release.id,
        sprint_id=sprint.id,
        status="ACTIVE",
        planned_date=date.today() + timedelta(days=3),
        critical=True,
        owner_id="owner-1",
    )
    MilestoneRepository(db_session, "tenant-a").add(milestone)
    work = DeliveryWorkItem(
        tenant_id="tenant-a",
        name="Authentication API",
        project_id=project.id,
        sprint_id=sprint.id,
        status="ACTIVE",
        story_points=8,
        assignee_id="owner-1",
        goal_critical=True,
    )
    db_session.add(work)
    db_session.flush()
    healthy = DeliveryReadService(db_session, "tenant-a", "owner-1").sprint_detail(
        sprint.id
    )

    work.blocked = True
    work.blocked_since = datetime.now(UTC) - timedelta(days=4)
    dependency = DeliveryDependency(
        tenant_id="tenant-a",
        name="Identity provider",
        project_id=project.id,
        dependency_type="EXTERNAL",
        status="BLOCKED",
        impact="CRITICAL",
        priority="CRITICAL",
        critical_path=True,
        owner_id="owner-1",
    )
    DependencyRepository(db_session, "tenant-a").add_with_endpoints(
        dependency, ("WORK_ITEM", work.id), ("MILESTONE", milestone.id)
    )
    evidence = DeliveryEvidence(
        tenant_id="tenant-a",
        entity_type="SPRINT",
        entity_id=sprint.id,
        source_type="TEST_FIXTURE",
        source_system="MANUAL",
        source_record_id="s24",
        title="Sprint 24 blocker",
    )
    db_session.add(evidence)
    db_session.commit()
    db_session.expire_all()

    service = DeliveryReadService(db_session, "tenant-a", "owner-1")
    at_risk = service.sprint_detail(sprint.id)
    command = service.command_center()
    my_day = service.my_day()
    assert healthy["healthScore"] > at_risk["healthScore"]
    assert at_risk["health"] in {"AMBER", "RED"}
    assert at_risk["blockers"][0]["id"] == work.id
    assert any(item["id"] == dependency.id for item in command["attentionItems"])
    assert any(
        item["id"] in {work.id, dependency.id, milestone.id} for item in my_day["items"]
    )
    assert at_risk["evidence"][0]["id"] == evidence.id
    assert (
        DependencyRepository(db_session, "tenant-a").critical_path()[0].id
        == dependency.id
    )
    assert (
        DependencyRepository(db_session, "tenant-a")
        .related("SOURCE", "WORK_ITEM", work.id)[0]
        .id
        == dependency.id
    )


def test_dependency_endpoints_and_milestones_are_tenant_scoped(db_session):
    project_a, _, sprint_a = hierarchy(db_session, "tenant-a")
    _, _, sprint_b = hierarchy(db_session, "tenant-b")
    dependency = DeliveryDependency(
        tenant_id="tenant-a",
        name="Invalid",
        project_id=project_a.id,
        dependency_type="CROSS_TEAM",
        status="OPEN",
    )
    with pytest.raises(ValueError, match="inaccessible"):
        DependencyRepository(db_session, "tenant-a").add_with_endpoints(
            dependency, ("SPRINT", sprint_a.id), ("SPRINT", sprint_b.id)
        )
    same = DeliveryDependency(
        tenant_id="tenant-a",
        name="Same",
        project_id=project_a.id,
        dependency_type="INTERNAL",
        status="OPEN",
    )
    with pytest.raises(ValueError, match="must differ"):
        DependencyRepository(db_session, "tenant-a").add_with_endpoints(
            same, ("SPRINT", sprint_a.id), ("SPRINT", sprint_a.id)
        )
    assert MilestoneRepository(db_session, "tenant-b").list() == []


def test_authenticated_delivery_apis_read_persisted_tenant_data(db_session):
    _, _, sprint = hierarchy(db_session)
    db_session.commit()
    app.dependency_overrides[get_current_user] = lambda: {
        "sub": "owner-1",
        "custom:tenant_id": "tenant-a",
        "permissions": [],
    }
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        client = TestClient(app)
        command = client.get("/api/delivery/command-center")
        my_day = client.get("/api/delivery/my-day")
        sprint_response = client.get(f"/api/sprints/{sprint.id}")
        assert (
            command.status_code
            == my_day.status_code
            == sprint_response.status_code
            == 200
        )
        assert command.json()["dataFreshness"]["source"] == "persisted"
        assert sprint_response.json()["mode"] == "api"
        assert sprint_response.json()["id"] == sprint.id
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_db, None)


def test_copilot_evidence_proposal_and_audit_chain_is_persisted_and_tenant_safe(
    db_session,
):
    project, _, sprint = hierarchy(db_session)
    work = DeliveryWorkItem(
        tenant_id="tenant-a",
        name="Authentication API",
        project_id=project.id,
        sprint_id=sprint.id,
        status="BLOCKED",
        blocked=True,
        blocked_since=datetime.now(UTC) - timedelta(days=3),
        story_points=8,
        goal_critical=True,
        assignee_id="owner-1",
    )
    db_session.add(work)
    db_session.flush()
    dependency = DeliveryDependency(
        tenant_id="tenant-a",
        name="Identity provider",
        project_id=project.id,
        dependency_type="EXTERNAL",
        status="BLOCKED",
        critical_path=True,
    )
    DependencyRepository(db_session, "tenant-a").add_with_endpoints(
        dependency,
        ("WORK_ITEM", work.id),
        ("EXTERNAL_PARTY", "identity-provider"),
    )
    evidence = DeliveryEvidence(
        tenant_id="tenant-a",
        entity_type="DEPENDENCY",
        entity_id=dependency.id,
        dependency_id=dependency.id,
        source_type="STATUS_UPDATE",
        source_system="MANUAL",
        source_record_id="identity-delay",
        title="Identity provider delivery delayed",
        summary="Provider is three days late.",
    )
    recommendation = DeliveryRecommendation(
        tenant_id="tenant-a",
        entity_type="SPRINT",
        entity_id=sprint.id,
        title="Escalate the identity provider dependency",
        explanation="The goal-critical item is blocked by a critical-path dependency.",
        priority="CRITICAL",
        confidence=0.91,
    )
    conversation = Conversation(
        title="Sprint review",
        tenant_id="tenant-a",
        user_id="owner-1",
    )
    db_session.add_all((evidence, recommendation, conversation))
    db_session.commit()

    app.dependency_overrides[get_current_user] = lambda: {
        "sub": "owner-1",
        "custom:tenant_id": "tenant-a",
        "permissions": [],
    }
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        client = TestClient(app)
        insight = client.post(
            "/api/delivery/copilot/sprint-insight",
            json={
                "conversation_id": str(conversation.id),
                "sprint_id": sprint.id,
                "message": "Will we meet the sprint goal and what should I do?",
            },
        )
        assert insight.status_code == 200, insight.text
        answer = insight.json()
        assert answer["sprint"]["id"] == sprint.id
        assert answer["primaryRisk"] == work.name
        assert answer["dependencies"][0]["id"] == dependency.id
        assert answer["evidence"][0]["id"] == evidence.id
        assert answer["recommendations"][0]["id"] == recommendation.id
        assert answer["externalWrites"] is False

        proposal = client.post(
            "/api/delivery/proposed-actions",
            json={
                "conversation_id": str(conversation.id),
                "message_id": answer["assistantMessageId"],
                "response_id": answer["id"],
                "sprint_id": sprint.id,
                "work_item_id": work.id,
                "dependency_id": dependency.id,
                "recommendation_id": recommendation.id,
                "trace_id": answer["traceId"],
                "action_type": "ESCALATE_DEPENDENCY",
                "content": "Ask the identity provider owner for a dated recovery plan.",
                "evidence_ids": [evidence.id],
            },
        )
        assert proposal.status_code == 201, proposal.text
        action_id = proposal.json()["id"]
        db_session.expire_all()

        persisted = client.get(f"/api/delivery/proposed-actions/{action_id}")
        assert persisted.status_code == 200
        assert persisted.json()["response_id"] == answer["id"]
        assert persisted.json()["evidence_ids"] == [evidence.id]
        assert db_session.scalar(select(func.count()).select_from(Message)) == 2
        assert (
            db_session.scalar(select(func.count()).select_from(DeliveryCopilotResponse))
            == 1
        )
        assert (
            db_session.scalar(select(func.count()).select_from(CopilotResponseEvidence))
            == 1
        )
        assert db_session.scalar(select(func.count()).select_from(AuditLog)) == 8

        invalid_evidence = client.post(
            "/api/delivery/proposed-actions",
            json={
                "conversation_id": str(conversation.id),
                "trace_id": answer["traceId"],
                "action_type": "ESCALATE_DEPENDENCY",
                "content": "Invalid evidence attempt",
                "evidence_ids": ["missing-evidence"],
            },
        )
        assert invalid_evidence.status_code == 404
        assert db_session.scalar(select(func.count()).select_from(AuditLog)) == 9

        other_project, _, other_sprint = hierarchy(db_session, "tenant-b")
        del other_project
        db_session.commit()
        rejected = client.post(
            "/api/delivery/proposed-actions",
            json={
                "conversation_id": str(conversation.id),
                "response_id": answer["id"],
                "sprint_id": other_sprint.id,
                "action_type": "ESCALATE_DEPENDENCY",
                "content": "Cross-tenant attempt",
                "evidence_ids": [evidence.id],
            },
        )
        assert rejected.status_code == 404
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_db, None)
