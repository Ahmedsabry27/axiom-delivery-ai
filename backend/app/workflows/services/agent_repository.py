from __future__ import annotations

from sqlalchemy.orm import Session

from app.database.models.agent import Agent


class AgentRepository:
    """
    Persistence layer for agents.

    Responsibilities:
    - Register agents
    - Retrieve agents
    - Update health
    - Update status
    - List available agents
    """

    def __init__(
        self,
        db: Session,
    ) -> None:

        self._db = db

    def register_agent(
        self,
        name: str,
        agent_type: str,
        status: str = "AVAILABLE",
        health: str = "HEALTHY",
    ) -> Agent:

        agent = Agent(
            name=name,
            agent_type=agent_type,
            status=status,
            health=health,
        )

        self._db.add(agent)
        self._db.commit()
        self._db.refresh(agent)

        return agent

    def get_agent(
        self,
        agent_id: int,
    ) -> Agent | None:

        return self._db.get(
            Agent,
            agent_id,
        )

    def get_agent_by_name(
        self,
        name: str,
    ) -> Agent | None:

        return self._db.query(Agent).filter(Agent.name == name).first()

    def list_agents(
        self,
    ) -> list[Agent]:

        return self._db.query(Agent).all()

    def update_status(
        self,
        agent_id: int,
        status: str,
    ) -> Agent | None:

        agent = self.get_agent(agent_id)

        if agent is None:
            return None

        agent.status = status

        self._db.commit()
        self._db.refresh(agent)

        return agent

    def update_health(
        self,
        agent_id: int,
        health: str,
    ) -> Agent | None:

        agent = self.get_agent(agent_id)

        if agent is None:
            return None

        agent.health = health

        self._db.commit()
        self._db.refresh(agent)

        return agent
