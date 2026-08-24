from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, HttpUrl
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.audit.events import append_audit_event
from app.auth.dependencies import get_current_user
from app.database.dependencies import get_db
from app.database.models.delivery import (
    DeliveryDependency,
    DeliveryDependencyHistory,
    DeliveryEvidence,
    DetectedDependencyCandidate,
    ProposedAction,
    ProposedActionEvidence,
)
from app.delivery.dependency_intelligence import (
    GRAPH_LIMITS,
    DependencyGraph,
    GraphEdge,
    GraphLimitError,
    dependency_health,
    dependency_priority,
    impact_result,
)
from app.delivery.dependency_repository import DependencyRepository

router = APIRouter(prefix="/api/dependencies", tags=["Dependency Intelligence"])


class EndpointInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    entity_type: str = Field(min_length=2, max_length=30)
    entity_id: str = Field(min_length=1, max_length=255)


class DependencyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reference: str = Field(min_length=2, max_length=40)
    name: str = Field(min_length=2, max_length=255)
    description: str = Field(min_length=2, max_length=10000)
    project_id: str
    dependency_type: str = Field(min_length=2, max_length=40)
    relationship_type: str = "DEPENDS_ON"
    provider: EndpointInput
    consumer: EndpointInput
    status: str = "IDENTIFIED"
    priority: str | None = None
    impact: str | None = None
    owner_id: str | None = None
    provider_owner_id: str | None = None
    consumer_owner_id: str | None = None
    required_by_date: date | None = None
    committed_resolution_date: date | None = None
    forecast_resolution_date: date | None = None
    next_review_date: date | None = None
    critical_path: bool = False
    external: bool = False
    source_system: str = "MANUAL"
    source_url: HttpUrl | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class DependencyPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int = Field(ge=1)
    name: str | None = Field(default=None, min_length=2, max_length=255)
    description: str | None = Field(default=None, min_length=2, max_length=10000)
    priority: str | None = None
    impact: str | None = None
    owner_id: str | None = None
    provider_owner_id: str | None = None
    consumer_owner_id: str | None = None
    required_by_date: date | None = None
    committed_resolution_date: date | None = None
    forecast_resolution_date: date | None = None
    next_review_date: date | None = None
    critical_path: bool | None = None


class TransitionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str
    version: int = Field(ge=1)
    reason: str | None = Field(default=None, max_length=5000)


class VersionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int = Field(ge=1)


class ReopenInput(VersionInput):
    reason: str = Field(min_length=2, max_length=5000)


class PathInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: str = Field(min_length=3, max_length=300)
    target: str = Field(min_length=3, max_length=300)
    max_depth: int = Field(default=8, ge=1, le=GRAPH_LIMITS["max_depth"])
    max_paths: int = Field(default=10, ge=1, le=GRAPH_LIMITS["max_paths"])


class ImpactInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dependency_id: str
    slip_days: int = Field(ge=-30, le=365)
    depth: int = Field(default=5, ge=1, le=GRAPH_LIMITS["max_depth"])


class ScenarioInput(ImpactInput):
    save: bool = False


class EvidenceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=2, max_length=500)
    summary: str | None = Field(default=None, max_length=10000)
    source_type: str = Field(min_length=2, max_length=80)
    source_system: str = Field(min_length=2, max_length=40)
    source_record_id: str = Field(min_length=1, max_length=255)
    source_url: HttpUrl | None = None


class ProposalInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action_type: Literal[
        "DRAFT_ESCALATION",
        "DRAFT_PROVIDER_FOLLOW_UP",
        "REQUEST_OWNER",
        "REQUEST_COMMITTED_DATE",
        "REQUEST_DECISION",
        "PROPOSE_ALTERNATE_DEPENDENCY",
        "PROPOSE_MITIGATION",
        "PROPOSE_STATUS_REVIEW",
    ]
    content: str = Field(min_length=2, max_length=10000)
    owner_id: str | None = None
    due_date: date | None = None
    status: Literal["DRAFT", "PROPOSED", "PENDING_APPROVAL"] = "PROPOSED"
    evidence_ids: list[str] = Field(default_factory=list, max_length=50)


class DismissInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=2, max_length=5000)


class CandidateAcceptInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project_id: str
    reference: str
    name: str | None = None
    description: str | None = None
    owner_id: str | None = None
    required_by_date: date | None = None
    forecast_resolution_date: date | None = None


class CopilotInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=2, max_length=10000)
    dependency_id: str | None = None
    slip_days: int | None = Field(default=None, ge=-30, le=365)


def _identity(user: dict) -> tuple[str, str]:
    tenant_id, actor_id = user.get("custom:tenant_id"), user.get("sub")
    if not tenant_id or not actor_id:
        raise HTTPException(401, "Incomplete authenticated identity")
    return tenant_id, actor_id


def _authorize(user: dict, capability: str) -> None:
    permissions = set(user.get("permissions") or [])
    if (
        permissions
        and capability not in permissions
        and "dependency.admin" not in permissions
    ):
        raise HTTPException(403, "Insufficient dependency permission")


