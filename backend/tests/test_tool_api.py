from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.tools import router
from app.auth.dependencies import get_current_user
from app.database.base import Base
from app.database.dependencies import get_db

engine = create_engine(
    "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
)
Session = sessionmaker(bind=engine)


def db_override():
    db = Session()
    try:
        yield db
    finally:
        db.close()


def admin():
    return {
        "sub": "admin-1",
        "cognito:groups": ["admin"],
        "custom:tenant_id": "default",
    }


app = FastAPI()
app.include_router(router)
app.dependency_overrides[get_db] = db_override
app.dependency_overrides[get_current_user] = admin
client = TestClient(app)


def setup_module():
    Base.metadata.create_all(engine)


def teardown_module():
    Base.metadata.drop_all(engine)


def test_catalog_detail_filters_and_openapi():
    response = client.get("/api/v1/tools", params={"provider": "servicenow"})
    assert response.status_code == 200
    assert response.json()["total"] == 4
    detail = client.get("/api/v1/tools/servicenow_incident_search")
    assert detail.status_code == 200
    assert detail.json()["parameters"]["additionalProperties"] is False
    assert "/api/v1/tools/{name}/execute" in app.openapi()["paths"]


def test_execute_validation_and_history():
    bad = client.post("/api/v1/tools/file_read/execute", json={"input": {}})
    assert bad.status_code == 422
    assert bad.json()["detail"]["code"] == "INVALID_TOOL_INPUT"
    failed = client.post(
        "/api/v1/tools/file_read/execute",
        json={"input": {"file_id": "00000000-0000-0000-0000-000000000000"}},
    )
    assert failed.status_code == 200
    assert failed.json()["status"] == "failed"
    history = client.get("/api/v1/tool-executions")
    assert history.status_code == 200
    assert history.json()["total"] >= 1


def test_integration_secret_is_write_only_and_verify():
    saved = client.put(
        "/api/v1/integrations/servicenow",
        json={
            "display_name": "ServiceNow",
            "base_url": "https://company.service-now.com",
            "auth_method": "oauth2_client_credentials",
            "secret_reference": "vault://servicenow/client",
            "enabled": True,
        },
    )
    assert saved.status_code == 200
    assert "secret_reference" not in saved.json()
    assert saved.json()["credential_configured"] is True
    listed = client.get("/api/v1/integrations").json()
    assert "secret_reference" not in next(
        x for x in listed if x["provider"] == "servicenow"
    )


def test_disable_prevents_execution():
    assert (
        client.patch(
            "/api/v1/tools/file_read/1.0.0/enabled", params={"enabled": False}
        ).status_code
        == 200
    )
    response = client.post(
        "/api/v1/tools/file_read/execute", json={"input": {"path": "a.txt"}}
    )
    assert response.status_code == 409
    client.patch("/api/v1/tools/file_read/1.0.0/enabled", params={"enabled": True})
