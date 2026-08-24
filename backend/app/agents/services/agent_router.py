from __future__ import annotations

from app.agents.models.routing import AgentMatch
from app.contracts.agent import Agent


class AgentRouter:
    """
    Selects the best agent based on requirements.
    """

    def route(
        self,
        agents: list[Agent],
        required_capabilities: list[str],
        required_tools: list[str] | None = None,
    ) -> AgentMatch | None:
        """
        Find best matching agent.
        """

        required_tools = required_tools or []

        matches: list[AgentMatch] = []

        for agent in agents:
            definition = agent.definition

            matched_capabilities = [
                capability.name
                for capability in definition.capabilities
                if capability.name in required_capabilities
            ]

            matched_tools = []

            for capability in definition.capabilities:
                for tool in capability.supported_tools:
                    if tool in required_tools:
                        matched_tools.append(tool)

            capability_score = (
                len(matched_capabilities) / len(required_capabilities)
                if required_capabilities
                else 0
            )

            tool_score = (
                len(matched_tools) / len(required_tools) if required_tools else 0
            )

            score = capability_score * 0.7 + tool_score * 0.3

            if score > 0:
                matches.append(
                    AgentMatch(
                        agent=agent,
                        score=round(
                            score,
                            2,
                        ),
                        matched_capabilities=matched_capabilities,
                        matched_tools=matched_tools,
                        reason=("Capability and tool match"),
                    )
                )

        if not matches:
            return None

        return max(
            matches,
            key=lambda match: match.score,
        )