def _repository(db: Session, user: dict, capability: str) -> DependencyRepository:
    _authorize(user, capability)
    tenant_id, actor_id = _identity(user)
    return DependencyRepository(db, tenant_id, actor_id)


def _audit(
    db: Session,
    user: dict,
    action: str,
    target_id: str,
    trace_id: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    tenant_id, actor_id = _identity(user)
    append_audit_event(
        db,
        tenant_id=tenant_id,
        actor_id=actor_id,
        action=action,
        target_type="DEPENDENCY",
        target_id=target_id,
        correlation_id=trace_id,
        metadata=metadata,
    )


def _commit(db: Session, operation):
    try:
        result = operation()
        db.commit()
        return result
    except GraphLimitError as exc:
        db.rollback()
        raise HTTPException(413, str(exc)) from exc
    except ValueError as exc:
        db.rollback()
        message = str(exc)
        status_code = (
            409
            if any(
                word in message.lower() for word in ("cycle", "duplicate", "modified")
            )
            else 422
        )
        raise HTTPException(status_code, message) from exc
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            409, "Dependency change conflicts with an existing record"
        ) from exc


def _require(repo: DependencyRepository, dependency_id: str) -> DeliveryDependency:
    dependency = repo.get(dependency_id)
    if dependency is None:
        raise HTTPException(404, "Dependency not found")
    return dependency


def _iso(value: Any) -> Any:
    return value.isoformat() if isinstance(value, (date, datetime)) else value


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _evidence_counts(db: Session, tenant_id: str, ids: list[str]) -> dict[str, int]:
    if not ids:
        return {}
    rows = db.execute(
        select(DeliveryEvidence.dependency_id, func.count(DeliveryEvidence.id))
        .where(
            DeliveryEvidence.tenant_id == tenant_id,
            DeliveryEvidence.dependency_id.in_(ids),
        )
        .group_by(DeliveryEvidence.dependency_id)
    )
    return {dependency_id: count for dependency_id, count in rows}


def _endpoint_json(endpoint, labels: dict[str, str]) -> dict[str, Any]:
    key = f"{endpoint.entity_type}:{endpoint.entity_id}"
    return {
        "key": key,
        "entityType": endpoint.entity_type,
        "entityId": endpoint.entity_id,
        "name": labels.get(key, endpoint.entity_id),
    }


def _views(
    repo: DependencyRepository, dependencies: list[DeliveryDependency]
) -> list[dict[str, Any]]:
    endpoint_map = repo.endpoints_for([item.id for item in dependencies])
    graph, _ = repo.graph()
    evidence_counts = _evidence_counts(
        repo.db, repo.tenant_id, [item.id for item in dependencies]
    )
    labels = repo.entity_labels(graph.nodes)
    views = []
    for item in dependencies:
        pair = endpoint_map.get(item.id, {})
        source, target = pair.get("SOURCE"), pair.get("TARGET")
        target_key = f"{target.entity_type}:{target.entity_id}" if target else ""
        downstream = (
            graph.traverse(
                target_key, direction="downstream", depth=GRAPH_LIMITS["max_depth"]
            )["nodes"]
            if target_key
            else []
        )
        downstream_nodes = [node["id"] for node in downstream]
        health = dependency_health(
            item,
            evidence_count=evidence_counts.get(item.id, 0),
            downstream_count=len(downstream_nodes),
        )
        priority = dependency_priority(
            item,
            downstream_nodes=downstream_nodes,
            evidence_count=evidence_counts.get(item.id, 0),
        )
        views.append(
            {
                "id": item.id,
                "reference": item.reference,
                "name": item.name,
                "description": item.description,
                "dependencyType": item.dependency_type,
                "relationshipType": item.relationship_type,
                "status": item.status,
                "health": health,
                "priority": priority,
                "impact": item.impact,
                "ownerId": item.owner_id,
                "providerOwnerId": item.provider_owner_id,
                "consumerOwnerId": item.consumer_owner_id,
                "provider": _endpoint_json(source, labels) if source else None,
                "consumer": _endpoint_json(target, labels) if target else None,
                "requiredByDate": _iso(item.required_by_date),
                "committedResolutionDate": _iso(item.committed_resolution_date),
                "forecastResolutionDate": _iso(item.forecast_resolution_date),
                "actualResolutionDate": _iso(item.actual_resolution_date),
                "identifiedAt": _iso(item.identified_at),
                "acknowledgedAt": _iso(item.acknowledged_at),
                "blockedSince": _iso(item.blocked_since),
                "lastReviewedAt": _iso(item.last_reviewed_at),
                "nextReviewDate": _iso(item.next_review_date),
                "criticalPath": item.critical_path,
                "external": item.external,
                "sourceSystem": item.source_system,
                "sourceUrl": item.source_url,
                "projectId": item.project_id,
                "ageDays": max(
                    (datetime.now(UTC) - _aware(item.identified_at)).days, 0
                ),
                "evidenceCount": evidence_counts.get(item.id, 0),
                "downstreamCount": len(downstream_nodes),
                "version": item.version,
                "updatedAt": _iso(item.updated_at),
            }
        )
    return views


