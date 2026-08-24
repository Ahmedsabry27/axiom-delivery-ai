from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.action_center.service import ACTION_TYPES, ActionCenterService
from app.agents.application_service import AgentIdentity
from app.auth.dependencies import get_current_user
from app.database.dependencies import get_db

router = APIRouter(prefix="/api", tags=["Approval and Action Center"])
Database = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[dict, Depends(get_current_user)]


class ActionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action_type: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=255)
    description: str = Field(default="", max_length=5000)
    origin: str = Field(default="USER", max_length=30)
    agent_id: str | None = Field(default=None, max_length=160)
    target_entity_type: str | None = Field(default=None, max_length=50)
    target_entity_id: str | None = Field(default=None, max_length=36)
    target_system: str = Field(default="INTERNAL", max_length=80)
    payload: dict[str, Any] = Field(default_factory=dict)
    evidence_ids: list[str] = Field(default_factory=list, max_length=100)
    idempotency_key: str | None = Field(default=None, max_length=120)
    trace_id: str | None = Field(default=None, max_length=80)


class ActionPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    action_type: str | None = Field(default=None, min_length=1, max_length=80)
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    target_entity_type: str | None = Field(default=None, max_length=50)
    target_entity_id: str | None = Field(default=None, max_length=36)
    target_system: str | None = Field(default=None, max_length=80)
    payload: dict[str, Any] | None = None
    evidence_ids: list[str] | None = Field(default=None, max_length=100)


class Submission(BaseModel):
    model_config = ConfigDict(extra="forbid")
    assigned_approver_id: str | None = Field(default=None, max_length=160)


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    comment: str = Field(default="", max_length=2000)


class Delegation(Decision):
    delegate_to: str = Field(min_length=1, max_length=160)


class Execution(BaseModel):
    model_config = ConfigDict(extra="forbid")
    idempotency_key: str = Field(min_length=8, max_length=120)


class PolicyEvaluation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action_type: str = Field(min_length=1, max_length=80)
    target_system: str = Field(default="INTERNAL", max_length=80)
    payload: dict[str, Any] = Field(default_factory=dict)


def _service(db: Session, user: dict) -> ActionCenterService:
    return ActionCenterService(db, AgentIdentity.from_claims(user))


@router.get("/action-types")
def action_types(user: CurrentUser):
    identity = AgentIdentity.from_claims(user)
    if not identity.allows("actions.read"):
        from fastapi import HTTPException

        raise HTTPException(
            403,
            {
                "code": "PERMISSION_DENIED",
                "message": "actions.read permission is required",
            },
        )
    return {"items": sorted(ACTION_TYPES)}


@router.get("/actions")
def list_actions(
    db: Database,
    user: CurrentUser,
    status: str | None = None,
    risk: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
):
    service = _service(db, user)
    rows = service.list_actions(status, risk)
    start = (page - 1) * page_size
    return {
        "items": [service.action_item(row) for row in rows[start : start + page_size]],
        "total": len(rows),
        "page": page,
    }


@router.get("/approvals/summary")
def approval_summary(db: Database, user: CurrentUser):
    service = _service(db, user)
    rows = service.list_approvals()
    now = datetime.now(UTC)

    def aware(value: datetime) -> datetime:
        return value if value.tzinfo else value.replace(tzinfo=UTC)

    pending = [row for row in rows if row.status == "PENDING"]
    decided = [row for row in rows if row.decided_at is not None]
    return {
        "awaitingMyDecision": sum(
            service.approval_authorization.capabilities(row).can_approve
            for row in pending
        ),
        "dueToday": sum(aware(row.expires_at).date() == now.date() for row in pending),
        "overdue": sum(aware(row.expires_at) < now for row in pending),
        "highRisk": sum(row.risk_level in {"HIGH", "CRITICAL"} for row in pending),
        "escalated": sum(
            bool((row.audit_metadata or {}).get("escalated")) for row in pending
        ),
        "delegatedToMe": sum(row.delegated_to == user.get("sub") for row in pending),
        "requestedChanges": sum(row.status == "CHANGES_REQUESTED" for row in rows),
        "approvedPeriod": sum(row.status == "APPROVED" for row in decided),
        "rejectedPeriod": sum(row.status == "REJECTED" for row in decided),
        "period": "visible records",
        "source": "approval_requests",
    }


@router.get("/approvals/submitted")
def submitted_approvals(
    db: Database,
    user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
):
    service = _service(db, user)
    rows = [
        row for row in service.list_approvals() if row.requester_id == user.get("sub")
    ]
    start = (page - 1) * page_size
    return {
        "items": [
            service.approval_item(row) for row in rows[start : start + page_size]
        ],
        "total": len(rows),
        "page": page,
    }


