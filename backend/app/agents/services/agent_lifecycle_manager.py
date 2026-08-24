from __future__ import annotations

from datetime import UTC, datetime

from app.agents.models.agent import AgentStatus
from app.agents.registry import AgentRegistry
from app.events.agent_events import (
    AgentExecutionFailed,
    AgentReady,
    AgentRegistered,
    AgentStarted,
    AgentStopped,
)
from app.runtime.event_bus import EventBus


class AgentLifecycleManager:
    """
    Centralized agent lifecycle controller.

    Responsibilities:

    - Register agents
    - Initialize agents
    - Start agents
    - Stop agents
    - Restart agents
    - Monitor readiness
    - Publish lifecycle events
    """

    def __init__(
        self,
        registry: AgentRegistry,
        event_bus: EventBus | None = None,
    ) -> None:

        self._registry = registry

        self._event_bus = event_bus if event_bus is not None else EventBus()

    async def register_agent(
        self,
        agent,
    ) -> None:
        """
        Register agent and publish event.
        """

        self._registry.register(agent)

        await self._event_bus.publish(
            AgentRegistered(
                agent_name=agent.name,
                timestamp=datetime.now(UTC),
            )
        )

    async def initialize_agent(
        self,
        agent_name: str,
    ) -> None:
        """
        Initialize single agent.

        Lifecycle:

        CREATED
            |
        AgentStarted
            |
        initialize()
            |
        READY
            |
        AgentReady
        """

        agent = self._registry.get(agent_name)

        if agent is None:
            raise ValueError(f"Agent '{agent_name}' not found.")

        try:
            await self._event_bus.publish(
                AgentStarted(
                    agent_name=agent_name,
                    timestamp=datetime.now(UTC),
                )
            )

            await agent.initialize()

            await self._event_bus.publish(
                AgentReady(
                    agent_name=agent_name,
                    timestamp=datetime.now(UTC),
                )
            )

        except Exception as ex:
            await self._event_bus.publish(
                AgentExecutionFailed(
                    agent_name=agent_name,
                    execution_id="lifecycle",
                    task_name="initialize",
                    error=str(ex),
                    timestamp=datetime.now(UTC),
                )
            )

            raise

    async def initialize_all(
        self,
    ) -> None:
        """
        Initialize all registered agents.
        """

        for agent_name in self._registry.agent_names():
            await self.initialize_agent(agent_name)

    async def stop_agent(
        self,
        agent_name: str,
    ) -> None:
        """
        Stop single agent.

        READY
          |
        shutdown()
          |
        STOPPED
          |
        AgentStopped
        """

        agent = self._registry.get(agent_name)

        if agent is None:
            raise ValueError(f"Agent '{agent_name}' not found.")

        await agent.shutdown()

        await self._event_bus.publish(
            AgentStopped(
                agent_name=agent_name,
                timestamp=datetime.now(UTC),
            )
        )

    async def stop_all(
        self,
    ) -> None:
        """
        Stop all agents.
        """

        for agent_name in self._registry.agent_names():
            await self.stop_agent(agent_name)

    async def restart_agent(
        self,
        agent_name: str,
    ) -> None:
        """
        Restart agent.

        STOPPED
            |
        initialize()
            |
        READY
        """

        await self.stop_agent(agent_name)

        await self.initialize_agent(agent_name)

    async def health_check(
        self,
        agent_name: str,
    ):
        """
        Get health status.
        """

        agent = self._registry.get(agent_name)

        if agent is None:
            raise ValueError(f"Agent '{agent_name}' not found.")

        return await agent.health_check()

    async def health_check_all(
        self,
    ):
        """
        Get health of all agents.
        """

        return await self._registry.health_check_all()

    def is_ready(
        self,
        agent_name: str,
    ) -> bool:
        """
        Check if agent is ready.
        """

        definition = self._registry.get_definition(agent_name)

        if definition is None:
            return False

        return definition.status == AgentStatus.READY
