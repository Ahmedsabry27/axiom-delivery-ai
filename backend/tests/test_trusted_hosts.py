from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.security.trusted_hosts import HealthAwareTrustedHostMiddleware


def _protected_app() -> FastAPI:
    app = FastAPI()

    @app.get("/health")
    def health():
        return {"status": "healthy"}

    @app.get("/ready")
    def ready():
        return {"status": "ready"}

    @app.get("/private")
    def private():
        return {"status": "ok"}

    app.add_middleware(
        HealthAwareTrustedHostMiddleware,
        allowed_hosts=["api.example.com"],
    )
    return app


def test_load_balancer_health_checks_accept_private_ip_host_header():
    client = TestClient(_protected_app())

    assert client.get("/health", headers={"host": "10.0.1.25:8000"}).status_code == 200
    assert client.get("/ready", headers={"host": "10.0.1.25:8000"}).status_code == 200


def test_non_health_routes_still_require_a_trusted_host():
    client = TestClient(_protected_app())

    rejected = client.get("/private", headers={"host": "10.0.1.25:8000"})
    accepted = client.get("/private", headers={"host": "api.example.com"})

    assert rejected.status_code == 400
    assert accepted.status_code == 200
