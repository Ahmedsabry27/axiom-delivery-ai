from __future__ import annotations

from app.database.models.action import Action
from app.database.models.agent import Agent
from app.database.models.agent_assignment import AgentToolAssignment
from app.database.models.integration import (
    IntegrationAgentAssignment,
    IntegrationCapability,
    IntegrationConnection,
)
from app.database.models.tool import ToolDefinition
from app.database.models.tool_discovery import ToolMarketplaceProfile
from app.integrations.runtime import register_capability

PERMISSIONS = {
    "jira.get_projects": "jira.project.read",
    "jira.search_issues": "jira.issue.read",
    "jira.get_issue": "jira.issue.read",
    "jira.get_create_metadata": "jira.issue.read",
    "jira.get_transitions": "jira.issue.read",
    "jira.create_issue": "jira.issue.create",
    "jira.update_issue": "jira.issue.update",
    "jira.add_comment": "jira.issue.comment",
    "jira.assign_issue": "jira.issue.assign",
    "jira.transition_issue": "jira.issue.transition",
}


def provision_capability(
    db,
    connection: IntegrationConnection,
    capability: IntegrationCapability,
    actor_id: str,
    registry,
) -> None:
    capability.enabled = True
    capability.provisioned = True
    permission = PERMISSIONS.get(
        capability.external_name, f"{connection.connector_type}.execute"
    )
    if capability.capability_type == "tool":
        tool = (
            db.query(ToolDefinition)
            .filter_by(
                tenant_id=connection.tenant_id,
                name=capability.external_name,
                version=capability.version,
                integration_connection_id=connection.id,
            )
            .first()
        )
        if not tool:
            tool = ToolDefinition(
                tenant_id=connection.tenant_id,
                name=capability.external_name,
                version=capability.version,
                integration_connection_id=connection.id,
                display_name=capability.display_name,
                description=capability.description,
                category="issue_management",
                provider=connection.connector_type,
                input_schema=capability.input_schema,
                output_schema=capability.output_schema,
                permissions=[permission],
                tags=["integration", connection.connector_type, connection.id],
                risk_level="read",
                registration_source="integration",
                configuration_state="ready",
                created_by=actor_id,
                updated_by=actor_id,
            )
            db.add(tool)
        tool.display_name = capability.display_name
        tool.description = capability.description
        tool.input_schema = capability.input_schema
        tool.output_schema = capability.output_schema
        tool.permissions = [permission]
        tool.enabled = True
        tool.active = True
        tool.configuration_state = (
            "ready" if connection.health_status == "healthy" else "not_configured"
        )
        profile = (
            db.query(ToolMarketplaceProfile)
            .filter_by(
                tenant_id=connection.tenant_id,
                tool_name=capability.external_name,
                tool_version=capability.version,
            )
            .first()
        )
        if not profile:
            profile = ToolMarketplaceProfile(
                tenant_id=connection.tenant_id,
                tool_name=capability.external_name,
                tool_version=capability.version,
                source="integration",
                updated_by=actor_id,
            )
            db.add(profile)
        profile.status = "enabled"
        profile.health_status = connection.health_status
        profile.approval_policy = "required" if capability.approval_required else "none"
        profile.safe_metadata = {
            "integration_connection_id": connection.id,
            "connector_type": connection.connector_type,
        }
    else:
        action = (
            db.query(Action)
            .filter_by(
                tenant_id=connection.tenant_id,
                integration_connection_id=connection.id,
                name=capability.external_name,
            )
            .first()
        )
        if not action:
            action = Action(
                tenant_id=connection.tenant_id,
                integration_connection_id=connection.id,
                name=capability.external_name,
                type="Integration",
                usage=0,
            )
            db.add(action)
        action.display_name = capability.display_name
        action.provider = connection.connector_type
        action.category = "issue_management"
        action.risk_level = capability.risk_level
        action.approval_required = capability.approval_required
        action.permissions = {"required": [permission]}
        action.status = "ENABLED"
    register_capability(connection, capability, registry)


def unprovision_capability(
    db, connection: IntegrationConnection, capability: IntegrationCapability, registry
) -> None:
    capability.enabled = False
    capability.provisioned = False
    tool = (
        db.query(ToolDefinition)
        .filter_by(
            tenant_id=connection.tenant_id,
            name=capability.external_name,
            version=capability.version,
            integration_connection_id=connection.id,
        )
        .first()
    )
    if tool:
        tool.enabled = False
        tool.active = False
        tool.configuration_state = "disabled"
    action = (
        db.query(Action)
        .filter_by(
            tenant_id=connection.tenant_id,
            integration_connection_id=connection.id,
            name=capability.external_name,
        )
        .first()
    )
    if action:
        action.status = "DISABLED"
    profile = (
        db.query(ToolMarketplaceProfile)
        .filter_by(
            tenant_id=connection.tenant_id,
            tool_name=capability.external_name,
            tool_version=capability.version,
        )
        .first()
    )
    if profile:
        profile.status = "disabled"
        profile.health_status = "unhealthy"
    registry.unregister(capability.external_name, capability.version)


def disable_connection_capabilities(
    db, connection: IntegrationConnection, registry
) -> None:
    for capability in (
        db.query(IntegrationCapability)
        .filter_by(connection_id=connection.id, tenant_id=connection.tenant_id)
        .all()
    ):
        if capability.provisioned:
            unprovision_capability(db, connection, capability, registry)


def sync_connection_assignments(
    db, connection: IntegrationConnection, actor_id: str
) -> None:
    capabilities = (
        db.query(IntegrationCapability)
        .filter_by(
            connection_id=connection.id,
            tenant_id=connection.tenant_id,
            enabled=True,
            provisioned=True,
        )
        .all()
    )
    by_name = {item.external_name: item for item in capabilities}
    assignments = (
        db.query(IntegrationAgentAssignment)
        .filter_by(connection_id=connection.id, tenant_id=connection.tenant_id)
        .all()
    )
    for assignment in assignments:
        assignment.capability_names = sorted(by_name)
        agent = (
            db.query(Agent)
            .filter_by(id=assignment.agent_id, tenant_id=connection.tenant_id)
            .first()
        )
        if not agent:
            continue
        for name, capability in by_name.items():
            existing = (
                db.query(AgentToolAssignment)
                .filter_by(
                    agent_id=agent.id,
                    tool_name=name,
                    assignment_action="execute",
                )
                .first()
            )
            if not existing:
                db.add(
                    AgentToolAssignment(
                        agent_id=agent.id,
                        agent_version=agent.current_version,
                        tenant_id=connection.tenant_id,
                        tool_name=name,
                        version_restriction=capability.version,
                        assignment_action="execute",
                        enabled=True,
                        risk_mode="write"
                        if capability.capability_type == "action"
                        else "read",
                        approval_required=capability.approval_required,
                        added_by=actor_id,
                    )
                )
