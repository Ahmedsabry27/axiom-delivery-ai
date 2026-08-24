"""Idempotently seed persisted AX-CI01 canonical templates and connected demo records."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.database.models.ceremony import (
    Ceremony,
    CeremonyChecklistResponse,
    CeremonyTemplate,
    Lesson,
    LessonAdoption,
)
from app.database.models.meeting import Meeting
from app.database.session import SessionLocal

TENANT = "axiom-demo"
TYPES = [
    ("SPRINT_PLANNING", "Sprint Planning", 90),
    ("DAILY_SCRUM", "Daily Scrum", 15),
    ("BACKLOG_REFINEMENT", "Backlog Refinement", 60),
    ("SPRINT_REVIEW", "Sprint Review", 60),
    ("SPRINT_RETROSPECTIVE", "Sprint Retrospective", 75),
    ("SCRUM_OF_SCRUMS", "Scrum of Scrums", 45),
    ("RAID_REVIEW", "RAID Review", 45),
    ("DEPENDENCY_REVIEW", "Dependency Review", 45),
    ("RELEASE_READINESS_REVIEW", "Release Readiness Review", 60),
    ("PROGRAMME_DELIVERY_REVIEW", "Programme Delivery Review", 60),
    ("PORTFOLIO_REVIEW", "Portfolio Review", 90),
    ("QUARTERLY_PI_PLANNING", "Quarterly / PI Planning", 240),
    ("RELEASE_RETROSPECTIVE", "Release Retrospective", 90),
    ("LESSONS_LEARNED", "Project / Programme Lessons Learned", 90),
    ("POST_INCIDENT_REVIEW", "Incident / Post-Incident Review", 90),
]
ITEMS = [
    {
        "key": "before-evidence",
        "section": "BEFORE",
        "label": "Required metrics and evidence available",
        "description": "Authorized, current evidence is attached before the ceremony.",
        "required": True,
        "weight": 2,
        "evidenceRequired": True,
        "responsibleRole": "FACILITATOR",
    },
    {
        "key": "before-actions",
        "section": "BEFORE",
        "label": "Previous actions reviewed",
        "description": "Open and carried actions are available for review.",
        "required": True,
        "weight": 1,
        "responsibleRole": "OWNER",
    },
    {
        "key": "during-decisions",
        "section": "DURING",
        "label": "Required decisions recorded",
        "description": "Decision, rationale, evidence, and follow-up are captured.",
        "required": True,
        "weight": 2,
        "evidenceRequired": True,
        "responsibleRole": "DECISION_MAKER",
    },
    {
        "key": "during-risks",
        "section": "DURING",
        "label": "Risks and dependencies reviewed",
        "description": "Existing RAID and dependency records are used.",
        "required": True,
        "weight": 1,
        "responsibleRole": "FACILITATOR",
    },
    {
        "key": "after-actions",
        "section": "AFTER",
        "label": "Actions assigned with due dates",
        "description": "Actions reuse Action Center and include success measures.",
        "required": True,
        "weight": 2,
        "responsibleRole": "ACTION_OWNER",
    },
    {
        "key": "after-lessons",
        "section": "AFTER",
        "label": "Verified lessons prepared for review",
        "description": "Draft lessons remain human-reviewed before publication.",
        "required": False,
        "weight": 1,
        "evidenceRequired": True,
        "responsibleRole": "REVIEWER",
    },
]


def main():
    db = SessionLocal()
    try:
        templates = []
        for key, name, timebox in TYPES:
            row = (
                db.query(CeremonyTemplate)
                .filter_by(tenant_id=TENANT, family_key=key.lower(), template_version=1)
                .first()
            )
            if not row:
                row = CeremonyTemplate(
                    tenant_id=TENANT,
                    family_key=key.lower(),
                    name=name,
                    ceremony_type=key,
                    description=f"Canonical {name} checklist and evidence standard.",
                    purpose=f"Run an evidence-led {name} without scoring individuals.",
                    required_roles=["FACILITATOR", "OWNER", "DECISION_MAKER"],
                    recommended_timebox_minutes=timebox,
                    items=ITEMS,
                    required_evidence=[
                        "Meeting notes or transcript",
                        "Relevant delivery metrics",
                    ],
                    expected_decisions=["Scope and follow-up decisions"],
                    expected_outputs=[
                        "Reviewed decisions",
                        "Owned actions",
                        "Verified lessons",
                    ],
                    scoring_config={
                        "version": "ceremony-effectiveness-v1",
                        "weights": {
                            "preparation": 0.20,
                            "evidence": 0.15,
                            "decisionCompletion": 0.20,
                            "actionQuality": 0.15,
                            "previousActionClosure": 0.15,
                            "outcomeAchievement": 0.15,
                        },
                    },
                    template_version=1,
                    effective_date=datetime.now(UTC).date(),
                    owner_id="local-developer",
                    status="ACTIVE",
                )
                db.add(row)
                db.flush()
            templates.append(row)
        meetings = (
            db.query(Meeting)
            .filter_by(tenant_id=TENANT)
            .order_by(Meeting.scheduled_start.desc())
            .limit(13)
            .all()
        )
        ceremonies = []
        for index, template in enumerate(templates[:13]):
            meeting = meetings[index] if index < len(meetings) else None
            title = (
                meeting.title
                if meeting
                else f"{template.name} — Connected delivery review"
            )
            row = (
                db.query(Ceremony)
                .filter_by(
                    tenant_id=TENANT, title=title, ceremony_type=template.ceremony_type
                )
                .first()
            )
            if not row:
                row = Ceremony(
                    tenant_id=TENANT,
                    meeting_id=meeting.id if meeting else None,
                    template_id=template.id,
                    template_version=1,
                    template_snapshot={
                        "id": template.id,
                        "name": template.name,
                        "version": 1,
                        "items": ITEMS,
                    },
                    title=title,
                    ceremony_type=template.ceremony_type,
                    status=["COMPLETED", "PREPARING", "PENDING_REVIEW"][index % 3],
                    project_id=meeting.project_id if meeting else None,
                    programme_id=meeting.programme_id if meeting else None,
                    team_id=meeting.team_id if meeting else None,
                    scheduled_start=(
                        meeting.scheduled_start
                        if meeting
                        else datetime.now(UTC) + timedelta(days=index)
                    ),
                    facilitator_id="local-developer",
                    purpose=template.purpose,
                    agenda=["Evidence review", "Decisions", "Actions", "Lessons"],
                    score_snapshot={},
                    analysis_findings=[
                        {
                            "id": f"finding-{index}",
                            "finding": "Evidence coverage requires human review",
                            "severity": "AMBER",
                            "confidence": 0.82,
                            "evidence": [],
                            "explanation": "One or more required inputs are incomplete.",
                            "limitations": "Deterministic seed scenario; no individual scoring.",
                            "reviewStatus": "PENDING_REVIEW",
                        }
                    ],
                    themes=[{"theme": "Evidence quality", "count": index % 4 + 1}],
                )
                db.add(row)
                db.flush()
                for item in ITEMS:
                    status = (
                        "COMPLETED"
                        if index % 3 == 0 and not item.get("evidenceRequired")
                        else "EVIDENCE_REQUIRED"
                        if item.get("evidenceRequired")
                        else "NOT_STARTED"
                    )
                    db.add(
                        CeremonyChecklistResponse(
                            tenant_id=TENANT,
                            ceremony_id=row.id,
                            item_key=item["key"],
                            section=item["section"],
                            label=item["label"],
                            description=item["description"],
                            required=item["required"],
                            weight=item["weight"],
                            evidence_required=item.get("evidenceRequired", False),
                            responsible_role=item.get("responsibleRole"),
                            status=status,
                            evidence_refs=[],
                        )
                    )
            ceremonies.append(row)
        lesson = (
            db.query(Lesson)
            .filter_by(
                tenant_id=TENANT,
                title="Validate release evidence before readiness decisions",
            )
            .first()
        )
        if not lesson:
            lesson = Lesson(
                tenant_id=TENANT,
                ceremony_id=ceremonies[0].id,
                meeting_id=ceremonies[0].meeting_id,
                title="Validate release evidence before readiness decisions",
                category="Release",
                sentiment="NEGATIVE",
                status="PUBLISHED",
                context="Readiness recommendation preceded complete evidence.",
                expected_outcome="Evidence complete before decision.",
                actual_outcome="Missing evidence delayed approval.",
                root_cause="Evidence ownership was not explicit.",
                contributing_factors=[
                    "Late security evidence",
                    "Unowned checklist item",
                ],
                recommendation="Assign evidence owners during preparation.",
                evidence_refs=[
                    {"source": "ceremony", "id": ceremonies[0].id, "authorized": True}
                ],
                affected_entities=[],
                applicability=[{"type": "PROJECT", "id": "all"}],
                owner_id="local-developer",
                reviewer_id="local-developer",
                published_at=datetime.now(UTC),
            )
            db.add(lesson)
            db.flush()
            db.add(
                LessonAdoption(
                    tenant_id=TENANT,
                    lesson_id=lesson.id,
                    target_type="PROJECT",
                    target_id="cross-project",
                    owner_id="local-developer",
                    status="VERIFIED",
                    success_measure="All required release evidence available before review",
                    verified_benefit="Readiness decision completed without evidence rework",
                    evidence_refs=[{"source": "ceremony", "id": ceremonies[0].id}],
                )
            )
        db.commit()
        print(
            f"Ceremony Intelligence seeded: {len(templates)} templates, {len(ceremonies)} ceremonies, 1 published lesson"
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