def _graph_json(
    repo: DependencyRepository,
    graph: DependencyGraph,
    records: dict[str, DeliveryDependency],
    *,
    selected: set[str] | None = None,
) -> dict[str, Any]:
    selected = selected or graph.nodes
    labels = repo.entity_labels(selected)
    nodes = [
        {
            "id": key,
            "entityType": key.split(":", 1)[0],
            "entityId": key.split(":", 1)[1],
            "name": labels.get(key, key.split(":", 1)[1]),
            "upstreamCount": len(graph.incoming[key]),
            "downstreamCount": len(graph.outgoing[key]),
        }
        for key in sorted(selected)
    ]
    edges = []
    for edge in graph.edges:
        if edge.source not in selected or edge.target not in selected:
            continue
        record = records[edge.dependency_id]
        edges.append(
            {
                "id": edge.dependency_id,
                "reference": record.reference,
                "source": edge.source,
                "target": edge.target,
                "relationshipType": edge.relationship_type,
                "status": edge.status,
                "criticalPath": edge.critical,
                "requiredByDate": _iso(edge.required_by),
                "forecastResolutionDate": _iso(edge.forecast_resolution),
            }
        )
    return {
        "nodes": nodes,
        "edges": edges,
        "nodeCount": len(nodes),
        "edgeCount": len(edges),
        "limits": GRAPH_LIMITS,
    }


