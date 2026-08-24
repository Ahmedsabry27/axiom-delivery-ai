from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi import HTTPException

from app.agents.application_service import AgentApplicationService, AgentIdentity
from app.database.models.agent import AgentActivityEvent, AgentVersion
from app.database.models.agent_assignment import (
    AgentAccessAssignment,
    AgentKnowledgeAssignment,
    AgentToolAssignment,
)
from app.database.models.knowledge_source import KnowledgeSource
from app.database.models.tool import ToolDefinition
from app.database.models.workflow import Workflow


def admin(tenant: str = "tenant-a") -> AgentIdentity:
    return AgentIdentity(
        "admin-user",
        tenant,
        frozenset(
            {
                "agents.list",
                "agents.read",
                "agents.create",
                "agents.update",
                "agents.publish",
                "agents.enable",
                "agents.disable",
                "agents.archive",
                "agents.restore",
                "agents.execute",
                "agents.tools.manage",
                "agents.knowledge.manage",
                "agents.access.manage",
            }
        ),
        frozenset(),
    )


def valid_agent() -> dict:
    return {
        "name": "Governed Agent",
        "instructions": "Follow approved evidence and tenant policy.",
        "model_configuration": {"provider": "configured", "model": "model-a"},
        "execution_limits": {"max_steps": 5, "timeout_seconds": 30},
        "change_note": "Ready for governance tests",
    }


def test_governed_publish_enable_disable_archive_restore(db_session):
    service = AgentApplicationService()
    actor = admin()
    row = service.create(db_session, actor, valid_agent())

    row = service.publish(db_session, actor, row.uuid, 1, "Approved version 1")
    assert row.lifecycle_status == "published"
    assert row.published_version == 1
    assert (
        db_session.query(AgentVersion).filter_by(agent_id=row.id, published=True).one()
    )

    row = service.lifecycle(db_session, actor, row.uuid, "enable", 2)
    assert row.lifecycle_status == "enabled"
    assert service.resolve_runtime(db_session, actor, row.uuid).metadata.version == "1"

    row = service.lifecycle(db_session, actor, row.uuid, "disable", 3)
    assert row.lifecycle_status == "disabled"
    with pytest.raises(HTTPException) as disabled:
        service.resolve_runtime(db_session, actor, row.uuid)
    assert disabled.value.status_code == 409

    with pytest.raises(HTTPException) as confirmation:
        service.lifecycle(db_session, actor, row.uuid, "archive", 4)
    assert confirmation.value.status_code == 400
    row = service.lifecycle(db_session, actor, row.uuid, "archive", 4, confirmed=True)
    assert row.lifecycle_status == "archived"
    assert row.archived_at is not None
    row = service.lifecycle(db_session, actor, row.uuid, "restore", 5)
    assert row.lifecycle_status == "disabled"
    assert row.archived_at is None
    event_types = {
        item.event_type
        for item in db_session.query(AgentActivityEvent).filter_by(agent_id=row.id)
    }
    assert {
        "agent.published",
        "agent.enabled",
        "agent.disabled",
        "agent.archived",
        "agent.restored",
    } <= event_types


def test_publish_validation_and_illegal_transitions_fail_closed(db_session):
    service = AgentApplicationService()
    actor = admin()
    invalid = service.create(db_session, actor, {"name": "Incomplete Agent"})
    with pytest.raises(HTTPException) as invalid_config:
        service.publish(db_session, actor, invalid.uuid, 1, "")
    assert invalid_config.value.status_code == 422
    with pytest.raises(HTTPException) as illegal:
        service.lifecycle(db_session, actor, invalid.uuid, "enable", 1)
    assert illegal.value.status_code == 409


def test_archive_dependency_check_prevents_orphaning_workflow(db_session):
    service = AgentApplicationService()
    actor = admin()
    row = service.create(db_session, actor, valid_agent())
    db_session.add(
        Workflow(
            goal="Protected workflow",
            status="ACTIVE",
            created_by="admin-user",
            assigned_agent=row.uuid,
        )
    )
    db_session.commit()
    with pytest.raises(HTTPException) as protected:
        service.lifecycle(db_session, actor, row.uuid, "archive", 1, confirmed=True)
    assert protected.value.status_code == 409
    assert protected.value.detail["code"] == "AGENT_HAS_DEPENDENCIES"


def tool(tenant: str = "tenant-a", enabled: bool = True) -> ToolDefinition:
    return ToolDefinition(
        tenant_id=tenant,
        name="deployment_report",
        display_name="Deployment Report",
        description="Creates a safe deployment report",
        category="operations",
        provider="native",
        version="1.0.0",
        input_schema={"type": "object"},
        permissions=[],
        enabled=enabled,
        active=True,
    )


