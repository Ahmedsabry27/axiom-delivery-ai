from app.agents.models.configuration import (
    AgentConfiguration,
)


def test_agent_configuration_defaults():

    config = AgentConfiguration()

    assert config.enabled is True

    assert config.timeout_seconds == 60

    assert config.max_concurrent_tasks == 5

    assert config.retry_count == 0


def test_agent_configuration_custom_values():

    config = AgentConfiguration(
        enabled=False,
        timeout_seconds=120,
        max_concurrent_tasks=10,
        retry_count=3,
        metadata={"environment": "production"},
    )

    assert config.enabled is False

    assert config.timeout_seconds == 120

    assert config.max_concurrent_tasks == 10

    assert config.retry_count == 3

    assert config.metadata["environment"] == "production"
