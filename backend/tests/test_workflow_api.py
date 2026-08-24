from fastapi.testclient import TestClient

from app.api.main import app

client = TestClient(app)


def test_health():

    response = client.get("/health")

    assert response.status_code == 200


def test_run_workflow():

    response = client.post(
        "/workflows/run", params={"goal": "Generate deployment report"}
    )

    assert response.status_code == 200

    data = response.json()

    assert "workflow_id" in data
    assert data["status"] == "RUNNING"
