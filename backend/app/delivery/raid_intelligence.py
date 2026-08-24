from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from difflib import SequenceMatcher
from typing import Any

RAID_TYPES = {"RISK", "ASSUMPTION", "ISSUE", "DEPENDENCY", "DECISION", "ACTION"}
PROBABILITY_VALUES = {
    "RARE": 1,
    "UNLIKELY": 2,
    "POSSIBLE": 3,
    "LIKELY": 4,
    "ALMOST_CERTAIN": 5,
}
IMPACT_VALUES = {
    "LOW": 1,
    "MINOR": 2,
    "MODERATE": 3,
    "MEDIUM": 3,
    "HIGH": 4,
    "CRITICAL": 5,
}
TERMINAL_STATUSES = {
    "RISK": {"CLOSED"},
    "ASSUMPTION": {"VALIDATED", "INVALIDATED", "CLOSED"},
    "ISSUE": {"RESOLVED", "CLOSED"},
    "DEPENDENCY": {"RESOLVED", "CLOSED"},
    "DECISION": {"REJECTED", "SUPERSEDED", "IMPLEMENTED"},
    "ACTION": {"COMPLETED", "CANCELLED"},
}

STATUS_TRANSITIONS: dict[str, dict[str, set[str]]] = {
    "RISK": {
        "IDENTIFIED": {"ASSESSED", "CLOSED"},
        "ASSESSED": {"OPEN", "CLOSED"},
        "OPEN": {"MITIGATING", "ESCALATED", "REALIZED", "CLOSED"},
        "MITIGATING": {"OPEN", "ESCALATED", "REALIZED", "CLOSED"},
        "ESCALATED": {"OPEN", "MITIGATING", "REALIZED", "CLOSED"},
        "REALIZED": {"CLOSED"},
    },
    "ASSUMPTION": {
        "IDENTIFIED": {"VALIDATING", "CLOSED"},
        "VALIDATING": {"VALIDATED", "INVALIDATED", "EXPIRED", "CLOSED"},
        "VALIDATED": {"CLOSED"},
        "INVALIDATED": {"CLOSED"},
        "EXPIRED": {"VALIDATING", "CLOSED"},
    },
    "ISSUE": {
        "OPEN": {"INVESTIGATING", "RESOLVING", "ESCALATED"},
        "INVESTIGATING": {"RESOLVING", "ESCALATED", "RESOLVED"},
        "RESOLVING": {"ESCALATED", "RESOLVED"},
        "ESCALATED": {"RESOLVING", "RESOLVED"},
        "RESOLVED": {"CLOSED", "OPEN"},
    },
    "DEPENDENCY": {
        "IDENTIFIED": {"ACKNOWLEDGED", "CLOSED"},
        "ACKNOWLEDGED": {"IN_PROGRESS", "BLOCKED", "AT_RISK"},
        "IN_PROGRESS": {"BLOCKED", "AT_RISK", "RESOLVED"},
        "BLOCKED": {"IN_PROGRESS", "AT_RISK", "RESOLVED"},
        "AT_RISK": {"IN_PROGRESS", "BLOCKED", "RESOLVED"},
        "RESOLVED": {"CLOSED", "IN_PROGRESS"},
    },
    "DECISION": {
        "PROPOSED": {"UNDER_REVIEW", "DEFERRED"},
        "UNDER_REVIEW": {"PENDING", "APPROVED", "REJECTED", "DEFERRED"},
        "PENDING": {"APPROVED", "REJECTED", "DEFERRED"},
        "APPROVED": {"IMPLEMENTED", "SUPERSEDED"},
        "DEFERRED": {"UNDER_REVIEW", "SUPERSEDED"},
    },
    "ACTION": {
        "OPEN": {"IN_PROGRESS", "BLOCKED", "OVERDUE", "CANCELLED"},
        "IN_PROGRESS": {"BLOCKED", "OVERDUE", "COMPLETED", "CANCELLED"},
        "BLOCKED": {"IN_PROGRESS", "OVERDUE", "CANCELLED"},
        "OVERDUE": {"IN_PROGRESS", "BLOCKED", "COMPLETED", "CANCELLED"},
    },
}

INITIAL_STATUS = {
    "RISK": "IDENTIFIED",
    "ASSUMPTION": "IDENTIFIED",
    "ISSUE": "OPEN",
    "DEPENDENCY": "IDENTIFIED",
    "DECISION": "PROPOSED",
    "ACTION": "OPEN",
}


class RAIDValidationError(ValueError):
    pass


@dataclass(frozen=True)
class ScoreResult:
    value: int | None
    band: str
    reasons: tuple[str, ...] = ()


