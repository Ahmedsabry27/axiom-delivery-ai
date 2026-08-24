from __future__ import annotations

from app.actions.contracts.action import Action


class ActionRegistry:
    """
    Enterprise Action Registry.

    Responsibilities:

    - Register actions
    - Retrieve actions
    - Discover actions
    - Search actions
    """

    def __init__(self):

        self._actions: dict[str, Action] = {}

    def register(
        self,
        action: Action,
    ) -> None:
        """
        Register executable action.
        """

        if action.name in self._actions:
            raise ValueError(f"Action '{action.name}' already exists.")

        self._actions[action.name] = action

    def get(
        self,
        action_name: str,
    ) -> Action | None:
        """
        Retrieve action by name.
        """

        return self._actions.get(action_name)

    def list_actions(
        self,
    ) -> list[str]:
        """
        List registered actions.
        """

        return list(self._actions.keys())

    def find_by_category(
        self,
        category: str,
    ) -> list[Action]:
        """
        Find actions by category.
        """

        return [
            action
            for action in self._actions.values()
            if action.definition.category == category
        ]

    def find_by_permission(
        self,
        permission: str,
    ) -> list[Action]:
        """
        Find actions requiring permission.
        """

        return [
            action
            for action in self._actions.values()
            if permission in action.definition.required_permissions
        ]

    def find_by_agent(
        self,
        agent_name: str,
    ) -> list[Action]:
        """
        Find actions supported by agent.
        """

        return [
            action
            for action in self._actions.values()
            if agent_name in action.definition.supported_agents
        ]

    def search(
        self,
        category: str | None = None,
        permission: str | None = None,
        agent: str | None = None,
    ) -> list[Action]:
        """
        Unified action discovery.
        """

        results = {}

        if category:
            for action in self.find_by_category(category):
                results[action.name] = action

        if permission:
            for action in self.find_by_permission(permission):
                results[action.name] = action

        if agent:
            for action in self.find_by_agent(agent):
                results[action.name] = action

        return list(results.values())
