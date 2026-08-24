from app.agents.default_agent import DefaultAgent
from app.agents.registry import AgentRegistry


def test_register_agent():

    registry = AgentRegistry()

    agent = DefaultAgent()

    registry.register(agent)

    registered = registry.get(agent.name)

    assert registered is agent


def test_get_unknown_agent():

    registry = AgentRegistry()

    result = registry.get("unknown-agent")

    assert result is None


def test_duplicate_agent_registration():

    registry = AgentRegistry()

    agent = DefaultAgent()

    registry.register(agent)

    try:
        registry.register(agent)

        raise AssertionError()

    except ValueError as ex:
        assert "already registered" in str(ex)