@router.get("/approvals/history")
def approval_history(
    db: Database,
    user: CurrentUser,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
):
    service = _service(db, user)
    terminal = {
        "APPROVED",
        "REJECTED",
        "WITHDRAWN",
        "EXPIRED",
        "CANCELLED",
        "SUPERSEDED",
    }
    rows = [row for row in service.list_approvals() if row.status in terminal]
    start = (page - 1) * page_size
    return {
        "items": [
            service.approval_item(row) for row in rows[start : start + page_size]
        ],
        "total": len(rows),
        "page": page,
    }


@router.post("/actions", status_code=201)
def create_action(payload: ActionCreate, db: Database, user: CurrentUser):
    service = _service(db, user)
    return service.action_item(service.create(payload.model_dump()))


@router.get("/actions/{action_id}")
def get_action(action_id: str, db: Database, user: CurrentUser):
    service = _service(db, user)
    service._require("actions.read")
    action = service._action(action_id)
    if action.requester_id != service.identity.actor_id and not service.identity.allows(
        "actions.read_all"
    ):
        from fastapi import HTTPException

        raise HTTPException(
            403, {"code": "PERMISSION_DENIED", "message": "Action is not visible"}
        )
    return service.action_item(action)


@router.patch("/actions/{action_id}")
def update_action(
    action_id: str, payload: ActionPatch, db: Database, user: CurrentUser
):
    values = payload.model_dump(exclude_unset=True)
    version = values.pop("expected_version")
    service = _service(db, user)
    return service.action_item(service.edit(action_id, values, version))


@router.post("/actions/{action_id}/submit")
def submit_action(action_id: str, payload: Submission, db: Database, user: CurrentUser):
    service = _service(db, user)
    return service.approval_item(
        service.submit(action_id, payload.assigned_approver_id)
    )


@router.post("/actions/{action_id}/execute")
def execute_action(action_id: str, payload: Execution, db: Database, user: CurrentUser):
    service = _service(db, user)
    return service.execution_item(service.execute(action_id, payload.idempotency_key))


@router.post("/actions/{action_id}/retry")
def retry_action(action_id: str, payload: Execution, db: Database, user: CurrentUser):
    service = _service(db, user)
    action = service._action(action_id)
    if action.status == "FAILED":
        action.status = "APPROVED"
        db.flush()
    return service.execution_item(service.execute(action_id, payload.idempotency_key))


@router.post("/actions/{action_id}/verify")
def verify_action(action_id: str, payload: Decision, db: Database, user: CurrentUser):
    verification = _service(db, user).verify(action_id, payload.comment)
    return {
        "id": verification.id,
        "status": verification.status,
        "observedResult": verification.observed_result,
        "verifiedBy": verification.verified_by,
        "verifiedAt": verification.verified_at.isoformat()
        if verification.verified_at
        else None,
    }


@router.post("/actions/{action_id}/cancel")
def cancel_action(action_id: str, payload: Decision, db: Database, user: CurrentUser):
    service = _service(db, user)
    return service.action_item(service.cancel(action_id, payload.comment))


@router.get("/approvals")
def list_approvals(
    db: Database,
    user: CurrentUser,
    status: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
):
    service = _service(db, user)
    rows = service.list_approvals(status)
    start = (page - 1) * page_size
    return {
        "items": [
            service.approval_item(row) for row in rows[start : start + page_size]
        ],
        "total": len(rows),
        "page": page,
    }


@router.get("/approvals/{approval_id}")
def get_approval(approval_id: str, db: Database, user: CurrentUser):
    service = _service(db, user)
    approval = service._approval(approval_id)
    service.approval_authorization.require_view(approval)
    result = service.approval_item(approval)
    result["action"] = service.action_item(
        service._action(str(approval.proposed_action_id))
    )
    return result


def _approval_context(approval_id: str, db: Session, user: dict):
    service = _service(db, user)
    approval = service._approval(approval_id)
    service.approval_authorization.require_view(approval)
    action = service._action(str(approval.proposed_action_id))
    return service, approval, action, service.action_item(action)


@router.get("/approvals/{approval_id}/capabilities")
def approval_capabilities(approval_id: str, db: Database, user: CurrentUser):
    service, approval, _, _ = _approval_context(approval_id, db, user)
    return service.approval_item(approval)["capabilities"]


