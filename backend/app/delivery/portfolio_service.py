from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models.delivery import (
    DeliveryDependency,
    DeliveryEvidence,
    DeliveryMilestone,
    DeliveryPortfolio,
    DeliveryProgramme,
    DeliveryProject,
    DeliveryRAIDItem,
    DeliveryRelease,
    DeliverySprint,
    DeliveryWorkItem,
    PortfolioInvestmentSnapshot,
    PortfolioOutcomeLink,
    PortfolioStrategicOutcome,
)
from app.delivery.intelligence import attention_score, portfolio_health

CLOSED = {"DONE", "COMPLETED", "CLOSED", "CANCELLED", "RESOLVED", "IMPLEMENTED"}
STATUS_SCORE = {
    "ACTIVE": 85,
    "PLANNED": 70,
    "AT_RISK": 45,
    "BLOCKED": 20,
    "COMPLETED": 100,
}


class PortfolioIntelligenceService:
    """Tenant-scoped, deterministic Portfolio Intelligence read model."""

    def __init__(self, db: Session, tenant_id: str, user_id: str):
        if not tenant_id or not user_id:
            raise ValueError("tenant and user identity are required")
        self.db, self.tenant_id, self.user_id = db, tenant_id, user_id

    def _all(self, model):
        return list(
            self.db.scalars(select(model).where(model.tenant_id == self.tenant_id))
        )

    @staticmethod
    def _meta(record, key, default=None):
        return (record.record_metadata or {}).get(key, default)

    @staticmethod
    def _money(record, key):
        raw = (record.record_metadata or {}).get(key)
        if raw in (None, ""):
            return None
        try:
            return str(Decimal(str(raw)).quantize(Decimal("0.01")))
        except (InvalidOperation, ValueError):
            return None

    @staticmethod
    def _health(status):
        score = STATUS_SCORE.get(status)
        return {
            "score": score,
            "status": "UNKNOWN"
            if score is None
            else "GREEN"
            if score >= 80
            else "AMBER"
            if score >= 60
            else "RED",
        }

    def _records(self):
        return {
            m.__tablename__: self._all(m)
            for m in (
                DeliveryPortfolio,
                DeliveryProgramme,
                DeliveryProject,
                DeliveryMilestone,
                DeliveryRAIDItem,
                DeliveryDependency,
                DeliveryRelease,
                DeliverySprint,
                DeliveryWorkItem,
                DeliveryEvidence,
                PortfolioStrategicOutcome,
                PortfolioOutcomeLink,
                PortfolioInvestmentSnapshot,
            )
        }

    def workspace(self, *, financial_access: bool = True) -> dict:
        today = datetime.now(UTC).date()
        r = self._records()
        portfolios, programmes, projects = (
            r["delivery_portfolios"],
            r["delivery_programmes"],
            r["delivery_projects"],
        )
        live_jira = any(project.source_system == "JIRA" for project in projects)
        if live_jira:
            projects = [project for project in projects if project.source_system == "JIRA"]
            project_ids = {project.id for project in projects}
            programme_ids = {project.programme_id for project in projects}
            programmes = [programme for programme in programmes if programme.id in programme_ids and programme.source_system == "JIRA"]
            portfolio_ids = {programme.portfolio_id for programme in programmes}
            portfolios = [portfolio for portfolio in portfolios if portfolio.id in portfolio_ids and portfolio.source_system == "JIRA"]
        milestones, raids, dependencies = (
            r["delivery_milestones"],
            r["delivery_raid_items"],
            r["delivery_dependencies"],
        )
        releases, evidence = r["delivery_releases"], r["delivery_evidence"]
        sprints, work_items = r["delivery_sprints"], r["delivery_work_items"]
        outcomes = r["portfolio_strategic_outcomes"]
        outcome_links = r["portfolio_outcome_links"]
        investment_snapshots = r["portfolio_investment_snapshots"]
        if live_jira:
            releases = [row for row in releases if row.project_id in project_ids and row.source_system == "JIRA"]
            sprints = [row for row in sprints if row.project_id in project_ids and row.source_system == "JIRA"]
            work_items = [row for row in work_items if row.project_id in project_ids and row.source_system == "JIRA"]
            milestones, raids, dependencies, outcomes, outcome_links, investment_snapshots = [], [], [], [], [], []
            evidence = [row for row in evidence if row.entity_id in project_ids]
        latest_investment = {}
        for snapshot in sorted(
            investment_snapshots,
            key=lambda x: (x.reporting_period, x.source_timestamp),
        ):
            latest_investment[(snapshot.entity_type, snapshot.entity_id)] = snapshot
        project_by_id = {p.id: p for p in projects}
        programme_by_id = {p.id: p for p in programmes}
        evidence_by_project = Counter(
            e.entity_id for e in evidence if str(e.entity_type).upper() == "PROJECT"
        )

        project_rows = []
        for project in projects:
            programme = programme_by_id.get(project.programme_id)
            project_raids = [
                x
                for x in raids
                if x.project_id == project.id and x.status not in CLOSED
            ]
            project_deps = [
                x
                for x in dependencies
                if x.project_id == project.id and x.status not in CLOSED
            ]
            project_milestones = [x for x in milestones if x.project_id == project.id]
            project_releases = [x for x in releases if x.project_id == project.id]
            project_work = [x for x in work_items if x.project_id == project.id]
            meta = project.record_metadata or {}
            snapshot = latest_investment.get(("PROJECT", project.id))
            project_sprints = [row for row in sprints if row.project_id == project.id]
            committed = sum(float(row.original_committed_points or 0) for row in project_sprints)
            completed = sum(float(row.completed_original_points or 0) for row in project_sprints)
            jira_health = round(min(100, completed / committed * 100), 1) if committed else None
            project_rows.append(
                {
                    "id": project.id,
                    "name": project.name,
                    "programmeId": project.programme_id,
                    "programme": programme.name if programme else "Not available",
                    "status": project.status,
                    "health": ({"score": jira_health, "status": "UNKNOWN" if jira_health is None else "GREEN" if jira_health >= 80 else "AMBER" if jira_health >= 60 else "RED"} if live_jira else self._health(project.status)),
                    "manager": meta.get("manager") or project.owner_id or "Unassigned",
                    "strategicTheme": meta.get("strategic_theme") or "Not available",
                    "confidence": jira_health if live_jira else meta.get("confidence"),
                    "startDate": meta.get("start_date"),
                    "targetDate": meta.get("target_date"),
                    "approvedBudget": str(snapshot.approved_budget)
                    if snapshot and snapshot.approved_budget is not None
                    else self._money(project, "approved_budget"),
                    "actualSpend": str(snapshot.actual_spend)
                    if snapshot and snapshot.actual_spend is not None
                    else self._money(project, "actual_spend"),
                    "forecast": str(snapshot.forecast)
                    if snapshot and snapshot.forecast is not None
                    else self._money(project, "forecast"),
                    "currency": snapshot.currency if snapshot else meta.get("currency"),
                    "financialSource": snapshot.source_system
                    if snapshot
                    else "LEGACY_METADATA",
                    "financialPeriod": snapshot.reporting_period.isoformat()
                    if snapshot
                    else None,
                    "criticalRaid": sum(
                        (x.priority in {"CRITICAL", "HIGH"} or x.severity == "CRITICAL")
                        for x in project_raids
                    ) if not live_jira else sum(x.goal_critical and x.status not in CLOSED for x in project_work),
                    "overdueDependencies": sum(
                        bool(
                            getattr(x, "required_by_date", None)
                            and x.required_by_date < today
                        )
                        for x in project_deps
                    ) if not live_jira else sum(x.blocked and x.status not in CLOSED for x in project_work),
                    "milestones": len(project_milestones),
                    "nextRelease": min(
                        (x.planned_date for x in project_releases if x.planned_date),
                        default=None,
                    ),
                    "evidenceCount": evidence_by_project[project.id],
                    "updatedAt": project.updated_at.isoformat(),
                    "description": meta.get("description")
                    or "No persisted project summary is available.",
                }
            )

        programme_rows = []
        for programme in programmes:
            children = [x for x in project_rows if x["programmeId"] == programme.id]
            meta = programme.record_metadata or {}
            snapshot = latest_investment.get(("PROGRAMME", programme.id))
            scores = [
                x["health"]["score"]
                for x in children
                if x["health"]["score"] is not None
            ]
            score = round(sum(scores) / len(scores), 1) if scores else None
            programme_rows.append(
                {
                    "id": programme.id,
                    "portfolioId": programme.portfolio_id,
                    "name": programme.name,
                    "description": meta.get("description")
                    or "No persisted programme summary is available.",
                    "status": programme.status,
                    "health": {
                        "score": score,
                        "status": "UNKNOWN"
                        if score is None
                        else "GREEN"
                        if score >= 80
                        else "AMBER"
                        if score >= 60
                        else "RED",
                    },
                    "confidence": meta.get("confidence"),
                    "sponsor": meta.get("sponsor") or "Unassigned",
                    "manager": meta.get("manager")
                    or programme.owner_id
                    or "Unassigned",
                    "strategicTheme": meta.get("strategic_theme") or "Not available",
                    "approvedBudget": str(snapshot.approved_budget)
                    if snapshot and snapshot.approved_budget is not None
                    else self._money(programme, "approved_budget"),
                    "actualSpend": str(snapshot.actual_spend)
                    if snapshot and snapshot.actual_spend is not None
                    else self._money(programme, "actual_spend"),
                    "forecast": str(snapshot.forecast)
                    if snapshot and snapshot.forecast is not None
                    else self._money(programme, "forecast"),
                    "currency": snapshot.currency if snapshot else meta.get("currency"),
                    "financialSource": snapshot.source_system
                    if snapshot
                    else "LEGACY_METADATA",
                    "financialPeriod": snapshot.reporting_period.isoformat()
                    if snapshot
                    else None,
                    "activeProjects": sum(x["status"] == "ACTIVE" for x in children),
                    "atRiskProjects": sum(
                        x["health"]["status"] in {"RED", "AMBER"} for x in children
                    ),
                    "criticalRaid": sum(x["criticalRaid"] for x in children),
                    "overdueDependencies": sum(
                        x["overdueDependencies"] for x in children
                    ),
                    "updatedAt": programme.updated_at.isoformat(),
                }
            )

        project_scores = [
            x["health"]["score"]
            for x in project_rows
            if x["health"]["score"] is not None
        ]
        release_scores = [
            x.readiness_score for x in releases if x.readiness_score is not None
        ]
        jira_risk_count = sum(x.goal_critical and x.status not in CLOSED for x in work_items)
        jira_dependency_count = sum(x.blocked and x.status not in CLOSED for x in work_items)
        raid_score = (
            100 - min(100, jira_risk_count * 3)
            if live_jira
            else
            100 - min(100, sum(x.status not in CLOSED for x in raids) * 5)
            if projects
            else None
        )
        dep_score = (
            100 - min(100, jira_dependency_count * 7)
            if live_jira
            else
            100 - min(100, sum(x.status not in CLOSED for x in dependencies) * 5)
            if projects
            else None
        )
        milestone_score = (
            100
            - min(
                100,
                sum(
                    x.status not in CLOSED and x.planned_date < today
                    for x in milestones
                )
                * 10,
            )
            if milestones
            else None
        )
        health = portfolio_health(
            {
                "project": sum(project_scores) / len(project_scores)
                if project_scores
                else None,
                "release": sum(release_scores) / len(release_scores)
                if release_scores
                else None,
                "risk": raid_score,
                "dependency": dep_score,
                "milestone": milestone_score,
            }
        )

        attention = []
        for item in [*raids, *dependencies, *milestones]:
            if item.status in CLOSED:
                continue
            due = (
                getattr(item, "due_date", None)
                or getattr(item, "required_by_date", None)
                or getattr(item, "planned_date", None)
            )
            result = attention_score(
                impact=5
                if getattr(item, "priority", None) in {"HIGH", "CRITICAL"}
                else 3,
                urgency=5 if due and due <= today else 3,
                critical_path=bool(
                    getattr(item, "critical_path", False)
                    or getattr(item, "critical", False)
                ),
                age_periods=1,
            )
            project = project_by_id.get(item.project_id)
            attention.append(
                {
                    "id": item.id,
                    "kind": item.__class__.__name__.replace("Delivery", "").replace(
                        "Item", ""
                    ),
                    "title": item.name,
                    "severity": result.status,
                    "score": result.value,
                    "explanation": result.factors,
                    "entity": project.name if project else "Not available",
                    "owner": item.owner_id or "Unassigned",
                    "dueDate": due.isoformat() if due else None,
                    "projectId": item.project_id,
                }
            )
        if live_jira:
            for item in work_items:
                if item.status in CLOSED or (not item.blocked and not item.goal_critical):
                    continue
                project = project_by_id.get(item.project_id)
                attention.append({
                    "id": item.id,
                    "kind": "Dependency" if item.blocked else "Risk",
                    "title": item.name,
                    "severity": "RED" if item.blocked else "AMBER",
                    "score": 90 if item.blocked else 70,
                    "explanation": ["Jira blocker link" if item.blocked else "High-priority incomplete Jira work"],
                    "entity": project.name if project else "Not available",
                    "owner": item.assignee_id or "Unassigned",
                    "dueDate": None,
                    "projectId": item.project_id,
                })
        attention.sort(key=lambda x: x["score"], reverse=True)

        currencies = sorted(
            {x["currency"] for x in [*project_rows, *programme_rows] if x["currency"]}
        )
        links_by_outcome = {}
        for link in outcome_links:
            links_by_outcome.setdefault(link.outcome_id, []).append(
                {
                    "entityType": link.entity_type,
                    "entityId": link.entity_id,
                    "contribution": link.contribution,
                }
            )
        outcome_rows = [
            {
                "id": item.id,
                "portfolioId": item.portfolio_id,
                "name": item.name,
                "status": item.status,
                "targetValue": item.target_value,
                "currentValue": item.current_value,
                "unit": item.unit,
                "targetDate": item.target_date.isoformat()
                if item.target_date
                else None,
                "confidence": item.confidence,
                "owner": item.owner_id or "Unassigned",
                "links": links_by_outcome.get(item.id, []),
                "updatedAt": item.updated_at.isoformat(),
            }
            for item in outcomes
        ]
        if not financial_access:
            for row in [*programme_rows, *project_rows]:
                for field in (
                    "approvedBudget",
                    "actualSpend",
                    "forecast",
                    "currency",
                    "financialSource",
                    "financialPeriod",
                ):
                    row[field] = None
        return {
            "generatedAt": datetime.now(UTC).isoformat(),
            "source": "Live Jira delivery records" if live_jira else "Persisted delivery records",
            "freshness": "Latest Jira synchronization" if live_jira else "Current database snapshot",
            "portfolios": [
                {
                    "id": x.id,
                    "name": x.name,
                    "status": x.status,
                    "updatedAt": x.updated_at.isoformat(),
                }
                for x in portfolios
            ],
            "health": {
                **health.to_dict(),
                "version": "portfolio-health-v1",
                "weights": {
                    "project": 0.25,
                    "release": 0.25,
                    "risk": 0.2,
                    "dependency": 0.15,
                    "milestone": 0.15,
                },
            },
            "programmes": programme_rows,
            "projects": project_rows,
            "outcomes": outcome_rows,
            "milestones": [
                {
                    "id": x.id,
                    "name": x.name,
                    "projectId": x.project_id,
                    "project": project_by_id[x.project_id].name
                    if x.project_id in project_by_id
                    else "Not available",
                    "status": x.status,
                    "baselineDate": x.planned_date.isoformat(),
                    "forecastDate": x.forecast_date.isoformat()
                    if x.forecast_date
                    else None,
                    "actualDate": x.actual_date.isoformat() if x.actual_date else None,
                    "varianceDays": (x.forecast_date - x.planned_date).days
                    if x.forecast_date
                    else None,
                    "critical": x.critical,
                    "owner": x.owner_id or "Unassigned",
                    "updatedAt": x.updated_at.isoformat(),
                }
                for x in milestones
            ],
            "sprints": [
                {"id": x.id, "projectId": x.project_id, "name": x.name, "status": x.status, "goal": x.goal, "startDate": x.start_date.isoformat() if x.start_date else None, "endDate": x.end_date.isoformat() if x.end_date else None, "committedPoints": x.original_committed_points or 0, "completedPoints": x.completed_original_points or 0, "sourceUrl": x.source_url}
                for x in sprints
            ],
            "releases": [
                {"id": x.id, "projectId": x.project_id, "name": x.name, "status": x.status, "plannedDate": x.planned_date.isoformat() if x.planned_date else None, "readinessScore": x.readiness_score, "sourceUrl": x.source_url}
                for x in releases
            ],
            "workItems": [
                {"id": x.id, "projectId": x.project_id, "name": x.name, "status": x.status, "storyPoints": x.story_points or 0, "blocked": x.blocked, "priority": "HIGH" if x.goal_critical else "MEDIUM", "assignee": x.assignee_id, "sourceUrl": x.source_url}
                for x in work_items
            ],
            "attention": attention[:50],
            "insights": self._insights(attention, health),
            "investment": {
                "authorized": financial_access,
                "currencies": currencies,
                "aggregationAllowed": len(currencies) <= 1,
                "notice": "Financial access is restricted."
                if not financial_access
                else "Jira does not provide authoritative financial values; unavailable amounts are shown explicitly."
                if live_jira
                else "Values use the latest persisted reporting snapshot, with legacy metadata identified explicitly; incompatible currencies are never aggregated.",
            },
        }

    @staticmethod
    def _insights(attention, health):
        findings = []
        if health.status in {"RED", "AMBER"}:
            findings.append(
                {
                    "id": "portfolio-health",
                    "finding": f"Portfolio health is {health.status.lower()}.",
                    "severity": health.status,
                    "confidence": "Deterministic",
                    "explanation": "Versioned weighted health calculation crossed its status threshold.",
                    "limitations": "Unavailable dimensions are excluded and reported as partial.",
                    "ruleVersion": "portfolio-health-v1",
                }
            )
        if attention:
            findings.append(
                {
                    "id": "attention-concentration",
                    "finding": f"{len(attention)} open items require prioritised review.",
                    "severity": attention[0]["severity"],
                    "confidence": "Deterministic",
                    "explanation": "Open RAID, dependency, and milestone records were ranked by impact, urgency, critical path, and age.",
                    "limitations": "Priority depends on the completeness of persisted due dates and classifications.",
                    "ruleVersion": "attention-v1",
                }
            )
        return findings
