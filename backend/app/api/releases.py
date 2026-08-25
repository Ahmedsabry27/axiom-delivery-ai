from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.audit.events import append_audit_event
from app.auth.dependencies import get_current_user
from app.database.dependencies import get_db
from app.database.models.delivery import DeliveryProject, DeliveryRelease

router = APIRouter(prefix="/api/releases", tags=["Releases"])


class ReleaseCreate(BaseModel):
    project_id: str
    name: str = Field(min_length=1, max_length=255)
    target_date: date | None = None
    lifecycle: str = Field(default="PLANNING", max_length=30)
    readiness_score: float | None = Field(default=None, ge=0, le=100)
    contract: dict[str, Any] = Field(default_factory=dict)


class ReleaseContractUpdate(BaseModel):
    version: int = Field(ge=1)
    contract: dict[str, Any]


class ReleaseDecisionRequest(BaseModel):
    decision: str
    rationale: str = Field(min_length=1, max_length=4000)
    conditions: list[str] = Field(default_factory=list, max_length=50)
    role: str = Field(default="Release approver", max_length=120)


def _tenant(user: dict) -> str:
    return str(user.get("custom:tenant_id", "default"))


def _authorize(user: dict, permission: str) -> None:
    permissions = set(user.get("permissions") or []) | set(
        str(user.get("scope") or "").split()
    )
    groups = {str(item).lower() for item in user.get("cognito:groups", []) or []}
    if (
        permission not in permissions
        and "release.admin" not in permissions
        and not (groups & {"admin", "administrators", "platform-admin"})
    ):
        raise HTTPException(403, "Insufficient release permission")


def _contract(row: DeliveryRelease) -> dict[str, Any]:
    stored = dict((row.record_metadata or {}).get("release_contract") or {})
    stored.update(
        {
            "id": row.id,
            "releaseId": stored.get("releaseId") or row.external_id or row.id,
            "name": row.name,
            "targetDate": stored.get("targetDate")
            or (row.planned_date.isoformat() if row.planned_date else None),
            "lifecycle": row.status,
            "readinessScore": row.readiness_score or 0,
            "updatedAt": row.updated_at.isoformat(),
            "recordVersion": row.version,
        }
    )
    return stored


def _get(db: Session, tenant_id: str, release_id: str) -> DeliveryRelease:
    row = (
        db.query(DeliveryRelease).filter_by(tenant_id=tenant_id, id=release_id).first()
    )
    if row is None:
        raise HTTPException(404, "Release not found")
    return row


@router.get("")
def list_releases(
    user: dict = Depends(get_current_user), db: Session = Depends(get_db)
):
    query = db.query(DeliveryRelease).filter_by(tenant_id=_tenant(user))
    if query.filter(DeliveryRelease.source_system == "JIRA").first():
        query = query.filter(DeliveryRelease.source_system == "JIRA")
    rows = query.order_by(
        DeliveryRelease.planned_date.asc(), DeliveryRelease.created_at.desc()
    ).all()
    return {"items": [_contract(row) for row in rows], "source": "database"}


@router.get("/{release_id}")
def get_release(
    release_id: str,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _contract(_get(db, _tenant(user), release_id))


@router.post("", status_code=201)
def create_release(
    payload: ReleaseCreate,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _authorize(user, "release.create")
    tenant_id = _tenant(user)
    if (
        db.query(DeliveryProject)
        .filter_by(tenant_id=tenant_id, id=payload.project_id)
        .first()
        is None
    ):
        raise HTTPException(422, "Project is unavailable for this tenant")
    row = DeliveryRelease(
        tenant_id=tenant_id,
        project_id=payload.project_id,
        name=payload.name,
        status=payload.lifecycle,
        planned_date=payload.target_date,
        readiness_score=payload.readiness_score,
        owner_id=user["sub"],
        created_by=user["sub"],
        updated_by=user["sub"],
        record_metadata={"release_contract": payload.contract},
    )
    db.add(row)
    db.flush()
    append_audit_event(
        db,
        tenant_id=tenant_id,
        actor_id=user["sub"],
        action="release.created",
        target_type="release",
        target_id=row.id,
    )
    db.commit()
    db.refresh(row)
    return _contract(row)


@router.put("/{release_id}/contract")
def update_release_contract(
    release_id: str,
    payload: ReleaseContractUpdate,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _authorize(user, "release.update")
    row = _get(db, _tenant(user), release_id)
    if payload.version != row.version:
        raise HTTPException(409, "Release changed; reload before saving")
    metadata = dict(row.record_metadata or {})
    metadata["release_contract"] = payload.contract
    row.record_metadata = metadata
    row.name = str(payload.contract.get("name") or row.name)
    row.status = str(payload.contract.get("lifecycle") or row.status)
    row.readiness_score = payload.contract.get("readinessScore", row.readiness_score)
    row.updated_by = user["sub"]
    row.version += 1
    append_audit_event(
        db,
        tenant_id=row.tenant_id,
        actor_id=user["sub"],
        action="release.contract.updated",
        target_type="release",
        target_id=row.id,
        metadata={"record_version": row.version},
    )
    db.commit()
    db.refresh(row)
    return _contract(row)


@router.post("/{release_id}/decisions", status_code=201)
def record_release_decision(
    release_id: str,
    payload: ReleaseDecisionRequest,
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _authorize(user, "release.approve")
    allowed = {"GO", "CONDITIONAL GO", "NO-GO", "Decision deferred"}
    if payload.decision not in allowed:
        raise HTTPException(422, "Unsupported release decision")
    row = _get(db, _tenant(user), release_id)
    contract = dict((row.record_metadata or {}).get("release_contract") or {})
    decision = {
        "decision": payload.decision,
        "owner": user["sub"],
        "role": payload.role,
        "timestamp": datetime.now(UTC).isoformat(),
        "rationale": payload.rationale,
        "conditions": payload.conditions,
    }
    history = list(contract.get("decisionHistory") or [])
    history.insert(0, {"id": f"decision-{row.version + 1}", **decision})
    contract.update({"currentDecision": decision, "decisionHistory": history})
    metadata = dict(row.record_metadata or {})
    metadata["release_contract"] = contract
    row.record_metadata = metadata
    row.version += 1
    row.updated_by = user["sub"]
    append_audit_event(
        db,
        tenant_id=row.tenant_id,
        actor_id=user["sub"],
        action="release.decision.recorded",
        target_type="release",
        target_id=row.id,
        metadata={"decision": payload.decision},
    )
    db.commit()
    db.refresh(row)
    return _contract(row)
