from __future__ import annotations

from datetime import UTC, datetime, time
from numbers import Real

from app.database.models.tool import ToolExecution
from app.database.models.tool_discovery import (
    ToolAssignment,
    ToolGovernancePolicy,
    ToolMarketplaceProfile,
)
from app.tool_discovery.schemas import PolicyDecision

FIELD_TYPES = {
    "user": "string",
    "role": "string",
    "group": "string",
    "agent": "string",
    "tenant": "string",
    "tool": "string",
    "tool_version": "string",
    "category": "string",
    "source": "string",
    "provider": "string",
    "action": "string",
    "environment": "string",
    "risk": "string",
    "data_classification": "string",
    "time": "datetime",
    "cost": "number",
    "execution_count": "number",
    "health": "string",
}
OPERATORS = {
    "equals",
    "not_equals",
    "in",
    "not_in",
    "contains",
    "gt",
    "gte",
    "lt",
    "lte",
    "before",
    "after",
    "within_schedule",
}


def validate_conditions(conditions: list[dict]) -> None:
    seen_equals: dict[str, object] = {}
    for condition in conditions:
        field = condition.get("field")
        operator = condition.get("operator", "equals")
        value = condition.get("value")
        if field not in FIELD_TYPES:
            raise ValueError(f"Unknown governance field: {field}")
        if operator not in OPERATORS:
            raise ValueError(f"Unknown governance operator: {operator}")
        kind = FIELD_TYPES[field]
        if operator in {"in", "not_in"} and not isinstance(value, list):
            raise ValueError(f"Operator {operator} requires a list")
        if kind == "number" and (
            not isinstance(value, Real) or isinstance(value, bool)
        ):
            raise ValueError(f"Field {field} requires a numeric value")
        if field == "cost" and value < 0:
            raise ValueError("Cost cannot be negative")
        if operator in {"before", "after"}:
            try:
                datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValueError("Before/after requires an ISO-8601 timestamp") from exc
        if operator == "within_schedule":
            if not isinstance(value, dict) or set(value) - {
                "days",
                "start",
                "end",
                "timezone",
            }:
                raise ValueError(
                    "Schedule must contain only days, start, end and timezone"
                )
            if value.get("timezone", "UTC") != "UTC" or not isinstance(
                value.get("days"), list
            ):
                raise ValueError("Schedule requires UTC and a days list")
            if not all(isinstance(day, int) and 0 <= day <= 6 for day in value["days"]):
                raise ValueError("Schedule days must be integers from 0 through 6")
            try:
                time.fromisoformat(value["start"])
                time.fromisoformat(value["end"])
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(
                    "Schedule start and end must be ISO local times"
                ) from exc
        if operator == "equals":
            if field in seen_equals and seen_equals[field] != value:
                raise ValueError(f"Contradictory equality conditions for {field}")
            seen_equals[field] = value


def _condition_matches(actual, operator, expected) -> bool:
    if operator == "equals":
        return actual == expected
    if operator == "not_equals":
        return actual != expected
    if operator == "in":
        return actual in expected
    if operator == "not_in":
        return actual not in expected
    if operator == "contains":
        return expected in (actual or [])
    if operator == "gt":
        return actual is not None and actual > expected
    if operator == "gte":
        return actual is not None and actual >= expected
    if operator == "lt":
        return actual is not None and actual < expected
    if operator == "lte":
        return actual is not None and actual <= expected
    if operator in {"before", "after"}:
        boundary = datetime.fromisoformat(str(expected).replace("Z", "+00:00"))
        return actual < boundary if operator == "before" else actual > boundary
    if operator == "within_schedule":
        current = actual.astimezone(UTC)
        return current.weekday() in expected["days"] and time.fromisoformat(
            expected["start"]
        ) <= current.time().replace(tzinfo=None) <= time.fromisoformat(expected["end"])
    return False


def _matches(conditions, tool, context, intent, profile, execution_count=0):
    now = datetime.now(UTC)
    values = {
        "user": context.actor_id,
        "role": context.roles,
        "group": context.groups,
        "tenant": context.tenant_id,
        "tool": tool.name,
        "category": tool.metadata.category,
        "source": profile.source,
        "environment": context.environment,
        "risk": tool.metadata.risk_level.value,
        "operation": intent.operation,
        "data_classification": context.data_classification,
        "agent": context.agent_id,
        "roles": context.roles,
        "groups": context.groups,
        "tool_version": tool.metadata.version,
        "max_cost": context.max_cost,
        "health": profile.health_status,
        "provider": tool.metadata.provider,
        "action": intent.operation,
        "time": now,
        "cost": profile.estimated_cost,
        "execution_count": execution_count,
    }
    for item in conditions:
        field, op, expected = (
            item.get("field"),
            item.get("operator", "equals"),
            item.get("value"),
        )
        actual = values.get(field)
        if field in {"role", "group"} and op in {
            "equals",
            "not_equals",
            "in",
            "not_in",
        }:
            present = (
                expected in actual
                if not isinstance(expected, list)
                else bool(set(expected) & set(actual))
            )
            matched = present if op in {"equals", "in"} else not present
        else:
            matched = _condition_matches(actual, op, expected)
        if not matched:
            return False
    return True


