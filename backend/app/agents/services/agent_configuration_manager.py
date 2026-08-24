from __future__ import annotations

from app.agents.models.configuration import AgentConfiguration
from app.agents.registry import AgentRegistry


class AgentConfigurationManager:
    """
    Runtime configuration manager for agents.

    Responsibilities:

    - Read configuration
    - Update configuration
    - Enable agents
    - Disable agents
    - Validate runtime settings
    """

    def __init__(
        self,
        registry: AgentRegistry,
    ) -> None:

        self._registry = registry

    def get_configuration(
        self,
        agent_name: str,
    ) -> AgentConfiguration:
        """
        Retrieve agent configuration.
        """

        definition = self._registry.get_definition(agent_name)

        if definition is None:
            raise ValueError(f"Agent '{agent_name}' not found.")

        return definition.configuration

    def update_configuration(
        self,
        agent_name: str,
        **updates,
    ) -> AgentConfiguration:
        """
        Update agent runtime configuration.

        Supports:
        - timeout_seconds
        - max_concurrent_tasks
        - max_concurrency (legacy alias)
        - retry_count
        - enabled
        """

        configuration = self.get_configuration(agent_name)

        for key, value in updates.items():
            # backward compatibility
            if key == "max_concurrency":
                key = "max_concurrent_tasks"

            if not hasattr(
                configuration,
                key,
            ):
                raise ValueError(f"Unsupported configuration '{key}'.")

            setattr(
                configuration,
                key,
                value,
            )

        return configuration

    def disable_agent(
        self,
        agent_name: str,
    ) -> None:
        """
        Disable agent execution.
        """

        configuration = self.get_configuration(agent_name)

        configuration.enabled = False

    def enable_agent(
        self,
        agent_name: str,
    ) -> None:
        """
        Enable agent execution.
        """

        configuration = self.get_configuration(agent_name)

        configuration.enabled = True

    def is_enabled(
        self,
        agent_name: str,
    ) -> bool:
        """
        Check whether an agent is enabled.
        """

        configuration = self.get_configuration(agent_name)

        return configuration.enabled
