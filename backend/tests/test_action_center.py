from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user
from app.database.dependencies import get_db
from app.database.models.action_center import ActionExecution, ApprovalDecision
from app.database.models.audit import AuditLog
from app.database.models.delivery import (
    DeliveryEvidence,
    DeliveryPortfolio,
    DeliveryProgramme,
    DeliveryProject,
)
from app.database.models.governance_workflow import ApprovalRequest
from app.main import app


def _claims(actor: str, tenant: str, *permissions: str) -> dict:
    return {
        "sub": actor,
        "custom:tenant_id": tenant,
        "permissions": list(permissions),
    }


def _seed_evidence(db_session, tenant: str = "tenant-a") -> tuple[str, str]:
    portfolio = DeliveryPortfolio(tenant_id=tenant, name="Portfolio", created_by="seed")
    db_session.add(portfolio)
    db_session.flush()
    programme = DeliveryProgramme(
        tenant_id=tenant,
        name="Programme",
        portfolio_id=portfolio.id,
        created_by="seed",
    )
    db_session.add(programme)
    db_session.flush()
    project = DeliveryProject(
        tenant_id=tenant,
        name="Project",
        programme_id=programme.id,
        created_by="seed",
    )
    db_session.add(project)
    db_session.flush()
    evidence = DeliveryEvidence(
        tenant_id=tenant,
        entity_type="PROJECT",
        entity_id=project.id,
        source_type="DELIVERY_RECORD",
        source_system="AXIOM",
        source_record_id=f"project:{project.id}",
        title="Current project delivery evidence",
        summary="The risk was confirmed in the delivery review.",
        captured_at=datetime.now(UTC),
    )
    db_session.add(evidence)
    db_session.commit()
    return project.id, evidence.id


def _client(db_session, current: dict) -> TestClient:
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: current
    return TestClient(app)