def exposure(probability: str | None, impact: str | None) -> ScoreResult:
    if not probability or not impact:
        return ScoreResult(None, "UNKNOWN", ("Probability or impact is missing",))
    probability_value = PROBABILITY_VALUES.get(probability.upper())
    impact_value = IMPACT_VALUES.get(impact.upper())
    if probability_value is None or impact_value is None:
        return ScoreResult(
            None, "INSUFFICIENT_DATA", ("Probability or impact is invalid",)
        )
    value = probability_value * impact_value
    band = (
        "LOW"
        if value <= 4
        else "MEDIUM"
        if value <= 9
        else "HIGH"
        if value <= 16
        else "CRITICAL"
    )
    return ScoreResult(
        value,
        band,
        (
            f"{probability.upper()} ({probability_value}) × {impact.upper()} ({impact_value})",
        ),
    )


def attention(
    item: Any, *, today: date | None = None, evidence_stale: bool = False
) -> ScoreResult:
    today = today or datetime.now(UTC).date()
    reasons: list[str] = []
    value = 0

    def add(points: int, reason: str) -> None:
        nonlocal value
        value += points
        reasons.append(f"{reason} +{points}")

    band = getattr(item, "residual_exposure_band", None) or getattr(
        item, "exposure_band", None
    )
    if band == "CRITICAL":
        add(40, "Critical exposure")
    elif band == "HIGH":
        add(25, "High exposure")
    due = getattr(item, "due_date", None) or getattr(item, "validation_due_date", None)
    if (
        due
        and due < today
        and getattr(item, "status", "")
        not in TERMINAL_STATUSES.get(getattr(item, "item_type", ""), set())
    ):
        add(25, "Overdue")
    elif due and due <= today + timedelta(days=2):
        add(10, "Due within two days")
    if getattr(item, "critical_path", False):
        add(20, "Critical-path dependency")
    if getattr(item, "severity", "") == "CRITICAL":
        add(20, "Critical issue severity")
    if (
        not getattr(item, "owner_id", None)
        and not getattr(item, "validation_owner_id", None)
        and not getattr(item, "decision_owner_id", None)
    ):
        add(15, "Missing owner")
    if getattr(item, "item_type", "") == "RISK" and not getattr(
        item, "mitigation_plan", None
    ):
        add(15, "Missing mitigation")
    if getattr(item, "item_type", "") == "ISSUE" and not getattr(
        item, "resolution_plan", None
    ):
        add(15, "Missing resolution plan")
    review_date = getattr(item, "review_date", None)
    if review_date and review_date < today:
        add(10, "Stale review date")
    identified = getattr(item, "identified_at", None)
    if identified and (today - identified.date()).days > 30:
        add(10, "Aging beyond 30 days")
    if evidence_stale:
        add(5, "Evidence outdated")
    if getattr(item, "escalated", False) or getattr(item, "status", "") == "ESCALATED":
        add(5, "Escalated")
    return ScoreResult(
        min(value, 100),
        "CRITICAL"
        if value >= 70
        else "HIGH"
        if value >= 45
        else "MEDIUM"
        if value >= 20
        else "LOW",
        tuple(reasons),
    )


def validate_required_fields(values: dict[str, Any]) -> None:
    item_type = str(values.get("item_type", "")).upper()
    if item_type not in RAID_TYPES:
        raise RAIDValidationError("Unsupported RAID type")
    required: dict[str, tuple[str, ...]] = {
        "RISK": ("name", "description", "probability", "impact", "review_date"),
        "ASSUMPTION": (
            "name",
            "description",
            "validation_owner_id",
            "validation_due_date",
        ),
        "ISSUE": ("name", "description", "severity", "owner_id"),
        "DEPENDENCY": ("name", "description", "owner_id", "due_date"),
        "DECISION": ("name", "description", "decision_owner_id", "due_date"),
        "ACTION": ("name", "description", "owner_id", "due_date"),
    }
    missing = [
        field for field in required[item_type] if values.get(field) in (None, "")
    ]
    if missing:
        raise RAIDValidationError(
            f"Missing required fields for {item_type}: {', '.join(missing)}"
        )
    due = values.get("due_date") or values.get("validation_due_date")
    identified = values.get("identified_at")
    if (
        due
        and identified
        and due
        < (identified.date() if isinstance(identified, datetime) else identified)
    ):
        raise RAIDValidationError("Due date cannot precede identified date")


def validate_transition(
    item_type: str,
    current: str,
    target: str,
    *,
    note: str | None = None,
    evidence_count: int = 0,
    completion_evidence_required: bool = False,
) -> None:
    allowed = STATUS_TRANSITIONS.get(item_type, {}).get(current, set())
    if target not in allowed:
        raise RAIDValidationError(
            f"Invalid {item_type} transition: {current} → {target}"
        )
    if target in TERMINAL_STATUSES.get(item_type, set()) and not note:
        raise RAIDValidationError("A closure or resolution note is required")
    if (
        target in {"COMPLETED", "IMPLEMENTED"}
        and completion_evidence_required
        and evidence_count == 0
    ):
        raise RAIDValidationError("Completion evidence is required")