def test_tool_assignments_validate_real_tenant_catalog_and_version(db_session):
    service = AgentApplicationService()
    actor = admin()
    row = service.create(db_session, actor, valid_agent())
    catalog_tool = tool()
    db_session.add(catalog_tool)
    db_session.commit()
    assigned = service.set_tools(
        db_session,
        actor,
        row.uuid,
        [
            {
                "tool_name": "deployment_report",
                "version_restriction": "1.0.0",
                "assignment_action": "execute",
                "enabled": True,
                "risk_mode": "read",
                "approval_required": False,
            }
        ],
    )
    assert assigned[0].tool_name == "deployment_report"
    assert db_session.query(AgentToolAssignment).filter_by(agent_id=row.id).count() == 1
    row = service.publish(
        db_session, actor, row.uuid, row.lock_version, "Tools approved"
    )
    assert (
        db_session.query(AgentToolAssignment)
        .filter_by(agent_id=row.id)
        .one()
        .agent_version
        == 1
    )
    row = service.lifecycle(db_session, actor, row.uuid, "enable", row.lock_version)
    runtime = service.resolve_runtime(db_session, actor, row.uuid)
    assert (
        runtime.metadata.metadata["tool_assignments"][0]["name"] == "deployment_report"
    )
    catalog_tool.enabled = False
    db_session.commit()
    with pytest.raises(HTTPException) as unavailable:
        service.resolve_runtime(db_session, actor, row.uuid)
    assert unavailable.value.detail["code"] == "ASSIGNED_TOOL_UNAVAILABLE"

    other = service.create(db_session, actor, {**valid_agent(), "name": "Other Agent"})
    with pytest.raises(HTTPException) as missing:
        service.set_tools(
            db_session,
            actor,
            other.uuid,
            [
                {
                    "tool_name": "missing_tool",
                    "version_restriction": "active",
                    "assignment_action": "execute",
                    "enabled": True,
                    "risk_mode": "read",
                    "approval_required": False,
                }
            ],
        )
    assert missing.value.status_code == 422


def test_knowledge_assignments_require_tenant_and_readiness(db_session):
    service = AgentApplicationService()
    actor = admin()
    row = service.create(db_session, actor, valid_agent())
    ready = KnowledgeSource(
        tenant_id="tenant-a",
        owner_id="admin-user",
        name="Runbooks",
        source_type="DOCUMENT",
        readiness_status="ready",
        health_status="healthy",
        last_synchronized_at=datetime.now(UTC),
    )
    foreign = KnowledgeSource(
        tenant_id="tenant-b",
        owner_id="foreign",
        name="Foreign",
        source_type="DOCUMENT",
        readiness_status="ready",
    )
    db_session.add_all([ready, foreign])
    db_session.commit()
    assigned = service.set_knowledge(
        db_session,
        actor,
        row.uuid,
        [
            {
                "knowledge_source_id": ready.id,
                "access_mode": "retrieve",
                "readiness_required": True,
                "enabled": True,
            }
        ],
    )
    assert assigned[0].source_type == "DOCUMENT"
    assert (
        db_session.query(AgentKnowledgeAssignment).filter_by(agent_id=row.id).count()
        == 1
    )
    with pytest.raises(HTTPException) as isolated:
        service.set_knowledge(
            db_session,
            actor,
            row.uuid,
            [
                {
                    "knowledge_source_id": foreign.id,
                    "access_mode": "read",
                    "readiness_required": True,
                    "enabled": True,
                }
            ],
        )
    assert isolated.value.status_code == 404


def test_access_assignment_grants_only_the_named_object_action(db_session):
    service = AgentApplicationService()
    actor = admin()
    row = service.create(db_session, actor, valid_agent())
    service.set_access(
        db_session,
        actor,
        row.uuid,
        [
            {
                "subject_type": "user",
                "subject_id": "reader-user",
                "action": "view",
                "enabled": True,
            }
        ],
    )
    reader = AgentIdentity(
        "reader-user", "tenant-a", frozenset({"agents.list"}), frozenset()
    )
    assert service.get(db_session, reader, row.uuid).uuid == row.uuid
    visible, total = service.list_agents(
        db_session,
        reader,
        search=None,
        status=None,
        owner=None,
        page=1,
        page_size=20,
        include_archived=False,
    )
    assert total == 1 and visible[0].uuid == row.uuid
    with pytest.raises(HTTPException) as edit_denied:
        service.update(db_session, reader, row.uuid, {"description": "forbidden"}, 1)
    assert edit_denied.value.status_code == 403
    assert (
        db_session.query(AgentAccessAssignment).filter_by(agent_id=row.id).count() == 1
    )


def test_effective_access_reports_role_grants_and_explicit_deny_precedence(db_session):
    service = AgentApplicationService()
    actor = admin()
    row = service.create(db_session, actor, valid_agent())
    service.set_access(
        db_session,
        actor,
        row.uuid,
        [
            {
                "subject_type": "role",
                "subject_id": "executor",
                "action": "execute",
                "enabled": True,
            },
            {
                "subject_type": "group",
                "subject_id": "restricted",
                "action": "execute",
                "enabled": False,
            },
        ],
    )
    allowed = AgentIdentity(
        "role-user",
        "tenant-a",
        frozenset(),
        frozenset(),
        frozenset({"executor"}),
    )
    preview = service.effective_access(db_session, allowed, row.uuid, "execute")
    assert preview["decision"] == "allow"
    assert preview["reason_codes"] == ["ROLE_GRANT"]
    assert preview["role_grants"]

    denied = AgentIdentity(
        "denied-admin",
        "tenant-a",
        frozenset({"agents.execute"}),
        frozenset({"restricted"}),
        frozenset({"executor"}),
    )
    preview = service.effective_access(db_session, denied, row.uuid, "execute")
    assert preview["decision"] == "deny"
    assert preview["reason_codes"] == ["EXPLICIT_DENY"]
    assert preview["platform_permission"] is True
    assert not service._has_object_access(db_session, row, denied, "execute")
