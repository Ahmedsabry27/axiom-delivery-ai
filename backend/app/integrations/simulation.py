from __future__ import annotations

from datetime import UTC, datetime, timedelta
from hashlib import sha256
from typing import Any

from app.integrations.base import CapabilityDefinition, EnterpriseConnector
from app.integrations.errors import IntegrationError

PROFILES: dict[str, dict[str, Any]] = {
    "jira": {
        "provider": "atlassian",
        "entities": [
            ("project", "Project", 8),
            ("sprint", "Sprint", 9),
            ("issue", "Work Item", 54),
        ],
        "quarantine": 1,
    },
    "confluence": {
        "provider": "atlassian",
        "entities": [("space", "Knowledge Source", 3), ("page", "Evidence", 24)],
        "quarantine": 0,
    },
    "outlook_calendar": {
        "provider": "microsoft",
        "entities": [
            ("calendar", "Calendar", 2),
            ("event", "Meeting", 9),
            ("series", "Meeting Series", 3),
        ],
        "quarantine": 0,
    },
    "microsoft_teams": {
        "provider": "microsoft",
        "entities": [
            ("meeting", "Meeting", 8),
            ("transcript", "Meeting Evidence", 6),
            ("review_item", "Review Item", 12),
        ],
        "quarantine": 1,
    },
}


def records(connector_type: str) -> list[dict]:
    profile = PROFILES[connector_type]
    result = []
    now = datetime.now(UTC).replace(microsecond=0)
    for entity, canonical, count in profile["entities"]:
        for number in range(1, count + 1):
            external_id = (
                f"{connector_type[:3].upper()}-{entity[:3].upper()}-{number:03d}"
            )
            title = f"{entity.replace('_', ' ').title()} {number}"
            payload = {
                "status": "active",
                "owner": f"Delivery owner {number % 7 + 1}",
                "simulated": True,
            }
            result.append(
                {
                    "external_entity_type": entity,
                    "external_entity_id": external_id,
                    "canonical_entity_type": canonical,
                    "canonical_entity_id": f"AX-{external_id}",
                    "source_version": "1",
                    "source_updated_at": now - timedelta(hours=number),
                    "title": title,
                    "source_url": f"https://example.invalid/{connector_type}/{external_id}",
                    "classification": "INTERNAL",
                    "safe_payload": payload,
                    "content_fingerprint": sha256(
                        f"{external_id}:1:{title}".encode()
                    ).hexdigest(),
                }
            )
    return result


class SimulatedConnector(EnterpriseConnector):
    def __init__(self, connector_type: str):
        self.connector_type = connector_type

    def validate_configuration(self, connection, secret: dict) -> None:
        if not connection.configuration.get("simulator", False):
            raise IntegrationError(
                "LIVE_CONFIGURATION_REQUIRED",
                "Live provider authorization is not configured",
                422,
            )

    async def test_connection(self, connection, secret: dict) -> dict:
        self.validate_configuration(connection, secret)
        return {
            "healthy": True,
            "mode": "SIMULATOR",
            "provider": PROFILES[self.connector_type]["provider"],
            "credential_values": "hidden",
        }

    async def discover_capabilities(self, connection, secret: dict):
        self.validate_configuration(connection, secret)
        reads = [
            CapabilityDefinition(
                f"{self.connector_type}.read.{item[0]}",
                f"Read {item[0]}",
                "Read authorized records",
                "tool",
                {"type": "object"},
                {"type": "object"},
            )
            for item in PROFILES[self.connector_type]["entities"]
        ]
        writes = [
            CapabilityDefinition(
                f"{self.connector_type}.propose.update",
                "Propose update",
                "Approval-controlled provider update",
                "action",
                {"type": "object", "required": ["entity_id", "changes"]},
                {"type": "object"},
                "high",
                True,
            )
        ]
        return reads + writes, {"schema_version": "sim-1", "mode": "SIMULATOR"}

    async def execute_tool(
        self, connection, capability: str, arguments: dict, secret: dict
    ):
        self.validate_configuration(connection, secret)
        return {"items": records(self.connector_type)[:10], "simulated": True}

    async def execute_action(
        self, connection, capability: str, arguments: dict, secret: dict
    ):
        raise IntegrationError(
            "APPROVAL_REQUIRED",
            "Outbound provider operations require an approved Action Center execution",
            409,
        )