@router.get("", summary="List authorized persisted dependencies")
def list_dependencies(
    project_id: str | None = None,
    dependency_status: str | None = Query(default=None, alias="status"),
    priority: str | None = None,
    owner_id: str | None = None,
    external: bool | None = None,
    critical_path: bool = False,
    overdue: bool = False,
    unowned: bool = False,
    search: str | None = Query(default=None, max_length=200),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    sort: str = "updated_at",
    direction: str = "desc",
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo = _repository(db, user, "dependency.read")
    items, total = repo.list(
        {
            "project_id": project_id,
            "status": dependency_status,
            "priority": priority,
            "owner_id": owner_id,
            "external": external,
            "critical_path": critical_path,
            "overdue": overdue,
            "unowned": unowned,
            "search": search,
            "page": page,
            "page_size": page_size,
            "sort": sort,
            "direction": direction,
        }
    )
    return {
        "items": _views(repo, items),
        "page": page,
        "pageSize": page_size,
        "total": total,
        "pages": (total + page_size - 1) // page_size,
        "generatedAt": datetime.now(UTC).isoformat(),
        "source": "persisted",
    }


@router.post("", status_code=201, summary="Create a reviewed dependency relationship")
def create_dependency(
    payload: DependencyCreate,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo = _repository(db, user, "dependency.create")
    trace_id = str(uuid4())
    values = payload.model_dump(exclude={"provider", "consumer", "metadata"})
    values["source_url"] = (
        str(values["source_url"]) if values.get("source_url") else None
    )
    values["record_metadata"] = payload.metadata

    def operation():
        dependency = repo.create(
            values,
            (payload.provider.entity_type, payload.provider.entity_id),
            (payload.consumer.entity_type, payload.consumer.entity_id),
            trace_id,
        )
        _audit(db, user, "DEPENDENCY_CREATED", dependency.id, trace_id)
        return dependency

    dependency = _commit(db, operation)
    return {
        "item": _views(repo, [dependency])[0],
        "traceId": trace_id,
        "externalWrites": False,
    }


@router.get("/summary")
def dependency_summary(
    user: dict = Depends(get_current_user), db: Session = Depends(get_db)
):
    repo = _repository(db, user, "dependency.read")
    items, _ = repo.list({"page": 1, "page_size": 100})
    views = _views(repo, items)
    graph, _ = repo.graph()
    today = datetime.now(UTC).date()
    return {
        "criticalDependencies": sum(
            item["priority"]["band"] == "CRITICAL" for item in views
        ),
        "atRiskDependencies": sum(
            item["status"] in {"AT_RISK", "ESCALATED"} for item in views
        ),
        "blockedDependencies": sum(item["status"] == "BLOCKED" for item in views),
        "overdueDependencies": sum(
            bool(
                item["requiredByDate"]
                and date.fromisoformat(item["requiredByDate"]) < today
                and item["status"] not in {"RESOLVED", "CLOSED", "CANCELLED"}
            )
            for item in views
        ),
        "unownedDependencies": sum(not item["ownerId"] for item in views),
        "criticalPaths": len(graph.critical_paths()),
        "generatedAt": datetime.now(UTC).isoformat(),
        "source": "persisted",
    }


@router.get("/attention")
def dependency_attention(
    user: dict = Depends(get_current_user), db: Session = Depends(get_db)
):
    repo = _repository(db, user, "dependency.read")
    items, _ = repo.list({"page": 1, "page_size": 100})
    return {
        "items": sorted(
            _views(repo, items),
            key=lambda item: item["priority"]["score"],
            reverse=True,
        )[:20],
        "generatedAt": datetime.now(UTC).isoformat(),
    }


@router.get("/graph")
def dependency_graph(
    root: str | None = None,
    direction: Literal["upstream", "downstream"] = "downstream",
    depth: int = Query(default=3, ge=1, le=GRAPH_LIMITS["max_depth"]),
    limit: int = Query(default=200, ge=1, le=500),
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo = _repository(db, user, "dependency.analyse")
    try:
        graph, records = repo.graph()
        selected = (
            {
                root,
                *[
                    item["id"]
                    for item in graph.traverse(root, direction=direction, depth=depth)[
                        "nodes"
                    ]
                ],
            }
            if root
            else set(sorted(graph.nodes)[:limit])
        )
        result = _graph_json(repo, graph, records, selected=selected)
    except GraphLimitError as exc:
        raise HTTPException(413, str(exc)) from exc
    trace_id = str(uuid4())
    _audit(
        db,
        user,
        "DEPENDENCY_GRAPH_QUERIED",
        root or "graph",
        trace_id,
        {"nodes": result["nodeCount"], "edges": result["edgeCount"], "depth": depth},
    )
    db.commit()
    return {
        **result,
        "traceId": trace_id,
        "generatedAt": datetime.now(UTC).isoformat(),
        "source": "persisted",
    }


@router.post("/graph/paths")
def dependency_paths(
    payload: PathInput,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo = _repository(db, user, "dependency.analyse")
    graph, _ = repo.graph()
    paths = graph.paths(
        payload.source,
        payload.target,
        max_paths=payload.max_paths,
        max_depth=payload.max_depth,
    )
    trace_id = str(uuid4())
    _audit(
        db,
        user,
        "DEPENDENCY_PATH_ANALYSED",
        payload.source,
        trace_id,
        {"target": payload.target, "paths": len(paths)},
    )
    db.commit()
    return {
        "paths": [[edge.dependency_id for edge in path] for path in paths],
        "pathNodes": [
            [path[0].source, *[edge.target for edge in path]] for path in paths
        ],
        "traceId": trace_id,
        "limitations": [],
    }


def _impact(
    repo: DependencyRepository, payload: ImpactInput
) -> tuple[dict[str, Any], GraphEdge]:
    dependency = _require(repo, payload.dependency_id)
    graph, _ = repo.graph()
    edge = next(
        (item for item in graph.edges if item.dependency_id == dependency.id), None
    )
    if edge is None:
        raise HTTPException(422, "Dependency has incomplete graph endpoints")
    return impact_result(
        graph, edge, slip_days=payload.slip_days, depth=payload.depth
    ), edge


@router.post("/graph/impact")
def graph_impact(
    payload: ImpactInput,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo = _repository(db, user, "dependency.analyse")
    result, _ = _impact(repo, payload)
    trace_id = str(uuid4())
    _audit(
        db,
        user,
        "DEPENDENCY_IMPACT_ANALYSED",
        payload.dependency_id,
        trace_id,
        {
            "slipDays": payload.slip_days,
            "affected": len(result["directlyAffectedEntities"])
            + len(result["indirectlyAffectedEntities"]),
        },
    )
    db.commit()
    return {
        "dependencyId": payload.dependency_id,
        "slipDays": payload.slip_days,
        **result,
        "traceId": trace_id,
    }


@router.post("/graph/scenarios")
def dependency_scenario(
    payload: ScenarioInput,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo = _repository(db, user, "dependency.analyse")
    result, _ = _impact(repo, payload)
    trace_id = str(uuid4())

    def operation():
        scenario = (
            repo.save_scenario(
                payload.dependency_id, result, slip_days=payload.slip_days
            )
            if payload.save
            else None
        )
        _audit(
            db,
            user,
            "DEPENDENCY_SCENARIO_SAVED" if payload.save else "DEPENDENCY_SCENARIO_RUN",
            payload.dependency_id,
            trace_id,
            {"slipDays": payload.slip_days, "readOnly": True},
        )
        return scenario

    scenario = _commit(db, operation)
    return {
        "scenarioId": scenario.id if scenario else f"simulation-{trace_id}",
        "baseDependencyId": payload.dependency_id,
        "changeType": "DELAY_DAYS",
        "changeValue": {"days": payload.slip_days},
        "baselineResult": {"delayDays": 0},
        "scenarioResult": result,
        "difference": {"delayDays": payload.slip_days},
        "saved": bool(scenario),
        "simulation": True,
        "authoritativeRecordsChanged": False,
        "traceId": trace_id,
    }


@router.get("/critical-paths")
def critical_paths(
    user: dict = Depends(get_current_user), db: Session = Depends(get_db)
):
    repo = _repository(db, user, "dependency.analyse")
    graph, _ = repo.graph()
    return {
        "items": graph.critical_paths(),
        "generatedAt": datetime.now(UTC).isoformat(),
        "source": "deterministic persisted graph",
    }


@router.get("/bottlenecks")
def bottlenecks(user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    repo = _repository(db, user, "dependency.analyse")
    graph, _ = repo.graph()
    return {
        "items": graph.bottlenecks(),
        "generatedAt": datetime.now(UTC).isoformat(),
        "source": "deterministic persisted graph",
    }


@router.get("/detected")
def detected_candidates(
    user: dict = Depends(get_current_user), db: Session = Depends(get_db)
):
    repo = _repository(db, user, "dependency.review_candidates")
    return {
        "items": [_candidate_json(item) for item in repo.candidates()],
        "generatedAt": datetime.now(UTC).isoformat(),
    }


@router.post("/copilot")
def dependency_copilot(
    payload: CopilotInput,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo = _repository(db, user, "dependency.analyse")
    graph, _ = repo.graph()
    dependency = (
        _require(repo, payload.dependency_id) if payload.dependency_id else None
    )
    selected = _views(repo, [dependency])[0] if dependency else None
    impact = (
        _impact(
            repo, ImpactInput(dependency_id=dependency.id, slip_days=payload.slip_days)
        )[0]
        if dependency and payload.slip_days is not None
        else None
    )
    trace_id = str(uuid4())
    _audit(
        db,
        user,
        "COPILOT_DEPENDENCY_QUESTION",
        dependency.id if dependency else "portfolio",
        trace_id,
        {"questionLength": len(payload.question)},
    )
    db.commit()
    return {
        "context": {
            "dependencyId": dependency.id if dependency else None,
            "question": payload.question,
        },
        "summary": f"{selected['reference']} is {selected['status']} with {selected['priority']['band']} deterministic priority."
        if selected
        else f"The authorized graph contains {len(graph.nodes)} entities and {len(graph.edges)} dependencies.",
        "dependencyHealth": selected["health"] if selected else None,
        "criticalPaths": graph.critical_paths(),
        "affectedEntities": impact["directlyAffectedEntities"]
        + impact["indirectlyAffectedEntities"]
        if impact
        else [],
        "impactAnalysis": impact,
        "bottlenecks": graph.bottlenecks()[:5],
        "recommendations": _recommendations(selected),
        "evidence": [],
        "confidence": 0.8 if selected else 0.7,
        "limitations": [
            "Authoritative path, score, and impact calculations are deterministic; no external action was executed."
        ],
        "generatedAt": datetime.now(UTC).isoformat(),
        "traceId": trace_id,
        "responseType": "DEPENDENCY_INTELLIGENCE",
        "externalWrites": False,
    }


@router.get("/{dependency_id}")
def dependency_detail(
    dependency_id: str,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo = _repository(db, user, "dependency.read")
    dependency = _require(repo, dependency_id)
    item = _views(repo, [dependency])[0]
    details = repo.details(dependency)
    graph, _ = repo.graph()
    edge = next(
        (value for value in graph.edges if value.dependency_id == dependency.id), None
    )
    upstream = (
        graph.traverse(edge.source, direction="upstream", depth=3)
        if edge
        else {"nodes": []}
    )
    downstream = (
        graph.traverse(edge.target, direction="downstream", depth=3)
        if edge
        else {"nodes": []}
    )
    return {
        "item": item,
        "upstream": upstream["nodes"],
        "downstream": downstream["nodes"],
        "evidence": [_evidence_json(value) for value in details["evidence"]],
        "recommendations": [
            {
                "id": value.id,
                "title": value.title,
                "explanation": value.explanation,
                "priority": value.priority,
                "confidence": value.confidence,
            }
            for value in details["recommendations"]
        ],
        "proposals": [
            {
                "id": value.id,
                "actionType": value.action_type,
                "content": value.content,
                "status": value.status,
                "createdAt": _iso(value.created_at),
            }
            for value in details["proposals"]
        ],
        "scenarios": [
            {
                "id": value.id,
                "changeType": value.change_type,
                "changeValue": value.change_value,
                "difference": value.difference,
                "createdAt": _iso(value.created_at),
            }
            for value in details["scenarios"]
        ],
        "history": [_history_json(value) for value in details["history"]],
        "relatedRAID": [
            {
                "id": value.id,
                "reference": value.reference,
                "name": value.name,
                "status": value.status,
            }
            for value in details["raid"]
        ],
        "recommendationDrafts": _recommendations(item),
        "traceId": str(uuid4()),
        "source": "persisted",
        "externalWrites": False,
    }


@router.patch("/{dependency_id}")
def update_dependency(
    dependency_id: str,
    payload: DependencyPatch,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo = _repository(db, user, "dependency.update")
    dependency = _require(repo, dependency_id)
    trace_id = str(uuid4())
    values = payload.model_dump(exclude={"version"}, exclude_unset=True)

    def operation():
        updated = repo.update(
            dependency, values, version=payload.version, trace_id=trace_id
        )
        _audit(
            db,
            user,
            "DEPENDENCY_UPDATED",
            dependency.id,
            trace_id,
            {"fields": sorted(values)},
        )
        return updated

    updated = _commit(db, operation)
    return {"item": _views(repo, [updated])[0], "traceId": trace_id}


@router.post("/{dependency_id}/transition")
def transition_dependency(
    dependency_id: str,
    payload: TransitionInput,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    capability = (
        "dependency.close"
        if payload.status == "CLOSED"
        else "dependency.resolve"
        if payload.status == "RESOLVED"
        else "dependency.update"
    )
    repo = _repository(db, user, capability)
    dependency = _require(repo, dependency_id)
    trace_id = str(uuid4())

    def operation():
        updated = repo.transition(
            dependency,
            payload.status,
            version=payload.version,
            reason=payload.reason,
            trace_id=trace_id,
        )
        _audit(
            db,
            user,
            "DEPENDENCY_STATUS_TRANSITION",
            dependency.id,
            trace_id,
            {"status": payload.status},
        )
        return updated

    updated = _commit(db, operation)
    return {
        "item": _views(repo, [updated])[0],
        "traceId": trace_id,
        "externalWrites": False,
    }


@router.post("/{dependency_id}/acknowledge")
def acknowledge_dependency(
    dependency_id: str,
    payload: VersionInput,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo = _repository(db, user, "dependency.acknowledge")
    dependency = _require(repo, dependency_id)
    trace_id = str(uuid4())

    def operation():
        updated = repo.acknowledge(
            dependency, version=payload.version, trace_id=trace_id
        )
        _audit(db, user, "DEPENDENCY_ACKNOWLEDGED", dependency.id, trace_id)
        return updated

    updated = _commit(db, operation)
    return {"item": _views(repo, [updated])[0], "traceId": trace_id}


@router.post("/{dependency_id}/reopen")
def reopen_dependency(
    dependency_id: str,
    payload: ReopenInput,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo = _repository(db, user, "dependency.update")
    dependency = _require(repo, dependency_id)
    trace_id = str(uuid4())
    updated = _commit(
        db,
        lambda: repo.reopen(
            dependency,
            version=payload.version,
            reason=payload.reason,
            trace_id=trace_id,
        ),
    )
    return {"item": _views(repo, [updated])[0], "traceId": trace_id}


@router.post("/{dependency_id}/evidence", status_code=201)
def add_dependency_evidence(
    dependency_id: str,
    payload: EvidenceInput,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo = _repository(db, user, "dependency.manage_evidence")
    dependency = _require(repo, dependency_id)
    trace_id = str(uuid4())

    def operation():
        evidence = DeliveryEvidence(
            tenant_id=repo.tenant_id,
            entity_type="DEPENDENCY",
            entity_id=dependency.id,
            dependency_id=dependency.id,
            source_type=payload.source_type,
            source_system=payload.source_system,
            source_record_id=payload.source_record_id,
            title=payload.title,
            summary=payload.summary,
            source_url=str(payload.source_url) if payload.source_url else None,
        )
        db.add(evidence)
        db.flush()
        repo._history(
            dependency,
            "EVIDENCE_LINKED",
            trace_id,
            change_data={"evidenceId": evidence.id},
        )
        _audit(
            db,
            user,
            "DEPENDENCY_EVIDENCE_LINKED",
            dependency.id,
            trace_id,
            {"evidenceId": evidence.id},
        )
        return evidence

    evidence = _commit(db, operation)
    return {"evidence": _evidence_json(evidence), "traceId": trace_id}


@router.get("/{dependency_id}/upstream")
def dependency_upstream(
    dependency_id: str,
    depth: int = Query(default=3, ge=1, le=GRAPH_LIMITS["max_depth"]),
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _dependency_traversal(dependency_id, "upstream", depth, user, db)


@router.get("/{dependency_id}/downstream")
def dependency_downstream(
    dependency_id: str,
    depth: int = Query(default=3, ge=1, le=GRAPH_LIMITS["max_depth"]),
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _dependency_traversal(dependency_id, "downstream", depth, user, db)


def _dependency_traversal(
    dependency_id: str, direction: str, depth: int, user: dict, db: Session
):
    repo = _repository(db, user, "dependency.analyse")
    _require(repo, dependency_id)
    graph, _ = repo.graph()
    edge = next(
        (value for value in graph.edges if value.dependency_id == dependency_id), None
    )
    if edge is None:
        raise HTTPException(422, "Dependency has incomplete graph endpoints")
    start = edge.source if direction == "upstream" else edge.target
    traversal = graph.traverse(start, direction=direction, depth=depth)
    return {
        "dependencyId": dependency_id,
        "direction": direction,
        "nodes": traversal["nodes"],
        "dependencies": [value.dependency_id for value in traversal["edges"]],
        "maximumDepth": traversal["maxDepth"],
    }


@router.get("/{dependency_id}/impact")
def dependency_impact(
    dependency_id: str,
    slip_days: int = Query(default=1, ge=-30, le=365),
    depth: int = Query(default=5, ge=1, le=GRAPH_LIMITS["max_depth"]),
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return graph_impact(
        ImpactInput(dependency_id=dependency_id, slip_days=slip_days, depth=depth),
        user,
        db,
    )


@router.get("/{dependency_id}/history")
def dependency_history(
    dependency_id: str,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo = _repository(db, user, "dependency.read")
    _require(repo, dependency_id)
    rows = db.scalars(
        select(DeliveryDependencyHistory)
        .where(
            DeliveryDependencyHistory.tenant_id == repo.tenant_id,
            DeliveryDependencyHistory.dependency_id == dependency_id,
        )
        .order_by(DeliveryDependencyHistory.changed_at.desc())
    )
    return {"items": [_history_json(value) for value in rows], "source": "persisted"}


@router.post("/{dependency_id}/proposals", status_code=201)
def create_dependency_proposal(
    dependency_id: str,
    payload: ProposalInput,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo = _repository(db, user, "dependency.update")
    dependency = _require(repo, dependency_id)
    trace_id = str(uuid4())

    def operation():
        evidence = (
            list(
                db.scalars(
                    select(DeliveryEvidence).where(
                        DeliveryEvidence.tenant_id == repo.tenant_id,
                        DeliveryEvidence.dependency_id == dependency.id,
                        DeliveryEvidence.id.in_(payload.evidence_ids),
                    )
                )
            )
            if payload.evidence_ids
            else []
        )
        if len(evidence) != len(set(payload.evidence_ids)):
            raise ValueError("One or more evidence references are inaccessible")
        proposal = ProposedAction(
            tenant_id=repo.tenant_id,
            dependency_id=dependency.id,
            trace_id=trace_id,
            action_type=payload.action_type,
            title=payload.content[:255],
            description=payload.content,
            content=payload.content,
            origin="USER",
            requester_id=repo.actor_id,
            target_entity_type="DEPENDENCY",
            target_entity_id=dependency.id,
            target_system="INTERNAL",
            payload={"content": payload.content, "dependency_id": dependency.id},
            original_payload={
                "content": payload.content,
                "dependency_id": dependency.id,
            },
            owner_id=payload.owner_id,
            due_date=payload.due_date,
            status=payload.status,
            created_by=repo.actor_id,
            approval_required=True,
        )
        db.add(proposal)
        db.flush()
        db.add_all(
            [
                ProposedActionEvidence(
                    tenant_id=repo.tenant_id,
                    proposed_action_id=proposal.id,
                    evidence_id=item.id,
                )
                for item in evidence
            ]
        )
        repo._history(
            dependency,
            "PROPOSED_INTERVENTION_CREATED",
            trace_id,
            change_data={"proposalId": proposal.id},
        )
        _audit(
            db,
            user,
            "DEPENDENCY_PROPOSED_INTERVENTION_CREATED",
            dependency.id,
            trace_id,
            {"proposalId": proposal.id},
        )
        return proposal

    proposal = _commit(db, operation)
    return {
        "proposal": {
            "id": proposal.id,
            "actionType": proposal.action_type,
            "content": proposal.content,
            "status": proposal.status,
        },
        "traceId": trace_id,
        "approvalRequired": True,
        "externalWrites": False,
    }


@router.post("/detected/{candidate_id}/accept", status_code=201)
def accept_candidate(
    candidate_id: str,
    payload: CandidateAcceptInput,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo = _repository(db, user, "dependency.review_candidates")
    candidate = repo.candidate(candidate_id)
    if candidate is None:
        raise HTTPException(404, "Dependency candidate not found")
    if candidate.status not in {"DETECTED", "UNDER_REVIEW"}:
        raise HTTPException(409, "Dependency candidate was already reviewed")
    trace_id = str(uuid4())
    values = {
        "reference": payload.reference,
        "name": payload.name or candidate.title,
        "description": payload.description or candidate.description,
        "project_id": payload.project_id,
        "dependency_type": candidate.candidate_type,
        "relationship_type": candidate.relationship_type,
        "status": "IDENTIFIED",
        "priority": candidate.suggested_priority,
        "owner_id": payload.owner_id or candidate.suggested_owner,
        "required_by_date": payload.required_by_date
        or candidate.suggested_required_by_date,
        "forecast_resolution_date": payload.forecast_resolution_date,
        "critical_path": candidate.candidate_type == "POSSIBLE_CRITICAL_PATH",
        "external": candidate.provider_entity_type in repo.PLACEHOLDER_TYPES
        or candidate.consumer_entity_type in repo.PLACEHOLDER_TYPES,
        "source_system": "AI_DETECTED",
        "record_metadata": {"candidateId": candidate.id, "humanReviewed": True},
    }

    def operation():
        dependency = repo.create(
            values,
            (candidate.provider_entity_type, candidate.provider_entity_id),
            (candidate.consumer_entity_type, candidate.consumer_entity_id),
            trace_id,
        )
        candidate.status, candidate.reviewed_by, candidate.reviewed_at = (
            "ACCEPTED",
            repo.actor_id,
            datetime.now(UTC),
        )
        candidate.accepted_dependency_id, candidate.version = (
            dependency.id,
            candidate.version + 1,
        )
        _audit(
            db,
            user,
            "DEPENDENCY_CANDIDATE_ACCEPTED",
            dependency.id,
            trace_id,
            {"candidateId": candidate.id},
        )
        return dependency

    dependency = _commit(db, operation)
    return {
        "item": _views(repo, [dependency])[0],
        "candidateId": candidate.id,
        "traceId": trace_id,
        "externalWrites": False,
    }


@router.post("/detected/{candidate_id}/dismiss")
def dismiss_candidate(
    candidate_id: str,
    payload: DismissInput,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo = _repository(db, user, "dependency.review_candidates")
    candidate = repo.candidate(candidate_id)
    if candidate is None:
        raise HTTPException(404, "Dependency candidate not found")
    trace_id = str(uuid4())

    def operation():
        if candidate.status not in {"DETECTED", "UNDER_REVIEW"}:
            raise ValueError("Dependency candidate was already reviewed")
        candidate.status, candidate.reviewed_by, candidate.reviewed_at = (
            "DISMISSED",
            repo.actor_id,
            datetime.now(UTC),
        )
        candidate.dismissal_reason, candidate.version = (
            payload.reason,
            candidate.version + 1,
        )
        _audit(
            db,
            user,
            "DEPENDENCY_CANDIDATE_DISMISSED",
            candidate.id,
            trace_id,
            {"reason": payload.reason},
        )
        return candidate

    _commit(db, operation)
    return {
        "candidate": _candidate_json(candidate),
        "traceId": trace_id,
        "externalWrites": False,
    }


@router.post("/detected/{candidate_id}/merge")
def merge_candidate(
    candidate_id: str,
    dependency_id: str,
    payload: DismissInput,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repo = _repository(db, user, "dependency.review_candidates")
    candidate, dependency = repo.candidate(candidate_id), _require(repo, dependency_id)
    if candidate is None:
        raise HTTPException(404, "Dependency candidate not found")
    trace_id = str(uuid4())

    def operation():
        if candidate.status not in {"DETECTED", "UNDER_REVIEW"}:
            raise ValueError("Dependency candidate was already reviewed")
        candidate.status, candidate.reviewed_by, candidate.reviewed_at = (
            "MERGED",
            repo.actor_id,
            datetime.now(UTC),
        )
        (
            candidate.dismissal_reason,
            candidate.merged_dependency_id,
            candidate.version,
        ) = payload.reason, dependency.id, candidate.version + 1
        _audit(
            db,
            user,
            "DEPENDENCY_CANDIDATE_MERGED",
            dependency.id,
            trace_id,
            {"candidateId": candidate.id},
        )
        return candidate

    _commit(db, operation)
    return {
        "candidate": _candidate_json(candidate),
        "dependencyId": dependency.id,
        "traceId": trace_id,
    }


def _candidate_json(candidate: DetectedDependencyCandidate) -> dict[str, Any]:
    return {
        "id": candidate.id,
        "candidateType": candidate.candidate_type,
        "title": candidate.title,
        "description": candidate.description,
        "provider": {
            "entityType": candidate.provider_entity_type,
            "entityId": candidate.provider_entity_id,
        },
        "consumer": {
            "entityType": candidate.consumer_entity_type,
            "entityId": candidate.consumer_entity_id,
        },
        "relationshipType": candidate.relationship_type,
        "confidence": candidate.confidence,
        "affectedEntities": candidate.affected_entities or [],
        "possibleDuplicates": candidate.possible_duplicates or [],
        "possibleCycle": candidate.possible_cycle or [],
        "suggestedOwner": candidate.suggested_owner,
        "suggestedRequiredByDate": _iso(candidate.suggested_required_by_date),
        "suggestedPriority": candidate.suggested_priority,
        "limitations": candidate.limitations or [],
        "detectedAt": _iso(candidate.detected_at),
        "agent": candidate.detected_by_agent,
        "model": candidate.model,
        "traceId": candidate.trace_id,
        "status": candidate.status,
        "version": candidate.version,
    }


def _evidence_json(evidence: DeliveryEvidence) -> dict[str, Any]:
    return {
        "id": evidence.id,
        "title": evidence.title,
        "summary": evidence.summary,
        "sourceType": evidence.source_type,
        "sourceSystem": evidence.source_system,
        "sourceUrl": evidence.source_url,
        "capturedAt": _iso(evidence.captured_at),
    }


def _history_json(history: DeliveryDependencyHistory) -> dict[str, Any]:
    return {
        "id": history.id,
        "eventType": history.event_type,
        "previousStatus": history.previous_status,
        "newStatus": history.new_status,
        "note": history.note,
        "actorId": history.actor_id,
        "traceId": history.trace_id,
        "recordVersion": history.record_version,
        "changedAt": _iso(history.changed_at),
        "changeData": history.change_data or {},
    }


def _recommendations(item: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not item:
        return []
    recommendations = []
    if not item["ownerId"]:
        recommendations.append(
            {
                "recommendation": "Assign an accountable dependency owner.",
                "reason": "The persisted dependency has no owner.",
                "priority": "HIGH",
                "proposedActionType": "REQUEST_OWNER",
                "limitations": [],
            }
        )
    if (
        item["forecastResolutionDate"]
        and item["requiredByDate"]
        and item["forecastResolutionDate"] > item["requiredByDate"]
    ):
        recommendations.append(
            {
                "recommendation": f"Draft an escalation for {item['reference']}.",
                "reason": "Forecast resolution is after the required-by date.",
                "priority": "CRITICAL",
                "proposedActionType": "DRAFT_ESCALATION",
                "limitations": ["Human review is required before any communication."],
            }
        )
    if item["evidenceCount"] == 0:
        recommendations.append(
            {
                "recommendation": "Link current delivery evidence.",
                "reason": "No authorized evidence supports the current status.",
                "priority": "MEDIUM",
                "proposedActionType": "PROPOSE_STATUS_REVIEW",
                "limitations": [],
            }
        )
    return recommendations