def evaluate(db, tool, context, intent, profile=None):
    profile = (
        profile
        or db.query(ToolMarketplaceProfile)
        .filter_by(
            tenant_id=context.tenant_id,
            tool_name=tool.name,
            tool_version=tool.metadata.version,
        )
        .first()
    )
    if not profile:
        return PolicyDecision(
            decision="deny",
            reason_codes=["MARKETPLACE_UNCONFIGURED"],
            safe_explanation="Tool is not available in this workspace",
        )
    if profile.status not in {"enabled", "degraded"}:
        return PolicyDecision(
            decision="deny",
            reason_codes=["TOOL_STATUS_BLOCKED"],
            safe_explanation="Tool is not currently available",
        )
    if profile.health_status == "unhealthy":
        return PolicyDecision(
            decision="deny",
            reason_codes=["TOOL_UNHEALTHY"],
            safe_explanation="Tool is temporarily unavailable",
        )
    if profile.environment not in {"all", context.environment}:
        return PolicyDecision(
            decision="deny",
            reason_codes=["ENVIRONMENT_MISMATCH"],
            safe_explanation="Tool is unavailable in this environment",
        )
    if context.data_classification not in (profile.data_classifications or []):
        return PolicyDecision(
            decision="deny",
            reason_codes=["DATA_CLASSIFICATION_DENIED"],
            safe_explanation="Tool cannot process this data classification",
        )
    if profile.agent_allowlist and context.agent_id not in profile.agent_allowlist:
        return PolicyDecision(
            decision="deny",
            reason_codes=["AGENT_NOT_ASSIGNED"],
            safe_explanation="Tool is not assigned to this agent",
        )
    if (
        "tools.admin" not in context.permissions
        and set(tool.metadata.permissions) - context.permissions
    ):
        return PolicyDecision(
            decision="deny",
            reason_codes=["PERMISSION_DENIED"],
            safe_explanation="Required tool permission is not granted",
        )
    subjects = {
        ("user", context.actor_id),
        ("agent", context.agent_id),
        *{("role", x) for x in context.roles},
        *{("group", x) for x in context.groups},
    }
    assignments = (
        db.query(ToolAssignment)
        .filter_by(tenant_id=context.tenant_id, tool_name=tool.name, status="active")
        .all()
    )
    matched = [
        x
        for x in assignments
        if (x.subject_type, x.subject_id) in subjects
        and x.action == "execute"
        and (x.tool_version is None or x.tool_version == tool.metadata.version)
    ]
    if any(x.decision == "deny" for x in matched):
        return PolicyDecision(
            decision="deny",
            reason_codes=["EXPLICIT_DENY"],
            safe_explanation="A tool assignment denies this action",
        )
    policies = (
        db.query(ToolGovernancePolicy)
        .filter_by(tenant_id=context.tenant_id, lifecycle="active")
        .order_by(ToolGovernancePolicy.priority)
        .all()
    )
    execution_count = (
        db.query(ToolExecution)
        .filter_by(tenant_id=context.tenant_id, tool_name=tool.name)
        .count()
    )
    applicable = [
        x
        for x in policies
        if _matches(x.conditions, tool, context, intent, profile, execution_count)
    ]
    denied = [x for x in applicable if x.decision == "deny"]
    if denied:
        return PolicyDecision(
            decision="deny",
            policy_ids=[x.id for x in denied],
            reason_codes=["POLICY_DENIED"],
            safe_explanation="An active governance policy denies this action",
        )
    approval = [x for x in applicable if x.decision == "approval_required"]
    risk_approval = (
        tool.metadata.risk_level.value == "destructive"
        or profile.approval_policy == "always"
    )
    if approval or risk_approval:
        return PolicyDecision(
            decision="approval_required",
            policy_ids=[x.id for x in approval],
            reason_codes=["APPROVAL_REQUIRED"],
            approval_required=True,
            safe_explanation="Human approval is required",
        )
    return PolicyDecision(
        decision="allow",
        policy_ids=[x.id for x in applicable],
        reason_codes=["PERMISSION_ALLOWED", "POLICY_ALLOWED"],
        safe_explanation="Tool is permitted",
    )
