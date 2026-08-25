from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user
from app.database.dependencies import get_db
from app.main import app


def client(db_session, identity):
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: identity
    return TestClient(app)


def clear():
    app.dependency_overrides.clear()


def test_saved_insights_are_durable_versioned_and_tenant_scoped(db_session):
    owner = {
        "sub": "owner",
        "custom:tenant_id": "tenant-a",
        "cognito:groups": ["platform-admin"],
    }
    other = {
        "sub": "other",
        "custom:tenant_id": "tenant-b",
        "cognito:groups": ["platform-admin"],
    }
    try:
        api = client(db_session, owner)
        created = api.post(
            "/api/copilot/saved-insights",
            json={
                "title": "Release confidence",
                "summary": "Confidence is constrained by two missing approvals.",
                "insight_type": "RELEASE",
                "confidence": "MEDIUM",
                "evidence_snapshots": [
                    {"id": "ev-1", "fingerprint": "sha256:original"}
                ],
            },
        ).json()
        assert created["version"] == 1
        assert api.get("/api/copilot/saved-insights").json()["total"] == 1
        updated = api.patch(
            f"/api/copilot/saved-insights/{created['id']}",
            json={"title": "Release confidence reviewed", "version": 1},
        ).json()
        assert updated["version"] == 2
        assert updated["evidenceSnapshots"][0]["fingerprint"] == "sha256:original"
        app.dependency_overrides[get_current_user] = lambda: other
        assert (
            api.get(f"/api/copilot/saved-insights/{created['id']}").status_code == 404
        )
        assert api.get("/api/copilot/saved-insights").json()["total"] == 0
    finally:
        clear()


def test_prompt_template_lifecycle_favorite_secret_guard_and_separation(db_session):
    author = {
        "sub": "author",
        "custom:tenant_id": "tenant-a",
        "cognito:groups": ["platform-admin"],
    }
    reviewer = {
        "sub": "reviewer",
        "custom:tenant_id": "tenant-a",
        "cognito:groups": ["platform-admin"],
    }
    try:
        api = client(db_session, author)
        rejected = api.post(
            "/api/copilot/prompt-templates",
            json={
                "name": "Unsafe",
                "category": "SPRINT",
                "prompt_body": "api_key=do-not-store",
            },
        )
        assert rejected.status_code == 422
        row = api.post(
            "/api/copilot/prompt-templates",
            json={
                "name": "Sprint health",
                "category": "SPRINT",
                "prompt_body": "Explain sprint health using authorized evidence.",
                "required_context_types": ["PROJECT", "SPRINT"],
            },
        ).json()
        assert (
            api.post(f"/api/copilot/prompt-templates/{row['id']}/favorite").status_code
            == 201
        )
        submitted = api.post(
            f"/api/copilot/prompt-templates/{row['id']}/lifecycle/submit"
        ).json()
        assert submitted["status"] == "PENDING_REVIEW"
        assert (
            api.post(
                f"/api/copilot/prompt-templates/{row['id']}/lifecycle/approve"
            ).status_code
            == 403
        )
        app.dependency_overrides[get_current_user] = lambda: reviewer
        approved = api.post(
            f"/api/copilot/prompt-templates/{row['id']}/lifecycle/approve"
        ).json()
        assert approved["status"] == "APPROVED"
        published = api.post(
            f"/api/copilot/prompt-templates/{row['id']}/lifecycle/publish"
        ).json()
        assert published["status"] == "PUBLISHED"
    finally:
        clear()


def test_missing_tenant_claim_fails_closed(db_session):
    try:
        api = client(db_session, {"sub": "user", "cognito:groups": ["platform-admin"]})
        response = api.get("/api/copilot/saved-insights")
        assert response.status_code == 403
        assert response.json()["detail"]["code"] == "TENANT_ASSIGNMENT_REQUIRED"
    finally:
        clear()


def test_conversation_preferences_archive_and_tenant_scope(db_session):
    owner = {
        "sub": "same-user",
        "custom:tenant_id": "tenant-a",
        "cognito:groups": ["platform-admin"],
    }
    other_tenant = {
        "sub": "same-user",
        "custom:tenant_id": "tenant-b",
        "cognito:groups": ["platform-admin"],
    }
    try:
        api = client(db_session, owner)
        created = api.post("/conversations", json={"title": "Delivery review"}).json()
        updated = api.patch(
            f"/conversations/{created['id']}",
            json={
                "is_pinned": True,
                "context_summary": {"type": "PROJECT", "id": "project-1"},
            },
        ).json()
        assert updated["is_pinned"] is True
        assert updated["context_summary"]["id"] == "project-1"
        archived = api.patch(f"/conversations/{created['id']}/archive").json()
        assert archived["is_archived"] is True
        app.dependency_overrides[get_current_user] = lambda: other_tenant
        assert api.get(f"/conversations/{created['id']}").status_code == 404
        assert api.get("/conversations").json() == []
    finally:
        clear()


def test_feedback_collection_reuses_durable_delivery_feedback(db_session):
    identity = {
        "sub": "owner",
        "custom:tenant_id": "tenant-a",
        "cognito:groups": ["platform-admin"],
    }
    try:
        api = client(db_session, identity)
        response = api.post(
            "/api/delivery/copilot/feedback",
            json={
                "conversation_id": "conversation-1",
                "message_id": "message-1",
                "feedback_type": "Helpful",
                "comment": "Evidence was clear.",
            },
        )
        assert response.status_code == 202
        records = api.get("/api/copilot/feedback").json()
        assert records["total"] == 1
        assert records["items"][0]["feedbackType"] == "Helpful"
        assert "messageContent" not in records["items"][0]
    finally:
        clear()


def test_read_only_identity_cannot_manage_templates(db_session):
    identity = {
        "sub": "reader",
        "custom:tenant_id": "tenant-a",
        "permissions": ["copilot.templates.read"],
    }
    try:
        api = client(db_session, identity)
        assert api.get("/api/copilot/prompt-templates").status_code == 200
        denied = api.post(
            "/api/copilot/prompt-templates",
            json={
                "name": "Denied",
                "category": "SPRINT",
                "prompt_body": "Explain sprint health.",
            },
        )
        assert denied.status_code == 403
        assert denied.json()["detail"]["code"] == "COPILOT_PERMISSION_REQUIRED"
    finally:
        clear()
