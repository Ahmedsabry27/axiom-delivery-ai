from __future__ import annotations

from app.agents.models.agent import AgentDefinition
from app.agents.models.capability import AgentCapability
from app.agents.models.metadata import AgentMetadata
from app.agents.services.capability_matcher import (
    CapabilityMatcher,
)


def create_test_agent() -> AgentDefinition:
    """
    Create sample agent definition.
    """

    return AgentDefinition(
        metadata=AgentMetadata(
            name="report-agent",
            description="Report generation agent",
        ),
        capabilities=[
            AgentCapability(
                name="report-generation",
                description=("Generate enterprise reports"),
                category="analytics",
                supported_tasks=[
                    "generate_report",
                    "deployment_report",
                ],
                supported_tools=[
                    "powerbi",
                    "sql",
                ],
            ),
            AgentCapability(
                name="data-analysis",
                description=("Analyze enterprise data"),
                category="analytics",
                supported_tasks=[
                    "analyze_data",
                ],
                supported_tools=[
                    "sql",
                ],
            ),
        ],
    )


def test_capability_full_match():

    matcher = CapabilityMatcher()

    agent = create_test_agent()

    result = matcher.matches(
        agent,
        [
            "report-generation",
        ],
    )

    assert result is True


def test_capability_missing_match():

    matcher = CapabilityMatcher()

    agent = create_test_agent()

    result = matcher.matches(
        agent,
        [
            "video-generation",
        ],
    )

    assert result is False


def test_capability_score_full_match():

    matcher = CapabilityMatcher()

    agent = create_test_agent()

    score = matcher.score(
        agent,
        [
            "report-generation",
        ],
    )

    assert score == 100.0


def test_capability_score_partial_match():

    matcher = CapabilityMatcher()

    agent = create_test_agent()

    score = matcher.score(
        agent,
        [
            "report-generation",
            "video-generation",
        ],
    )

    assert score == 50.0


def test_match_task():

    matcher = CapabilityMatcher()

    agent = create_test_agent()

    result = matcher.match_task(
        agent,
        "deployment_report",
    )

    assert result is True


def test_task_not_supported():

    matcher = CapabilityMatcher()

    agent = create_test_agent()

    result = matcher.match_task(
        agent,
        "image_generation",
    )

    assert result is False


def test_match_tools():

    matcher = CapabilityMatcher()

    agent = create_test_agent()

    result = matcher.match_tools(
        agent,
        [
            "powerbi",
            "sql",
        ],
    )

    assert result is True


def test_missing_tools():

    matcher = CapabilityMatcher()

    agent = create_test_agent()

    result = matcher.match_tools(
        agent,
        [
            "powerbi",
            "kubernetes",
        ],
    )

    assert result is False


def test_calculate_agent_score():

    matcher = CapabilityMatcher()

    agent = create_test_agent()

    score = matcher.calculate_agent_score(
        agent,
        required_capabilities=[
            "report-generation",
        ],
        required_tools=[
            "powerbi",
        ],
    )

    assert score == 100.0
