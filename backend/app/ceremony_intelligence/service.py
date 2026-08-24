from __future__ import annotations

from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.agents.application_service import AgentIdentity
from app.audit.events import append_audit_event
from app.database.models.ceremony import (
    Ceremony,
    CeremonyChecklistResponse,
    CeremonyTemplate,
    Lesson,
    LessonAdoption,
)
from app.database.models.meeting import Meeting, MeetingFinding

CHECKLIST_STATUSES = {
    "NOT_STARTED",
    "IN_PROGRESS",
    "COMPLETED",
    "MISSING",
    "BLOCKED",
    "EVIDENCE_REQUIRED",
    "NOT_APPLICABLE",
}
CEREMONY_STATUSES = {
    "PLANNED",
    "PREPARING",
    "READY",
    "IN_PROGRESS",
    "PENDING_REVIEW",
    "COMPLETED",
    "CANCELLED",
}
LESSON_TRANSITIONS = {
    "DRAFT": {"IN_REVIEW"},
    "IN_REVIEW": {"REVIEWED", "REJECTED"},
    "REVIEWED": {"PUBLISHED", "REJECTED"},
    "PUBLISHED": {"SUPERSEDED", "RETIRED"},
}
EFFECTIVENESS_WEIGHTS = {
    "preparation": 0.20,
    "evidence": 0.15,
    "decision_completion": 0.20,
    "action_quality": 0.15,
    "previous_action_closure": 0.15,
    "outcome_achievement": 0.15,
}


def error(status, code, message):
    return HTTPException(status, {"code": code, "message": message})


def checklist_scores(items):
    eligible = [x for x in items if x.status != "NOT_APPLICABLE"]
    total = sum(x.weight for x in eligible)
    completed = sum(x.weight for x in eligible if x.status == "COMPLETED")
    evidence_items = [x for x in eligible if x.evidence_required]
    covered = sum(
        x.status == "COMPLETED" and bool(x.evidence_refs) for x in evidence_items
    )
    return {
        "checklistCompletion": {
            "value": round(completed / total * 100, 2) if total else None,
            "completedWeight": completed,
            "eligibleWeight": total,
        },
        "evidenceCoverage": {
            "value": round(covered / len(evidence_items) * 100, 2)
            if evidence_items
            else None,
            "covered": covered,
            "eligible": len(evidence_items),
        },
    }


def effectiveness(inputs):
    known = {
        k: v for k, v in inputs.items() if v is not None and k in EFFECTIVENESS_WEIGHTS
    }
    missing = [k for k in EFFECTIVENESS_WEIGHTS if k not in known]
    weight = sum(EFFECTIVENESS_WEIGHTS[k] for k in known)
    return {
        "value": round(
            sum(known[k] * EFFECTIVENESS_WEIGHTS[k] for k in known) / weight, 2
        )
        if weight >= 0.5
        else None,
        "version": "ceremony-effectiveness-v1",
        "weights": EFFECTIVENESS_WEIGHTS,
        "inputs": inputs,
        "missingDimensions": missing,
        "sufficientData": weight >= 0.5,
    }


