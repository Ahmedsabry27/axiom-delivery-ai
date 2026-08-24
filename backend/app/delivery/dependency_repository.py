from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, ClassVar

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.database.models.delivery import (
    DeliveryDefect,
    DeliveryDependency,
    DeliveryDependencyEndpoint,
    DeliveryDependencyHistory,
    DeliveryDependencyScenario,
    DeliveryEvidence,
    DeliveryMilestone,
    DeliveryPortfolio,
    DeliveryProgramme,
    DeliveryProject,
    DeliveryRAIDItem,
    DeliveryRecommendation,
    DeliveryRelease,
    DeliverySprint,
    DeliveryTeam,
    DeliveryWorkItem,
    DetectedDependencyCandidate,
    ProposedAction,
)
from app.delivery.dependency_intelligence import (
    ENTITY_TYPES,
    RELATIONSHIP_TYPES,
    DependencyGraph,
    GraphEdge,
    validate_transition,
)


class DependencyRepository:
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
    }
    PLACEHOLDER_TYPES: ClassVar[set[str]] = {
        "SYSTEM",
        "SERVICE",
        "ENVIRONMENT",
        "VENDOR",
        "EXTERNAL_PARTY",
    }

    def __init__(self, db: Session, tenant_id: str, actor_id: str):
        self.db = db
        self.tenant_id = tenant_id
        self.actor_id = actor_id

    def get(self, dependency_id: str) -> DeliveryDependency | None:
        return self.db.scalar(
            select(DeliveryDependency).where(
                DeliveryDependency.tenant_id == self.tenant_id,
                DeliveryDependency.id == dependency_id,
            )
        )

    def list(self, filters: dict[str, Any]) -> tuple[list[DeliveryDependency], int]:
        page = max(int(filters.get("page") or 1), 1)
        page_size = min(max(int(filters.get("page_size") or 20), 1), 100)
        conditions = [DeliveryDependency.tenant_id == self.tenant_id]
        for key, column in (
            ("project_id", DeliveryDependency.project_id),
            ("status", DeliveryDependency.status),
            ("priority", DeliveryDependency.priority),
            ("owner_id", DeliveryDependency.owner_id),
        ):
            if filters.get(key):
                conditions.append(column == filters[key])
        if filters.get("external") is not None:
            conditions.append(DeliveryDependency.external == filters["external"])
        if filters.get("critical_path"):
            conditions.append(DeliveryDependency.critical_path.is_(True))
        if filters.get("unowned"):
            conditions.append(DeliveryDependency.owner_id.is_(None))
        if filters.get("overdue"):
            conditions.extend(
                [
                    DeliveryDependency.required_by_date < datetime.now(UTC).date(),
                    DeliveryDependency.status.not_in(
                        ("RESOLVED", "CLOSED", "CANCELLED")
                    ),
                ]
            )
        if search := filters.get("search"):
            pattern = f"%{search.strip()}%"
            conditions.append(
                or_(
                    DeliveryDependency.reference.ilike(pattern),
                    DeliveryDependency.name.ilike(pattern),
                    DeliveryDependency.description.ilike(pattern),
                )
            )
        sort_columns = {
            "reference": DeliveryDependency.reference,
            "title": DeliveryDependency.name,
            "status": DeliveryDependency.status,
            "required_by_date": DeliveryDependency.required_by_date,
            "forecast_resolution_date": DeliveryDependency.forecast_resolution_date,
            "updated_at": DeliveryDependency.updated_at,
        }
        sort = sort_columns.get(filters.get("sort"), DeliveryDependency.updated_at)
        order = sort.asc() if filters.get("direction") == "asc" else sort.desc()
        total = (
            self.db.scalar(
                select(func.count()).select_from(DeliveryDependency).where(*conditions)
            )
            or 0
        )
        query = (
            select(DeliveryDependency)
            .where(*conditions)
            .order_by(order, DeliveryDependency.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list(self.db.scalars(query)), total

    def endpoints_for(
        self, dependency_ids: list[str]
    ) -> dict[str, dict[str, DeliveryDependencyEndpoint]]:
        if not dependency_ids:
            return {}
        result: dict[str, dict[str, DeliveryDependencyEndpoint]] = {}
        query = select(DeliveryDependencyEndpoint).where(
            DeliveryDependencyEndpoint.tenant_id == self.tenant_id,
            DeliveryDependencyEndpoint.dependency_id.in_(dependency_ids),
        )
        for endpoint in self.db.scalars(query):
            result.setdefault(endpoint.dependency_id, {})[endpoint.direction] = endpoint
        return result

    def graph_records(
        self,
    ) -> tuple[
        list[DeliveryDependency], dict[str, dict[str, DeliveryDependencyEndpoint]]
    ]:
        dependencies = list(
            self.db.scalars(
                select(DeliveryDependency).where(
                    DeliveryDependency.tenant_id == self.tenant_id,
                    DeliveryDependency.status != "CANCELLED",
                )
            )
        )
        return dependencies, self.endpoints_for([item.id for item in dependencies])

    def graph(self) -> tuple[DependencyGraph, dict[str, DeliveryDependency]]:
        dependencies, endpoint_map = self.graph_records()
        edges = []
        records = {}
        for dependency in dependencies:
            pair = endpoint_map.get(dependency.id, {})
            if "SOURCE" not in pair or "TARGET" not in pair:
                continue
            source, target = pair["SOURCE"], pair["TARGET"]
            edges.append(
                GraphEdge(
                    dependency_id=dependency.id,
                    source=f"{source.entity_type}:{source.entity_id}",
                    target=f"{target.entity_type}:{target.entity_id}",
                    relationship_type=dependency.relationship_type,
                    status=dependency.status,
                    critical=dependency.critical_path,
                    required_by=dependency.required_by_date,
                    forecast_resolution=dependency.forecast_resolution_date,
                )
            )
            records[dependency.id] = dependency
        return DependencyGraph(edges), records

    def entity_labels(self, nodes: set[str]) -> dict[str, str]:
        labels = {node: node.split(":", 1)[1] for node in nodes}
        grouped: dict[str, list[str]] = {}
        for node in nodes:
            entity_type, entity_id = node.split(":", 1)
            grouped.setdefault(entity_type, []).append(entity_id)
        for entity_type, ids in grouped.items():
            model = self.ENTITY_MODELS.get(entity_type)
            if model is None:
                continue
            rows = self.db.execute(
                select(model.id, model.name).where(
                    model.tenant_id == self.tenant_id,
                    model.id.in_(ids),
                )
            )
            for entity_id, name in rows:
                labels[f"{entity_type}:{entity_id}"] = name
        return labels

    def validate_endpoint(
        self, entity_type: str, entity_id: str, *, external: bool
    ) -> None:
        if entity_type not in ENTITY_TYPES:
            raise ValueError("Unsupported dependency endpoint type")
        if entity_type == "EPIC":
            exists = self.db.scalar(
                select(DeliveryWorkItem.id).where(
                    DeliveryWorkItem.tenant_id == self.tenant_id,
                    DeliveryWorkItem.id == entity_id,
                    DeliveryWorkItem.item_kind == "EPIC",
                )
            )
        elif model := self.ENTITY_MODELS.get(entity_type):
            exists = self.db.scalar(
                select(model.id).where(
                    model.tenant_id == self.tenant_id,
                    model.id == entity_id,
                )
            )
        else:
            exists = (
                entity_id
                if external and entity_type in self.PLACEHOLDER_TYPES
                else None
            )
        if exists is None:
            raise ValueError("Dependency endpoint does not exist or is inaccessible")

    def create(
        self,
        values: dict[str, Any],
        source: tuple[str, str],
        target: tuple[str, str],
        trace_id: str,
    ) -> DeliveryDependency:
        if source == target:
            raise ValueError("Dependency provider and consumer must differ")
        relationship_type = values.get("relationship_type", "DEPENDS_ON")
        if relationship_type not in RELATIONSHIP_TYPES:
            raise ValueError("Unsupported dependency relationship type")
        external = bool(values.get("external"))
        self.validate_endpoint(*source, external=external)
        self.validate_endpoint(*target, external=external)
        dependencies, endpoints = self.graph_records()
        for dependency in dependencies:
            pair = endpoints.get(dependency.id, {})
            if "SOURCE" in pair and "TARGET" in pair:
                existing = (
                    (pair["SOURCE"].entity_type, pair["SOURCE"].entity_id),
                    (pair["TARGET"].entity_type, pair["TARGET"].entity_id),
                    dependency.relationship_type,
                )
                if existing == (
                    source,
                    target,
                    relationship_type,
                ) and dependency.status not in {"RESOLVED", "CLOSED", "CANCELLED"}:
                    raise ValueError(
                        f"Duplicate active dependency relationship: {dependency.reference}"
                    )
        graph, _ = self.graph()
        proposed = GraphEdge(
            "candidate",
            f"{source[0]}:{source[1]}",
            f"{target[0]}:{target[1]}",
            relationship_type,
        )
        if cycle := graph.cycle_path(proposed):
            raise ValueError(
                f"Dependency relationship would create a cycle: {' → '.join(cycle)}"
            )
        dependency = DeliveryDependency(
            tenant_id=self.tenant_id,
            created_by=self.actor_id,
            updated_by=self.actor_id,
            **values,
        )
        self.db.add(dependency)
        self.db.flush()
        self.db.add_all(
            [
                DeliveryDependencyEndpoint(
                    tenant_id=self.tenant_id,
                    dependency_id=dependency.id,
                    direction=direction,
                    entity_type=endpoint[0],
                    entity_id=endpoint[1],
                )
                for direction, endpoint in (("SOURCE", source), ("TARGET", target))
            ]
        )
        self._history(dependency, "CREATED", trace_id, new_status=dependency.status)
        self.db.flush()
        return dependency

    def update(
        self,
        dependency: DeliveryDependency,
        values: dict[str, Any],
        *,
        version: int,
        trace_id: str,
    ) -> DeliveryDependency:
        if dependency.version != version:
            raise ValueError("Dependency was modified by another user")
        before = {key: getattr(dependency, key) for key in values}
        for key, value in values.items():
            setattr(dependency, key, value)
        dependency.updated_by = self.actor_id
        dependency.version += 1
        self._history(
            dependency,
            "UPDATED",
            trace_id,
            change_data={"before": before, "fields": sorted(values)},
        )
        self.db.flush()
        return dependency

    def transition(
        self,
        dependency: DeliveryDependency,
        requested: str,
        *,
        version: int,
        reason: str | None,
        trace_id: str,
    ) -> DeliveryDependency:
        if dependency.version != version:
            raise ValueError("Dependency was modified by another user")
        validate_transition(dependency.status, requested, reason)
        previous = dependency.status
        dependency.status = requested
        dependency.updated_by = self.actor_id
        dependency.version += 1
        if requested == "ACKNOWLEDGED":
            dependency.acknowledged_at = datetime.now(UTC)
        if requested == "BLOCKED" and not dependency.blocked_since:
            dependency.blocked_since = datetime.now(UTC)
        if requested == "RESOLVED":
            dependency.resolved_at = datetime.now(UTC)
            dependency.actual_resolution_date = datetime.now(UTC).date()
        self._history(
            dependency,
            "STATUS_TRANSITION",
            trace_id,
            previous_status=previous,
            new_status=requested,
            note=reason,
        )
        self.db.flush()
        return dependency

    def reopen(
        self,
        dependency: DeliveryDependency,
        *,
        version: int,
        reason: str,
        trace_id: str,
    ) -> DeliveryDependency:
        if dependency.status not in {"RESOLVED", "CLOSED"}:
            raise ValueError("Only resolved or closed dependencies can be reopened")
        if dependency.version != version:
            raise ValueError("Dependency was modified by another user")
        previous = dependency.status
        dependency.status = "ACKNOWLEDGED"
        dependency.resolved_at = None
        dependency.actual_resolution_date = None
        dependency.version += 1
        dependency.updated_by = self.actor_id
        self._history(
            dependency,
            "REOPENED",
            trace_id,
            previous_status=previous,
            new_status="ACKNOWLEDGED",
            note=reason,
        )
        self.db.flush()
        return dependency

    def acknowledge(
        self, dependency: DeliveryDependency, *, version: int, trace_id: str
    ) -> DeliveryDependency:
        if dependency.version != version:
            raise ValueError("Dependency was modified by another user")
        previous = dependency.status
        if previous in {"IDENTIFIED", "PROPOSED"}:
            dependency.status = "ACKNOWLEDGED"
        dependency.acknowledged_at = datetime.now(UTC)
        dependency.provider_owner_id = dependency.provider_owner_id or self.actor_id
        dependency.version += 1
        dependency.updated_by = self.actor_id
        self._history(
            dependency,
            "ACKNOWLEDGED",
            trace_id,
            previous_status=previous,
            new_status=dependency.status,
        )
        self.db.flush()
        return dependency

    def details(self, dependency: DeliveryDependency) -> dict[str, Any]:
        evidence = list(
            self.db.scalars(
                select(DeliveryEvidence)
                .where(
                    DeliveryEvidence.tenant_id == self.tenant_id,
                    DeliveryEvidence.dependency_id == dependency.id,
                )
                .order_by(DeliveryEvidence.captured_at.desc())
            )
        )
        history = list(
            self.db.scalars(
                select(DeliveryDependencyHistory)
                .where(
                    DeliveryDependencyHistory.tenant_id == self.tenant_id,
                    DeliveryDependencyHistory.dependency_id == dependency.id,
                )
                .order_by(DeliveryDependencyHistory.changed_at.desc())
            )
        )
        recommendations = list(
            self.db.scalars(
                select(DeliveryRecommendation).where(
                    DeliveryRecommendation.tenant_id == self.tenant_id,
                    DeliveryRecommendation.dependency_id == dependency.id,
                )
            )
        )
        proposals = list(
            self.db.scalars(
                select(ProposedAction).where(
                    ProposedAction.tenant_id == self.tenant_id,
                    ProposedAction.dependency_id == dependency.id,
                )
            )
        )
        scenarios = list(
            self.db.scalars(
                select(DeliveryDependencyScenario)
                .where(
                    DeliveryDependencyScenario.tenant_id == self.tenant_id,
                    DeliveryDependencyScenario.dependency_id == dependency.id,
                )
                .order_by(DeliveryDependencyScenario.created_at.desc())
            )
        )
        raid = list(
            self.db.scalars(
                select(DeliveryRAIDItem).where(
                    DeliveryRAIDItem.tenant_id == self.tenant_id,
                    DeliveryRAIDItem.dependency_id == dependency.id,
                )
            )
        )
        return {
            "evidence": evidence,
            "history": history,
            "recommendations": recommendations,
            "proposals": proposals,
            "scenarios": scenarios,
            "raid": raid,
        }

    def save_scenario(
        self, dependency_id: str, result: dict[str, Any], *, slip_days: int
    ) -> DeliveryDependencyScenario:
        scenario = DeliveryDependencyScenario(
            tenant_id=self.tenant_id,
            dependency_id=dependency_id,
            change_type="DELAY_DAYS",
            change_value={"days": slip_days},
            assumptions=result["assumptions"],
            baseline_result={"delayDays": 0},
            scenario_result=result,
            difference={
                "delayDays": slip_days,
                "affectedEntityCount": len(result["directlyAffectedEntities"])
                + len(result["indirectlyAffectedEntities"]),
            },
            confidence=result["confidence"],
            limitations=result["limitations"],
            status="SAVED",
            created_by=self.actor_id,
        )
        self.db.add(scenario)
        self.db.flush()
        return scenario

    def candidates(self) -> list[DetectedDependencyCandidate]:
        return list(
            self.db.scalars(
                select(DetectedDependencyCandidate)
                .where(
                    DetectedDependencyCandidate.tenant_id == self.tenant_id,
                    DetectedDependencyCandidate.status.in_(
                        ("DETECTED", "UNDER_REVIEW")
                    ),
                )
                .order_by(DetectedDependencyCandidate.detected_at.desc())
                .limit(50)
            )
        )

    def candidate(self, candidate_id: str) -> DetectedDependencyCandidate | None:
        return self.db.scalar(
            select(DetectedDependencyCandidate).where(
                DetectedDependencyCandidate.tenant_id == self.tenant_id,
                DetectedDependencyCandidate.id == candidate_id,
            )
        )

    def _history(
        self,
        dependency: DeliveryDependency,
        event_type: str,
        trace_id: str,
        *,
        previous_status: str | None = None,
        new_status: str | None = None,
        note: str | None = None,
        change_data: dict[str, Any] | None = None,
    ) -> None:
        self.db.add(
            DeliveryDependencyHistory(
                tenant_id=self.tenant_id,
                dependency_id=dependency.id,
                event_type=event_type,
                previous_status=previous_status,
                new_status=new_status,
                note=note,
                actor_id=self.actor_id,
                trace_id=trace_id,
                record_version=dependency.version,
                change_data=change_data or {},
            )
        )
