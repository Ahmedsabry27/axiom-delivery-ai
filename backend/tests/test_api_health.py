from fastapi.testclient import TestClient

from app.api.main import app

client = TestClient(app)


def test_health_endpoint():

    response = client.get("/health")

    assert response.status_code == 200

    assert response.json() == {
        "status": "healthy",
        "service": "ai-delivery-platform-api",
    }


def test_run_workflow_endpoint():

    response = client.post(
        "/api/workflows/run", json={"goal": "Generate deployment report"}
    )

    assert response.status_code == 200

    body = response.json()

    assert "workflow_id" in body

    assert body["status"] == "RUNNING"


def test_list_workflows_endpoint():

    response = client.get("/api/workflows")

    assert response.status_code == 200

    assert isinstance(
        response.json(),
        list,
    )
