from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class Definition:
    key: str
    category: str
    label: str
    type: str
    scopes: tuple[str, ...]
    default: object
    choices: tuple[object, ...] = ()
    locked: bool = False
    approval_required: bool = False
    effective_dated: bool = False
    description: str = ""


def d(key, category, label, type_, scopes, default, **kw):
    return Definition(key, category, label, type_, tuple(scopes), default, **kw)


DEFINITIONS = [
    d(
        "profile.display_timezone",
        "profile",
        "Display timezone",
        "timezone",
        ["user"],
        "UTC",
    ),
    d(
        "profile.locale",
        "profile",
        "Locale",
        "enum",
        ["user"],
        "en-GB",
        choices=("en-GB", "en-US", "fr-FR", "ar-EG"),
    ),
    d(
        "preferences.landing_page",
        "preferences",
        "Default landing page",
        "enum",
        ["user"],
        "/command-center",
        choices=("/command-center", "/my-day", "/portfolio", "/copilot"),
    ),
    d(
        "preferences.week_start",
        "preferences",
        "Week starts",
        "enum",
        ["user"],
        "Monday",
        choices=("Monday", "Sunday"),
    ),
    d(
        "preferences.page_size",
        "preferences",
        "Table page size",
        "integer",
        ["user"],
        25,
    ),
    d(
        "preferences.sidebar",
        "preferences",
        "Sidebar state",
        "enum",
        ["user"],
        "expanded",
        choices=("expanded", "collapsed"),
    ),
    d(
        "preferences.chart_period",
        "preferences",
        "Default chart period",
        "enum",
        ["user"],
        "4 weeks",
        choices=("1 week", "4 weeks", "12 weeks"),
    ),
    d(
        "appearance.theme",
        "appearance",
        "Theme",
        "enum",
        ["user"],
        "system",
        choices=("light", "system"),
    ),
    d(
        "appearance.density",
        "appearance",
        "Interface density",
        "enum",
        ["user"],
        "comfortable",
        choices=("compact", "comfortable"),
    ),
    d(
        "appearance.reduced_motion",
        "appearance",
        "Reduced motion",
        "boolean",
        ["user"],
        False,
    ),
    d(
        "appearance.high_contrast",
        "appearance",
        "High contrast",
        "boolean",
        ["user"],
        False,
    ),
    d("appearance.font_scale", "appearance", "Font scale", "decimal", ["user"], 1.0),
    d(
        "notifications.assigned_actions",
        "notifications",
        "Assigned actions",
        "enum",
        ["user"],
        "Immediate",
        choices=("Immediate", "Daily digest", "Weekly digest", "In-app only"),
    ),
    d(
        "notifications.approval_requests",
        "notifications",
        "Approval requests",
        "enum",
        ["user"],
        "Immediate",
        choices=("Immediate", "Daily digest", "In-app only"),
        locked=True,
    ),
    d(
        "notifications.model_incident",
        "notifications",
        "Model incident",
        "enum",
        ["user"],
        "Immediate",
        choices=("Immediate", "In-app only"),
        locked=True,
    ),
    d(
        "notifications.weekly_briefing",
        "notifications",
        "Weekly executive briefing",
        "enum",
        ["user"],
        "Weekly digest",
        choices=("Weekly digest", "In-app only", "Disabled"),
    ),
    d(
        "notifications.quiet_timezone",
        "notifications",
        "Quiet-hours timezone",
        "timezone",
        ["user"],
        "UTC",
    ),
    d(
        "workspace.display_name",
        "workspace",
        "Workspace display name",
        "string",
        ["tenant"],
        "Axiom Workspace",
    ),
    d(
        "workspace.primary_timezone",
        "workspace",
        "Primary timezone",
        "timezone",
        ["tenant"],
        "UTC",
    ),
    d(
        "workspace.locale",
        "workspace",
        "Default locale",
        "enum",
        ["tenant"],
        "en-GB",
        choices=("en-GB", "en-US"),
    ),
    d(
        "workspace.base_currency",
        "workspace",
        "Base currency",
        "enum",
        ["tenant"],
        "GBP",
        choices=("GBP", "USD", "EUR"),
        approval_required=True,
    ),
    d(
        "workspace.environment",
        "workspace",
        "Environment",
        "string",
        [],
        "Managed by deployment",
        locked=True,
    ),
    d(
        "delivery.sprint_length_days",
        "delivery",
        "Sprint length",
        "integer",
        ["tenant"],
        14,
    ),
    d(
        "delivery.estimation_unit",
        "delivery",
        "Estimation unit",
        "enum",
        ["tenant"],
        "Story points",
        choices=("Story points", "Hours", "Items"),
    ),
    d(
        "delivery.evidence_fresh_days",
        "delivery",
        "Evidence freshness days",
        "integer",
        ["tenant"],
        7,
        effective_dated=True,
        approval_required=True,
    ),
    d(
        "delivery.blocker_critical_days",
        "delivery",
        "Critical blocker age",
        "integer",
        ["tenant"],
        5,
        effective_dated=True,
        approval_required=True,
    ),
    d(
        "reporting.fiscal_year_start",
        "reporting",
        "Fiscal year start",
        "date",
        ["tenant"],
        "2027-04-01",
        effective_dated=True,
    ),
    d(
        "reporting.cadence",
        "reporting",
        "Reporting cadence",
        "enum",
        ["tenant"],
        "Weekly",
        choices=("Weekly", "Monthly", "Quarterly"),
        effective_dated=True,
    ),
    d("reporting.trend_weeks", "reporting", "Trend period", "integer", ["tenant"], 4),
    d(
        "reporting.percentage_precision",
        "reporting",
        "Percentage precision",
        "integer",
        ["tenant"],
        1,
    ),
    d(
        "ai.response_detail",
        "ai",
        "Response detail",
        "enum",
        ["user"],
        "Detailed",
        choices=("Concise", "Balanced", "Detailed"),
    ),
    d(
        "ai.show_confidence",
        "ai",
        "Show confidence",
        "boolean",
        ["user"],
        True,
        locked=True,
    ),
    d(
        "ai.show_limitations",
        "ai",
        "Show limitations",
        "boolean",
        ["user"],
        True,
        locked=True,
    ),
    d(
        "ai.ask_before_proposal",
        "ai",
        "Ask before draft proposal",
        "boolean",
        ["user"],
        True,
    ),
    d(
        "data.retention_policy",
        "data",
        "Default retention policy",
        "string",
        [],
        "Governance managed",
        locked=True,
    ),
    d(
        "data.audit_retention",
        "data",
        "Audit retention",
        "string",
        [],
        "Protected",
        locked=True,
    ),
    d(
        "features.portfolio",
        "features",
        "Portfolio Intelligence",
        "boolean",
        ["tenant"],
        True,
    ),
    d(
        "features.sprints",
        "features",
        "Sprint Intelligence",
        "boolean",
        ["tenant"],
        True,
    ),
    d("features.raid", "features", "RAID Intelligence", "boolean", ["tenant"], True),
    d(
        "features.dependencies",
        "features",
        "Dependency Intelligence",
        "boolean",
        ["tenant"],
        True,
    ),
    d(
        "features.meetings",
        "features",
        "Meeting Intelligence",
        "boolean",
        ["tenant"],
        True,
    ),
    d(
        "features.agents",
        "features",
        "Agents",
        "boolean",
        ["tenant"],
        True,
        approval_required=True,
    ),
    d(
        "features.workflows",
        "features",
        "Workflows",
        "boolean",
        ["tenant"],
        True,
        approval_required=True,
    ),
]
CATALOG = {item.key: item for item in DEFINITIONS}


def public_definition(item: Definition) -> dict:
    return asdict(item) | {
        "scopes": list(item.scopes),
        "choices": list(item.choices),
        "sensitive": False,
        "deprecated": False,
    }


def validate_value(item: Definition, value: object) -> object:
    if item.locked or not item.scopes:
        raise ValueError("Setting is locked by policy")
    if item.type == "boolean" and type(value) is not bool:
        raise ValueError("Boolean value required")
    if item.type == "integer" and (type(value) is not int or not 1 <= value <= 1000):
        raise ValueError("Integer must be between 1 and 1000")
    if item.type == "decimal":
        value = float(Decimal(str(value)))
        if not 0.8 <= value <= 1.5:
            raise ValueError("Value must be between 0.8 and 1.5")
    if item.type == "enum" and value not in item.choices:
        raise ValueError("Value is not an allowed option")
    if item.type == "string" and (not isinstance(value, str) or len(value) > 255):
        raise ValueError("String value required (maximum 255 characters)")
    if item.type == "timezone":
        if not isinstance(value, str):
            raise ValueError("Timezone required")
        ZoneInfo(value)
    if item.type == "date":
        datetime.fromisoformat(str(value))
    return value
