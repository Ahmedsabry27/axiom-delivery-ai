import hashlib
import os
from datetime import UTC, datetime, timedelta

from app.database.models.knowledge import (
    KnowledgeDecision,
    KnowledgeItem,
    KnowledgeItemVersion,
    KnowledgeTemplate,
)
from app.database.session import SessionLocal

TENANT = "axiom-demo"
ACTOR = "local-developer"
ITEMS = [
    (
        "Release dependency playbook",
        "DELIVERY_GUIDANCE",
        "APPROVED",
        "APPROVED_GUIDANCE",
        "CURRENT",
        "CONFLUENCE",
        "Use evidence gates and named owners to resolve cross-team release dependencies.",
    ),
    (
        "Atlas 3.2 readiness decision rationale",
        "DELIVERY_DECISION",
        "PUBLISHED",
        "HUMAN_VERIFIED",
        "CURRENT",
        "JIRA",
        "The release proceeds only after identity token-exchange evidence is verified.",
    ),
    (
        "Identity integration retrospective",
        "RETROSPECTIVE_INSIGHT",
        "PENDING_REVIEW",
        "SOURCE_VERIFIED",
        "CURRENT",
        "MICROSOFT_TEAMS",
        "Early contract testing reduced late release risk; reuse the dependency workshop pattern.",
    ),
    (
        "Legacy programme status procedure",
        "STANDARD_OPERATING_PROCEDURE",
        "SUPERSEDED",
        "SUPERSEDED",
        "STALE",
        "CONFLUENCE",
        "Historical procedure retained for audit; use the current delivery playbook.",
    ),
    (
        "Executive investment assumptions",
        "PORTFOLIO_DOCUMENT",
        "APPROVED",
        "HUMAN_VERIFIED",
        "REVIEW_DUE",
        "AXIOM",
        "Restricted assumptions supporting FY27 investment decisions.",
    ),
    (
        "Sprint evidence capture guide",
        "PLAYBOOK",
        "PUBLISHED",
        "APPROVED_GUIDANCE",
        "CURRENT",
        "JIRA",
        "Capture issue, test, review, and approval evidence before sprint closure.",
    ),
    (
        "Dependency resolution pattern",
        "TECHNICAL_REFERENCE",
        "PUBLISHED",
        "SOURCE_VERIFIED",
        "CURRENT",
        "CONFLUENCE",
        "Map provider and consumer milestones, owners, dates, and acceptance evidence.",
    ),
    (
        "Release retrospective lesson",
        "LESSON_LEARNED",
        "PENDING_REVIEW",
        "UNVERIFIED",
        "UNKNOWN",
        "OUTLOOK_CALENDAR",
        "Draft lesson awaiting human verification and evidence review.",
    ),
]
TEMPLATES = [
    "Lesson learned",
    "Architecture decision",
    "Delivery decision",
    "Retrospective summary",
    "Sprint review summary",
    "Release readiness evidence",
    "Project closure report",
    "RAID review",
    "Dependency resolution",
    "Meeting summary",
    "Programme status report",
    "Portfolio review",
    "Incident review",
    "Standard operating procedure",
    "Delivery playbook",
]


def main():
    if os.getenv("APP_ENV", "development").lower() not in {"development", "test"}:
        raise SystemExit("Knowledge demo seed is development/test only")
    with SessionLocal() as db:
        for i, (title, typ, status, trust, fresh, source, content) in enumerate(ITEMS):
            row = (
                db.query(KnowledgeItem).filter_by(tenant_id=TENANT, title=title).first()
            )
            fp = hashlib.sha256(content.encode()).hexdigest()
            if not row:
                row = KnowledgeItem(
                    tenant_id=TENANT,
                    title=title,
                    item_type=typ,
                    summary=content,
                    content=f"# {title}\n\n{content}\n\n## Evidence boundary\nOnly authorized source references may be used.",
                    status=status,
                    trust_status=trust,
                    freshness_status=fresh,
                    access_classification="RESTRICTED"
                    if "Executive" in title
                    else "INTERNAL",
                    source_system=source,
                    source_record_id=f"KN-DEMO-{i + 1:03}",
                    source_url=None,
                    owner_id=ACTOR,
                    reviewers=["delivery-governance"],
                    tags=["delivery", "evidence", typ.lower()],
                    context={
                        "portfolio": "Digital Transformation Portfolio",
                        "project": "Atlas Platform Modernisation",
                    },
                    content_fingerprint=fp,
                    current_version=1,
                    evidence_coverage=80 if trust != "UNVERIFIED" else None,
                    last_synchronized_at=datetime.now(UTC) - timedelta(hours=i),
                    last_verified_at=datetime.now(UTC) - timedelta(days=i)
                    if trust in {"HUMAN_VERIFIED", "APPROVED_GUIDANCE"}
                    else None,
                    next_review_at=datetime.now(UTC) + timedelta(days=90 - i),
                    created_by=ACTOR,
                    updated_by=ACTOR,
                )
                db.add(row)
                db.flush()
                db.add(
                    KnowledgeItemVersion(
                        tenant_id=TENANT,
                        item_id=row.id,
                        version_number=1,
                        title=title,
                        summary=content,
                        content=row.content,
                        content_fingerprint=fp,
                        change_summary="Connected demonstration version",
                        author_id=ACTOR,
                        review_status=status,
                    )
                )
        for name in TEMPLATES:
            key = name.upper().replace(" ", "_")
            if (
                not db.query(KnowledgeTemplate)
                .filter_by(tenant_id=TENANT, family_key=key, template_version=1)
                .first()
            ):
                db.add(
                    KnowledgeTemplate(
                        tenant_id=TENANT,
                        family_key=key,
                        name=name,
                        template_type=key,
                        description=f"Governed {name.lower()} template",
                        schema={
                            "sections": ["Context", "Evidence", "Outcome", "Review"]
                        },
                        template_version=1,
                        status="PUBLISHED",
                        owner_id=ACTOR,
                    )
                )
        if (
            not db.query(KnowledgeDecision)
            .filter_by(
                tenant_id=TENANT, title="Proceed with Atlas 3.2 conditional release"
            )
            .first()
        ):
            db.add(
                KnowledgeDecision(
                    tenant_id=TENANT,
                    title="Proceed with Atlas 3.2 conditional release",
                    statement="Proceed after identity evidence is verified.",
                    rationale="The controlled dependency plan and approval evidence reduce release exposure.",
                    selected_option="Conditional release",
                    options=["Delay", "Conditional release", "Full release"],
                    status="ACTIVE",
                    owner_id=ACTOR,
                    context={"release": "Atlas 3.2"},
                    evidence_ids=[],
                )
            )
        db.commit()
        print(
            f"Knowledge Intelligence seeded: {len(ITEMS)} items, {len(TEMPLATES)} templates, 1 decision"
        )


if __name__ == "__main__":
    main()
