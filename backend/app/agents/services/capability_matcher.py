from __future__ import annotations

from app.agents.models.agent import AgentDefinition


class CapabilityMatcher:
    """
    Matches agent capabilities against
    task requirements.

    Responsible for:
    - Capability matching
    - Capability scoring
    - Agent suitability evaluation
    """

    def matches(
        self,
        agent: AgentDefinition,
        required_capabilities: list[str],
    ) -> bool:
        """
        Check whether an agent supports
        all required capabilities.

        Example:

        Required:
        [
            "report-generation"
        ]

        Agent:
        [
            "report-generation",
            "task-execution"
        ]

        Result:
            True
        """

        if not required_capabilities:
            return False

        return all(
            agent.has_capability(capability) for capability in required_capabilities
        )

    def score(
        self,
        agent: AgentDefinition,
        required_capabilities: list[str],
    ) -> float:
        """
        Calculate capability match score.

        Score:
        100  -> Full match
        50   -> Partial match
        0    -> No match
        """

        if not required_capabilities:
            return 0.0

        matched = sum(
            1
            for capability in required_capabilities
            if agent.has_capability(capability)
        )

        return round(
            (matched / len(required_capabilities)) * 100,
            2,
        )

    def match_task(
        self,
        agent: AgentDefinition,
        task_name: str,
    ) -> bool:
        """
        Check if agent can execute
        a specific task.

        Uses capability supported_tasks.
        """

        for capability in agent.capabilities:
            if capability.supports_task(task_name):
                return True

        return False

    def match_tools(
        self,
        agent: AgentDefinition,
        required_tools: list[str],
    ) -> bool:
        """
        Check if agent supports
        required tools.
        """

        if not required_tools:
            return True

        supported_tools = []

        for capability in agent.capabilities:
            supported_tools.extend(capability.supported_tools)

        return all(tool in supported_tools for tool in required_tools)

    def calculate_agent_score(
        self,
        agent: AgentDefinition,
        required_capabilities: list[str],
        required_tools: list[str] | None = None,
    ) -> float:
        """
        Calculate final agent suitability score.

        Weighting:

        Capability match: 70%
        Tool match:       30%
        """

        capability_score = self.score(
            agent,
            required_capabilities,
        )

        tool_score = 100.0

        if required_tools:
            tool_score = (
                100.0
                if self.match_tools(
                    agent,
                    required_tools,
                )
                else 0.0
            )

        return round(
            (capability_score * 0.7) + (tool_score * 0.3),
            2,
        )