class CeremonyService:
    def __init__(self, db: Session, identity: AgentIdentity):
        self.db = db
        self.identity = identity

    def require(self, p):
        if not self.identity.allows(p):
            raise error(403, "PERMISSION_DENIED", f"{p} permission is required")

    def audit(self, action, target_type, target_id, metadata=None):
        append_audit_event(
            self.db,
            tenant_id=self.identity.tenant_id,
            actor_id=self.identity.actor_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            correlation_id=target_id,
            metadata=metadata or {},
        )

    def template(self, id):
        self.require("ceremonies.templates.read")
        row = (
            self.db.query(CeremonyTemplate)
            .filter_by(tenant_id=self.identity.tenant_id, id=id)
            .first()
        )
        if not row:
            raise error(404, "TEMPLATE_NOT_FOUND", "Template was not found")
        return row

    def templates(self):
        self.require("ceremonies.templates.read")
        return (
            self.db.query(CeremonyTemplate)
            .filter_by(tenant_id=self.identity.tenant_id)
            .order_by(
                CeremonyTemplate.ceremony_type, CeremonyTemplate.template_version.desc()
            )
            .all()
        )

    def create_template(self, v):
        self.require("ceremonies.templates.manage")
        family = v.get("family_key") or v["ceremony_type"].lower().replace("_", "-")
        last = (
            self.db.query(CeremonyTemplate)
            .filter_by(tenant_id=self.identity.tenant_id, family_key=family)
            .order_by(CeremonyTemplate.template_version.desc())
            .first()
        )
        version = last.template_version + 1 if last else 1
        row = CeremonyTemplate(
            tenant_id=self.identity.tenant_id,
            family_key=family,
            template_version=version,
            owner_id=self.identity.actor_id,
            **{k: x for k, x in v.items() if k != "family_key"},
        )
        self.db.add(row)
        self.db.flush()
        self.audit(
            "ceremony.template.created",
            "ceremony_template",
            row.id,
            {"version": version},
        )
        self.db.commit()
        return row

    def ceremonies(self):
        self.require("ceremonies.read")
        return (
            self.db.query(Ceremony)
            .filter_by(tenant_id=self.identity.tenant_id)
            .order_by(Ceremony.scheduled_start.desc())
            .all()
        )

    def get(self, id):
        self.require("ceremonies.read")
        row = (
            self.db.query(Ceremony)
            .filter_by(tenant_id=self.identity.tenant_id, id=id)
            .first()
        )
        if not row:
            raise error(404, "CEREMONY_NOT_FOUND", "Ceremony was not found")
        return row

    def create(self, v):
        self.require("ceremonies.create")
        template = self.template(v.pop("template_id"))
        meeting_id = v.get("meeting_id")
        if (
            meeting_id
            and not self.db.query(Meeting)
            .filter_by(tenant_id=self.identity.tenant_id, id=meeting_id)
            .first()
        ):
            raise error(404, "MEETING_NOT_FOUND", "Meeting was not found")
        snapshot = {
            "id": template.id,
            "name": template.name,
            "version": template.template_version,
            "items": template.items,
            "requiredRoles": template.required_roles,
            "timebox": template.recommended_timebox_minutes,
            "scoringConfig": template.scoring_config,
        }
        row = Ceremony(
            tenant_id=self.identity.tenant_id,
            template_id=template.id,
            template_version=template.template_version,
            template_snapshot=snapshot,
            ceremony_type=template.ceremony_type,
            purpose=v.pop("purpose", None) or template.purpose,
            facilitator_id=v.pop("facilitator_id", None) or self.identity.actor_id,
            **v,
        )
        self.db.add(row)
        self.db.flush()
        for item in template.items:
            self.db.add(
                CeremonyChecklistResponse(
                    tenant_id=self.identity.tenant_id,
                    ceremony_id=row.id,
                    item_key=item["key"],
                    section=item.get("section", "BEFORE"),
                    label=item["label"],
                    description=item.get("description", ""),
                    required=item.get("required", False),
                    weight=float(item.get("weight", 1)),
                    evidence_required=item.get("evidenceRequired", False),
                    responsible_role=item.get("responsibleRole"),
                    source="TEMPLATE",
                )
            )
        self.audit(
            "ceremony.created",
            "ceremony",
            row.id,
            {"templateVersion": row.template_version},
        )
        self.db.commit()
        return row

    def checklist(self, id):
        self.get(id)
        return (
            self.db.query(CeremonyChecklistResponse)
            .filter_by(tenant_id=self.identity.tenant_id, ceremony_id=id)
            .order_by(
                CeremonyChecklistResponse.section, CeremonyChecklistResponse.item_key
            )
            .all()
        )

    def update_checklist(self, id, item_key, v):
        self.require("ceremonies.facilitate")
        ceremony = self.get(id)
        row = (
            self.db.query(CeremonyChecklistResponse)
            .filter_by(
                tenant_id=self.identity.tenant_id, ceremony_id=id, item_key=item_key
            )
            .first()
        )
        if not row:
            raise error(404, "CHECKLIST_ITEM_NOT_FOUND", "Checklist item was not found")
        if v.pop("expected_version") != row.version:
            raise error(
                409, "STALE_VERSION", "Checklist item changed; refresh and retry"
            )
        status = v.get("status", row.status)
        evidence = v.get("evidence_refs", row.evidence_refs)
        if status not in CHECKLIST_STATUSES:
            raise error(422, "INVALID_STATUS", "Checklist status is invalid")
        if status == "COMPLETED" and row.evidence_required and not evidence:
            raise error(
                422,
                "EVIDENCE_REQUIRED",
                "Authorized evidence is required before completion",
            )
        if status == "NOT_APPLICABLE" and not v.get(
            "applicability_reason", row.applicability_reason
        ):
            raise error(422, "APPLICABILITY_REASON_REQUIRED", "A reason is required")
        for k, x in v.items():
            setattr(row, k, x)
        row.status = status
        row.evidence_refs = evidence
        row.version += 1
        if status == "COMPLETED":
            row.completed_by = self.identity.actor_id
            row.completed_at = datetime.now(UTC)
        scores = checklist_scores(self.checklist(id))
        ceremony.score_snapshot = {
            **(ceremony.score_snapshot or {}),
            **scores,
            "effectiveness": effectiveness(
                {
                    "preparation": scores["checklistCompletion"]["value"],
                    "evidence": scores["evidenceCoverage"]["value"],
                    "decision_completion": None,
                    "action_quality": None,
                    "previous_action_closure": None,
                    "outcome_achievement": None,
                }
            ),
        }
        ceremony.version += 1
        self.audit(
            "ceremony.checklist.updated",
            "ceremony",
            id,
            {"itemKey": item_key, "status": status},
        )
        self.db.commit()
        return row

    def related(self, id):
        row = self.get(id)
        findings = (
            self.db.query(MeetingFinding)
            .filter_by(tenant_id=self.identity.tenant_id, meeting_id=row.meeting_id)
            .all()
            if row.meeting_id
            else []
        )
        return {
            "decisions": [x for x in findings if x.finding_type == "DECISION"],
            "actions": [x for x in findings if x.finding_type == "ACTION"],
        }


