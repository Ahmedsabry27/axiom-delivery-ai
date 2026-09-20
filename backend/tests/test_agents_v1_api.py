from __future__ import annotations

from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.agents.application_service import AgentIdentity, agent_application_service
from app.api.agents_v1 import router
from app.auth.dependencies import get_current_user
from app.database.dependencies import get_db
from app.database.models.agent import Agent, AgentActivityEvent
from app.database.models.knowledge_source import KnowledgeSource
from app.database.models.tool import ToolDefinition
from app.database.models.workflow import Workflow
from app.models.runtime_execution import RuntimeExecution


def make_client(db_session, claims: dict) -> TestClient:
    app = FastAPI()
    app.include_router(router)

    def database_override():
        yield db_session

    def identity_override():
        return claims

    app.dependency_overrides[get_db] = database_override
    app.dependency_overrides[get_current_user] = identity_override
    return TestClient(app)


def admin_claims(tenant: str = "tenant-a") -> dict:
    return {
        "sub": "admin-user",
        "custom:tenant_id": tenant,
        "permissions": [
            "agents.list",
            "agents.read",
            "agents.create",
            "agents.update",
            "agents.publish",
            "agents.enable",
            "agents.disable",
            "agents.archive",
            "agents.delete",
            "agents.restore",
            "agents.tools.manage",
            "agents.knowledge.manage",
            "agents.access.manage",
            "agents.evaluate",
        ],
    }


def test_create_list_detail_and_update_contract(db_session):
    client = make_client(db_session, admin_claims())
    created = client.post(
        "/api/v1/agents",
        json={
            "name": "Release Analyst",
            "instructions": "Use approved release records.",
            "model_configuration": {
                "provider": "openai",
                "model": "gpt-4.1-mini",
            },
        },
    )
    assert created.status_code == 201
    public_id = created.json()["id"]
    assert created.json()["lifecycle_status"] == "draft"

    listing = client.get("/api/v1/agents", params={"search": "release"})
    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    assert listing.json()["items"][0]["id"] == public_id
    assert client.get(f"/api/v1/agents/{public_id}").status_code == 200

    updated = client.patch(
        f"/api/v1/agents/{public_id}",
        headers={"If-Match": "1"},
        json={"description": "Updated safely", "change_note": "API update"},
    )
    assert updated.status_code == 200
    assert updated.json()["lock_version"] == 2
    conflict = client.patch(
        f"/api/v1/agents/{public_id}",
        headers={"If-Match": "1"},
        json={"description": "stale"},
    )
    assert conflict.status_code == 409


def test_unknown_fields_and_missing_permission_are_rejected(db_session):
    client = make_client(db_session, admin_claims())
    assert (
        client.post(
            "/api/v1/agents", json={"name": "Valid Agent", "unexpected": True}
        ).status_code
        == 422
    )

    denied = make_client(
        db_session,
        {
            "sub": "reader",
            "custom:tenant_id": "tenant-a",
            "permissions": ["agents.list"],
        },
    )
    response = denied.post("/api/v1/agents", json={"name": "Denied Agent"})
    assert response.status_code == 403


def test_cross_tenant_agent_identifier_is_not_visible(db_session):
    tenant_a = make_client(db_session, admin_claims("tenant-a"))
    public_id = tenant_a.post("/api/v1/agents", json={"name": "Tenant A Agent"}).json()[
        "id"
    ]
    tenant_b = make_client(db_session, admin_claims("tenant-b"))
    assert tenant_b.get(f"/api/v1/agents/{public_id}").status_code == 404


def test_agent_evaluations_are_tenant_scoped_and_paginated(db_session):
    tenant_a = make_client(db_session, admin_claims("tenant-a"))
    public_id = tenant_a.post(
        "/api/v1/agents", json={"name": "Evaluation Agent"}
    ).json()["id"]

    response = tenant_a.get(f"/api/v1/agents/{public_id}/evaluations")
    assert response.status_code == 200
    assert response.json() == {
        "items": [],
        "page": 1,
        "page_size": 20,
        "total": 0,
        "pages": 1,
    }

    tenant_b = make_client(db_session, admin_claims("tenant-b"))
    assert tenant_b.get(f"/api/v1/agents/{public_id}/evaluations").status_code == 404


