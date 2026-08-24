from __future__ import annotations

from dataclasses import dataclass

from app.contracts.agent import Agent


@dataclass
class AgentMatch:
    """
    Represents an agent routing decision.
    """

    agent: Agent

    score: float

    matched_capabilities: list[str]

    matched_tools: list[str]

    reason: str