def _create_action(client: TestClient, project_id: str, evidence_id: str) -> dict:
    response = client.post(
        "/api/actions",
        json={
            "action_type": "CREATE_RAID_ITEM",
            "title": "Register supplier delivery risk",
            "description": "Record the verified risk for active management.",
            "payload": {
                "project_id": project_id,
                "item_type": "RISK",
                "name": "Supplier readiness",
                "description": "Supplier readiness may delay the release.",
                "probability": "LIKELY",
                "impact": "HIGH",
                "review_date": (date.today() + timedelta(days=7)).isoformat(),
            },
            "evidence_ids": [evidence_id],
            "idempotency_key": "create-risk-request-001",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_authenticated_action_journey_is_persisted_and_idempotent(db_session):
    project_id, evidence_id = _seed_evidence(db_session)
    current = _claims(
        "requester",
        "tenant-a",
        "actions.create",
        "actions.read",
        "actions.edit",
        "approvals.request",
    )
    client = _client(db_session, current)
    try:
        action = _create_action(client, project_id, evidence_id)
        assert action["status"] == "DRAFT"
        assert action["riskLevel"] == "MEDIUM"

        submitted = client.post(
            f"/api/actions/{action['id']}/submit",
            json={"assigned_approver_id": "approver"},
        )
        assert submitted.status_code == 200, submitted.text
        approval = submitted.json()
        assert approval["status"] == "PENDING"

        current.clear()
        current.update(
            _claims("approver", "tenant-a", "approvals.read", "approvals.approve")
        )
        approved = client.post(
            f"/api/approvals/{approval['id']}/approve",
            json={"comment": "Evidence and scope reviewed."},
        )
        assert approved.status_code == 200, approved.text
        assert approved.json()["status"] == "APPROVED"

        current.clear()
        current.update(_claims("executor", "tenant-a", "actions.execute"))
        execution = client.post(
            f"/api/actions/{action['id']}/execute",
            json={"idempotency_key": "execute-risk-001"},
        )
        assert execution.status_code == 200, execution.text
        assert execution.json()["status"] == "EXECUTED"
        duplicate = client.post(
            f"/api/actions/{action['id']}/execute",
            json={"idempotency_key": "execute-risk-001"},
        )
        assert duplicate.status_code == 200
        assert duplicate.json()["id"] == execution.json()["id"]

        current.clear()
        current.update(_claims("verifier", "tenant-a", "actions.verify"))
        verified = client.post(
            f"/api/actions/{action['id']}/verify",
            json={"comment": "RAID system-of-record read succeeded."},
        )
        assert verified.status_code == 200, verified.text
        assert verified.json()["status"] == "VERIFIED"

        db_session.expire_all()
        current.clear()
        current.update(
            _claims("requester", "tenant-a", "actions.read", "actions.read_all")
        )
        reloaded = client.get(f"/api/actions/{action['id']}")
        assert reloaded.status_code == 200
        assert reloaded.json()["status"] == "VERIFIED"
        assert len(reloaded.json()["executions"]) == 1
        assert db_session.query(ActionExecution).count() == 1
        assert db_session.query(ApprovalDecision).count() == 1
        assert (
            db_session.query(AuditLog)
            .filter(AuditLog.action == "action.verified")
            .count()
            == 1
        )
    finally:
        app.dependency_overrides.clear()


def test_assigned_approver_detail_and_decision_capabilities(db_session):
    project_id, evidence_id = _seed_evidence(db_session)
    current = _claims(
        "requester",
        "tenant-a",
        "actions.create",
        "actions.read",
        "approvals.request",
    )
    client = _client(db_session, current)
    try:
        action = _create_action(client, project_id, evidence_id)
        approval = client.post(
            f"/api/actions/{action['id']}/submit",
            json={"assigned_approver_id": "approver"},
        ).json()

        current.clear()
        current.update(_claims("approver", "tenant-a", "approvals.read"))
        detail = client.get(f"/api/approvals/{approval['id']}")
        assert detail.status_code == 200
        assert detail.json()["capabilities"] == {
            "canView": True,
            "canApprove": False,
            "canReject": False,
            "canRequestChanges": False,
            "canDelegate": False,
            "denialReasonCode": "DECISION_NOT_ALLOWED",
        }
        denied = client.post(
            f"/api/approvals/{approval['id']}/approve", json={"comment": "reviewed"}
        )
        assert denied.status_code == 403

        current.clear()
        current.update(_claims("approver", "tenant-a", "approvals.approve"))
        assert client.get(f"/api/approvals/{approval['id']}").status_code == 403

        current["permissions"].append("approvals.read")
        decided = client.post(
            f"/api/approvals/{approval['id']}/approve", json={"comment": "reviewed"}
        )
        assert decided.status_code == 200
    finally:
        app.dependency_overrides.clear()


def test_role_assignment_uses_same_list_detail_and_decision_policy(db_session):
    project_id, evidence_id = _seed_evidence(db_session)
    current = _claims(
        "requester",
        "tenant-a",
        "actions.create",
        "actions.read",
        "approvals.request",
    )
    client = _client(db_session, current)
    try:
        action = _create_action(client, project_id, evidence_id)
        approval_data = client.post(
            f"/api/actions/{action['id']}/submit", json={}
        ).json()
        approval = db_session.get(ApprovalRequest, approval_data["id"])
        approval.assigned_role = "delivery-manager"
        db_session.commit()

        current.clear()
        current.update(
            {
                **_claims(
                    "role-approver",
                    "tenant-a",
                    "approvals.read",
                    "approvals.approve",
                ),
                "roles": ["DELIVERY-MANAGER"],
            }
        )
        listed = client.get("/api/approvals?status=PENDING")
        assert listed.status_code == 200
        assert [item["id"] for item in listed.json()["items"]] == [approval.id]
        assert client.get(f"/api/approvals/{approval.id}").status_code == 200
        assert (
            client.post(
                f"/api/approvals/{approval.id}/approve",
                json={"comment": "Role assignment reviewed"},
            ).status_code
            == 200
        )
    finally:
        app.dependency_overrides.clear()


def test_submission_requires_evidence(db_session):
    project_id, _ = _seed_evidence(db_session)
    current = _claims(
        "requester", "tenant-a", "actions.create", "actions.read", "approvals.request"
    )
    client = _client(db_session, current)
    try:
        created = client.post(
            "/api/actions",
            json={
                "action_type": "CREATE_RAID_ITEM",
                "title": "No evidence",
                "payload": {"project_id": project_id},
            },
        ).json()
        response = client.post(f"/api/actions/{created['id']}/submit", json={})
        assert response.status_code == 422
        assert response.json()["detail"]["code"] == "EVIDENCE_REQUIRED"
    finally:
        app.dependency_overrides.clear()


def test_separation_of_duties_and_tenant_boundary(db_session):
    project_id, evidence_id = _seed_evidence(db_session)
    current = _claims(
        "requester",
        "tenant-a",
        "actions.create",
        "actions.read",
        "approvals.request",
        "approvals.approve",
    )
    client = _client(db_session, current)
    try:
        action = _create_action(client, project_id, evidence_id)
        approval = client.post(
            f"/api/actions/{action['id']}/submit",
            json={"assigned_approver_id": "requester"},
        ).json()
        self_approval = client.post(
            f"/api/approvals/{approval['id']}/approve", json={"comment": "self"}
        )
        assert self_approval.status_code == 403
        assert self_approval.json()["detail"]["code"] == "SEPARATION_OF_DUTIES"

        current.clear()
        current.update(_claims("other", "tenant-b", "actions.execute"))
        cross_tenant = client.post(
            f"/api/actions/{action['id']}/execute",
            json={"idempotency_key": "cross-tenant-attempt"},
        )
        assert cross_tenant.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_expired_and_stale_approvals_fail_closed(db_session):
    project_id, evidence_id = _seed_evidence(db_session)
    current = _claims(
        "requester",
        "tenant-a",
        "actions.create",
        "actions.read",
        "actions.edit",
        "approvals.request",
    )
    client = _client(db_session, current)
    try:
        action = _create_action(client, project_id, evidence_id)
        approval = client.post(
            f"/api/actions/{action['id']}/submit",
            json={"assigned_approver_id": "approver"},
        ).json()
        row = db_session.query(ApprovalRequest).filter_by(id=approval["id"]).one()
        row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db_session.commit()

        current.clear()
        current.update(_claims("approver", "tenant-a", "approvals.approve"))
        expired = client.post(
            f"/api/approvals/{approval['id']}/approve", json={"comment": "late"}
        )
        assert expired.status_code == 409
        assert expired.json()["detail"]["code"] == "APPROVAL_EXPIRED"
    finally:
        app.dependency_overrides.clear()


def test_unknown_and_external_actions_have_no_execution_path(db_session):
    current = _claims("reader", "tenant-a", "actions.read")
    client = _client(db_session, current)
    try:
        unknown = client.post(
            "/api/action-policies/evaluate",
            json={"action_type": "UNREGISTERED_MUTATION", "payload": {}},
        )
        assert unknown.status_code == 200
        assert unknown.json()["riskLevel"] == "RESTRICTED"
        assert unknown.json()["executionAllowed"] is False
        external = client.post(
            "/api/action-policies/evaluate",
            json={
                "action_type": "SEND_MESSAGE",
                "target_system": "SLACK",
                "payload": {},
            },
        )
        assert external.status_code == 200
        assert external.json()["draftOnly"] is True
        assert external.json()["adapter"] is None
    finally:
        app.dependency_overrides.clear()


def test_rejection_blocks_execution_and_decisions_are_append_only(db_session):
    project_id, evidence_id = _seed_evidence(db_session)
    current = _claims(
        "requester",
        "tenant-a",
        "actions.create",
        "actions.read",
        "approvals.request",
    )
    client = _client(db_session, current)
    try:
        action = _create_action(client, project_id, evidence_id)
        approval = client.post(
            f"/api/actions/{action['id']}/submit",
            json={"assigned_approver_id": "approver"},
        ).json()
        current.clear()
        current.update(_claims("approver", "tenant-a", "approvals.approve"))
        rejected = client.post(
            f"/api/approvals/{approval['id']}/reject",
            json={"comment": "Evidence does not support this intervention."},
        )
        assert rejected.status_code == 200
        current.clear()
        current.update(_claims("executor", "tenant-a", "actions.execute"))
        execution = client.post(
            f"/api/actions/{action['id']}/execute",
            json={"idempotency_key": "rejected-execution"},
        )
        assert execution.status_code == 409
        assert execution.json()["detail"]["code"] == "ACTION_NOT_APPROVED"
        decision = db_session.query(ApprovalDecision).one()
        decision.comment = "Mutation attempt"
        with pytest.raises(ValueError, match="append-only"):
            db_session.commit()
        db_session.rollback()
    finally:
        app.dependency_overrides.clear()


def test_stale_edit_is_rejected(db_session):
    project_id, evidence_id = _seed_evidence(db_session)
    current = _claims(
        "requester",
        "tenant-a",
        "actions.create",
        "actions.read",
        "actions.edit",
    )
    client = _client(db_session, current)
    try:
        action = _create_action(client, project_id, evidence_id)
        stale = client.patch(
            f"/api/actions/{action['id']}",
            json={"expected_version": action["version"] + 1, "title": "Stale edit"},
        )
        assert stale.status_code == 409
        assert stale.json()["detail"]["code"] == "STALE_ACTION_VERSION"
    finally:
        app.dependency_overrides.clear()