def test_lifecycle_versions_assignments_and_activity_contract(db_session):
    client = make_client(db_session, admin_claims())
    created = client.post(
        "/api/v1/agents",
        json={
            "name": "Governed API Agent",
            "instructions": "Follow tenant governance.",
            "model_configuration": {"provider": "openai", "model": "gpt-4.1-mini"},
        },
    ).json()
    public_id = created["id"]
    db_session.add(
        ToolDefinition(
            tenant_id="tenant-a",
            name="safe_tool",
            display_name="Safe Tool",
            description="Harmless test tool",
            category="test",
            provider="native",
            version="1.0.0",
            input_schema={"type": "object"},
            permissions=[],
            enabled=True,
            active=True,
        )
    )
    source = KnowledgeSource(
        tenant_id="tenant-a",
        owner_id="admin-user",
        name="Safe source",
        source_type="DOCUMENT",
        readiness_status="ready",
    )
    db_session.add(source)
    db_session.commit()
    tools = client.put(
        f"/api/v1/agents/{public_id}/tools",
        json={"assignments": [{"tool_name": "safe_tool"}]},
    )
    assert tools.status_code == 200 and tools.json()[0]["tool_name"] == "safe_tool"
    knowledge = client.put(
        f"/api/v1/agents/{public_id}/knowledge",
        json={"assignments": [{"knowledge_source_id": source.id}]},
    )
    assert knowledge.status_code == 200
    access = client.put(
        f"/api/v1/agents/{public_id}/access",
        json={
            "assignments": [
                {"subject_type": "user", "subject_id": "reader", "action": "view"}
            ]
        },
    )
    assert access.status_code == 200
    published = client.post(
        f"/api/v1/agents/{public_id}/publish",
        headers={"If-Match": "1"},
        json={"change_note": "Reviewed"},
    )
    assert published.status_code == 200
    enabled = client.post(
        f"/api/v1/agents/{public_id}/enable",
        headers={"If-Match": "2"},
        json={},
    )
    assert enabled.status_code == 200
    assert enabled.json()["lifecycle_status"] == "enabled"
    assert client.get(f"/api/v1/agents/{public_id}/versions").json()[0]["published"]
    assert client.get(f"/api/v1/agents/{public_id}/activity").status_code == 200


def test_edit_persists_owner_environment_and_rejects_unauthorized_access(db_session):
    client = make_client(db_session, admin_claims())
    public_id = client.post(
        "/api/v1/agents", json={"name": "Editable Agent"}
    ).json()["id"]

    updated = client.patch(
        f"/api/v1/agents/{public_id}",
        headers={"If-Match": "1"},
        json={
            "name": "Edited Agent",
            "owner_id": "new-owner",
            "execution_limits": {
                "max_steps": 12,
                "timeout_seconds": 90,
                "environments": ["staging"],
            },
        },
    )
    assert updated.status_code == 200
    assert updated.json()["owner_id"] == "new-owner"
    assert updated.json()["environment_restrictions"] == ["staging"]

    denied = make_client(
        db_session,
        {
            "sub": "reader",
            "custom:tenant_id": "tenant-a",
            "permissions": ["agents.list", "agents.read"],
        },
    )
    assert (
        denied.patch(
            f"/api/v1/agents/{public_id}",
            headers={"If-Match": "2"},
            json={"name": "Denied Edit"},
        ).status_code
        == 403
    )
    cross_tenant = make_client(db_session, admin_claims("tenant-b"))
    assert (
        cross_tenant.patch(
            f"/api/v1/agents/{public_id}",
            headers={"If-Match": "2"},
            json={"name": "Hidden Edit"},
        ).status_code
        == 404
    )


