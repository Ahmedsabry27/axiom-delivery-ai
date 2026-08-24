from __future__ import annotations

from time import perf_counter

from app.contracts.tool import Tool
from app.contracts.tool_models import (
    ExecutionContext,
    RiskLevel,
    ToolMetadata,
    ToolResult,
)
from app.database.models.integration import (
    IntegrationCapability,
    IntegrationConnection,
    IntegrationUsage,
)
from app.database.models.tool import ToolDefinition
from app.integrations.errors import IntegrationError
from app.integrations.registry import connector_registry
from app.integrations.secrets import secret_provider

RUNTIME_PERMISSIONS = {
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


class IntegrationTool(Tool):
    def __init__(
        self, connection: IntegrationConnection, capability: IntegrationCapability
    ):
        self.connection_id = connection.id
        self.capability_type = capability.capability_type
        self.connection_health = connection.health_status
        self.metadata = ToolMetadata(
            name=capability.external_name,
            display_name=capability.display_name,
            description=capability.description,
            category="integration",
            provider=connection.connector_type,
            version=capability.version,
            tags=(
                "integration",
                capability.capability_type,
                connection.connector_type,
                connection.id,
            ),
            parameters=capability.input_schema,
            output_schema=capability.output_schema,
            permissions=(
                RUNTIME_PERMISSIONS.get(
                    capability.external_name,
                    f"integrations.{connection.connector_type}.execute",
                ),
            ),
            risk_level=RiskLevel.WRITE
            if capability.capability_type == "action"
            else RiskLevel.READ,
            idempotent=capability.capability_type == "tool",
        )

    async def health(self) -> dict:
        healthy = self.connection_health == "healthy"
        return {
            "ready": healthy,
            "status": self.connection_health,
            "message": "Integration connection is healthy"
            if healthy
            else "Integration connection is not healthy",
        }

    async def execute(self, input_data: dict, context: ExecutionContext) -> ToolResult:
        db = context.db_session
        connection = (
            db.query(IntegrationConnection)
            .filter_by(id=self.connection_id, tenant_id=context.tenant_id, enabled=True)
            .first()
        )
        capability = (
            db.query(IntegrationCapability)
            .filter_by(
                connection_id=self.connection_id,
                tenant_id=context.tenant_id,
                external_name=self.metadata.name,
                enabled=True,
                provisioned=True,
            )
            .first()
        )
        if not connection or not capability:
            return ToolResult.failed(
                "CAPABILITY_UNAVAILABLE", "The integration capability is disabled"
            )
        started = perf_counter()
        connector = connector_registry.get(connection.connector_type)
        try:
            secret = secret_provider.resolve(connection.secret_ref)
            result = await (
                connector.execute_action(
                    connection, capability.external_name, input_data, secret
                )
                if capability.capability_type == "action"
                else connector.execute_tool(
                    connection, capability.external_name, input_data, secret
                )
            )
            db.add(
                IntegrationUsage(
                    connection_id=connection.id,
                    tenant_id=context.tenant_id,
                    capability_name=capability.external_name,
                    capability_type=capability.capability_type,
                    agent_id=context.agent_id,
                    actor_id=context.actor_id,
                    status="succeeded",
                    latency_ms=(perf_counter() - started) * 1000,
                )
            )
            db.commit()
            return ToolResult.succeeded(result)
        except IntegrationError as exc:
            db.add(
                IntegrationUsage(
                    connection_id=connection.id,
                    tenant_id=context.tenant_id,
                    capability_name=capability.external_name,
                    capability_type=capability.capability_type,
                    agent_id=context.agent_id,
                    actor_id=context.actor_id,
                    status="failed",
                    latency_ms=(perf_counter() - started) * 1000,
                    error_code=exc.code,
                )
            )
            db.commit()
            return ToolResult.failed(exc.code, exc.safe_message)


def register_capability(connection, capability, registry) -> None:
    registry.unregister(capability.external_name, capability.version)
    registry.register(IntegrationTool(connection, capability))
    registry.set_enabled(
        capability.external_name, capability.version, capability.enabled
    )


def load_integration_tools(db, registry) -> int:
    rows = (
        db.query(IntegrationCapability, IntegrationConnection)
        .join(
            IntegrationConnection,
            IntegrationConnection.id == IntegrationCapability.connection_id,
        )
        .filter(
            IntegrationCapability.enabled.is_(True),
            IntegrationCapability.provisioned.is_(True),
            IntegrationConnection.enabled.is_(True),
        )
        .all()
    )
    # Keep persisted capability contracts aligned with connector code so existing
    # connections receive backwards-compatible schema additions after deploys.
    from app.integrations.jira import CAPABILITIES as JIRA_CAPABILITIES

    current = {item.name: item for item in JIRA_CAPABILITIES}
    for capability, connection in rows:
        definition = (
            current.get(capability.external_name)
            if connection.connector_type == "jira"
            else None
        )
        if definition is not None:
            capability.input_schema = definition.input_schema
            capability.output_schema = definition.output_schema
            catalog = (
                db.query(ToolDefinition)
                .filter_by(
                    tenant_id=connection.tenant_id,
                    name=capability.external_name,
                    version=capability.version,
                    integration_connection_id=connection.id,
                )
                .first()
            )
            if catalog is not None:
                catalog.input_schema = definition.input_schema
                catalog.output_schema = definition.output_schema
        register_capability(connection, capability, registry)
    db.commit()
    return len(rows)
