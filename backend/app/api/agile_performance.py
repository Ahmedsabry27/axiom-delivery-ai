from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.agents.application_service import AgentIdentity
from app.agile_intelligence.service import AgileIntelligenceService
from app.auth.dependencies import get_current_user
from app.database.dependencies import get_db
from app.delivery.metrics import metric_catalogue

router = APIRouter(prefix="/api/agile-performance", tags=["Agile Performance"])
DB = Annotated[Session, Depends(get_db)]
User = Annotated[dict, Depends(get_current_user)]


def service(db, user):
    return AgileIntelligenceService(db, AgentIdentity.from_claims(user))


class ObjectiveIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=255)
    description: str = ""
    level: str
    owner_id: str | None = None
    contributors: list[str] = []
    start_date: date
    target_date: date
    status: str = "DRAFT"
    confidence: float | None = None
    baseline: float | None = None
    target: float | None = None
    current_value: float | None = None
    unit: str = "percent"
    related_metrics: list[str] = []
    related_entities: list[dict] = []
    evidence_refs: list[dict] = []
    risks: list[dict] = []
    dependencies: list[dict] = []
    suggested_target: bool = False
    key_results: list[dict] = []


class ObjectivePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int
    description: str | None = None
    confidence: float | None = None
    baseline: float | None = None
    target: float | None = None
    current_value: float | None = None
    status: str | None = None
    target_date: date | None = None
    contributors: list[str] | None = None
    related_metrics: list[str] | None = None
    related_entities: list[dict] | None = None
    evidence_refs: list[dict] | None = None
    risks: list[dict] | None = None
    dependencies: list[dict] | None = None


class CheckInIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_value: float | None = None
    confidence: float | None = None
    status: str
    note: str = ""
    evidence_refs: list[dict] = []
    limitations: list[str] = []


@router.get("/summary")
def summary(
    db: DB, user: User, context_type: str | None = None, context_id: str | None = None
):
    return service(db, user).summary(context_type, context_id)


@router.get("/metrics")
def metrics(
    db: DB,
    user: User,
    context_type: str | None = None,
    context_id: str | None = None,
    metric_key: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=200),
):
    rows = [
        service(db, user).metric_json(row)
        for row in service(db, user).observations(context_type, context_id, metric_key)
    ]
    return {
        "items": rows[(page - 1) * page_size : page * page_size],
        "total": len(rows),
        "page": page,
        "pageSize": page_size,
        "definitions": metric_catalogue(),
    }


@router.get("/attention")
def attention(
    db: DB, user: User, context_type: str | None = None, context_id: str | None = None
):
    rows = service(db, user).observations(context_type, context_id)
    return {
        "items": [
            service(db, user).metric_json(row)
            for row in rows
            if row.status in {"RED", "CRITICAL", "AT_RISK"} or row.value is None
        ][:100]
    }


@router.get("/okrs")
def objectives(
    db: DB,
    user: User,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
):
    current = service(db, user)
    rows = [current.objective_json(row) for row in current.objectives()]
    return {
        "items": rows[(page - 1) * page_size : page * page_size],
        "total": len(rows),
        "page": page,
        "pageSize": page_size,
    }


@router.post("/okrs", status_code=201)
def create_objective(values: ObjectiveIn, db: DB, user: User):
    current = service(db, user)
    return current.objective_json(current.create_objective(values.model_dump()))


@router.get("/okrs/{objective_id}")
def objective(objective_id: str, db: DB, user: User):
    current = service(db, user)
    return current.objective_json(current.objective(objective_id))


@router.patch("/okrs/{objective_id}")
def update_objective(objective_id: str, values: ObjectivePatch, db: DB, user: User):
    current = service(db, user)
    payload = values.model_dump(exclude_unset=True)
    expected = payload.pop("expected_version")
    return current.objective_json(
        current.update_objective(objective_id, expected, payload)
    )


@router.post("/okrs/{objective_id}/check-ins", status_code=201)
def check_in(objective_id: str, values: CheckInIn, db: DB, user: User):
    current = service(db, user)
    current.check_in(objective_id, values.model_dump())
    return current.objective_json(current.objective(objective_id))
