from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from enum import StrEnum


class DeliveryIntent(StrEnum):
    DELIVERY_HEALTH = "delivery.health"
    DELIVERY_CHANGE = "delivery.change_analysis"
    SPRINT_HEALTH = "sprint.health"
    SPRINT_FORECAST = "sprint.forecast"
    RELEASE_RISK = "release.risk"
    RELEASE_READINESS = "release.readiness"
    RAID_SEARCH = "raid.search"
    DEPENDENCY_ANALYSIS = "dependency.analysis"
    ACTION_SEARCH = "action.search"
    DECISION_SEARCH = "decision.search"
    REPORT_GENERATE = "report.generate"
    RECOMMENDATION_GENERATE = "recommendation.generate"
    PROPOSED_ACTION_GENERATE = "proposed_action.generate"
    GENERAL = "general.delivery_question"


@dataclass(frozen=True, slots=True)
class IntentRoute:
    intent: DeliveryIntent
    requires_retrieval: bool = True
    structured_output: bool = True
    approval_required: bool = False
    clarification_required: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


def classify_delivery_intent(message: str) -> IntentRoute:
    text = " ".join(message.lower().split())
    if any(
        word in text for word in ("draft ", "prepare a follow-up", "create a proposed")
    ):
        return IntentRoute(
            DeliveryIntent.PROPOSED_ACTION_GENERATE, approval_required=True
        )
    if "steering" in text or "weekly" in text or "executive summary" in text:
        return IntentRoute(DeliveryIntent.REPORT_GENERATE)
    if "recommend" in text or "should i escalate" in text:
        return IntentRoute(DeliveryIntent.RECOMMENDATION_GENERATE)
    if "release" in text and any(
        word in text for word in ("threat", "risk", "confidence")
    ):
        return IntentRoute(DeliveryIntent.RELEASE_RISK)
    if "release" in text or "go-live" in text:
        return IntentRoute(DeliveryIntent.RELEASE_READINESS)
    if "sprint" in text and any(
        word in text for word in ("likely", "forecast", "meet its goal")
    ):
        return IntentRoute(DeliveryIntent.SPRINT_FORECAST)
    if "sprint" in text:
        return IntentRoute(DeliveryIntent.SPRINT_HEALTH)
    if "dependenc" in text or "blocked by" in text:
        return IntentRoute(DeliveryIntent.DEPENDENCY_ANALYSIS)
    if any(word in text for word in ("risk", "raid", "issue", "mitigation")):
        return IntentRoute(DeliveryIntent.RAID_SEARCH)
    if "decision" in text:
        return IntentRoute(DeliveryIntent.DECISION_SEARCH)
    if "action" in text:
        return IntentRoute(DeliveryIntent.ACTION_SEARCH)
    if "changed" in text or "since last" in text:
        return IntentRoute(DeliveryIntent.DELIVERY_CHANGE)
    if "health" in text or "focus" in text:
        return IntentRoute(DeliveryIntent.DELIVERY_HEALTH)
    return IntentRoute(DeliveryIntent.GENERAL)


def mentioned_entity(message: str) -> dict | None:
    match = re.search(
        r"\b(release|sprint|project|programme)\s+([\w-]+)", message, re.IGNORECASE
    )
    return (
        {
            "type": match.group(1).title(),
            "name": f"{match.group(1).title()} {match.group(2)}",
        }
        if match
        else None
    )


def validate_confidence(value: int, evidence_count: int) -> int:
    if not 0 <= value <= 100:
        raise ValueError("Confidence must be between 0 and 100")
    if evidence_count == 0:
        return 0
    return min(value, 95)
