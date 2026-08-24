from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any, ClassVar
from uuid import uuid4

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.database.models.delivery import (
    DeliveryDefect,
    DeliveryEvidence,
    DeliveryMilestone,
    DeliveryPortfolio,
    DeliveryProgramme,
    DeliveryProject,
    DeliveryRAIDEvidence,
    DeliveryRAIDHistory,
    DeliveryRAIDItem,
    DeliveryRAIDRelatedItem,
    DeliveryRAIDRelationship,
    DeliveryRAIDReview,
    DeliveryRecommendation,
    DeliveryRelease,
    DeliverySprint,
    DeliveryTeam,
    DeliveryWorkItem,
    DetectedRAIDCandidate,
    DetectedRAIDCandidateEvidence,
    ProposedAction,
)
from app.delivery.raid_intelligence import (
    INITIAL_STATUS,
    RAIDValidationError,
    apply_scores,
    duplicate_similarity,
    hygiene_findings,
    validate_required_fields,
    validate_transition,
)


class RAIDNotFoundError(LookupError):
    pass


class RAIDConflictError(RuntimeError):
    pass


class RAIDRepository:
    ENTITY_MODELS: ClassVar[dict[str, Any]] = {
        "PORTFOLIO": DeliveryPortfolio,
        "PROGRAMME": DeliveryProgramme,
        "PROJECT": DeliveryProject,
        "TEAM": DeliveryTeam,
        "SPRINT": DeliverySprint,
        "RELEASE": DeliveryRelease,
        "MILESTONE": DeliveryMilestone,
        "WORK_ITEM": DeliveryWorkItem,
        "DEFECT": DeliveryDefect,
        "EVIDENCE": DeliveryEvidence,
    }
    SORT_COLUMNS: ClassVar[dict[str, Any]] = {
        "reference": DeliveryRAIDItem.reference,
        "title": DeliveryRAIDItem.name,
        "type": DeliveryRAIDItem.item_type,
        "status": DeliveryRAIDItem.status,
        "priority": DeliveryRAIDItem.priority,
        "due_date": DeliveryRAIDItem.due_date,
        "attention": DeliveryRAIDItem.attention_score,
        "updated_at": DeliveryRAIDItem.updated_at,
    }

    def __init__(self, db: Session, tenant_id: str, actor_id: str):
        if not tenant_id or not actor_id:
            raise ValueError("tenant and actor are required")
        self.db = db
        self.tenant_id = tenant_id
        self.actor_id = actor_id

    def get(self, raid_id: str) -> DeliveryRAIDItem | None:
        return self.db.scalar(
            select(DeliveryRAIDItem).where(
                DeliveryRAIDItem.tenant_id == self.tenant_id,
                DeliveryRAIDItem.id == raid_id,
            )
        )

    def require(self, raid_id: str) -> DeliveryRAIDItem:
        item = self.get(raid_id)
        if item is None:
            raise RAIDNotFoundError("RAID item not found")
        return item

    def list(
        self,
        *,
        filters: dict[str, Any] | None = None,
        page: int = 1,
        page_size: int = 25,
        sort: str = "attention",
        direction: str = "desc",
    ) -> tuple[list[DeliveryRAIDItem], int]:
        if page < 1 or not 1 <= page_size <= 100:
            raise RAIDValidationError("Invalid pagination")
        if sort not in self.SORT_COLUMNS or direction not in {"asc", "desc"}:
            raise RAIDValidationError("Invalid sort")
        filters = filters or {}
        query = select(DeliveryRAIDItem).where(
            DeliveryRAIDItem.tenant_id == self.tenant_id
        )
        count_query = (
            select(func.count())
            .select_from(DeliveryRAIDItem)
            .where(DeliveryRAIDItem.tenant_id == self.tenant_id)
        )
        criteria = self._criteria(filters)
        if criteria:
            query = query.where(*criteria)
            count_query = count_query.where(*criteria)
        column = self.SORT_COLUMNS[sort]
        ordering = column.asc() if direction == "asc" else column.desc()
        query = (
            query.order_by(ordering.nulls_last(), DeliveryRAIDItem.id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(self.db.scalars(query)), int(self.db.scalar(count_query) or 0)

    def create(
        self, values: dict[str, Any], *, trace_id: str | None = None
    ) -> DeliveryRAIDItem:
        values = {**values}
        values["item_type"] = str(values.get("item_type", "")).upper()
        values.setdefault(
            "status", INITIAL_STATUS.get(values["item_type"], "IDENTIFIED")
        )
        values.setdefault("identified_at", datetime.now(UTC))
        values.setdefault("created_by", self.actor_id)
        values.setdefault("updated_by", self.actor_id)
        self._require_entity("PROJECT", values.get("project_id"))
        self._validate_direct_relationships(values)
        validate_required_fields(values)
        item = DeliveryRAIDItem(tenant_id=self.tenant_id, **values)
        if not item.reference:
            item.reference = self._next_reference(item.item_type)
        apply_scores(item)
        self.db.add(item)
        self.db.flush()
        self._history(
            item,
            "CREATED",
            new_status=item.status,
            trace_id=trace_id,
            change_data={"reference": item.reference},
        )
        return item

    def update(
        self,
        raid_id: str,
        values: dict[str, Any],
        *,
        expected_version: int,
        trace_id: str | None = None,
    ) -> DeliveryRAIDItem:
        item = self.require(raid_id)
        if item.version != expected_version:
            raise RAIDConflictError("RAID item was changed by another user")
        immutable = {
            "id",
            "tenant_id",
            "item_type",
            "reference",
            "created_at",
            "created_by",
            "status",
        }
        unknown = set(values) - set(DeliveryRAIDItem.__table__.columns.keys())
        if unknown or immutable.intersection(values):
            raise RAIDValidationError("Unsupported or immutable fields")
        self._validate_direct_relationships(values)
        before = {key: getattr(item, key) for key in values}
        for key, value in values.items():
            setattr(item, key, value)
        validate_required_fields(
            {
                column.name: getattr(item, column.name)
                for column in DeliveryRAIDItem.__table__.columns
            }
        )
        item.updated_by = self.actor_id
        item.version += 1
        apply_scores(item)
        self.db.flush()
        self._history(
            item,
            "UPDATED",
            trace_id=trace_id,
            change_data={"before": _safe(before), "fields": sorted(values)},
        )
        return item

    def transition(
        self,
        raid_id: str,
        target_status: str,
        *,
        expected_version: int,
        note: str | None,
        trace_id: str | None = None,
    ) -> DeliveryRAIDItem:
        item = self.require(raid_id)
        if item.version != expected_version:
            raise RAIDConflictError("RAID item was changed by another user")
        evidence_count = self.evidence_count(item.id)
        target = target_status.upper()
        validate_transition(
            item.item_type,
            item.status,
            target,
            note=note,
            evidence_count=evidence_count,
            completion_evidence_required=item.completion_evidence_required,
        )
        previous = item.status
        item.status = target
        item.updated_by = self.actor_id
        item.version += 1
        if target in {"CLOSED", "RESOLVED", "COMPLETED", "IMPLEMENTED", "CANCELLED"}:
            item.closed_at = datetime.now(UTC)
            item.closure_reason = note
        item.escalated = target == "ESCALATED" or item.escalated
        apply_scores(item)
        self.db.flush()
        self._history(
            item,
            "STATUS_TRANSITION",
            previous_status=previous,
            new_status=target,
            note=note,
            trace_id=trace_id,
        )
        return item

    def assign(
        self,
        raid_id: str,
        owner_id: str | None,
        *,
        expected_version: int,
        trace_id: str | None = None,
    ) -> DeliveryRAIDItem:
        return self.update(
            raid_id,
            {"owner_id": owner_id},
            expected_version=expected_version,
            trace_id=trace_id,
        )

    def review(
        self,
        raid_id: str,
        note: str,
        next_review_date: date | None,
        *,
        expected_version: int,
        trace_id: str | None = None,
    ) -> DeliveryRAIDReview:
        item = self.require(raid_id)
        if item.version != expected_version:
            raise RAIDConflictError("RAID item was changed by another user")
        reviewed_at = datetime.now(UTC)
        review = DeliveryRAIDReview(
            tenant_id=self.tenant_id,
            raid_id=item.id,
            note=note,
            reviewed_by=self.actor_id,
            reviewed_at=reviewed_at,
            next_review_date=next_review_date,
        )
        item.last_reviewed_at = reviewed_at
        item.review_date = next_review_date or item.review_date
        item.updated_by = self.actor_id
        item.version += 1
        apply_scores(item)
        self.db.add(review)
        self.db.flush()
        self._history(
            item,
            "REVIEWED",
            note=note,
            trace_id=trace_id,
            change_data={
                "nextReviewDate": next_review_date.isoformat()
                if next_review_date
                else None
            },
        )
        return review

    def link_evidence(
        self, raid_id: str, evidence_id: str, *, trace_id: str | None = None
    ) -> DeliveryRAIDEvidence:
        item = self.require(raid_id)
        self._require_entity("EVIDENCE", evidence_id)
        existing = self.db.get(
            DeliveryRAIDEvidence, (self.tenant_id, raid_id, evidence_id)
        )
        if existing:
            return existing
        link = DeliveryRAIDEvidence(
            tenant_id=self.tenant_id,
            raid_id=raid_id,
            evidence_id=evidence_id,
            linked_by=self.actor_id,
        )
        self.db.add(link)
        item.version += 1
        self.db.flush()
        self._history(
            item,
            "EVIDENCE_LINKED",
            trace_id=trace_id,
            change_data={"evidenceId": evidence_id},
        )
        return link

    def unlink_evidence(
        self, raid_id: str, evidence_id: str, *, trace_id: str | None = None
    ) -> None:
        item = self.require(raid_id)
        link = self.db.get(DeliveryRAIDEvidence, (self.tenant_id, raid_id, evidence_id))
        if link is None:
            raise RAIDNotFoundError("Evidence link not found")
        self.db.delete(link)
        item.version += 1
        self.db.flush()
        self._history(
            item,
            "EVIDENCE_UNLINKED",
            trace_id=trace_id,
            change_data={"evidenceId": evidence_id},
        )

    def add_relationship(
        self,
        raid_id: str,
        entity_type: str,
        entity_id: str,
        relationship_type: str,
        *,
        trace_id: str | None = None,
    ) -> DeliveryRAIDRelationship:
        item = self.require(raid_id)
        entity_type = entity_type.upper()
        self._require_entity(entity_type, entity_id)
        relationship = DeliveryRAIDRelationship(
            tenant_id=self.tenant_id,
            raid_id=raid_id,
            entity_type=entity_type,
            entity_id=entity_id,
            relationship_type=relationship_type.upper(),
            created_by=self.actor_id,
        )
        self.db.add(relationship)
        item.version += 1
        self.db.flush()
        self._history(
            item,
            "RELATIONSHIP_ADDED",
            trace_id=trace_id,
            change_data={
                "relationshipId": relationship.id,
                "entityType": entity_type,
                "entityId": entity_id,
            },
        )
        return relationship

    def remove_relationship(
        self, raid_id: str, relationship_id: str, *, trace_id: str | None = None
    ) -> None:
        item = self.require(raid_id)
        relationship = self.db.scalar(
            select(DeliveryRAIDRelationship).where(
                DeliveryRAIDRelationship.tenant_id == self.tenant_id,
                DeliveryRAIDRelationship.raid_id == raid_id,
                DeliveryRAIDRelationship.id == relationship_id,
            )
        )
        if relationship is None:
            raise RAIDNotFoundError("Relationship not found")
        self.db.delete(relationship)
        item.version += 1
        self.db.flush()
        self._history(
            item,
            "RELATIONSHIP_REMOVED",
            trace_id=trace_id,
            change_data={"relationshipId": relationship_id},
        )

    def relate_item(
        self, raid_id: str, related_raid_id: str, relationship_type: str = "RELATED"
    ) -> DeliveryRAIDRelatedItem:
        self.require(raid_id)
        self.require(related_raid_id)
        relation = DeliveryRAIDRelatedItem(
            tenant_id=self.tenant_id,
            raid_id=raid_id,
            related_raid_id=related_raid_id,
            relationship_type=relationship_type,
            created_by=self.actor_id,
        )
        self.db.add(relation)
        self.db.flush()
        return relation

    def history(self, raid_id: str) -> list[DeliveryRAIDHistory]:
        self.require(raid_id)
        return list(
            self.db.scalars(
                select(DeliveryRAIDHistory)
                .where(
                    DeliveryRAIDHistory.tenant_id == self.tenant_id,
                    DeliveryRAIDHistory.raid_id == raid_id,
                )
                .order_by(
                    DeliveryRAIDHistory.changed_at.desc(), DeliveryRAIDHistory.id.desc()
                )
            )
        )

    def details(self, raid_id: str) -> dict[str, Any]:
        item = self.require(raid_id)
        evidence = list(
            self.db.scalars(
                select(DeliveryEvidence)
                .join(
                    DeliveryRAIDEvidence,
                    (DeliveryRAIDEvidence.tenant_id == DeliveryEvidence.tenant_id)
                    & (DeliveryRAIDEvidence.evidence_id == DeliveryEvidence.id),
                )
                .where(
                    DeliveryRAIDEvidence.tenant_id == self.tenant_id,
                    DeliveryRAIDEvidence.raid_id == raid_id,
                )
            )
        )
        relationships = list(
            self.db.scalars(
                select(DeliveryRAIDRelationship).where(
                    DeliveryRAIDRelationship.tenant_id == self.tenant_id,
                    DeliveryRAIDRelationship.raid_id == raid_id,
                )
            )
        )
        recommendations = list(
            self.db.scalars(
                select(DeliveryRecommendation).where(
                    DeliveryRecommendation.tenant_id == self.tenant_id,
                    DeliveryRecommendation.raid_id == raid_id,
                )
            )
        )
        proposals = list(
            self.db.scalars(
                select(ProposedAction).where(
                    ProposedAction.tenant_id == self.tenant_id,
                    ProposedAction.raid_id == raid_id,
                )
            )
        )
        reviews = list(
            self.db.scalars(
                select(DeliveryRAIDReview)
                .where(
                    DeliveryRAIDReview.tenant_id == self.tenant_id,
                    DeliveryRAIDReview.raid_id == raid_id,
                )
                .order_by(DeliveryRAIDReview.reviewed_at.desc())
            )
        )
        related = list(
            self.db.scalars(
                select(DeliveryRAIDRelatedItem).where(
                    DeliveryRAIDRelatedItem.tenant_id == self.tenant_id,
                    or_(
                        DeliveryRAIDRelatedItem.raid_id == raid_id,
                        DeliveryRAIDRelatedItem.related_raid_id == raid_id,
                    ),
                )
            )
        )
        return {
            "item": item,
            "evidence": evidence,
            "relationships": relationships,
            "recommendations": recommendations,
            "proposals": proposals,
            "reviews": reviews,
            "related": related,
            "history": self.history(raid_id),
        }

    def summary(self) -> dict[str, int]:
        items, _ = self.list(page_size=100)
        open_items = [
            item
            for item in items
            if item.status
            not in {
                "CLOSED",
                "RESOLVED",
                "COMPLETED",
                "CANCELLED",
                "IMPLEMENTED",
                "VALIDATED",
            }
        ]
        return {
            "criticalRisks": sum(
                item.item_type == "RISK"
                and (item.residual_exposure_band or item.exposure_band) == "CRITICAL"
                for item in open_items
            ),
            "openIssues": sum(item.item_type == "ISSUE" for item in open_items),
            "atRiskDependencies": sum(
                item.item_type == "DEPENDENCY"
                and (item.status in {"AT_RISK", "BLOCKED"} or item.critical_path)
                for item in open_items
            ),
            "pendingDecisions": sum(
                item.item_type == "DECISION" for item in open_items
            ),
            "overdueActions": sum(
                item.item_type == "ACTION"
                and bool(item.due_date and item.due_date < datetime.now(UTC).date())
                for item in open_items
            ),
            "unvalidatedAssumptions": sum(
                item.item_type == "ASSUMPTION" for item in open_items
            ),
        }

    def hygiene(self) -> list[dict[str, Any]]:
        items, _ = self.list(page_size=100)
        links = list(
            self.db.execute(
                select(
                    DeliveryRAIDEvidence.raid_id,
                    func.count(),
                    func.max(DeliveryEvidence.captured_at),
                )
                .join(
                    DeliveryEvidence,
                    (DeliveryEvidence.tenant_id == DeliveryRAIDEvidence.tenant_id)
                    & (DeliveryEvidence.id == DeliveryRAIDEvidence.evidence_id),
                )
                .where(DeliveryRAIDEvidence.tenant_id == self.tenant_id)
                .group_by(DeliveryRAIDEvidence.raid_id)
            )
        )
        evidence = {raid_id: (count, latest) for raid_id, count, latest in links}
        return [
            finding
            for item in items
            for finding in hygiene_findings(
                item,
                evidence_count=evidence.get(item.id, (0, None))[0],
                latest_evidence_at=evidence.get(item.id, (0, None))[1],
            )
        ]

    def duplicates(
        self, values: dict[str, Any], *, threshold: float = 0.55
    ) -> list[dict[str, Any]]:
        items, _ = self.list(
            filters={"project_id": values.get("project_id")}, page_size=100
        )
        matches = []
        for item in items:
            confidence, reasons = duplicate_similarity(values, item)
            if confidence >= threshold:
                matches.append(
                    {
                        "id": item.id,
                        "reference": item.reference,
                        "title": item.name,
                        "confidence": round(confidence, 2),
                        "reasons": reasons,
                    }
                )
        return sorted(matches, key=lambda match: match["confidence"], reverse=True)

    def candidate(self, candidate_id: str) -> DetectedRAIDCandidate | None:
        return self.db.scalar(
            select(DetectedRAIDCandidate).where(
                DetectedRAIDCandidate.tenant_id == self.tenant_id,
                DetectedRAIDCandidate.id == candidate_id,
            )
        )

    def candidate_evidence(self, candidate_id: str) -> list[DeliveryEvidence]:
        return list(
            self.db.scalars(
                select(DeliveryEvidence)
                .join(
                    DetectedRAIDCandidateEvidence,
                    (
                        DetectedRAIDCandidateEvidence.tenant_id
                        == DeliveryEvidence.tenant_id
                    )
                    & (
                        DetectedRAIDCandidateEvidence.evidence_id == DeliveryEvidence.id
                    ),
                )
                .where(
                    DetectedRAIDCandidateEvidence.tenant_id == self.tenant_id,
                    DetectedRAIDCandidateEvidence.candidate_id == candidate_id,
                )
            )
        )

    def list_candidates(self) -> list[DetectedRAIDCandidate]:
        return list(
            self.db.scalars(
                select(DetectedRAIDCandidate)
                .where(
                    DetectedRAIDCandidate.tenant_id == self.tenant_id,
                    DetectedRAIDCandidate.status.in_(("DETECTED", "UNDER_REVIEW")),
                )
                .order_by(DetectedRAIDCandidate.detected_at.desc())
            )
        )

    def accept_candidate(
        self, candidate_id: str, values: dict[str, Any]
    ) -> tuple[DetectedRAIDCandidate, DeliveryRAIDItem]:
        candidate = self.candidate(candidate_id)
        if candidate is None:
            raise RAIDNotFoundError("Candidate not found")
        if candidate.status not in {"DETECTED", "UNDER_REVIEW"}:
            raise RAIDValidationError("Candidate has already been reviewed")
        evidence = self.candidate_evidence(candidate_id)
        if not evidence:
            raise RAIDValidationError("Candidate requires authorized evidence")
        candidate_values = {
            "item_type": candidate.candidate_type,
            "name": candidate.title,
            "description": candidate.description,
            "owner_id": candidate.suggested_owner,
            "due_date": candidate.suggested_due_date,
            "probability": candidate.suggested_probability,
            "impact": candidate.suggested_impact,
            **values,
        }
        item = self.create(candidate_values, trace_id=candidate.trace_id)
        for record in evidence:
            self.link_evidence(item.id, record.id, trace_id=candidate.trace_id)
        candidate.status = "ACCEPTED"
        candidate.accepted_raid_id = item.id
        candidate.reviewed_by = self.actor_id
        candidate.reviewed_at = datetime.now(UTC)
        candidate.version += 1
        self.db.flush()
        return candidate, item

    def dismiss_candidate(
        self, candidate_id: str, reason: str
    ) -> DetectedRAIDCandidate:
        candidate = self.candidate(candidate_id)
        if candidate is None:
            raise RAIDNotFoundError("Candidate not found")
        if candidate.status not in {"DETECTED", "UNDER_REVIEW"}:
            raise RAIDValidationError("Candidate has already been reviewed")
        candidate.status = "DISMISSED"
        candidate.dismissal_reason = reason
        candidate.reviewed_by = self.actor_id
        candidate.reviewed_at = datetime.now(UTC)
        candidate.version += 1
        self.db.flush()
        return candidate

    def merge_candidate(self, candidate_id: str, raid_id: str) -> DetectedRAIDCandidate:
        candidate = self.candidate(candidate_id)
        item = self.require(raid_id)
        if candidate is None:
            raise RAIDNotFoundError("Candidate not found")
        for evidence in self.candidate_evidence(candidate_id):
            self.link_evidence(item.id, evidence.id, trace_id=candidate.trace_id)
        candidate.status = "MERGED"
        candidate.merged_raid_id = item.id
        candidate.reviewed_by = self.actor_id
        candidate.reviewed_at = datetime.now(UTC)
        candidate.version += 1
        self.db.flush()
        return candidate

    def evidence_count(self, raid_id: str) -> int:
        return int(
            self.db.scalar(
                select(func.count())
                .select_from(DeliveryRAIDEvidence)
                .where(
                    DeliveryRAIDEvidence.tenant_id == self.tenant_id,
                    DeliveryRAIDEvidence.raid_id == raid_id,
                )
            )
            or 0
        )

    def _criteria(self, filters: dict[str, Any]) -> list[Any]:
        criteria: list[Any] = []
        exact = {
            "item_type",
            "status",
            "priority",
            "probability",
            "impact",
            "project_id",
            "programme_id",
            "team_id",
            "sprint_id",
            "release_id",
            "milestone_id",
            "owner_id",
            "source_system",
            "exposure_band",
        }
        for key, value in filters.items():
            if value in (None, "", False):
                continue
            if key in exact:
                criteria.append(getattr(DeliveryRAIDItem, key) == value)
            elif key == "search":
                safe = str(value)[:200].replace("%", "\\%").replace("_", "\\_")
                criteria.append(
                    or_(
                        DeliveryRAIDItem.name.ilike(f"%{safe}%", escape="\\"),
                        DeliveryRAIDItem.reference.ilike(f"%{safe}%", escape="\\"),
                        DeliveryRAIDItem.description.ilike(f"%{safe}%", escape="\\"),
                    )
                )
            elif key == "overdue" and value:
                criteria.append(DeliveryRAIDItem.due_date < datetime.now(UTC).date())
            elif key == "unowned" and value:
                criteria.append(DeliveryRAIDItem.owner_id.is_(None))
            elif key == "critical_path" and value:
                criteria.append(DeliveryRAIDItem.critical_path.is_(True))
            elif key == "stale" and value:
                criteria.append(DeliveryRAIDItem.review_date < datetime.now(UTC).date())
            elif key == "due_from":
                criteria.append(DeliveryRAIDItem.due_date >= value)
            elif key == "due_to":
                criteria.append(DeliveryRAIDItem.due_date <= value)
            else:
                raise RAIDValidationError(f"Unsupported filter: {key}")
        return criteria

    def _next_reference(self, item_type: str) -> str:
        prefix = {
            "RISK": "R",
            "ASSUMPTION": "A",
            "ISSUE": "I",
            "DEPENDENCY": "D",
            "DECISION": "DEC",
            "ACTION": "ACT",
        }[item_type]
        count = int(
            self.db.scalar(
                select(func.count())
                .select_from(DeliveryRAIDItem)
                .where(
                    DeliveryRAIDItem.tenant_id == self.tenant_id,
                    DeliveryRAIDItem.item_type == item_type,
                )
            )
            or 0
        )
        while True:
            count += 1
            reference = f"{prefix}-{count:03d}"
            exists = self.db.scalar(
                select(DeliveryRAIDItem.id).where(
                    DeliveryRAIDItem.tenant_id == self.tenant_id,
                    DeliveryRAIDItem.reference == reference,
                )
            )
            if not exists:
                return reference

    def _require_entity(self, entity_type: str, entity_id: str | None) -> None:
        model = self.ENTITY_MODELS.get(entity_type)
        if model is None or not entity_id:
            raise RAIDValidationError("Relationship target is unsupported or missing")
        exists = self.db.scalar(
            select(model.id).where(
                model.tenant_id == self.tenant_id, model.id == entity_id
            )
        )
        if exists is None:
            raise RAIDValidationError(
                "Relationship target does not exist or is inaccessible"
            )

    def _validate_direct_relationships(self, values: dict[str, Any]) -> None:
        for field, entity_type in {
            "programme_id": "PROGRAMME",
            "project_id": "PROJECT",
            "team_id": "TEAM",
            "sprint_id": "SPRINT",
            "release_id": "RELEASE",
            "milestone_id": "MILESTONE",
            "work_item_id": "WORK_ITEM",
            "defect_id": "DEFECT",
        }.items():
            if values.get(field):
                self._require_entity(entity_type, values[field])

    def _history(
        self,
        item: DeliveryRAIDItem,
        event_type: str,
        *,
        previous_status: str | None = None,
        new_status: str | None = None,
        note: str | None = None,
        trace_id: str | None = None,
        change_data: dict[str, Any] | None = None,
    ) -> None:
        self.db.add(
            DeliveryRAIDHistory(
                tenant_id=self.tenant_id,
                raid_id=item.id,
                event_type=event_type,
                previous_status=previous_status,
                new_status=new_status,
                note=note,
                actor_id=self.actor_id,
                trace_id=trace_id or str(uuid4()),
                record_version=item.version,
                change_data=change_data or {},
            )
        )


def _safe(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _safe(item) for key, item in value.items()}
    return value
