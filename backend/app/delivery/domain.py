from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from enum import StrEnum
from typing import Any


class DeliveryHealth(StrEnum):
    GREEN = "GREEN"
    AMBER = "AMBER"
    RED = "RED"
    UNKNOWN = "UNKNOWN"


class DeliveryStatus(StrEnum):
    PLANNED = "PLANNED"
    ACTIVE = "ACTIVE"
    AT_RISK = "AT_RISK"
    BLOCKED = "BLOCKED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    ON_HOLD = "ON_HOLD"


class RAIDType(StrEnum):
    RISK = "RISK"
    ASSUMPTION = "ASSUMPTION"
    ISSUE = "ISSUE"
    DEPENDENCY = "DEPENDENCY"
    DECISION = "DECISION"
    ACTION = "ACTION"


class Impact(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class Probability(StrEnum):
    RARE = "RARE"
    UNLIKELY = "UNLIKELY"
    POSSIBLE = "POSSIBLE"
    LIKELY = "LIKELY"
    ALMOST_CERTAIN = "ALMOST_CERTAIN"


class SourceSystem(StrEnum):
    MANUAL = "MANUAL"
    JIRA = "JIRA"
    AZURE_DEVOPS = "AZURE_DEVOPS"
    SERVICENOW = "SERVICENOW"
    SHAREPOINT = "SHAREPOINT"
    TEAMS = "TEAMS"
    IMPORT = "IMPORT"


@dataclass(slots=True, kw_only=True)
class DeliveryEntity:
    id: str
    tenant_id: str
    name: str
    description: str = ""
    status: DeliveryStatus = DeliveryStatus.PLANNED
    external_id: str | None = None
    source_system: SourceSystem = SourceSystem.MANUAL
    source_url: str | None = None
    owner_id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    created_by: str | None = None
    updated_by: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True, kw_only=True)
class Portfolio(DeliveryEntity):
    health: DeliveryHealth = DeliveryHealth.UNKNOWN


@dataclass(slots=True, kw_only=True)
class Programme(DeliveryEntity):
    portfolio_id: str
    sponsor_id: str | None = None
    delivery_owner_id: str | None = None
    health: DeliveryHealth = DeliveryHealth.UNKNOWN
    start_date: date | None = None
    target_end_date: date | None = None


@dataclass(slots=True, kw_only=True)
class Project(DeliveryEntity):
    programme_id: str
    project_manager_id: str | None = None
    health: DeliveryHealth = DeliveryHealth.UNKNOWN
    start_date: date | None = None
    target_end_date: date | None = None


@dataclass(slots=True, kw_only=True)
class Team(DeliveryEntity):
    project_id: str
    team_lead_id: str | None = None
    delivery_methodology: str | None = None
    capacity: float | None = None
    active: bool = True


@dataclass(slots=True, kw_only=True)
class Sprint(DeliveryEntity):
    project_id: str
    team_id: str
    goal: str = ""
    start_date: date | None = None
    end_date: date | None = None
    committed_points: float | None = None
    completed_points: float | None = None


@dataclass(slots=True, kw_only=True)
class WorkItem(DeliveryEntity):
    project_id: str
    sprint_id: str | None = None
    parent_id: str | None = None
    item_kind: str = "WORK_ITEM"
    priority: str | None = None
    story_points: float | None = None
    assignee_id: str | None = None
    blocked: bool = False
    blocked_since: datetime | None = None


@dataclass(slots=True, kw_only=True)
class Defect(DeliveryEntity):
    project_id: str
    sprint_id: str | None = None
    release_id: str | None = None
    work_item_id: str | None = None
    severity: str | None = None
    priority: str | None = None
    environment: str | None = None
    escaped: bool = False


@dataclass(slots=True, kw_only=True)
class Release(DeliveryEntity):
    project_id: str
    planned_date: date | None = None
    actual_date: date | None = None
    health: DeliveryHealth = DeliveryHealth.UNKNOWN
    readiness_score: float | None = None
    decision_status: str | None = None


@dataclass(slots=True, kw_only=True)
class RAIDItem(DeliveryEntity):
    project_id: str
    item_type: RAIDType
    sprint_id: str | None = None
    release_id: str | None = None
    milestone_id: str | None = None
    programme_id: str | None = None
    team_id: str | None = None
    work_item_id: str | None = None
    defect_id: str | None = None
    dependency_id: str | None = None
    reference: str | None = None
    impact: Impact | None = None
    probability: Probability | None = None
    score: float | None = None
    exposure_band: str = "UNKNOWN"
    residual_probability: Probability | None = None
    residual_impact: Impact | None = None
    residual_score: float | None = None
    residual_exposure_band: str = "UNKNOWN"
    attention_score: float | None = None
    attention_reasons: list[str] = field(default_factory=list)
    priority: str | None = None
    due_date: date | None = None
    identified_at: datetime | None = None
    closed_at: datetime | None = None
    review_date: date | None = None
    last_reviewed_at: datetime | None = None
    closure_reason: str | None = None
    mitigation_plan: str | None = None
    contingency_plan: str | None = None
    validation_owner_id: str | None = None
    validation_due_date: date | None = None
    severity: Impact | None = None
    resolution_plan: str | None = None
    critical_path: bool = False
    decision_owner_id: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True, kw_only=True)
class Milestone(DeliveryEntity):
    project_id: str
    release_id: str | None = None
    planned_date: date | None = None
    actual_date: date | None = None
    critical: bool = False


@dataclass(slots=True, kw_only=True)
class EvidenceReference:
    id: str
    tenant_id: str
    source_type: str
    source_system: SourceSystem
    source_record_id: str
    title: str
    source_url: str | None = None
    summary: str | None = None
    captured_at: datetime | None = None
    source_updated_at: datetime | None = None
    content_hash: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


ENTITY_TYPES = (
    Portfolio,
    Programme,
    Project,
    Team,
    Sprint,
    WorkItem,
    Defect,
    Release,
    RAIDItem,
    Milestone,
    EvidenceReference,
)


def contract_metadata() -> dict[str, Any]:
    return {
        "entity_types": [entity.__name__ for entity in ENTITY_TYPES],
        "delivery_health": [value.value for value in DeliveryHealth],
        "delivery_status": [value.value for value in DeliveryStatus],
        "raid_types": [value.value for value in RAIDType],
        "impact": [value.value for value in Impact],
        "probability": [value.value for value in Probability],
        "source_systems": [value.value for value in SourceSystem],
    }


def to_dict(value: Any) -> dict[str, Any]:
    return asdict(value)