def apply_scores(
    item: Any, *, today: date | None = None, evidence_stale: bool = False
) -> None:
    inherent = exposure(
        getattr(item, "probability", None), getattr(item, "impact", None)
    )
    residual = exposure(
        getattr(item, "residual_probability", None),
        getattr(item, "residual_impact", None),
    )
    item.exposure_score, item.exposure_band = inherent.value, inherent.band
    item.residual_exposure_score, item.residual_exposure_band = (
        residual.value,
        residual.band,
    )
    attention_result = attention(item, today=today, evidence_stale=evidence_stale)
    item.attention_score = attention_result.value
    item.attention_reasons = list(attention_result.reasons)


def hygiene_findings(
    item: Any,
    *,
    evidence_count: int = 0,
    latest_evidence_at: datetime | None = None,
    today: date | None = None,
) -> list[dict[str, Any]]:
    today = today or datetime.now(UTC).date()
    findings: list[dict[str, Any]] = []

    def add(
        kind: str,
        severity: str,
        rule: str,
        observed: Any,
        expected: str,
        correction: str,
    ) -> None:
        findings.append(
            {
                "findingType": kind,
                "severity": severity,
                "record": getattr(item, "id", None),
                "rule": rule,
                "observedValue": observed,
                "expectedValue": expected,
                "recommendedCorrection": correction,
            }
        )

    if (
        not getattr(item, "owner_id", None)
        and not getattr(item, "validation_owner_id", None)
        and not getattr(item, "decision_owner_id", None)
    ):
        add(
            "UNOWNED",
            "HIGH",
            "An active RAID item needs an accountable owner",
            None,
            "owner",
            "Assign an authorized owner",
        )
    if not getattr(item, "due_date", None) and getattr(item, "item_type", "") in {
        "DEPENDENCY",
        "DECISION",
        "ACTION",
    }:
        add(
            "MISSING_DUE_DATE",
            "MEDIUM",
            "Time-bound items need a due date",
            None,
            "due date",
            "Set a realistic due date",
        )
    if getattr(item, "item_type", "") == "RISK" and not getattr(
        item, "review_date", None
    ):
        add(
            "MISSING_REVIEW_DATE",
            "MEDIUM",
            "Open risks need a review date",
            None,
            "review date",
            "Schedule a risk review",
        )
    if getattr(item, "item_type", "") == "RISK" and not getattr(
        item, "mitigation_plan", None
    ):
        add(
            "MISSING_MITIGATION",
            "HIGH",
            "Open risks need mitigation",
            None,
            "mitigation plan",
            "Add a mitigation plan",
        )
    if getattr(item, "item_type", "") == "ISSUE" and not getattr(
        item, "resolution_plan", None
    ):
        add(
            "MISSING_RESOLUTION_PLAN",
            "HIGH",
            "Issues need a resolution plan",
            None,
            "resolution plan",
            "Add a resolution plan",
        )
    if evidence_count == 0:
        add(
            "MISSING_EVIDENCE",
            "MEDIUM",
            "Material assertions need evidence",
            0,
            "at least one evidence link",
            "Link authorized persisted evidence",
        )
    if latest_evidence_at and datetime.now(UTC) - _aware(
        latest_evidence_at
    ) > timedelta(days=30):
        add(
            "STALE_EVIDENCE",
            "LOW",
            "Evidence should be refreshed within 30 days",
            latest_evidence_at.isoformat(),
            "fresh evidence",
            "Review and refresh evidence",
        )
    due = getattr(item, "due_date", None) or getattr(item, "validation_due_date", None)
    if (
        due
        and due < today
        and getattr(item, "status", "")
        not in TERMINAL_STATUSES.get(getattr(item, "item_type", ""), set())
    ):
        add(
            "OVERDUE",
            "HIGH",
            "Active record has passed its due date",
            due.isoformat(),
            f"date on or after {today.isoformat()}",
            "Review status, owner, and due date",
        )
    if getattr(item, "closed_at", None) and not getattr(item, "closure_reason", None):
        add(
            "CLOSURE_WITHOUT_RATIONALE",
            "HIGH",
            "Closure requires rationale",
            None,
            "closure rationale",
            "Record the resolution or closure rationale",
        )
    return findings


def duplicate_similarity(
    candidate: dict[str, Any], item: Any
) -> tuple[float, list[str]]:
    candidate_title = _normalize(candidate.get("title", ""))
    item_title = _normalize(getattr(item, "name", ""))
    title_score = SequenceMatcher(None, candidate_title, item_title).ratio()
    reasons: list[str] = []
    score = title_score * 0.65
    if title_score >= 0.75:
        reasons.append("Similar normalized title")
    if candidate.get("owner_id") and candidate.get("owner_id") == getattr(
        item, "owner_id", None
    ):
        score += 0.1
        reasons.append("Same owner")
    if candidate.get("due_date") and candidate.get("due_date") == getattr(
        item, "due_date", None
    ):
        score += 0.1
        reasons.append("Same due date")
    if candidate.get("project_id") and candidate.get("project_id") == getattr(
        item, "project_id", None
    ):
        score += 0.15
        reasons.append("Same project")
    return min(score, 1.0), reasons


def _normalize(value: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", value.lower()).split())


def _aware(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value
