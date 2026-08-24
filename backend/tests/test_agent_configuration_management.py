import pytest

from app.agents.default_agent import DefaultAgent
from app.agents.registry import AgentRegistry
from app.agents.services.agent_configuration_manager import (
    AgentConfigurationManager,
)


@pytest.fixture
def manager():

    registry = AgentRegistry()

    registry.register(DefaultAgent())

    return AgentConfigurationManager(registry)


def test_agent_configuration_defaults(
    manager,
):

    config = manager.get_configuration("default-agent")

    assert config.enabled is True


def test_disable_agent(
    manager,
):

    manager.disable_agent("default-agent")

    assert manager.is_enabled("default-agent") is False


def test_enable_agent(
    manager,
):

    manager.disable_agent("default-agent")

    manager.enable_agent("default-agent")

    assert manager.is_enabled("default-agent") is True


def test_update_agent_configuration(
    manager,
):

    config = manager.update_configuration(
        "default-agent",
        timeout_seconds=60,
        max_concurrency=5,
    )

    assert config.timeout_seconds == 60

    assert config.max_concurrency == 5


def test_invalid_configuration_update(
    manager,
):

    with pytest.raises(ValueError):
        manager.update_configuration(
            "default-agent",
            unknown_property=True,
        )
