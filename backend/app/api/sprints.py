from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.database.dependencies import get_db
from app.delivery.read_service import DeliveryReadService

router = APIRouter(prefix="/api/sprints", tags=["Sprint Intelligence"])


def service(user: dict, db: Session) -> DeliveryReadService:
    return DeliveryReadService(db, user["custom:tenant_id"], user["sub"])


@router.get("")
def list_sprints(
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return service(user, db).sprint_list(limit=limit, offset=offset)


@router.get("/{sprint_id}")
def get_sprint(
    sprint_id: str,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    detail = service(user, db).sprint_detail(sprint_id)
    if detail is None:
        raise HTTPException(404, "Sprint not found or not accessible")
    return {**detail, "tenantId": user["custom:tenant_id"]}


@router.get("/{sprint_id}/{section}")
def get_sprint_section(
    sprint_id: str,
    section: str,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    allowed = {
        "metrics",
        "health",
        "forecast",
        "burndown",
        "work-items",
        "blockers",
        "readiness",
        "quality",
        "anti-patterns",
        "recommendations",
        "comparison",
        "daily-brief",
        "retrospective-insights",
    }
    if section not in allowed:
        raise HTTPException(404, "Sprint Intelligence section not found")
    detail = get_sprint(sprint_id, user, db)
    keys = {
        "health": ("healthScore", "healthDimensions"),
        "forecast": ("forecastDetail",),
        "work-items": ("workItems",),
        "anti-patterns": ("antiPatterns",),
        "daily-brief": ("limitations",),
        "retrospective-insights": ("limitations",),
    }
    selected = keys.get(section, (section,))
    return {
        "sprintId": sprint_id,
        "section": section,
        "data": {key: detail.get(key) for key in selected},
        "traceId": f"persisted-{sprint_id}-{section}",
        "externalWrites": False,
    }