def test_delete_unused_draft_preserves_audit_and_enforces_permissions(db_session):
    client = make_client(db_session, admin_claims())
    public_id = client.post(
        "/api/v1/agents", json={"name": "Disposable Draft"}
    ).json()["id"]

    impact = client.get(f"/api/v1/agents/{public_id}/deletion-impact")
    assert impact.status_code == 200
    assert impact.json()["eligible_for_permanent_deletion"] is True

    denied = make_client(
        db_session,
        {
            "sub": "reader",
            "custom:tenant_id": "tenant-a",
            "permissions": ["agents.list", "agents.read"],
        },
    )
    assert denied.delete(f"/api/v1/agents/{public_id}").status_code == 403
    assert client.delete(f"/api/v1/agents/{public_id}").status_code == 204
    assert client.get(f"/api/v1/agents/{public_id}").status_code == 404

    row = db_session.query(Agent).filter_by(uuid=public_id).one()
    assert row.deleted_at is not None
    assert (
        db_session.query(AgentActivityEvent)
        .filter_by(agent_id=row.id, event_type="agent.deleted")
        .count()
        == 1
    )


def test_delete_rejects_published_and_executed_agents(db_session):
    client = make_client(db_session, admin_claims())
    published_id = client.post(
        "/api/v1/agents",
        json={
            "name": "Published Agent",
            "instructions": "Use governed evidence.",
            "model_configuration": {
                "provider": "openai",
                "model": "gpt-4.1-mini",
            },
        },
    ).json()["id"]
    assert (
        client.post(
            f"/api/v1/agents/{published_id}/publish",
            headers={"If-Match": "1"},
            json={},
        ).status_code
        == 200
    )
    response = client.delete(f"/api/v1/agents/{published_id}")
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "AGENT_DELETE_REQUIRES_ARCHIVE"

    executed_id = client.post(
        "/api/v1/agents", json={"name": "Executed Agent"}
    ).json()["id"]
    db_session.add(
        RuntimeExecution(
            conversation_id=uuid4(),
            workflow_id=uuid4(),
            user_id="admin-user",
            tenant_id="tenant-a",
            agent=executed_id,
            selected_agent_id=executed_id,
            status="SUCCEEDED",
        )
    )
    db_session.commit()
    impact = client.get(f"/api/v1/agents/{executed_id}/deletion-impact").json()
    assert impact["execution_count"] > 0
    assert client.delete(f"/api/v1/agents/{executed_id}").status_code == 409


def test_workflow_reference_requires_archive_and_archived_agent_cannot_route(
    db_session,
):
    client = make_client(db_session, admin_claims())
    public_id = client.post(
        "/api/v1/agents", json={"name": "Referenced Agent"}
    ).json()["id"]
    db_session.add(
        Workflow(
            tenant_id="tenant-a",
            goal="Use referenced agent",
            assigned_agent=public_id,
            created_by="admin-user",
        )
    )
    db_session.commit()

    impact = client.get(f"/api/v1/agents/{public_id}/deletion-impact").json()
    assert impact["workflow_reference_count"] == 1
    assert impact["recommended_action"] == "archive"
    assert client.delete(f"/api/v1/agents/{public_id}").status_code == 409
    archived = client.post(
        f"/api/v1/agents/{public_id}/archive",
        headers={"If-Match": "1"},
        json={"confirmed": True},
    )
    assert archived.status_code == 200
    assert archived.json()["lifecycle_status"] == "archived"

    runtime_identity = AgentIdentity(
        actor_id="admin-user",
        tenant_id="tenant-a",
        permissions=frozenset({"agents.execute"}),
        groups=frozenset(),
    )
    try:
        agent_application_service.resolve_runtime(
            db_session, runtime_identity, public_id
        )
    except Exception as error:  # FastAPI raises the governed HTTP error directly.
        assert getattr(error, "status_code", None) == 409
    else:
        raise AssertionError("Archived agent unexpectedly resolved for runtime")


def test_cross_tenant_delete_is_non_enumerating(db_session):
    tenant_a = make_client(db_session, admin_claims("tenant-a"))
    public_id = tenant_a.post(
        "/api/v1/agents", json={"name": "Tenant A Delete"}
    ).json()["id"]
    tenant_b = make_client(db_session, admin_claims("tenant-b"))
    assert tenant_b.delete(f"/api/v1/agents/{public_id}").status_code == 404
