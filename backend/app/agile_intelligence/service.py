from __future__ import annotations

from datetime import UTC, datetime
from statistics import median, quantiles

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.agents.application_service import AgentIdentity
from app.audit.events import append_audit_event
from app.database.models.agile_intelligence import (
    AgileKeyResult,
    AgileMetricObservation,
    AgileObjective,
    AgileObjectiveCheckIn,
)
from app.database.models.delivery import (
    DeliveryDefect,
    DeliverySprint,
    DeliveryWorkItem,
)
from app.delivery.metrics import metric_catalogue

OKR_LEVELS = {"ORGANIZATION", "PORTFOLIO", "PROGRAMME", "PROJECT", "TEAM"}
ANONYMOUS_TEAM_HEALTH_MINIMUM = 5


def percentile(values: list[float], percentile_value: int) -> float | None:
    clean = sorted(float(value) for value in values if value is not None)
    if not clean:
        return None
    if len(clean) == 1:
        return clean[0]
    return round(quantiles(clean, n=100, method="inclusive")[percentile_value - 1], 2)


def safe_ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or denominator <= 0:
        return None
    return round(numerator / denominator * 100, 2)


def aggregate_team_health(
    responses: list[float], minimum: int = ANONYMOUS_TEAM_HEALTH_MINIMUM
) -> dict:
    if len(responses) < minimum:
        return {
            "value": None,
            "status": "INSUFFICIENT_DATA",
            "responseCount": len(responses),
            "minimumResponses": minimum,
        }
    return {
        "value": round(sum(responses) / len(responses), 2),
        "status": "AVAILABLE",
        "responseCount": len(responses),
        "minimumResponses": minimum,
    }


