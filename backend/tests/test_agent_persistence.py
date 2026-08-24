from app.agents.services.agent_repository import AgentRepository


def test_register_agent(
    db_session,
):

    repository = AgentRepository(db_session)

    agent = repository.register_agent(
        name="planner-agent",
    )

    assert agent.id is not None

    assert agent.name == "planner-agent"

    assert agent.status == "AVAILABLE"

    assert agent.health == "HEALTHY"


def test_update_status(
    db_session,
):

    repository = AgentRepository(db_session)

    agent = repository.register_agent(
        "planner-agent",
    )

    updated = repository.update_status(
        agent.id,
        "BUSY",
    )

    assert updated.status == "BUSY"


def test_update_health(
    db_session,
):

    repository = AgentRepository(db_session)

    agent = repository.register_agent(
        "planner-agent",
    )

    updated = repository.update_health(
        agent.id,
        "UNHEALTHY",
    )

    assert updated.health == "UNHEALTHY"
