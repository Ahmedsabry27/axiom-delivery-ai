"""Create an idempotent OKR view backed by synchronized Jira delivery evidence."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import NAMESPACE_URL, uuid5

from app.agents.application_service import AgentIdentity
from app.agile_intelligence.service import AgileIntelligenceService
from app.database.models.agile_intelligence import AgileKeyResult, AgileObjective
from app.database.models.delivery import DeliveryPortfolio, DeliverySprint
from app.database.session import SessionLocal

TENANT = "axiom-demo"


def stable(kind: str, value: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"axiom:{TENANT}:jira-okr:{kind}:{value}"))


def status(value: float | None, target: float, higher_is_better: bool = True) -> str:
    if value is None:
        return "AT_RISK"
    achieved = value >= target if higher_is_better else value <= target
    return "ACHIEVED" if achieved else "AT_RISK"


def main() -> None:
    db = SessionLocal()
    try:
        identity = AgentIdentity(
            actor_id="Ahmed Sabry",
            tenant_id=TENANT,
            permissions=frozenset({"agile.metrics.read"}),
            groups=frozenset(),
        )
        service = AgileIntelligenceService(db, identity)
        metrics, _ = service._live_delivery_metrics("PORTFOLIO", None)
        portfolio = (
            db.query(DeliveryPortfolio)
            .filter_by(tenant_id=TENANT, source_system="JIRA")
            .order_by(DeliveryPortfolio.name)
            .first()
        )
        sprints = (
            db.query(DeliverySprint)
            .filter_by(tenant_id=TENANT, source_system="JIRA")
            .all()
        )
        today = datetime.now(UTC).date()
        start_date = min(
            (row.start_date for row in sprints if row.start_date), default=today
        )
        target_date = max(
            (row.end_date for row in sprints if row.end_date),
            default=today + timedelta(days=90),
        )
        if target_date < today:
            target_date = today + timedelta(days=90)
        related_entities = (
            [
                {
                    "type": "PORTFOLIO",
                    "id": portfolio.id,
                    "name": portfolio.name,
                    "externalId": portfolio.external_id,
                    "url": portfolio.source_url,
                }
            ]
            if portfolio
            else []
        )
        specs = (
            (
                "predictability",
                "Improve delivery predictability",
                "Increase the percentage of originally committed Jira scope completed in its sprint.",
                (
                    (
                        "commitment_achievement",
                        "Raise commitment achievement",
                        80.0,
                        True,
                    ),
                    ("carryover_rate", "Reduce carryover", 20.0, False),
                ),
            ),
            (
                "flow",
                "Improve delivery flow",
                "Improve throughput while reducing unresolved work using synchronized Jira workflow evidence.",
                (
                    ("throughput", "Sustain completed-item throughput", 30.0, True),
                    ("work_in_progress", "Reduce work in progress", 40.0, False),
                ),
            ),
            (
                "readiness",
                "Strengthen backlog readiness",
                "Ensure Jira work is estimated, outcome-linked and has explicit acceptance criteria.",
                (
                    (
                        "acceptance_criteria_coverage",
                        "Acceptance criteria coverage",
                        95.0,
                        True,
                    ),
                    ("estimate_coverage", "Estimate coverage", 95.0, True),
                    ("outcome_linkage", "Outcome linkage", 85.0, True),
                ),
            ),
            (
                "evidence",
                "Increase delivery evidence coverage",
                "Maintain traceable Jira source records and dependency evidence for portfolio decisions.",
                (
                    ("evidence_coverage", "Delivery evidence coverage", 95.0, True),
                    (
                        "dependency_identification",
                        "Dependency identification",
                        80.0,
                        True,
                    ),
                ),
            ),
        )
        for slug, title, description, key_result_specs in specs:
            objective_id = stable("objective", slug)
            primary_metric = metrics[key_result_specs[0][0]]
            row = (
                db.query(AgileObjective)
                .filter_by(tenant_id=TENANT, id=objective_id)
                .first()
            )
            values = {
                "title": title,
                "description": description,
                "level": "PORTFOLIO",
                "owner_id": "Ahmed Sabry",
                "contributors": ["Jira delivery teams"],
                "start_date": start_date,
                "target_date": target_date,
                "status": status(
                    primary_metric["value"],
                    key_result_specs[0][2],
                    key_result_specs[0][3],
                ),
                "confidence": 90.0 if primary_metric["value"] is not None else None,
                "baseline": primary_metric["value"],
                "target": key_result_specs[0][2],
                "current_value": primary_metric["value"],
                "unit": primary_metric["unit"],
                "related_metrics": [item[0] for item in key_result_specs],
                "related_entities": related_entities,
                "evidence_refs": primary_metric["evidence"],
                "risks": [],
                "dependencies": [],
                "suggested_target": True,
            }
            if row is None:
                row = AgileObjective(id=objective_id, tenant_id=TENANT, **values)
                db.add(row)
            else:
                for key, value in values.items():
                    setattr(row, key, value)
                row.version += 1
            db.flush()
            db.query(AgileKeyResult).filter_by(
                tenant_id=TENANT, objective_id=objective_id
            ).delete(synchronize_session=False)
            for (
                metric_key,
                key_result_title,
                target,
                higher_is_better,
            ) in key_result_specs:
                metric = metrics[metric_key]
                db.add(
                    AgileKeyResult(
                        id=stable("key-result", f"{slug}:{metric_key}"),
                        tenant_id=TENANT,
                        objective_id=objective_id,
                        title=key_result_title,
                        baseline=metric["value"],
                        target=target,
                        current_value=metric["value"],
                        unit=metric["unit"],
                        status=status(metric["value"], target, higher_is_better),
                        confidence=90.0 if metric["value"] is not None else None,
                        metric_key=metric_key,
                        evidence_refs=metric["evidence"],
                    )
                )
        db.commit()
        print(
            f"Jira-backed Agile OKRs synchronized: {len(specs)} objectives at "
            f"{datetime.now(UTC).isoformat()}"
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
