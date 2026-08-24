from __future__ import annotations

from app.agents.models.agent import (
    AgentDefinition,
    AgentHealth,
    AgentStatus,
)
from app.agents.services.capability_matcher import (
    CapabilityMatcher,
)
from app.contracts.agent import Agent


class AgentRegistry:
    """
    Enterprise agent registry.

    Responsibilities:
    - Register agents
    - Discover agents
    - Search agents
    - Match capabilities
    - Route tasks to agents
    - Manage lifecycle
    - Monitor health
    """

    def __init__(self) -> None:

        self._agents: dict[str, Agent] = {}

        self._definitions: dict[
            str,
            AgentDefinition,
        ] = {}

        self._matcher = CapabilityMatcher()

    # ---------------------------------------------------------
    # Registration
    # ---------------------------------------------------------

    def register(
        self,
        agent: Agent,
    ) -> None:
        """
        Register an agent.
        """

        if agent.name in self._agents:
            raise ValueError(f"Agent '{agent.name}' already registered.")

        self._agents[agent.name] = agent

        self._definitions[agent.name] = agent.definition

    def get(
        self,
        agent_name: str,
    ) -> Agent | None:
        """
        Retrieve agent by name.
        """

        return self._agents.get(agent_name)

    def list_agents(
        self,
    ) -> list[str]:
        """
        Return all registered agent names.

        Used by lifecycle manager.
        """

        return list(self._agents.keys())

    def is_registered(
        self,
        agent_name: str,
    ) -> bool:
        """
        Check if agent exists.
        """

        return agent_name in self._agents

    # ---------------------------------------------------------
    # Definitions & Status
    # ---------------------------------------------------------

    def get_definition(
        self,
        agent_name: str,
    ) -> AgentDefinition | None:
        """
        Retrieve agent definition.
        """

        return self._definitions.get(agent_name)

    def get_status(
        self,
        agent_name: str,
    ) -> AgentStatus | None:
        """
        Retrieve lifecycle status.
        """

        definition = self.get_definition(agent_name)

        if definition is None:
            return None

        return definition.status

    def get_all_definitions(
        self,
    ) -> dict[str, AgentDefinition]:
        """
        Return all agent definitions.

        Used for monitoring and dashboards.
        """

        return self._definitions.copy()

    # ---------------------------------------------------------
    # Capability Discovery
    # ---------------------------------------------------------

    def find_by_capability(
        self,
        capability_name: str,
    ) -> list[Agent]:

        return [
            agent
            for name, agent in self._agents.items()
            if self._definitions[name].has_capability(capability_name)
        ]

    def find_matching_agents(
        self,
        required_capabilities: list[str],
    ) -> list[Agent]:

        return [
            agent
            for name, agent in self._agents.items()
            if self._matcher.matches(
                self._definitions[name],
                required_capabilities,
            )
        ]

    def find_by_task(
        self,
        task_name: str,
    ) -> list[Agent]:

        matched = []

        for name, agent in self._agents.items():
            definition = self._definitions[name]

            for capability in definition.capabilities:
                if task_name in capability.supported_tasks:
                    matched.append(agent)

                    break

        return matched

    def find_by_tool(
        self,
        tool_name: str,
    ) -> list[Agent]:

        matched = []

        for name, agent in self._agents.items():
            definition = self._definitions[name]

            for capability in definition.capabilities:
                if tool_name in capability.supported_tools:
                    matched.append(agent)

                    break

        return matched

    def search(
        self,
        capability: str | None = None,
        task: str | None = None,
        tool: str | None = None,
    ) -> list[Agent]:
        """
        Unified agent discovery.
        """

        results: dict[str, Agent] = {}

        if capability:
            for agent in self.find_by_capability(capability):
                results[agent.name] = agent

        if task:
            for agent in self.find_by_task(task):
                results[agent.name] = agent

        if tool:
            for agent in self.find_by_tool(tool):
                results[agent.name] = agent

        return list(results.values())

    # ---------------------------------------------------------
    # Dynamic Routing
    # ---------------------------------------------------------

    def select_agent(
        self,
        required_capabilities: list[str],
    ) -> Agent:
        """
        Select best available agent.
        """

        candidates = []

        for name, agent in self._agents.items():
            definition = self._definitions[name]

            if definition.status not in [
                AgentStatus.READY,
                AgentStatus.CREATED,
                AgentStatus.INITIALIZED,
            ]:
                continue

            score = self._matcher.score(
                definition,
                required_capabilities,
            )

            if score > 0:
                candidates.append(
                    (
                        score,
                        agent,
                    )
                )

        if not candidates:
            raise ValueError("No agent found matching required capabilities.")

        candidates.sort(
            key=lambda item: item[0],
            reverse=True,
        )

        return candidates[0][1]

    # ---------------------------------------------------------
    # Lifecycle
    # ---------------------------------------------------------

    async def initialize_all(
        self,
    ) -> None:

        for agent in self._agents.values():
            await agent.initialize()

    async def shutdown_all(
        self,
    ) -> None:

        for agent in self._agents.values():
            await agent.shutdown()

    async def restart_agent(
        self,
        agent_name: str,
    ) -> None:
        """
        Restart an agent lifecycle.
        """

        agent = self.get(agent_name)

        if agent is None:
            raise ValueError(f"Agent '{agent_name}' not found.")

        await agent.shutdown()

        await agent.initialize()

    # ---------------------------------------------------------
    # Monitoring
    # ---------------------------------------------------------

    async def health_check_all(
        self,
    ) -> dict[str, AgentHealth]:

        health = {}

        for name, agent in self._agents.items():
            health[name] = await agent.health_check()

        return health

    def available_agents(
        self,
    ) -> list[Agent]:
        """
        Return READY agents only.
        """

        return [
            agent
            for name, agent in self._agents.items()
            if self._definitions[name].status == AgentStatus.READY
        ]


def agent_names(
    self,
) -> list[str]:
    """
    Return all registered agent names.
    """

    return list(self._agents.keys())