class LessonService:
    def __init__(self, db, identity):
        self.db = db
        self.identity = identity

    def require(self, p):
        if not self.identity.allows(p):
            raise error(403, "PERMISSION_DENIED", f"{p} permission is required")

    def list(self):
        self.require("lessons.read")
        return (
            self.db.query(Lesson)
            .filter_by(tenant_id=self.identity.tenant_id)
            .order_by(Lesson.updated_at.desc())
            .all()
        )

    def get(self, id):
        self.require("lessons.read")
        row = (
            self.db.query(Lesson)
            .filter_by(tenant_id=self.identity.tenant_id, id=id)
            .first()
        )
        if not row:
            raise error(404, "LESSON_NOT_FOUND", "Lesson was not found")
        return row

    def create(self, v):
        self.require("lessons.create")
        row = Lesson(
            tenant_id=self.identity.tenant_id,
            owner_id=v.pop("owner_id", None) or self.identity.actor_id,
            **v,
        )
        self.db.add(row)
        self.db.commit()
        return row

    def transition(self, id, target, expected_version):
        row = self.get(id)
        permission = "lessons.publish" if target == "PUBLISHED" else "lessons.review"
        self.require(permission)
        if row.version != expected_version:
            raise error(409, "STALE_VERSION", "Lesson changed; refresh and retry")
        if target not in LESSON_TRANSITIONS.get(row.status, set()):
            raise error(
                422, "INVALID_TRANSITION", f"Cannot move {row.status} to {target}"
            )
        if target == "PUBLISHED" and not row.evidence_refs:
            raise error(422, "EVIDENCE_REQUIRED", "Published lessons require evidence")
        row.status = target
        row.version += 1
        if target == "PUBLISHED":
            row.published_at = datetime.now(UTC)
        self.db.commit()
        return row

    def adopt(self, id, v):
        self.get(id)
        self.require("lessons.adopt")
        row = LessonAdoption(tenant_id=self.identity.tenant_id, lesson_id=id, **v)
        self.db.add(row)
        self.db.commit()
        return row
