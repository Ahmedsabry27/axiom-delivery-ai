from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.database.models.delivery import (
    DeliveryDefect,
    DeliveryDependency,
    DeliveryDependencyEndpoint,
    DeliveryEvidence,
    DeliveryMilestone,
    DeliveryPortfolio,
    DeliveryProgramme,
    DeliveryProject,
    DeliveryRAIDItem,
    DeliveryRecommendation,
    DeliverySprint,
    DeliveryTeam,
    DeliveryWorkItem,
    DetectedDependencyCandidate,
    DetectedRAIDCandidate,
    ProposedAction,
)
from app.database.models.governance_workflow import ApprovalRequest
from app.delivery.intelligence import attention_score, sprint_predictability
from app.delivery.raid_intelligence import attention as raid_attention
from app.delivery.sprint_intelligence import (
    forecast,
    sprint_health,
    sprint_metrics,
    work_item_risk,
)


def _now() -> str:
    return datetime.now(UTC).isoformat()


class DeliveryReadService:
    """One tenant-scoped read model shared by delivery UI modules."""

    def __init__(self, db: Session, tenant_id: str, user_id: str):
        if not tenant_id or not user_id:
            raise ValueError("tenant and user identity are required")
        self.db = db
        self.tenant_id = tenant_id
        self.user_id = user_id

    def _all(self, model, *criteria):
        return list(
            self.db.scalars(
                select(model).where(model.tenant_id == self.tenant_id, *criteria)
            )
        )

    def command_center(self, context_id: str | None = None) -> dict:
        portfolios = self._all(DeliveryPortfolio)
        programmes = self._all(DeliveryProgramme)
        projects = self._all(DeliveryProject)
        # A connected Jira workspace is authoritative for the Command Center.
        # Seeded/manual records remain available to their own modules, but must not
        # be blended into live executive metrics.
        jira_projects = [row for row in projects if row.source_system == "JIRA"]
        if jira_projects:
            projects = jira_projects
            jira_programme_ids = {row.programme_id for row in projects}
            programmes = [
                row
                for row in programmes
                if row.id in jira_programme_ids and row.source_system == "JIRA"
            ]
            jira_portfolio_ids = {row.portfolio_id for row in programmes}
            portfolios = [
                row
                for row in portfolios
                if row.id in jira_portfolio_ids and row.source_system == "JIRA"
            ]

        scoped_projects = projects
        if context_id and context_id != "portfolio-all":
            portfolio = next((row for row in portfolios if row.id == context_id), None)
            programme = next((row for row in programmes if row.id == context_id), None)
            project = next((row for row in projects if row.id == context_id), None)
            if portfolio:
                programme_ids = {
                    row.id for row in programmes if row.portfolio_id == portfolio.id
                }
                scoped_projects = [
                    row for row in projects if row.programme_id in programme_ids
                ]
            elif programme:
                scoped_projects = [
                    row for row in projects if row.programme_id == programme.id
                ]
            elif project:
                scoped_projects = [project]
            # Unknown/stale browser context deliberately falls back to All delivery.
        projects = scoped_projects
        project_ids = {row.id for row in projects}
        live_jira = bool(jira_projects)
        sprints = self._all(
            DeliverySprint,
            DeliverySprint.project_id.in_(project_ids),
            *([DeliverySprint.source_system == "JIRA"] if live_jira else []),
        ) if project_ids else []
        work_items = self._all(
            DeliveryWorkItem,
            DeliveryWorkItem.project_id.in_(project_ids),
            *([DeliveryWorkItem.source_system == "JIRA"] if live_jira else []),
        ) if project_ids else []
        raid_items = self._all(
            DeliveryRAIDItem,
            DeliveryRAIDItem.project_id.in_(project_ids),
            DeliveryRAIDItem.status.not_in(
                ("COMPLETED", "CLOSED", "CANCELLED", "RESOLVED", "IMPLEMENTED")
            ),
            *([DeliveryRAIDItem.source_system == "JIRA"] if live_jira else []),
        ) if project_ids else []
        risks = [item for item in raid_items if item.item_type in {"RISK", "ISSUE"}]
        jira_risk_signals = [
            item
            for item in work_items
            if item.goal_critical
            and item.status not in {"DONE", "CLOSED", "COMPLETED", "RESOLVED"}
        ]
        jira_dependency_signals = [item for item in work_items if item.blocked]
        dependencies = self._all(
            DeliveryDependency,
            DeliveryDependency.project_id.in_(project_ids),
            DeliveryDependency.status.not_in(("RESOLVED", "CLOSED", "CANCELLED")),
            *([DeliveryDependency.source_system == "JIRA"] if live_jira else []),
        ) if project_ids else []
        milestones = self._all(
            DeliveryMilestone,
            DeliveryMilestone.project_id.in_(project_ids),
            DeliveryMilestone.status.not_in(("COMPLETED", "CANCELLED")),
            *([DeliveryMilestone.source_system == "JIRA"] if live_jira else []),
        ) if project_ids else []
        recommendations = self._all(
            DeliveryRecommendation,
            DeliveryRecommendation.status.not_in(("DISMISSED", "COMPLETED")),
        )
        if live_jira:
            # Recommendations have no source-system column. Do not leak seeded
            # advice into a live Jira workspace; a Jira evidence generator can
            # populate this collection explicitly in a later intelligence run.
            recommendations = []
        governed_actions = [] if live_jira else self._all(
            ProposedAction,
            ProposedAction.status.in_(
                ("PENDING_APPROVAL", "FAILED", "VERIFICATION_FAILED")
            ),
        )

        committed = sum(s.original_committed_points or 0 for s in sprints)
        completed = sum(s.completed_original_points or 0 for s in sprints)
        predictability = (
            sprint_predictability(committed, completed) if committed else None
        )
        status_scores = {
            "ACTIVE": 85,
            "PLANNED": 75,
            "AT_RISK": 45,
            "BLOCKED": 20,
            "COMPLETED": 100,
            "CANCELLED": 0,
        }
        sprint_scores_by_project = {}
        for sprint in sprints:
            committed_points = float(sprint.original_committed_points or 0)
            if committed_points:
                sprint_scores_by_project.setdefault(sprint.project_id, []).append(
                    min(
                        100,
                        float(sprint.completed_original_points or 0)
                        / committed_points
                        * 100,
                    )
                )
        scored = [
            round(sum(sprint_scores_by_project[project.id]) / len(sprint_scores_by_project[project.id]), 1)
            if sprint_scores_by_project.get(project.id)
            else status_scores.get(project.status, 50)
            for project in projects
        ]
        portfolio_value = round(sum(scored) / len(scored), 1) if scored else 0
        delivery_trend = []
        for sprint in sorted(
            (row for row in sprints if row.end_date and row.original_committed_points),
            key=lambda row: row.end_date,
        )[-12:]:
            sprint_committed = float(sprint.original_committed_points or 0)
            original_completed = float(sprint.completed_original_points or 0)
            total_completed = float(sprint.completed_points or 0)
            delivery_performance = round(
                min(100, (original_completed / sprint_committed) * 100), 1
            )
            scope_completed = round(
                min(100, (total_completed / sprint_committed) * 100), 1
            )
            plan_commitment = round(
                min(
                    100,
                    max(
                        60,
                        delivery_performance * 0.7
                        + (100 - min(40, float(sprint.scope_added_points or 0))) * 0.3,
                    ),
                ),
                1,
            )
            delivery_trend.append(
                {
                    "period": sprint.end_date.strftime("%d %b"),
                    "portfolioHealth": plan_commitment,
                    "sprintPredictability": delivery_performance,
                    "commitmentAchievement": scope_completed,
                }
            )
        trend_change = (
            round(
                delivery_trend[-1]["portfolioHealth"]
                - delivery_trend[-2]["portfolioHealth"],
                1,
            )
            if len(delivery_trend) >= 2
            else 0
        )
        predictability_change = (
            round(
                delivery_trend[-1]["sprintPredictability"]
                - delivery_trend[-2]["sprintPredictability"],
                1,
            )
            if len(delivery_trend) >= 2
            else 0
        )
        attention = []
        for item in jira_risk_signals:
            attention.append(
                {
                    "id": item.id,
                    "item": item.name,
                    "type": "Risk",
                    "impact": "High",
                    "status": item.status,
                    "owner": item.assignee_id or "Unassigned",
                    "dueDate": "",
                    "description": "High-priority incomplete work reported by Jira",
                    "score": 75,
                    "scoreBreakdown": [
                        "Jira priority is High or Highest",
                        "Work is not in a completed status",
                    ],
                    "route": None,
                }
            )
        for item in [*dependencies, *milestones]:
            due = (
                getattr(item, "required_by_date", None)
                or getattr(item, "due_date", None)
                or getattr(item, "planned_date", None)
            )
            urgency = 5 if due and due <= datetime.now(UTC).date() else 3
            score = attention_score(
                impact=5 if getattr(item, "impact", "") in {"HIGH", "CRITICAL"} else 3,
                urgency=urgency,
                critical_path=bool(
                    getattr(item, "critical_path", False)
                    or getattr(item, "critical", False)
                ),
                age_periods=1,
            )
            attention.append(
                {
                    "id": item.id,
                    "item": item.name,
                    "type": "Dependency"
                    if isinstance(item, DeliveryDependency)
                    else "Risk",
                    "impact": "High" if score.value >= 70 else "Medium",
                    "status": item.status,
                    "owner": item.owner_id or "Unassigned",
                    "dueDate": due.isoformat() if due else "",
                    "description": getattr(item, "description", None)
                    or "Persisted delivery record",
                    "score": score.value,
                    "scoreBreakdown": [
                        f"{name}: {value:g}" for name, value in score.factors.items()
                    ],
                    "route": f"/dependencies/{item.id}"
                    if isinstance(item, DeliveryDependency)
                    else None,
                }
            )
        for item in raid_items:
            score = raid_attention(item)
            attention.append(
                {
                    "id": item.id,
                    "item": item.name,
                    "type": item.item_type.title(),
                    "impact": score.band.title(),
                    "status": item.status,
                    "owner": item.owner_id
                    or item.validation_owner_id
                    or item.decision_owner_id
                    or "Unassigned",
                    "dueDate": (item.due_date or item.validation_due_date).isoformat()
                    if item.due_date or item.validation_due_date
                    else "",
                    "description": item.description or "Persisted RAID record",
                    "score": score.value,
                    "scoreBreakdown": list(score.reasons),
                    "route": f"/raid/{item.id}",
                }
            )
        for item in governed_actions:
            attention.append(
                {
                    "id": item.id,
                    "item": item.title or item.action_type,
                    "type": "Approval"
                    if item.status == "PENDING_APPROVAL"
                    else "Action",
                    "impact": item.risk_level.title(),
                    "status": item.status,
                    "owner": item.requester_id or "Unassigned",
                    "dueDate": item.expires_at.date().isoformat()
                    if item.expires_at
                    else "",
                    "description": item.failure_message
                    or item.description
                    or "Governed action requires attention",
                    "score": 90 if item.status != "PENDING_APPROVAL" else 70,
                    "scoreBreakdown": [
                        "Failed execution or verification requires intervention"
                        if item.status != "PENDING_APPROVAL"
                        else "Human approval is pending"
                    ],
                    "route": f"/actions/{item.id}",
                }
            )
        attention.sort(key=lambda item: item["score"], reverse=True)
        return {
            "generatedAt": _now(),
            "dataFreshness": {
                "calculatedAt": _now(),
                "source": "persisted",
                "limitations": ["Historical trend unavailable"],
            },
            "portfolioHealth": {
                "label": "Portfolio Health",
                "value": portfolio_value,
                "unit": "%",
                "status": "UNKNOWN"
                if not scored
                else ("Healthy" if portfolio_value >= 75 else "At Risk"),
                "detail": f"{len(projects)} Jira projects" if live_jira else f"{len(projects)} persisted projects",
                "change": trend_change,
                "changeLabel": "vs previous sprint",
                "state": "missing" if not scored else "ready",
            },
            "sprintPredictability": {
                "label": "Sprint Predictability",
                "value": predictability.value if predictability else 0,
                "unit": "%",
                "status": predictability.status if predictability else "UNKNOWN",
                "detail": "Jira original commitment" if live_jira else "Persisted original commitment",
                "change": predictability_change,
                "changeLabel": "vs previous sprint",
                "state": "ready" if predictability else "missing",
            },
            "openRisks": {
                "label": "Open Risks",
                "value": len(risks) + len(jira_risk_signals),
                "status": "Critical"
                if any(r.impact == "CRITICAL" for r in risks)
                else "Open",
                "detail": f"{len(jira_risk_signals)} high-priority Jira items" if live_jira else f"{len(risks)} persisted",
                "change": 0,
                "changeLabel": "insufficient history",
                "state": "ready",
            },
            "dependencies": {
                "label": "Dependencies",
                "value": len(dependencies) + len(jira_dependency_signals),
                "status": "Warning" if dependencies or jira_dependency_signals else "Healthy",
                "detail": f"{len(jira_dependency_signals)} Jira blockers" if live_jira else f"{sum(1 for d in dependencies if d.critical_path)} critical",
                "change": 0,
                "changeLabel": "insufficient history",
                "state": "ready",
            },
            "deliveryTrend": delivery_trend,
            "attentionItems": attention[:50],
            "recommendations": [
                {
                    "id": r.id,
                    "title": r.title,
                    "priority": r.priority.title(),
                    "explanation": r.explanation,
                    "affectedArea": f"{r.entity_type}:{r.entity_id}",
                    "evidenceCount": self.db.scalar(
                        select(func.count())
                        .select_from(DeliveryEvidence)
                        .where(
                            DeliveryEvidence.tenant_id == self.tenant_id,
                            DeliveryEvidence.entity_type == r.entity_type,
                            DeliveryEvidence.entity_id == r.entity_id,
                        )
                    )
                    or 0,
                    "confidence": r.confidence,
                    "status": r.status.title(),
                    "generatedAt": r.created_at.isoformat(),
                }
                for r in recommendations[:50]
            ],
            "contexts": [
                {"id": p.id, "name": p.name, "type": "Portfolio"} for p in portfolios
            ]
            + [{"id": p.id, "name": p.name, "type": "Programme"} for p in programmes]
            + [{"id": p.id, "name": p.name, "type": "Project"} for p in scoped_projects],
            "safeActions": {"mode": "proposal_only", "externalWrites": False},
        }

    def my_day(self) -> dict:
        live_jira = bool(self._all(DeliveryProject, DeliveryProject.source_system == "JIRA"))
        actions = [] if live_jira else self._all(
            ProposedAction,
            ProposedAction.owner_id == self.user_id,
            ProposedAction.status.not_in(("COMPLETED", "CANCELLED")),
        )
        dependencies = [] if live_jira else self._all(
            DeliveryDependency,
            DeliveryDependency.owner_id == self.user_id,
            DeliveryDependency.status.not_in(("RESOLVED", "CLOSED")),
        )
        work = self._all(
            DeliveryWorkItem,
            DeliveryWorkItem.assignee_id == self.user_id,
            DeliveryWorkItem.status.not_in(("DONE", "CLOSED", "COMPLETED", "RESOLVED", "CANCELLED")),
            *([DeliveryWorkItem.source_system == "JIRA"] if live_jira else [DeliveryWorkItem.blocked.is_(True)]),
        )
        milestones = [] if live_jira else self._all(
            DeliveryMilestone,
            DeliveryMilestone.owner_id == self.user_id,
            DeliveryMilestone.status.not_in(("COMPLETED", "CANCELLED")),
        )
        raid_items = [] if live_jira else self._all(
            DeliveryRAIDItem,
            DeliveryRAIDItem.owner_id == self.user_id,
            DeliveryRAIDItem.status.not_in(
                ("COMPLETED", "CLOSED", "CANCELLED", "RESOLVED", "IMPLEMENTED")
            ),
        )
        candidates = [] if live_jira else self._all(
            DetectedRAIDCandidate,
            DetectedRAIDCandidate.status.in_(("DETECTED", "UNDER_REVIEW")),
        )
        dependency_candidates = [] if live_jira else self._all(
            DetectedDependencyCandidate,
            DetectedDependencyCandidate.status.in_(("DETECTED", "UNDER_REVIEW")),
        )
        assigned_approvals = [] if live_jira else self._all(
            ApprovalRequest,
            ApprovalRequest.proposed_action_id.is_not(None),
            ApprovalRequest.assigned_approver_id == self.user_id,
            ApprovalRequest.status == "PENDING",
        )
        items = []
        for record, kind, due, summary in [
            *[
                (
                    a,
                    "Approval" if a.status == "PENDING_APPROVAL" else "Action",
                    a.due_date,
                    a.content,
                )
                for a in actions
            ],
            *[
                (d, "Attention", d.required_by_date, d.description or "Open dependency")
                for d in dependencies
            ],
            *[(w, "Attention", None, "Blocked Jira work" if w.blocked else "Assigned Jira sprint work") for w in work],
            *[
                (
                    m,
                    "Attention",
                    m.forecast_date or m.planned_date,
                    m.description or "Delivery milestone",
                )
                for m in milestones
            ],
            *[
                (
                    item,
                    item.item_type.title(),
                    item.due_date or item.validation_due_date or item.review_date,
                    item.description or "RAID item requires attention",
                )
                for item in raid_items
            ],
            *[
                (
                    candidate,
                    "RAID Candidate",
                    candidate.suggested_due_date,
                    f"Human review required: {candidate.description}",
                )
                for candidate in candidates
            ],
            *[
                (
                    candidate,
                    "Dependency Candidate",
                    candidate.suggested_required_by_date,
                    f"Human review required: {candidate.description}",
                )
                for candidate in dependency_candidates
            ],
        ]:
            items.append(
                {
                    "id": record.id,
                    "title": getattr(record, "name", None)
                    or getattr(record, "action_type", "Action"),
                    "kind": kind,
                    "dueDate": due.isoformat() if due else None,
                    "priority": "Critical"
                    if getattr(record, "critical_path", False)
                    or getattr(record, "goal_critical", False)
                    else "High",
                    "context": getattr(record, "project_id", "Delivery"),
                    "summary": summary,
                    "route": (
                        f"/dependencies/{record.id}"
                        if isinstance(record, DeliveryDependency)
                        else "/dependencies?view=detected"
                        if isinstance(record, DetectedDependencyCandidate)
                        else f"/actions/{record.id}"
                        if isinstance(record, ProposedAction)
                        else None
                    ),
                }
            )
        for approval in assigned_approvals:
            summary = approval.safe_action_summary or {}
            items.append(
                {
                    "id": approval.id,
                    "title": summary.get("title", "Action approval"),
                    "kind": "Approval",
                    "dueDate": approval.expires_at.isoformat(),
                    "priority": "Critical"
                    if approval.risk_level == "RESTRICTED"
                    else "High",
                    "context": summary.get("targetSystem", "Delivery"),
                    "summary": "Review evidence, policy, and exact payload",
                    "route": f"/approvals/{approval.id}",
                }
            )
        evidence_count = int(
            self.db.scalar(
                select(func.count())
                .select_from(DeliveryEvidence)
                .where(DeliveryEvidence.tenant_id == self.tenant_id)
            )
            or 0
        )
        briefings = []
        if items:
            critical_count = sum(item["priority"] == "Critical" for item in items)
            briefings.append(
                {
                    "id": "daily-attention",
                    "title": "Daily delivery attention briefing",
                    "summary": (
                        f"{len(items)} owned items require review today; "
                        f"{critical_count} are on a critical delivery path."
                    ),
                    "evidenceCount": evidence_count,
                }
            )
        if dependencies:
            highest_dependency = sorted(
                dependencies,
                key=lambda row: (
                    not row.critical_path,
                    row.required_by_date is None,
                    row.required_by_date,
                ),
            )[0]
            briefings.append(
                {
                    "id": f"dependency-{highest_dependency.id}",
                    "title": "Dependency intervention briefing",
                    "summary": (
                        f"{highest_dependency.name} remains {highest_dependency.status.lower()} "
                        "and should be reviewed before the next release decision."
                    ),
                    "evidenceCount": sum(
                        evidence.dependency_id == highest_dependency.id
                        for evidence in self._all(DeliveryEvidence)
                    ),
                }
            )
        if actions or assigned_approvals:
            briefings.append(
                {
                    "id": "governed-decisions",
                    "title": "Governed decisions awaiting attention",
                    "summary": (
                        f"{len(actions)} assigned actions and {len(assigned_approvals)} "
                        "approval requests are available for controlled review."
                    ),
                    "evidenceCount": evidence_count,
                }
            )
        return {
            "generatedAt": _now(),
            "focusScore": round(100 - (sum(item["priority"] == "Critical" for item in items) / max(1, len(items))) * 50),
            "items": items,
            "briefings": briefings,
            "capabilities": {"schedule": False, "briefings": True},
            "dataFreshness": {"calculatedAt": _now(), "source": "JIRA" if live_jira else "persisted"},
        }

    def sprint_detail(self, sprint_id: str) -> dict | None:
        sprint = self.db.scalar(
            select(DeliverySprint).where(
                DeliverySprint.tenant_id == self.tenant_id,
                DeliverySprint.id == sprint_id,
            )
        )
        if sprint is None:
            return None
        team = self.db.scalar(
            select(DeliveryTeam).where(
                DeliveryTeam.tenant_id == self.tenant_id,
                DeliveryTeam.id == sprint.team_id,
            )
        )
        project = self.db.scalar(
            select(DeliveryProject).where(
                DeliveryProject.tenant_id == self.tenant_id,
                DeliveryProject.id == sprint.project_id,
            )
        )
        work = self._all(DeliveryWorkItem, DeliveryWorkItem.sprint_id == sprint.id)
        defects = self._all(DeliveryDefect, DeliveryDefect.sprint_id == sprint.id)
        raid_items = self._all(
            DeliveryRAIDItem,
            DeliveryRAIDItem.sprint_id == sprint.id,
            DeliveryRAIDItem.status.not_in(
                ("COMPLETED", "CLOSED", "CANCELLED", "RESOLVED", "IMPLEMENTED")
            ),
        )
        work_ids = {item.id for item in work}
        dependency_ids = {
            row[0]
            for row in self.db.execute(
                select(DeliveryDependencyEndpoint.dependency_id).where(
                    DeliveryDependencyEndpoint.tenant_id == self.tenant_id,
                    (
                        (DeliveryDependencyEndpoint.entity_type == "SPRINT")
                        & (DeliveryDependencyEndpoint.entity_id == sprint.id)
                    )
                    | (
                        (DeliveryDependencyEndpoint.entity_type == "WORK_ITEM")
                        & (DeliveryDependencyEndpoint.entity_id.in_(work_ids))
                    ),
                )
            )
        }
        dependencies = (
            self._all(DeliveryDependency, DeliveryDependency.id.in_(dependency_ids))
            if dependency_ids
            else []
        )
        evidence = self._all(
            DeliveryEvidence,
            DeliveryEvidence.entity_type == "SPRINT",
            DeliveryEvidence.entity_id == sprint.id,
        )
        recommendations = self._all(
            DeliveryRecommendation,
            DeliveryRecommendation.entity_type == "SPRINT",
            DeliveryRecommendation.entity_id == sprint.id,
        )
        blocked = [item for item in work if item.blocked]
        blocked_points = sum(item.story_points or 0 for item in blocked)
        active_points = sum(
            item.story_points or 0
            for item in work
            if item.status not in ("COMPLETED", "CANCELLED")
        )
        blocker_ages = [
            max(
                0,
                (
                    datetime.now(UTC)
                    - (
                        item.blocked_since.replace(tzinfo=UTC)
                        if item.blocked_since.tzinfo is None
                        else item.blocked_since
                    )
                ).days,
            )
            for item in blocked
            if item.blocked_since
        ]
        metrics = sprint_metrics(
            original_points=sprint.original_committed_points,
            completed_original=sprint.completed_original_points,
            completed_total=sprint.completed_points,
            scope_added=sprint.scope_added_points,
            scope_removed=sprint.scope_removed_points,
            blocked_points=blocked_points,
            active_points=active_points,
            blocker_ages=blocker_ages,
            defects=len(defects),
            completed_items=sum(1 for item in work if item.status == "COMPLETED"),
        )
        dimensions = {
            "delivery_progress": metrics["commitment_achievement"]["value"],
            "goal_confidence": 30
            if any(item.goal_critical for item in blocked)
            or any(
                item.item_type == "RISK"
                and (item.residual_exposure_band or item.exposure_band) == "CRITICAL"
                for item in raid_items
            )
            else metrics["commitment_achievement"]["value"],
            "blocked_work": max(0, 100 - (metrics["blocked_work_ratio"]["value"] or 0)),
            "scope_stability": max(
                0, 100 - (metrics["scope_change_rate"]["value"] or 0)
            ),
            "dependency_health": 40
            if any(
                d.critical_path and d.status not in ("RESOLVED", "CLOSED")
                for d in dependencies
            )
            else 100,
            "backlog_readiness": None,
            "quality": max(0, 100 - len(defects) * 10),
        }
        health = sprint_health(dimensions)
        elapsed = (
            max(1, (datetime.now(UTC).date() - sprint.start_date).days + 1)
            if sprint.start_date
            else 1
        )
        total = (
            max(1, (sprint.end_date - sprint.start_date).days + 1)
            if sprint.start_date and sprint.end_date
            else elapsed
        )
        historical = [
            s.completed_points
            for s in self._all(
                DeliverySprint,
                DeliverySprint.team_id == sprint.team_id,
                DeliverySprint.status == "COMPLETED",
                DeliverySprint.id != sprint.id,
            )
            if s.completed_points is not None
        ]
        prediction = forecast(
            completed=sprint.completed_points,
            elapsed_days=elapsed,
            total_days=total,
            historical_completed=historical,
            original_points=sprint.original_committed_points,
            blocked_points=blocked_points,
            scope_added=sprint.scope_added_points,
        )
        item_rows = [
            {
                "id": item.id,
                "title": item.name,
                "status": item.status,
                "points": item.story_points or 0,
                "owner": item.assignee_id or "Unassigned",
                "blockedDays": next(
                    (
                        age
                        for candidate, age in zip(blocked, blocker_ages, strict=False)
                        if candidate.id == item.id
                    ),
                    0,
                ),
                "goalCritical": item.goal_critical,
                **work_item_risk(
                    blocked_days=next(
                        (
                            age
                            for candidate, age in zip(
                                blocked, blocker_ages, strict=False
                            )
                            if candidate.id == item.id
                        ),
                        0,
                    ),
                    goal_critical=item.goal_critical,
                    remaining_points=item.story_points or 0,
                    days_remaining=max(total - elapsed, 0),
                    dependency=bool(dependencies),
                ),
                "readinessGaps": [],
                "evidence": [],
            }
            for item in work
        ]
        predictability = metrics["predictability"]["value"]
        summary = {
            "id": sprint.id,
            "name": sprint.name,
            "team": team.name if team else "Unknown",
            "project": project.name if project else "Unknown",
            "goal": sprint.goal,
            "day": min(elapsed, total),
            "totalDays": total,
            "health": health["status"],
            "committed": sprint.original_committed_points,
            "completed": sprint.completed_points,
            "forecast": prediction["completed_points"],
            "predictability": predictability,
            "blocked": blocked_points,
            "scopeChange": sprint.scope_added_points + sprint.scope_removed_points,
            "endDate": sprint.end_date.isoformat() if sprint.end_date else "",
            "primaryRisk": blocked[0].name if blocked else "No persisted blocker",
        }
        return {
            **summary,
            "startDate": sprint.start_date.isoformat() if sprint.start_date else "",
            "sourceSystem": sprint.source_system,
            "lastUpdated": sprint.updated_at.isoformat(),
            "calculatedAt": _now(),
            "mode": "api",
            "metrics": metrics,
            "healthScore": health["score"],
            "healthDimensions": [
                {"name": name, "score": score, "weight": 0}
                for name, score in health["dimensions"].items()
            ],
            "forecastDetail": prediction,
            "burndown": [],
            "workItems": item_rows,
            "atRisk": item_rows,
            "blockers": [
                {
                    "id": item.id,
                    "title": item.name,
                    "age": age,
                    "owner": item.assignee_id or "Unassigned",
                    "impact": "Goal critical" if item.goal_critical else "Flow",
                }
                for item, age in zip(blocked, blocker_ages, strict=False)
            ],
            "readiness": {
                "score": 0,
                "ready": 0,
                "total": len(work),
                "gaps": ["Readiness criteria are not persisted"],
            },
            "quality": {
                "defects": len(defects),
                "escaped": sum(1 for defect in defects if defect.escaped),
                "qaQueue": 0,
                "automationCoverage": 0,
            },
            "antiPatterns": [],
            "recommendations": [
                {
                    "id": r.id,
                    "title": r.title,
                    "priority": r.priority,
                    "evidenceCount": 0,
                    "explanation": r.explanation,
                }
                for r in recommendations
            ],
            "raidItems": [
                {
                    "id": item.id,
                    "reference": item.reference,
                    "title": item.name,
                    "type": item.item_type,
                    "status": item.status,
                    "exposure": item.residual_exposure_band
                    or item.exposure_band
                    or "UNKNOWN",
                    "owner": item.owner_id or "Unassigned",
                    "evidenceCount": self.db.scalar(
                        select(func.count())
                        .select_from(DeliveryEvidence)
                        .where(
                            DeliveryEvidence.tenant_id == self.tenant_id,
                            DeliveryEvidence.entity_type == "RAID",
                            DeliveryEvidence.entity_id == item.id,
                        )
                    )
                    or 0,
                }
                for item in raid_items
            ],
            "dependencies": [
                {
                    "id": item.id,
                    "reference": item.reference,
                    "name": item.name,
                    "status": item.status,
                    "owner": item.owner_id or "Unassigned",
                    "providerOwner": item.provider_owner_id or "Unassigned",
                    "requiredByDate": item.required_by_date.isoformat()
                    if item.required_by_date
                    else None,
                    "forecastResolutionDate": item.forecast_resolution_date.isoformat()
                    if item.forecast_resolution_date
                    else None,
                    "criticalPath": item.critical_path,
                    "route": f"/dependencies/{item.id}",
                }
                for item in dependencies
            ],
            "comparison": [],
            "evidence": [
                {
                    "id": e.id,
                    "tenantId": e.tenant_id,
                    "sourceType": e.source_type,
                    "sourceSystem": e.source_system,
                    "sourceRecordId": e.source_record_id,
                    "title": e.title,
                    "summary": e.summary,
                    "capturedAt": e.captured_at.isoformat(),
                }
                for e in evidence
            ],
            "limitations": ["No persisted transition history for burndown"],
        }

    def sprint_list(self, *, limit: int, offset: int) -> dict:
        jira_rows = self._all(DeliverySprint, DeliverySprint.source_system == "JIRA")
        rows = (jira_rows or self._all(DeliverySprint))[offset : offset + limit]
        items = [self.sprint_detail(row.id) for row in rows]
        summaries = [
            {
                key: item[key]
                for key in (
                    "id",
                    "name",
                    "team",
                    "project",
                    "goal",
                    "day",
                    "totalDays",
                    "health",
                    "committed",
                    "completed",
                    "forecast",
                    "predictability",
                    "blocked",
                    "scopeChange",
                    "endDate",
                    "primaryRisk",
                    "sourceSystem",
                )
            }
            for item in items
            if item
        ]
        total = len(jira_rows) if jira_rows else int(
            self.db.scalar(
                select(func.count()).select_from(DeliverySprint).where(
                    DeliverySprint.tenant_id == self.tenant_id
                )
            ) or 0
        )
        return {
            "tenantId": self.tenant_id,
            "items": summaries,
            "total": total,
            "generatedAt": _now(),
            "mode": "api",
        }