class AgileIntelligenceService:
    def __init__(self, db: Session, identity: AgentIdentity):
        self.db, self.identity = db, identity

    def require(self, permission: str) -> None:
        if not self.identity.allows(permission):
            raise HTTPException(
                403,
                {
                    "code": "PERMISSION_DENIED",
                    "message": f"{permission} permission is required",
                },
            )

    def observations(
        self,
        context_type: str | None = None,
        context_id: str | None = None,
        metric_key: str | None = None,
    ):
        self.require("agile.metrics.read")
        query = self.db.query(AgileMetricObservation).filter_by(
            tenant_id=self.identity.tenant_id
        )
        if context_type:
            query = query.filter_by(context_type=context_type.upper())
        if context_id:
            query = query.filter_by(context_id=context_id)
        if metric_key:
            query = query.filter_by(metric_key=metric_key)
        return query.order_by(
            AgileMetricObservation.period_end.desc(), AgileMetricObservation.metric_key
        ).all()

    @staticmethod
    def metric_json(row: AgileMetricObservation) -> dict:
        return {
            "id": row.id,
            "key": row.metric_key,
            "metricVersion": row.metric_version,
            "contextType": row.context_type,
            "contextId": row.context_id,
            "periodStart": row.period_start,
            "periodEnd": row.period_end,
            "value": row.value,
            "unit": row.unit,
            "status": row.status if row.value is not None else "UNKNOWN",
            "source": row.source_system,
            "freshness": row.source_timestamp,
            "missingInputs": row.missing_inputs,
            "evidence": row.evidence_refs,
            "metadata": row.metadata_json,
        }

    def _live_delivery_metrics(
        self, context_type: str | None, context_id: str | None
    ) -> tuple[dict[str, dict], dict[str, list[dict]]]:
        """Calculate current Agile signals from synchronized delivery records."""
        tenant_id = self.identity.tenant_id
        sprint_query = self.db.query(DeliverySprint).filter_by(tenant_id=tenant_id)
        work_query = self.db.query(DeliveryWorkItem).filter_by(tenant_id=tenant_id)
        defect_query = self.db.query(DeliveryDefect).filter_by(tenant_id=tenant_id)
        normalized_context = (context_type or "PORTFOLIO").upper()
        if context_id and normalized_context == "PROJECT":
            sprint_query = sprint_query.filter_by(project_id=context_id)
            work_query = work_query.filter_by(project_id=context_id)
            defect_query = defect_query.filter_by(project_id=context_id)
        if context_id and normalized_context == "TEAM":
            sprint_query = sprint_query.filter_by(team_id=context_id)

        sprints = sprint_query.order_by(DeliverySprint.end_date.desc()).all()
        work_items = work_query.all()
        defects = defect_query.all()
        if any(row.source_system == "JIRA" for row in sprints + work_items):
            sprints = [row for row in sprints if row.source_system == "JIRA"]
            work_items = [row for row in work_items if row.source_system == "JIRA"]
            defects = [row for row in defects if row.source_system == "JIRA"]

        freshness_values = [
            row.updated_at
            for row in [*sprints, *work_items, *defects]
            if row.updated_at
        ]
        freshness = max(freshness_values) if freshness_values else None
        source = (
            "JIRA"
            if any(row.source_system == "JIRA" for row in sprints + work_items)
            else "DELIVERY_DATABASE"
        )
        closed = {"DONE", "COMPLETED", "CLOSED", "RESOLVED", "RELEASED"}

        def observation(
            key: str,
            value: float | int | None,
            unit: str,
            numerator: float | int | None,
            denominator: float | int | None,
            evidence: list[dict],
            missing: list[str] | None = None,
        ) -> dict:
            return {
                "key": key,
                "metricVersion": "1.0",
                "contextType": normalized_context,
                "contextId": context_id,
                "periodStart": min(
                    (row.start_date for row in sprints if row.start_date), default=None
                ),
                "periodEnd": max(
                    (row.end_date for row in sprints if row.end_date), default=None
                ),
                "value": None if value is None else round(float(value), 2),
                "unit": unit,
                "status": "UNKNOWN" if value is None else "AVAILABLE",
                "source": source,
                "freshness": freshness,
                "missingInputs": missing or [],
                "evidence": evidence[:100],
                "metadata": {
                    "numerator": numerator,
                    "denominator": denominator,
                    "derivedLive": True,
                },
            }

        sprint_evidence = [
            {
                "type": "SPRINT",
                "id": row.id,
                "externalId": row.external_id,
                "url": row.source_url,
            }
            for row in sprints
        ]
        work_evidence = [
            {
                "type": "WORK_ITEM",
                "id": row.id,
                "externalId": row.external_id,
                "url": row.source_url,
            }
            for row in work_items
        ]
        committed = sum(float(row.original_committed_points or 0) for row in sprints)
        completed_original = sum(
            float(row.completed_original_points or 0) for row in sprints
        )
        completed_total = sum(float(row.completed_points or 0) for row in sprints)
        scope_changed = sum(
            float(row.scope_added_points or 0) + float(row.scope_removed_points or 0)
            for row in sprints
        )
        assessed_goals = [row for row in sprints if row.goal.strip()]
        achieved_goals = [
            row
            for row in assessed_goals
            if row.original_committed_points
            and (row.completed_original_points or 0) >= row.original_committed_points
        ]
        completed_work = [
            row
            for row in work_items
            if row.completed_at or row.status.upper() in closed
        ]
        active_work = [row for row in work_items if row.status.upper() not in closed]
        cycle_days = [
            (row.completed_at - row.started_at).total_seconds() / 86400
            for row in completed_work
            if row.completed_at and row.started_at
        ]
        lead_days = [
            (row.completed_at - row.created_at).total_seconds() / 86400
            for row in completed_work
            if row.completed_at and row.created_at
        ]
        blocked = [row for row in active_work if row.blocked]
        estimated = [row for row in work_items if row.story_points is not None]
        with_acceptance = [
            row
            for row in work_items
            if (row.record_metadata or {}).get("acceptanceCriteria")
        ]
        linked_outcome = [
            row
            for row in work_items
            if (row.record_metadata or {}).get("outcomeId") or row.goal_critical
        ]
        dependency_assessed = [
            row
            for row in work_items
            if "dependency" in (row.record_metadata or {}) or row.blocked
        ]
        escaped = [row for row in defects if row.escaped]
        sourced = [
            row
            for row in [*sprints, *work_items, *defects]
            if row.source_url or row.external_id
        ]
        all_records = [*sprints, *work_items, *defects]

        values = {
            "sprint_goal_achievement": observation(
                "sprint_goal_achievement",
                safe_ratio(len(achieved_goals), len(assessed_goals)),
                "percent",
                len(achieved_goals),
                len(assessed_goals),
                sprint_evidence,
                [] if assessed_goals else ["No assessed sprint goals"],
            ),
            "commitment_achievement": observation(
                "commitment_achievement",
                safe_ratio(completed_original, committed),
                "percent",
                completed_original,
                committed,
                sprint_evidence,
                [] if committed else ["No positive original commitment"],
            ),
            "sprint_predictability": observation(
                "sprint_predictability",
                safe_ratio(completed_original, committed),
                "percent",
                completed_original,
                committed,
                sprint_evidence,
                [] if committed else ["No positive original commitment"],
            ),
            "carryover_rate": observation(
                "carryover_rate",
                safe_ratio(max(committed - completed_original, 0), committed),
                "percent",
                max(committed - completed_original, 0),
                committed,
                sprint_evidence,
                [] if committed else ["No positive original commitment"],
            ),
            "scope_change_rate": observation(
                "scope_change_rate",
                safe_ratio(scope_changed, committed),
                "percent",
                scope_changed,
                committed,
                sprint_evidence,
                [] if committed else ["No positive original commitment"],
            ),
            "throughput": observation(
                "throughput",
                len(completed_work),
                "items",
                len(completed_work),
                len(work_items),
                work_evidence,
            ),
            "velocity": observation(
                "velocity",
                completed_total / len(sprints) if sprints else None,
                "story_points",
                completed_total,
                len(sprints),
                sprint_evidence,
                [] if sprints else ["No synchronized sprints"],
            ),
            "cycle_time": observation(
                "cycle_time",
                median(cycle_days) if cycle_days else None,
                "days",
                None,
                len(cycle_days),
                work_evidence,
                []
                if cycle_days
                else ["Completed work lacks start/completion timestamps"],
            ),
            "cycle_time_p85": observation(
                "cycle_time_p85",
                percentile(cycle_days, 85),
                "days",
                None,
                len(cycle_days),
                work_evidence,
                []
                if cycle_days
                else ["Completed work lacks start/completion timestamps"],
            ),
            "lead_time": observation(
                "lead_time",
                median(lead_days) if lead_days else None,
                "days",
                None,
                len(lead_days),
                work_evidence,
                []
                if lead_days
                else ["Completed work lacks creation/completion timestamps"],
            ),
            "lead_time_p85": observation(
                "lead_time_p85",
                percentile(lead_days, 85),
                "days",
                None,
                len(lead_days),
                work_evidence,
                []
                if lead_days
                else ["Completed work lacks creation/completion timestamps"],
            ),
            "work_in_progress": observation(
                "work_in_progress",
                len(active_work),
                "items",
                len(active_work),
                len(work_items),
                work_evidence,
            ),
            "blocked_work": observation(
                "blocked_work",
                safe_ratio(len(blocked), len(active_work)),
                "percent",
                len(blocked),
                len(active_work),
                work_evidence,
                [] if active_work else ["No active work"],
            ),
            "estimate_coverage": observation(
                "estimate_coverage",
                safe_ratio(len(estimated), len(work_items)),
                "percent",
                len(estimated),
                len(work_items),
                work_evidence,
                [] if work_items else ["No synchronized work items"],
            ),
            "acceptance_criteria_coverage": observation(
                "acceptance_criteria_coverage",
                safe_ratio(len(with_acceptance), len(work_items)),
                "percent",
                len(with_acceptance),
                len(work_items),
                work_evidence,
                [] if work_items else ["No synchronized work items"],
            ),
            "outcome_linkage": observation(
                "outcome_linkage",
                safe_ratio(len(linked_outcome), len(work_items)),
                "percent",
                len(linked_outcome),
                len(work_items),
                work_evidence,
                [] if work_items else ["No synchronized work items"],
            ),
            "dependency_identification": observation(
                "dependency_identification",
                safe_ratio(len(dependency_assessed), len(work_items)),
                "percent",
                len(dependency_assessed),
                len(work_items),
                work_evidence,
                [] if work_items else ["No synchronized work items"],
            ),
            "defect_escape_rate": observation(
                "defect_escape_rate",
                safe_ratio(len(escaped), len(defects)),
                "percent",
                len(escaped),
                len(defects),
                work_evidence,
                [] if defects else ["No synchronized defect records"],
            ),
            "evidence_coverage": observation(
                "evidence_coverage",
                safe_ratio(len(sourced), len(all_records)),
                "percent",
                len(sourced),
                len(all_records),
                sprint_evidence + work_evidence,
                [] if all_records else ["No synchronized delivery records"],
            ),
            "risk_exposure": observation(
                "risk_exposure",
                len(blocked),
                "count",
                len(blocked),
                len(active_work),
                work_evidence,
            ),
        }

        trends: dict[str, list[dict]] = {"commitment_achievement": []}
        for row in reversed(sprints[:6]):
            row_committed = float(row.original_committed_points or 0)
            trends["commitment_achievement"].append(
                observation(
                    "commitment_achievement",
                    safe_ratio(
                        float(row.completed_original_points or 0), row_committed
                    ),
                    "percent",
                    row.completed_original_points,
                    row_committed,
                    [
                        {
                            "type": "SPRINT",
                            "id": row.id,
                            "externalId": row.external_id,
                            "url": row.source_url,
                        }
                    ],
                    [] if row_committed else ["No positive original commitment"],
                )
            )
        return values, trends

    def summary(
        self, context_type: str | None = None, context_id: str | None = None
    ) -> dict:
        rows = self.observations(context_type, context_id)
        grouped: dict[str, list[AgileMetricObservation]] = {}
        for row in rows:
            grouped.setdefault(row.metric_key, []).append(row)
        current = {key: self.metric_json(values[0]) for key, values in grouped.items()}
        trends = {
            key: [self.metric_json(row) for row in reversed(values[:6])]
            for key, values in grouped.items()
        }
        live_current, live_trends = self._live_delivery_metrics(
            context_type, context_id
        )
        current.update(live_current)
        for key, values in live_trends.items():
            if values:
                trends[key] = values
        required = [
            "sprint_goal_achievement",
            "commitment_achievement",
            "carryover_rate",
            "evidence_coverage",
        ]
        missing = [
            key
            for key in required
            if key not in current or current[key]["value"] is None
        ]
        definitions = {item["key"]: item for item in metric_catalogue()}
        metrics = []
        for key, definition in definitions.items():
            metric = current.get(
                key,
                {
                    "key": key,
                    "value": None,
                    "status": "UNKNOWN",
                    "unit": definition["unit"],
                    "missingInputs": ["No persisted observation for this context"],
                    "evidence": [],
                },
            )
            metrics.append({**metric, "definition": definition})
        return {
            "context": {"type": context_type or "PORTFOLIO", "id": context_id},
            "generatedAt": datetime.now(UTC),
            "kpis": [
                {
                    **current.get(
                        key,
                        {
                            "key": key,
                            "value": None,
                            "status": "UNKNOWN",
                            "missingInputs": ["No persisted comparable observation"],
                        },
                    ),
                    "definition": definitions.get(key),
                }
                for key in required
            ],
            "metrics": metrics,
            "trends": trends,
            "insufficientData": missing,
            "privacy": {
                "individualScoring": False,
                "teamHealthMinimumResponses": ANONYMOUS_TEAM_HEALTH_MINIMUM,
            },
            "calculationBoundary": "BACKEND_ONLY",
        }

    def objective(self, objective_id: str) -> AgileObjective:
        self.require("agile.okrs.read")
        row = (
            self.db.query(AgileObjective)
            .filter_by(tenant_id=self.identity.tenant_id, id=objective_id)
            .first()
        )
        if not row:
            raise HTTPException(
                404,
                {"code": "OBJECTIVE_NOT_FOUND", "message": "Objective was not found"},
            )
        return row

    def objectives(self):
        self.require("agile.okrs.read")
        return (
            self.db.query(AgileObjective)
            .filter_by(tenant_id=self.identity.tenant_id)
            .order_by(AgileObjective.target_date, AgileObjective.title)
            .all()
        )

    def create_objective(self, values: dict) -> AgileObjective:
        self.require("agile.okrs.manage")
        if values["level"] not in OKR_LEVELS:
            raise HTTPException(
                422, {"code": "INVALID_OKR_LEVEL", "message": "Unsupported OKR level"}
            )
        key_results = values.pop("key_results", [])
        row = AgileObjective(
            tenant_id=self.identity.tenant_id,
            owner_id=values.pop("owner_id", None) or self.identity.actor_id,
            **values,
        )
        self.db.add(row)
        self.db.flush()
        for item in key_results:
            self.db.add(
                AgileKeyResult(
                    tenant_id=self.identity.tenant_id, objective_id=row.id, **item
                )
            )
        self._audit("agile.objective.created", row.id, {"level": row.level})
        self.db.commit()
        return row

    def update_objective(
        self, objective_id: str, expected_version: int, values: dict
    ) -> AgileObjective:
        self.require("agile.okrs.manage")
        row = self.objective(objective_id)
        if row.version != expected_version:
            raise HTTPException(
                409,
                {
                    "code": "STALE_VERSION",
                    "message": "Objective changed; refresh and retry",
                },
            )
        for key, value in values.items():
            if key not in {
                "baseline",
                "target",
                "current_value",
                "confidence",
                "status",
                "description",
                "target_date",
                "contributors",
                "related_metrics",
                "related_entities",
                "evidence_refs",
                "risks",
                "dependencies",
            }:
                continue
            setattr(row, key, value)
        row.version += 1
        self._audit("agile.objective.updated", row.id, {"version": row.version})
        self.db.commit()
        return row

    def check_in(self, objective_id: str, values: dict) -> AgileObjectiveCheckIn:
        self.require("agile.okrs.check_in")
        objective = self.objective(objective_id)
        row = AgileObjectiveCheckIn(
            tenant_id=self.identity.tenant_id,
            objective_id=objective.id,
            actor_id=self.identity.actor_id,
            **values,
        )
        self.db.add(row)
        objective.current_value, objective.confidence, objective.status = (
            row.current_value,
            row.confidence,
            row.status,
        )
        objective.version += 1
        self._audit("agile.objective.checked_in", objective.id, {"checkInId": row.id})
        self.db.commit()
        return row

    def objective_json(self, row: AgileObjective) -> dict:
        key_results = (
            self.db.query(AgileKeyResult)
            .filter_by(tenant_id=self.identity.tenant_id, objective_id=row.id)
            .all()
        )
        check_ins = (
            self.db.query(AgileObjectiveCheckIn)
            .filter_by(tenant_id=self.identity.tenant_id, objective_id=row.id)
            .order_by(AgileObjectiveCheckIn.created_at.desc())
            .all()
        )
        return {
            "id": row.id,
            "title": row.title,
            "description": row.description,
            "level": row.level,
            "ownerId": row.owner_id,
            "contributors": row.contributors,
            "startDate": row.start_date,
            "targetDate": row.target_date,
            "status": row.status,
            "confidence": row.confidence,
            "baseline": row.baseline,
            "target": row.target,
            "currentValue": row.current_value,
            "unit": row.unit,
            "relatedMetrics": row.related_metrics,
            "relatedEntities": row.related_entities,
            "evidence": row.evidence_refs,
            "risks": row.risks,
            "dependencies": row.dependencies,
            "suggestedTarget": row.suggested_target,
            "version": row.version,
            "updatedAt": row.updated_at,
            "keyResults": [
                {
                    "id": item.id,
                    "title": item.title,
                    "baseline": item.baseline,
                    "target": item.target,
                    "currentValue": item.current_value,
                    "unit": item.unit,
                    "status": item.status,
                    "confidence": item.confidence,
                    "metricKey": item.metric_key,
                    "evidence": item.evidence_refs,
                }
                for item in key_results
            ],
            "checkIns": [
                {
                    "id": item.id,
                    "actorId": item.actor_id,
                    "currentValue": item.current_value,
                    "confidence": item.confidence,
                    "status": item.status,
                    "note": item.note,
                    "evidence": item.evidence_refs,
                    "limitations": item.limitations,
                    "createdAt": item.created_at,
                }
                for item in check_ins
            ],
        }

    def _audit(self, action: str, target_id: str, metadata: dict) -> None:
        append_audit_event(
            self.db,
            tenant_id=self.identity.tenant_id,
            actor_id=self.identity.actor_id,
            action=action,
            target_type="agile_objective",
            target_id=target_id,
            correlation_id=target_id,
            metadata=metadata,
        )
