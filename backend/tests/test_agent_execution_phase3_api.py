from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.agents.application_service import AgentApplicationService, AgentIdentity
from app.api.agent_executions import agent_router, execution_router
from app.auth.dependencies import get_current_user
from app.database.dependencies import get_db
from app.database.models.agent_execution import AgentExecution
from app.database.models.tool import ToolDefinition


def claims(tenant="tenant-a"):
    return {
        "sub": "api-user",
        "custom:tenant_id": tenant,
        "permissions": [
            "agents.create",
            "agents.read",
            "agents.update",
            "agents.publish",
            "agents.enable",
            "agents.execute",
            "agents.tools.manage",
            "agents.executions.read",
            "deployment.reports.create",
        ],
    }


def client(db, user):
    app = FastAPI()
    app.include_router(agent_router)
    app.include_router(execution_router)

    def database_override():
        yield db

    app.dependency_overrides[get_db] = database_override
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


def enabled(db):
    identity = AgentIdentity.from_claims(claims())
    service = AgentApplicationService()
    row = service.create(
        db,
        identity,
        {
            "name": "API Runtime",
            "instructions": "Use safe API evidence.",
            "model_configuration": {"provider": "configured", "model": "model-a"},
        },
    )
    db.add(
        ToolDefinition(
            tenant_id="tenant-a",
            name="deployment_report",
            display_name="Deployment Report",
            description="Report",
            category="operations",
            provider="native",
            version="1.0.0",
            input_schema={},
            permissions=[],
            enabled=True,
            active=True,
        )
    )
    db.commit()
    service.set_tools(
        db,
        identity,
        row.uuid,
        [
            {
                "tool_name": "deployment_report",
                "version_restriction": "1.0.0",
                "assignment_action": "execute",
                "enabled": True,
                "risk_mode": "write",
                "approval_required": False,
            }
        ],
    )
    row = service.publish(db, identity, row.uuid, row.lock_version, "api")
    return service.lifecycle(db, identity, row.uuid, "enable", row.lock_version)


def test_execute_resume_history_detail_and_cancel_api(db_session):
    row = enabled(db_session)
    api = client(db_session, claims())
    started = api.post(
        f"/api/v1/agents/{row.uuid}/execute",
        json={"message": "Generate a deployment report", "inputs": {}},
    )
    assert started.status_code == 200
    body = started.json()
    assert body["status"] == "waiting_for_input"
    resumed = api.post(
        f"/api/v1/agent-executions/{body['execution_id']}/input",
        json={
            "resume_token": body["continuation"]["resume_token"],
            "response": {
                "project_name": "Copilot",
                "release_version": "3",
                "environment": "production",
                "status": "succeeded",
            },
        },
    )
    assert resumed.status_code == 200 and resumed.json()["status"] == "succeeded"
    assert (
        api.get(f"/api/v1/agents/{row.uuid}/executions").json()["items"][0][
            "agent_version"
        ]
        == 1
    )
    assert (
        api.get(
            f"/api/v1/agents/{row.uuid}/executions/{body['execution_id']}"
        ).status_code
        == 200
    )
    assert (
        api.post(
            f"/api/v1/agents/{row.uuid}/executions/{body['execution_id']}/cancel"
        ).json()["status"]
        == "succeeded"
    )
    assert (
        api.post(
            f"/api/v1/agent-executions/{body['execution_id']}/input",
            json={"resume_token": body["continuation"]["resume_token"], "response": {}},
        ).status_code
        == 409
    )


def test_execution_api_rejects_unknown_fields_and_cross_tenant(db_session):
    row = enabled(db_session)
    assert (
        client(db_session, claims())
        .post(
            f"/api/v1/agents/{row.uuid}/execute", json={"message": "x", "admin": True}
        )
        .status_code
        == 422
    )


def test_execution_filters_and_analytics_are_server_backed(db_session):
    row = enabled(db_session)
    api = client(db_session, claims())
    started = api.post(
        f"/api/v1/agents/{row.uuid}/execute",
        json={
            "message": "Generate a deployment report",
            "inputs": {},
            "environment": "staging",
        },
    ).json()
    execution = db_session.get(AgentExecution, started["execution_id"])
    execution.duration_ms = 125
    execution.token_usage = {"total_tokens": 42}
    execution.estimated_cost = 0.12
    db_session.commit()

    history = api.get(
        f"/api/v1/agents/{row.uuid}/executions",
        params={
            "mode": "production",
            "tool": "deployment_report",
            "version": 1,
            "sort": "duration_ms",
            "direction": "asc",
        },
    )
    assert history.status_code == 200
    assert history.json()["total"] == 1

    analytics = api.get(
        f"/api/v1/agents/{row.uuid}/analytics",
        params={"environment": "staging", "mode": "production", "version": 1},
    )
    assert analytics.status_code == 200
    body = analytics.json()
    assert body["total_executions"] == 1
    assert body["p50_duration_ms"] == 125
    assert body["p95_duration_ms"] == 125
    assert body["total_tokens"] == 42
    assert body["estimated_cost"] == 0.12
    assert body["environment_breakdown"] == [
        {"environment": "staging", "executions": 1}
    ]

    empty = api.get(
        f"/api/v1/agents/{row.uuid}/analytics", params={"status": "succeeded"}
    ).json()
    assert empty["total_executions"] == 0
    assert empty["p50_duration_ms"] is None
    assert (
        client(db_session, claims("tenant-b"))
        .post(f"/api/v1/agents/{row.uuid}/execute", json={"message": "x"})
        .status_code
        == 404
    )
