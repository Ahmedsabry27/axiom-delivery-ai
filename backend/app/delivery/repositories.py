from __future__ import annotations

from typing import ClassVar, Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models.delivery import (
    CopilotFeedback,
    DeliveryDependency,
    DeliveryDependencyEndpoint,
    DeliveryEvidence,
    DeliveryMilestone,
    DeliveryProgramme,
    DeliveryProject,
    DeliveryRecommendation,
    DeliveryRelease,
    DeliverySprint,
    DeliveryTeam,
    DeliveryWorkItem,
    ProposedAction,
)

T = TypeVar("T")


class TenantRepository(Generic[T]):
    """Repository base that makes tenant scope mandatory for every lookup."""

    def __init__(self, db: Session, model: type[T], tenant_id: str):
        if not tenant_id:
            raise ValueError("tenant_id is required")
        self.db, self.model, self.tenant_id = db, model, tenant_id

    def get(self, record_id: str) -> T | None:
        return self.db.scalar(
            select(self.model).where(
                self.model.tenant_id == self.tenant_id, self.model.id == record_id
            )
        )

    def list(self, *, limit: int = 50, offset: int = 0, **filters) -> list[T]:
        if not 1 <= limit <= 100 or offset < 0:
            raise ValueError("Invalid pagination")
        query = select(self.model).where(self.model.tenant_id == self.tenant_id)
        for key, value in filters.items():
            if not hasattr(self.model, key):
                raise ValueError(f"Unsupported filter: {key}")
            query = query.where(getattr(self.model, key) == value)
        return list(self.db.scalars(query.limit(limit).offset(offset)))

    def add(self, record: T) -> T:
        if getattr(record, "tenant_id", None) != self.tenant_id:
            raise ValueError("Cross-tenant record rejected")
        self.db.add(record)
        self.db.flush()
        return record


class EvidenceRepository(TenantRepository[DeliveryEvidence]):
    def __init__(self, db: Session, tenant_id: str):
        super().__init__(db, DeliveryEvidence, tenant_id)

    def authorized_for_entity(
        self, entity_type: str, entity_id: str, *, limit: int = 25
    ) -> list[DeliveryEvidence]:
        return self.list(limit=limit, entity_type=entity_type, entity_id=entity_id)

    def require_authorized_ids(self, evidence_ids: list[str]) -> list[DeliveryEvidence]:
        if not evidence_ids:
            return []
        records = list(
            self.db.scalars(
                select(DeliveryEvidence).where(
                    DeliveryEvidence.tenant_id == self.tenant_id,
                    DeliveryEvidence.id.in_(evidence_ids),
                )
            )
        )
        if len({record.id for record in records}) != len(set(evidence_ids)):
            raise ValueError("Missing or inaccessible evidence")
        return records


class ProposedActionRepository(TenantRepository[ProposedAction]):
    def __init__(self, db: Session, tenant_id: str):
        super().__init__(db, ProposedAction, tenant_id)


class FeedbackRepository(TenantRepository[CopilotFeedback]):
    def __init__(self, db: Session, tenant_id: str):
        super().__init__(db, CopilotFeedback, tenant_id)


class RecommendationRepository(TenantRepository[DeliveryRecommendation]):
    def __init__(self, db: Session, tenant_id: str):
        super().__init__(db, DeliveryRecommendation, tenant_id)


class MilestoneRepository(TenantRepository[DeliveryMilestone]):
    def __init__(self, db: Session, tenant_id: str):
        super().__init__(db, DeliveryMilestone, tenant_id)

    def overdue(self, today, *, limit: int = 50):
        query = (
            select(DeliveryMilestone)
            .where(
                DeliveryMilestone.tenant_id == self.tenant_id,
                DeliveryMilestone.status.not_in(("COMPLETED", "CANCELLED")),
                DeliveryMilestone.planned_date < today,
            )
            .limit(limit)
        )
        return list(self.db.scalars(query))


class DependencyRepository(TenantRepository[DeliveryDependency]):
    ENTITY_MODELS: ClassVar[dict] = {
        "PROGRAMME": DeliveryProgramme,
        "PROJECT": DeliveryProject,
        "TEAM": DeliveryTeam,
        "SPRINT": DeliverySprint,
        "RELEASE": DeliveryRelease,
        "MILESTONE": DeliveryMilestone,
        "WORK_ITEM": DeliveryWorkItem,
    }

    def __init__(self, db: Session, tenant_id: str):
        super().__init__(db, DeliveryDependency, tenant_id)

    def add_with_endpoints(
        self, record, source: tuple[str, str], target: tuple[str, str]
    ):
        if source == target:
            raise ValueError("Dependency source and target must differ")
        for entity_type, entity_id in (source, target):
            model = self.ENTITY_MODELS.get(entity_type)
            if (
                model is not None
                and self.db.scalar(
                    select(model.id).where(
                        model.tenant_id == self.tenant_id, model.id == entity_id
                    )
                )
                is None
            ):
                raise ValueError(
                    "Dependency endpoint does not exist or is inaccessible"
                )
            if model is None and entity_type not in {"SYSTEM", "EXTERNAL_PARTY"}:
                raise ValueError("Unsupported dependency endpoint type")
        self.add(record)
        for direction, endpoint in (("SOURCE", source), ("TARGET", target)):
            self.db.add(
                DeliveryDependencyEndpoint(
                    dependency_id=record.id,
                    tenant_id=self.tenant_id,
                    direction=direction,
                    entity_type=endpoint[0],
                    entity_id=endpoint[1],
                )
            )
        self.db.flush()
        return record

    def related(
        self, direction: str, entity_type: str, entity_id: str, *, limit: int = 50
    ):
        query = (
            select(DeliveryDependency)
            .join(
                DeliveryDependencyEndpoint,
                (DeliveryDependencyEndpoint.tenant_id == DeliveryDependency.tenant_id)
                & (DeliveryDependencyEndpoint.dependency_id == DeliveryDependency.id),
            )
            .where(
                DeliveryDependency.tenant_id == self.tenant_id,
                DeliveryDependencyEndpoint.direction == direction,
                DeliveryDependencyEndpoint.entity_type == entity_type,
                DeliveryDependencyEndpoint.entity_id == entity_id,
            )
            .limit(limit)
        )
        return list(self.db.scalars(query))

    def critical_path(self, *, limit: int = 50):
        return self.list(limit=limit, critical_path=True)

    def resolve(self, dependency_id: str, resolved_at):
        record = self.get(dependency_id)
        if record is None:
            return None
        record.status = "RESOLVED"
        record.resolved_at = resolved_at
        record.version += 1
        self.db.flush()
        return record
