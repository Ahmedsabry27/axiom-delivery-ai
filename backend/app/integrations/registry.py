from __future__ import annotations

from app.integrations.base import EnterpriseConnector
from app.integrations.errors import IntegrationError


class ConnectorRegistry:
    def __init__(self):
        self._connectors: dict[str, EnterpriseConnector] = {}

    def register(self, connector: EnterpriseConnector) -> None:
        self._connectors[connector.connector_type] = connector

    def get(self, connector_type: str) -> EnterpriseConnector:
        connector = self._connectors.get(connector_type)
        if not connector:
            raise IntegrationError(
                "CAPABILITY_UNAVAILABLE", "This connector is not implemented", 422
            )
        return connector

    def implemented(self) -> set[str]:
        return set(self._connectors)


connector_registry = ConnectorRegistry()


def register_builtin_connectors() -> None:
    from app.integrations.jira import JiraConnector
    from app.integrations.simulation import SimulatedConnector

    connector_registry.register(JiraConnector())
    for connector_type in ("confluence", "outlook_calendar", "microsoft_teams"):
        connector_registry.register(SimulatedConnector(connector_type))


register_builtin_connectors()
