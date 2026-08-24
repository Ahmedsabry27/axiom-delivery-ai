from types import SimpleNamespace

import pytest

from app.integrations.errors import IntegrationError
from app.integrations.jira import CAPABILITIES
from app.integrations.registry import connector_registry
from app.integrations.secrets import SecretProvider
from app.integrations.simulation import PROFILES, SimulatedConnector, records


def test_connector_pack_is_registered_and_demo_counts_are_deterministic():
    assert {
        "jira",
        "confluence",
        "outlook_calendar",
        "microsoft_teams",
    } <= connector_registry.implemented()
    for connector_type, profile in PROFILES.items():
        expected = sum(count for _, _, count in profile["entities"])
        first = records(connector_type)
        assert len(first) == expected
        assert [
            (row["external_entity_id"], row["content_fingerprint"]) for row in first
        ] == [
            (row["external_entity_id"], row["content_fingerprint"])
            for row in records(connector_type)
        ]
        assert all(
            row["source_url"].startswith("https://example.invalid/") for row in first
        )


def test_test_secret_provider_contains_no_token_value():
    assert SecretProvider().resolve("simulator://oauth/tenant") == {"simulator": True}


@pytest.mark.asyncio
async def test_simulated_outbound_action_always_fails_closed():
    connector = SimulatedConnector("confluence")
    connection = SimpleNamespace(configuration={"simulator": True})
    with pytest.raises(IntegrationError) as error:
        await connector.execute_action(
            connection, "confluence.propose.update", {"entity_id": "1"}, {}
        )
    assert error.value.code == "APPROVAL_REQUIRED"


def test_every_jira_outbound_capability_requires_approval():
    actions = [item for item in CAPABILITIES if item.capability_type == "action"]
    assert actions
    assert all(item.approval_required for item in actions)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "connector_type", ["confluence", "outlook_calendar", "microsoft_teams"]
)
async def test_schema_discovery_is_read_only_plus_approval_controlled_proposal(
    connector_type,
):
    connector = SimulatedConnector(connector_type)
    connection = SimpleNamespace(configuration={"simulator": True})
    definitions, metadata = await connector.discover_capabilities(connection, {})
    assert metadata == {"schema_version": "sim-1", "mode": "SIMULATOR"}
    assert any(item.capability_type == "tool" for item in definitions)
    assert all(
        item.approval_required
        for item in definitions
        if item.capability_type == "action"
    )
