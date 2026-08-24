from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.agents.application_service import AgentApplicationService, AgentIdentity
from app.api.agents_v1 import AgentCreate
from app.database.models.agent import AgentActivityEvent, AgentVersion


def identity(actor: str, tenant: str, *permissions: str) -> AgentIdentity:
    return AgentIdentity(actor, tenant, frozenset(permissions), frozenset())


def payload(name: str = "Deployment Analyst") -> dict:
    return {
        "name": name,
        "description": "Produces governed deployment analysis",
        "instructions": "Use only approved deployment evidence.",
        "model_configuration": {"provider": "openai", "model": "configured-model"},
        "planner_configuration": {"strategy": "default"},
        "memory_configuration": {"enabled": False},
        "execution_limits": {
            "max_steps": 8,
            "timeout_seconds": 45,
            "risk_limit": "read",
        },
        "tool_discovery_configuration": {"mode": "assigned_only"},
        "capabilities": ["deployment-report"],
        "change_note": "Initial governed draft",
    }


def test_create_is_tenant_scoped_versioned_and_audited(db_session):
    service = AgentApplicationService()
    actor = identity(
        "owner-1", "tenant-a", "agents.create", "agents.list", "agents.read"
    )
    row = service.create(db_session, actor, payload())

    assert row.tenant_id == "tenant-a"
    assert row.owner_id == "owner-1"
    assert row.lifecycle_status == "draft"
    assert row.operational_health == "unknown"
    assert len(row.uuid) == 36
    version = db_session.query(AgentVersion).filter_by(agent_id=row.id).one()
    assert version.instructions == "Use only approved deployment evidence."
    assert (
        version.configuration_snapshot["model_configuration"]["model"]
        == "configured-model"
    )
    assert (
        db_session.query(AgentActivityEvent)
        .filter_by(agent_id=row.id, event_type="agent.created")
        .count()
        == 1
    )


def test_list_and_detail_do_not_cross_tenant_boundary(db_session):
    service = AgentApplicationService()
    admin_a = identity("a", "tenant-a", "agents.create", "agents.list", "agents.read")
    admin_b = identity("b", "tenant-b", "agents.create", "agents.list", "agents.read")
    row_a = service.create(db_session, admin_a, payload("Agent A"))
    service.create(db_session, admin_b, payload("Agent B"))

    rows, total = service.list_agents(
        db_session,
        admin_a,
        search=None,
        status=None,
        owner=None,
        page=1,
        page_size=20,
        include_archived=False,
    )
    assert total == 1
    assert [row.uuid for row in rows] == [row_a.uuid]
    with pytest.raises(HTTPException) as exc:
        service.get(db_session, admin_b, row_a.uuid)
    assert exc.value.status_code == 404


def test_update_requires_owner_or_permission_and_optimistic_lock(db_session):
    service = AgentApplicationService()
    owner = identity("owner", "tenant", "agents.create", "agents.read")
    stranger = identity("stranger", "tenant", "agents.read")
    row = service.create(db_session, owner, payload())

    with pytest.raises(HTTPException) as denied:
        service.update(db_session, stranger, row.uuid, {"description": "no"}, 1)
    assert denied.value.status_code == 403
    updated = service.update(
        db_session,
        owner,
        row.uuid,
        {"instructions": "Published rules win.", "change_note": "Instruction update"},
        1,
    )
    assert updated.current_version == 2
    assert updated.lock_version == 2
    with pytest.raises(HTTPException) as conflict:
        service.update(db_session, owner, row.uuid, {"description": "stale"}, 1)
    assert conflict.value.status_code == 409


def test_runtime_resolution_uses_published_persisted_version_and_fails_closed(
    db_session,
):
    service = AgentApplicationService()
    actor = identity(
        "owner", "tenant", "agents.create", "agents.read", "agents.execute"
    )
    row = service.create(db_session, actor, payload())
    with pytest.raises(HTTPException) as disabled:
        service.resolve_runtime(db_session, actor, row.uuid)
    assert disabled.value.status_code == 409

    row.lifecycle_status = "enabled"
    row.published_version = 1
    row.published_at = datetime.now(UTC)
    version = db_session.query(AgentVersion).filter_by(agent_id=row.id, version=1).one()
    version.published = True
    db_session.commit()

    runtime = service.resolve_runtime(db_session, actor, row.uuid)
    assert (
        runtime.metadata.metadata["instructions"]
        == "Use only approved deployment evidence."
    )
    assert (
        runtime.metadata.metadata["model_configuration"]["model"] == "configured-model"
    )
    assert runtime.configuration.timeout_seconds == 45
    assert runtime.configuration.metadata["agent_version"] == 1


def test_unknown_fields_and_instruction_bounds_are_rejected():
    with pytest.raises(ValidationError):
        AgentCreate(name="Valid name", unexpected=True)
    with pytest.raises(ValidationError):
        AgentCreate(name="Valid name", instructions="x" * 50001)


def test_explicit_permission_is_required(db_session):
    service = AgentApplicationService()
    with pytest.raises(HTTPException) as denied:
        service.create(db_session, identity("user", "tenant"), payload())
    assert denied.value.status_code == 403