@router.get("/approvals/{approval_id}/evidence")
def approval_evidence(approval_id: str, db: Database, user: CurrentUser):
    _, _, _, action = _approval_context(approval_id, db, user)
    evidence = action["evidence"]
    return {
        "items": evidence,
        "available": len(evidence),
        "required": 1,
        "missing": max(0, 1 - len(evidence)),
        "stale": 0,
        "conflicting": 0,
    }


@router.get("/approvals/{approval_id}/impact")
def approval_impact(approval_id: str, db: Database, user: CurrentUser):
    service, approval, action_row, action = _approval_context(approval_id, db, user)
    policy = service.policy_for(
        action_row.action_type, action_row.target_system, action_row.payload
    )
    return {
        "riskLevel": approval.risk_level,
        "policy": policy,
        "targetSystem": action["targetSystem"],
        "targetEntityType": action["targetEntityType"],
        "reversibility": (action_row.payload or {}).get(
            "reversibility", "POLICY_DEFINED"
        ),
        "separationOfDuties": approval.separation_of_duties,
        "explanation": {
            "whyApprovalRequired": f"{approval.risk_level.title()} risk action governed by policy",
            "whyRequesterCannotApprove": "Separation of duties is enforced"
            if approval.separation_of_duties
            else "Policy does not require separation",
            "afterApproval": "The related action becomes eligible for controlled execution",
            "notAutomatic": "Approval does not imply execution or successful verification",
        },
    }


@router.get("/approvals/{approval_id}/execution")
def approval_execution(approval_id: str, db: Database, user: CurrentUser):
    _, _, _, action = _approval_context(approval_id, db, user)
    return {
        "actionId": action["id"],
        "actionStatus": action["status"],
        "executions": action["executions"],
        "verificationSeparate": True,
        "idempotency": "tenant + proposed action + idempotency key",
    }


@router.get("/approvals/{approval_id}/activity")
def approval_activity(approval_id: str, db: Database, user: CurrentUser):
    service, approval, _, action = _approval_context(approval_id, db, user)
    decisions = service.approval_item(approval)["decisions"]
    decision_events = [
        {
            "id": item["id"],
            "event": f"approval.{item['decision'].lower()}",
            "actorId": item["actorId"],
            "occurredAt": item["createdAt"],
            "reason": item.get("comment"),
        }
        for item in decisions
    ]
    audit_events = [
        {
            "id": item["id"],
            "event": item["action"],
            "actorId": item["actorId"],
            "occurredAt": item["occurredAt"],
            "correlationId": item.get("correlationId"),
        }
        for item in action["auditTrail"]
    ]
    return {
        "items": sorted(
            [*audit_events, *decision_events],
            key=lambda item: item.get("occurredAt") or "",
        )
    }


@router.post("/approvals/{approval_id}/approve")
def approve(approval_id: str, payload: Decision, db: Database, user: CurrentUser):
    service = _service(db, user)
    return service.approval_item(
        service.decide(approval_id, "APPROVED", payload.comment)
    )


@router.post("/approvals/{approval_id}/reject")
def reject(approval_id: str, payload: Decision, db: Database, user: CurrentUser):
    service = _service(db, user)
    return service.approval_item(
        service.decide(approval_id, "REJECTED", payload.comment)
    )


@router.post("/approvals/{approval_id}/request-changes")
def request_changes(
    approval_id: str, payload: Decision, db: Database, user: CurrentUser
):
    service = _service(db, user)
    return service.approval_item(
        service.decide(approval_id, "CHANGES_REQUESTED", payload.comment)
    )


@router.post("/approvals/{approval_id}/delegate")
def delegate(approval_id: str, payload: Delegation, db: Database, user: CurrentUser):
    service = _service(db, user)
    return service.approval_item(
        service.delegate(approval_id, payload.delegate_to, payload.comment)
    )


@router.get("/action-policies")
def policies(db: Database, user: CurrentUser):
    service = _service(db, user)
    return {"items": [service.policy_item(row) for row in service.list_policies()]}


@router.post("/action-policies/evaluate")
def evaluate(payload: PolicyEvaluation, db: Database, user: CurrentUser):
    return _service(db, user).evaluate(
        payload.action_type, payload.target_system, payload.payload
    )


@router.get("/notifications")
def notifications(db: Database, user: CurrentUser, unread_only: bool = False):
    service = _service(db, user)
    rows = service.list_notifications(unread_only)
    return {"items": [service.notification_item(row) for row in rows]}


@router.post("/notifications/{notification_id}/read")
def read_notification(notification_id: str, db: Database, user: CurrentUser):
    service = _service(db, user)
    return service.notification_item(service.read_notification(notification_id))
