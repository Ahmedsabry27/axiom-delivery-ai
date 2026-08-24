from __future__ import annotations

from sqlalchemy.orm import Session

from app.database.models.agent import Agent


class AgentRepository:
    """
    Persistence layer for agents.

    Responsibilities:
    - Register agents
    - Retrieve agents
    - Update agent status
    - Update agent health
    - List agents
    """

    def __init__(
        self,
        db: Session,
    ) -> None:

        self._db = db

    def register_agent(
        self,
        name: str,
        status: str = "AVAILABLE",
        health: str = "HEALTHY",
    ) -> Agent:
        """
        Register an agent in persistence storage.
        """

        agent = Agent(
            name=name,
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
        """
        Retrieve agent by id.
        """

        return self._db.get(
            Agent,
            agent_id,
        )

    def get_agent_by_name(
        self,
        name: str,
    ) -> Agent | None:
        """
        Retrieve agent by name.
        """

        return self._db.query(Agent).filter(Agent.name == name).first()

    def list_agents(
        self,
    ) -> list[Agent]:
        """
        Return all persisted agents.
        """

        return self._db.query(Agent).all()

    def update_status(
        self,
        agent_id: int,
        status: str,
    ) -> Agent | None:
        """
        Update agent runtime status.
        """

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
        """
        Update agent health state.
        """

        agent = self.get_agent(agent_id)

        if agent is None:
            return None

        agent.health = health

        self._db.commit()

        self._db.refresh(agent)

        return agent
