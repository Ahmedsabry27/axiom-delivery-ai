from fastapi.testclient import TestClient

from app.main import app


def test_liveness_readiness_and_security_headers():
    client = TestClient(app)
    live = client.get("/health")
    ready = client.get("/ready")
    assert live.status_code == 200
    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"
    assert live.headers["x-content-type-options"] == "nosniff"
    assert live.headers["x-frame-options"] == "DENY"
    assert live.headers["cache-control"] == "no-store"
