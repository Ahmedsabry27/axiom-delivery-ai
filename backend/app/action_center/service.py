from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.action_center.authorization import ApprovalAuthorizationService
from app.agents.application_service import AgentIdentity
from app.audit.events import append_audit_event
from app.database.models.action_center import (
    ActionExecution,
    ActionNotification,
    ActionPolicyDefinition,
    ActionVerification,
    ApprovalDecision,
)
from app.database.models.audit import AuditLog
from app.database.models.delivery import (
    DeliveryEvidence,
    DeliveryRAIDItem,
    ProposedAction,
    ProposedActionEvidence,
)
from app.database.models.governance_workflow import ApprovalRequest
from app.delivery.raid_repository import RAIDRepository

ACTION_TYPES = {
    "CREATE_RAID_ITEM",
    "UPDATE_RAID_ITEM",
    "CREATE_DEPENDENCY",
    "UPDATE_DEPENDENCY",
    "CREATE_DELIVERY_ACTION",
    "UPDATE_DELIVERY_ACTION",
    "ASSIGN_OWNER",
    "REQUEST_DECISION",
    "DRAFT_ESCALATION",
    "DRAFT_FOLLOW_UP",
    "DRAFT_STATUS_REPORT",
    "DRAFT_EXECUTIVE_SUMMARY",
    "SCHEDULE_REVIEW",
    "SEND_MESSAGE",
    "CREATE_CALENDAR_EVENT",
    "UPDATE_EXTERNAL_WORK_ITEM",
    "TRIGGER_WORKFLOW",
}
EXTERNAL_DRAFT_ONLY = {
    "DRAFT_ESCALATION",
    "DRAFT_FOLLOW_UP",
    "DRAFT_STATUS_REPORT",
    "DRAFT_EXECUTIVE_SUMMARY",
    "SCHEDULE_REVIEW",
    "SEND_MESSAGE",
    "CREATE_CALENDAR_EVENT",
    "UPDATE_EXTERNAL_WORK_ITEM",
}
EXECUTION_ADAPTERS = {
    "CREATE_RAID_ITEM": "INTERNAL_RAID_CREATE_V1",
    "UPDATE_RAID_ITEM": "INTERNAL_RAID_UPDATE_V1",
}
MATERIAL_FIELDS = {
    "action_type",
    "title",
    "description",
    "target_entity_type",
    "target_entity_id",
    "target_system",
    "payload",
    "evidence_ids",
}
TERMINAL_ACTION_STATES = {
    "VERIFIED",
    "REJECTED",
    "CANCELLED",
    "EXPIRED",
}


def _now() -> datetime:
    return datetime.now(UTC)


def _iso(value: datetime | date | None) -> str | None:
    return value.isoformat() if value else None


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def _error(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status, {"code": code, "message": message})


def _hash_payload(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


class ActionCenterService:
    """Single transition authority for proposed actions and linked approvals."""

    def __init__(self, db: Session, identity: AgentIdentity):
        self.db = db
        self.identity = identity
        self.approval_authorization = ApprovalAuthorizationService(identity)

    def _require(self, permission: str) -> None:
        if not self.identity.allows(permission):
            raise _error(
                403, "PERMISSION_DENIED", f"{permission} permission is required"
            )

    def _action(self, action_id: str) -> ProposedAction:
        row = (
            self.db.query(ProposedAction)
            .filter_by(id=action_id, tenant_id=self.identity.tenant_id)
            .first()
        )
        if row is None:
            raise _error(404, "ACTION_NOT_FOUND", "Proposed action was not found")
        return row

    def _action_for_update(self, action_id: str) -> ProposedAction:
        row = (
            self.db.query(ProposedAction)
            .filter_by(id=action_id, tenant_id=self.identity.tenant_id)
            .with_for_update()
            .first()
        )
        if row is None:
            raise _error(404, "ACTION_NOT_FOUND", "Proposed action was not found")
        return row

    def _approval(self, approval_id: str) -> ApprovalRequest:
        row = (
            self.db.query(ApprovalRequest)
            .filter_by(
                id=approval_id,
                tenant_id=self.identity.tenant_id,
            )
            .filter(ApprovalRequest.proposed_action_id.is_not(None))
            .first()
        )
        if row is None:
            raise _error(404, "APPROVAL_NOT_FOUND", "Approval request was not found")
        return row

    @staticmethod
    def policy_for(action_type: str, target_system: str, payload: dict) -> dict:
        action_type = action_type.upper()
        target_system = target_system.upper()
        known = action_type in ACTION_TYPES
        external = target_system != "INTERNAL" or action_type in EXTERNAL_DRAFT_ONLY
        executable = action_type in EXECUTION_ADAPTERS and not external
        risk = "RESTRICTED"
        approvals = 2
        reasons: list[str] = []
        if not known:
            reasons.append("Unknown action types fail closed")
        elif external:
            risk = "HIGH"
            approvals = 1
            reasons.append(
                "External operations are draft-only without an approved connector"
            )
        elif action_type == "CREATE_RAID_ITEM":
            risk = "MEDIUM"
            approvals = 1
            reasons.append("Creates a governed internal delivery record")
        elif action_type == "UPDATE_RAID_ITEM":
            risk = "HIGH"
            approvals = 1
            reasons.append("Changes an existing governed delivery record")
        else:
            risk = "HIGH"
            approvals = 1
            reasons.append("No explicit internal execution adapter is registered")
        if payload.get("critical_path") or payload.get("production_impact"):
            risk = "RESTRICTED"
            approvals = max(approvals, 2)
            reasons.append(
                "Critical-path or production impact requires restricted handling"
            )
        return {
            "actionType": action_type,
            "knownActionType": known,
            "riskLevel": risk,
            "approvalRequired": risk != "LOW",
            "requiredApprovalCount": approvals,
            "separationOfDuties": risk in {"MEDIUM", "HIGH", "RESTRICTED"},
            "evidenceRequired": risk in {"MEDIUM", "HIGH", "RESTRICTED"},
            "verificationRequired": executable,
            "executionAllowed": executable,
            "adapter": EXECUTION_ADAPTERS.get(action_type) if executable else None,
            "draftOnly": external or not executable,
            "reasons": reasons,
            "policyVersion": 1,
        }

    def _policy_row(self, action_type: str, evaluation: dict) -> ActionPolicyDefinition:
        row = (
            self.db.query(ActionPolicyDefinition)
            .filter_by(
                tenant_id=self.identity.tenant_id,
                action_type=action_type,
                version=evaluation["policyVersion"],
            )
            .first()
        )
        if row:
            return row
        row = ActionPolicyDefinition(
            tenant_id=self.identity.tenant_id,
            name=f"Axiom default policy: {action_type}",
            version=evaluation["policyVersion"],
            status="ACTIVE",
            action_type=action_type,
            conditions={"targetSystem": "INTERNAL"},
            risk_level=evaluation["riskLevel"],
            approval_rules={
                "required": evaluation["approvalRequired"],
                "count": evaluation["requiredApprovalCount"],
                "separationOfDuties": evaluation["separationOfDuties"],
            },
            verification_rules={"required": evaluation["verificationRequired"]},
            execution_rules={
                "allowed": evaluation["executionAllowed"],
                "adapter": evaluation["adapter"],
                "draftOnly": evaluation["draftOnly"],
            },
            activated_at=_now(),
        )
        self.db.add(row)
        self.db.flush()
        return row

    def evaluate(self, action_type: str, target_system: str, payload: dict) -> dict:
        self._require("actions.read")
        return self.policy_for(action_type, target_system, payload)

    def create(self, values: dict[str, Any]) -> ProposedAction:
        self._require("actions.create")
        action_type = values["action_type"].upper()
        target_system = values.get("target_system", "INTERNAL").upper()
        payload = values.get("payload") or {}
        idem = values.get("idempotency_key")
        if idem:
            existing = (
                self.db.query(ProposedAction)
                .filter_by(tenant_id=self.identity.tenant_id, idempotency_key=idem)
                .first()
            )
            if existing:
                return existing
        evaluation = self.policy_for(action_type, target_system, payload)
        policy = self._policy_row(action_type, evaluation)
        action = ProposedAction(
            tenant_id=self.identity.tenant_id,
            action_type=action_type,
            title=values["title"],
            description=values.get("description") or "",
            content=values.get("description") or values["title"],
            origin=values.get("origin", "USER").upper(),
            requester_id=self.identity.actor_id,
            agent_id=values.get("agent_id"),
            target_entity_type=values.get("target_entity_type"),
            target_entity_id=values.get("target_entity_id"),
            target_system=target_system,
            target=values.get("target_entity_id"),
            owner_id=self.identity.actor_id,
            payload=payload,
            original_payload=payload,
            status="DRAFT",
            risk_classification=evaluation["riskLevel"],
            risk_level=evaluation["riskLevel"],
            policy_id=policy.id,
            policy_version=policy.version,
            approval_required=evaluation["approvalRequired"],
            required_approval_count=evaluation["requiredApprovalCount"],
            expires_at=_now() + timedelta(days=7),
            idempotency_key=idem,
            trace_id=values.get("trace_id") or str(uuid4()),
            created_by=self.identity.actor_id,
        )
        self.db.add(action)
        self.db.flush()
        self._replace_evidence(action, values.get("evidence_ids", []))
        self._audit("action.created", action, after={"status": action.status})
        self.db.commit()
        self.db.refresh(action)
        return action

    def edit(
        self, action_id: str, values: dict[str, Any], expected_version: int
    ) -> ProposedAction:
        self._require("actions.edit")
        action = self._action(action_id)
        if action.requester_id != self.identity.actor_id and not self.identity.allows(
            "actions.admin"
        ):
            raise _error(
                403, "PERMISSION_DENIED", "Only the requester can edit this action"
            )
        if action.version != expected_version:
            raise _error(
                409, "STALE_ACTION_VERSION", "The action changed; reload before editing"
            )
        if action.status not in {"DRAFT", "CHANGES_REQUESTED"}:
            raise _error(
                409, "INVALID_ACTION_TRANSITION", "Only editable actions can be changed"
            )
        before = self.action_item(action)
        material = bool(MATERIAL_FIELDS.intersection(values))
        for key in (
            "title",
            "description",
            "target_entity_type",
            "target_entity_id",
            "target_system",
            "payload",
        ):
            if key in values:
                setattr(action, key, values[key])
        if "action_type" in values:
            action.action_type = values["action_type"].upper()
        if "evidence_ids" in values:
            self._replace_evidence(action, values["evidence_ids"])
        if material:
            action.version += 1
            action.status = "DRAFT"
            evaluation = self.policy_for(
                action.action_type, action.target_system, action.payload
            )
            policy = self._policy_row(action.action_type, evaluation)
            action.risk_level = evaluation["riskLevel"]
            action.risk_classification = evaluation["riskLevel"]
            action.policy_id = policy.id
            action.policy_version = policy.version
            action.required_approval_count = evaluation["requiredApprovalCount"]
            pending = (
                self.db.query(ApprovalRequest)
                .filter_by(
                    tenant_id=self.identity.tenant_id, proposed_action_id=action.id
                )
                .filter(ApprovalRequest.status == "PENDING")
                .all()
            )
            for approval in pending:
                approval.status = "SUPERSEDED"
        action.updated_at = _now()
        self._audit(
            "action.edited", action, before=before, after={"version": action.version}
        )
        self.db.commit()
        self.db.refresh(action)
        return action

    def _replace_evidence(
        self, action: ProposedAction, evidence_ids: list[str]
    ) -> None:
        self.db.query(ProposedActionEvidence).filter_by(
            tenant_id=self.identity.tenant_id, proposed_action_id=action.id
        ).delete()
        unique_ids = list(dict.fromkeys(evidence_ids))
        if not unique_ids:
            return
        evidence = (
            self.db.query(DeliveryEvidence)
            .filter(
                DeliveryEvidence.tenant_id == self.identity.tenant_id,
                DeliveryEvidence.id.in_(unique_ids),
            )
            .all()
        )
        if len(evidence) != len(unique_ids):
            raise _error(
                422, "INVALID_EVIDENCE", "Evidence must exist in the same tenant"
            )
        self.db.add_all(
            [
                ProposedActionEvidence(
                    tenant_id=self.identity.tenant_id,
                    proposed_action_id=action.id,
                    evidence_id=evidence_id,
                )
                for evidence_id in unique_ids
            ]
        )

    def _evidence(self, action: ProposedAction) -> list[DeliveryEvidence]:
        return (
            self.db.query(DeliveryEvidence)
            .join(
                ProposedActionEvidence,
                (ProposedActionEvidence.tenant_id == DeliveryEvidence.tenant_id)
                & (ProposedActionEvidence.evidence_id == DeliveryEvidence.id),
            )
            .filter(
                ProposedActionEvidence.tenant_id == self.identity.tenant_id,
                ProposedActionEvidence.proposed_action_id == action.id,
            )
            .all()
        )

    def submit(
        self, action_id: str, assigned_approver_id: str | None
    ) -> ApprovalRequest:
        self._require("approvals.request")
        action = self._action(action_id)
        if action.requester_id is None:
            action.requester_id = action.created_by
            action.owner_id = action.owner_id or action.created_by
        if action.requester_id != self.identity.actor_id and not self.identity.allows(
            "actions.admin"
        ):
            raise _error(
                403, "PERMISSION_DENIED", "Only the requester can submit this action"
            )
        if action.status not in {"DRAFT", "PROPOSED", "CHANGES_REQUESTED"}:
            existing = (
                self.db.query(ApprovalRequest)
                .filter_by(
                    tenant_id=self.identity.tenant_id,
                    proposed_action_id=action.id,
                    action_version=action.version,
                )
                .filter(ApprovalRequest.status.in_(["PENDING", "APPROVED"]))
                .first()
            )
            if existing:
                return existing
            raise _error(409, "INVALID_ACTION_TRANSITION", "Action cannot be submitted")
        evaluation = self.policy_for(
            action.action_type, action.target_system, action.payload
        )
        evidence = self._evidence(action)
        if evaluation["evidenceRequired"] and not evidence:
            raise _error(
                422,
                "EVIDENCE_REQUIRED",
                "Current tenant-authorized evidence is required",
            )
        if any((_now() - _aware(row.captured_at)).days > 90 for row in evidence):
            raise _error(
                422, "STALE_EVIDENCE", "Evidence older than 90 days must be refreshed"
            )
        policy = self._policy_row(action.action_type, evaluation)
        action.risk_level = evaluation["riskLevel"]
        action.policy_id = policy.id
        action.policy_version = policy.version
        action.required_approval_count = evaluation["requiredApprovalCount"]
        action.submitted_at = _now()
        action.status = "PENDING_APPROVAL"
        action.expires_at = action.expires_at or (_now() + timedelta(days=7))
        summary = {
            "actionId": action.id,
            "title": action.title,
            "actionType": action.action_type,
            "targetSystem": action.target_system,
            "targetEntityType": action.target_entity_type,
            "targetEntityId": action.target_entity_id,
            "version": action.version,
        }
        token = str(uuid4()) + str(uuid4())
        approval = ApprovalRequest(
            tenant_id=self.identity.tenant_id,
            proposed_action_id=action.id,
            action_version=action.version,
            tool_name=f"action:{action.action_type}",
            tool_version=str(policy.version),
            requester_id=self.identity.actor_id,
            requester_agent_id=action.agent_id,
            policy_id=policy.id,
            policy_version=policy.version,
            assigned_approver_id=assigned_approver_id,
            required_approval_count=evaluation["requiredApprovalCount"],
            separation_of_duties=evaluation["separationOfDuties"],
            risk_level=evaluation["riskLevel"],
            environment=action.target_system,
            safe_action_summary=summary,
            input_fingerprint=_hash_payload(action.payload),
            status="PENDING",
            expires_at=action.expires_at,
            resume_token_hash=hashlib.sha256(token.encode()).hexdigest(),
            audit_metadata={"evidenceIds": [row.id for row in evidence]},
        )
        self.db.add(approval)
        self.db.flush()
        if assigned_approver_id:
            self._notify(
                assigned_approver_id,
                "APPROVAL_ASSIGNED",
                f"Approval required: {action.title}",
                "Review this evidence-backed proposed action.",
                f"/approvals/{approval.id}",
                action,
                approval,
            )
        self._audit("action.submitted", action, after=summary)
        self.db.commit()
        self.db.refresh(approval)
        return approval

    def decide(self, approval_id: str, decision: str, comment: str) -> ApprovalRequest:
        approval = self._approval(approval_id)
        self.approval_authorization.require_decide(approval)
        action = self._action(str(approval.proposed_action_id))
        if approval.status != "PENDING":
            raise _error(
                409, "APPROVAL_ALREADY_DECIDED", "Approval is no longer pending"
            )
        if _aware(approval.expires_at) <= _now():
            approval.status = "EXPIRED"
            action.status = "EXPIRED"
            self.db.commit()
            raise _error(409, "APPROVAL_EXPIRED", "Approval has expired")
        if approval.action_version != action.version:
            approval.status = "SUPERSEDED"
            self.db.commit()
            raise _error(
                409, "STALE_ACTION_VERSION", "Approval targets an old action version"
            )
        if (
            approval.separation_of_duties
            and approval.requester_id == self.identity.actor_id
        ):
            raise _error(
                403, "SEPARATION_OF_DUTIES", "Requester cannot approve their own action"
            )
        decision = decision.upper()
        if decision not in {"APPROVED", "REJECTED", "CHANGES_REQUESTED"}:
            raise _error(422, "INVALID_DECISION", "Unsupported approval decision")
        if decision != "APPROVED" and not comment.strip():
            raise _error(422, "DECISION_COMMENT_REQUIRED", "A reason is required")
        prior = (
            self.db.query(ApprovalDecision)
            .filter_by(
                tenant_id=self.identity.tenant_id,
                approval_request_id=approval.id,
                action_version=action.version,
                actor_id=self.identity.actor_id,
            )
            .first()
        )
        if prior:
            raise _error(409, "DUPLICATE_DECISION", "This approver already decided")
        evidence = self._evidence(action)
        evaluation = self.policy_for(
            action.action_type, action.target_system, action.payload
        )
        record = ApprovalDecision(
            tenant_id=self.identity.tenant_id,
            approval_request_id=approval.id,
            proposed_action_id=action.id,
            action_version=action.version,
            decision=decision,
            actor_id=self.identity.actor_id,
            comment=comment.strip() or None,
            evidence_snapshot=[
                {"id": row.id, "title": row.title, "capturedAt": _iso(row.captured_at)}
                for row in evidence
            ],
            policy_snapshot=evaluation,
        )
        self.db.add(record)
        self.db.flush()
        approval.status = decision
        approval.approver_id = self.identity.actor_id
        approval.decision = decision
        approval.decision_reason = comment.strip() or None
        approval.decided_at = _now()
        if decision == "APPROVED":
            approved_count = (
                self.db.query(func.count(ApprovalDecision.id))
                .filter_by(
                    tenant_id=self.identity.tenant_id,
                    proposed_action_id=action.id,
                    action_version=action.version,
                    decision="APPROVED",
                )
                .scalar()
                or 0
            )
            if approved_count >= approval.required_approval_count:
                action.status = "APPROVED"
                action.approved_at = _now()
            else:
                approval.status = "PENDING"
                approval.assigned_approver_id = None
                action.status = "PENDING_APPROVAL"
        elif decision == "REJECTED":
            action.status = "REJECTED"
        else:
            action.status = "CHANGES_REQUESTED"
        self._notify(
            str(action.requester_id),
            f"APPROVAL_{decision}",
            f"{decision.replace('_', ' ').title()}: {action.title}",
            comment.strip() or "Approval decision recorded.",
            f"/actions/{action.id}",
            action,
            approval,
        )
        self._audit(f"approval.{decision.lower()}", action, after={"comment": comment})
        self.db.commit()
        self.db.refresh(approval)
        return approval

    def delegate(
        self, approval_id: str, delegate_to: str, comment: str
    ) -> ApprovalRequest:
        approval = self._approval(approval_id)
        self.approval_authorization.require_delegate(approval)
        if approval.status != "PENDING":
            raise _error(
                409,
                "INVALID_APPROVAL_TRANSITION",
                "Only pending approvals can be delegated",
            )
        if (
            approval.assigned_approver_id
            and approval.assigned_approver_id != self.identity.actor_id
        ):
            raise _error(
                403, "NOT_ASSIGNED_APPROVER", "Approval is assigned to another user"
            )
        if delegate_to == approval.requester_id:
            raise _error(
                422, "SEPARATION_OF_DUTIES", "Cannot delegate to the requester"
            )
        approval.delegated_from = self.identity.actor_id
        approval.delegated_to = delegate_to
        approval.assigned_approver_id = delegate_to
        approval.decision_reason = comment or None
        self._notify(
            delegate_to,
            "APPROVAL_DELEGATED",
            "Approval delegated to you",
            comment or "Review the assigned action.",
            f"/approvals/{approval.id}",
            self._action(str(approval.proposed_action_id)),
            approval,
        )
        self.db.commit()
        self.db.refresh(approval)
        return approval

    def execute(self, action_id: str, idempotency_key: str) -> ActionExecution:
        self._require("actions.execute")
        action = self._action_for_update(action_id)
        existing = (
            self.db.query(ActionExecution)
            .filter_by(
                tenant_id=self.identity.tenant_id,
                proposed_action_id=action.id,
                idempotency_key=idempotency_key,
            )
            .first()
        )
        if existing:
            return existing
        if action.status != "APPROVED":
            raise _error(
                409, "ACTION_NOT_APPROVED", "Only approved actions can execute"
            )
        if action.expires_at and _aware(action.expires_at) <= _now():
            action.status = "EXPIRED"
            self.db.commit()
            raise _error(409, "ACTION_EXPIRED", "Action approval has expired")
        evaluation = self.policy_for(
            action.action_type, action.target_system, action.payload
        )
        if not evaluation["executionAllowed"] or not evaluation["adapter"]:
            raise _error(
                409, "EXECUTION_NOT_ALLOWED", "Policy permits draft output only"
            )
        approval = (
            self.db.query(ApprovalRequest)
            .filter_by(
                tenant_id=self.identity.tenant_id,
                proposed_action_id=action.id,
                action_version=action.version,
                status="APPROVED",
            )
            .first()
        )
        if not approval or approval.input_fingerprint != _hash_payload(action.payload):
            raise _error(
                409,
                "APPROVAL_BINDING_INVALID",
                "Approval does not bind the current payload",
            )
        trace_id = str(uuid4())
        attempt = (
            self.db.query(func.count(ActionExecution.id))
            .filter_by(tenant_id=self.identity.tenant_id, proposed_action_id=action.id)
            .scalar()
            or 0
        ) + 1
        execution = ActionExecution(
            tenant_id=self.identity.tenant_id,
            proposed_action_id=action.id,
            action_version=action.version,
            attempt_number=attempt,
            adapter=evaluation["adapter"],
            idempotency_key=idempotency_key,
            status="EXECUTING",
            request_snapshot=action.payload,
            result_summary={},
            retryable=False,
            trace_id=trace_id,
            executed_by=self.identity.actor_id,
        )
        self.db.add(execution)
        action.status = "EXECUTING"
        try:
            self.db.flush()
        except IntegrityError:
            self.db.rollback()
            replay = (
                self.db.query(ActionExecution)
                .filter_by(
                    tenant_id=self.identity.tenant_id,
                    proposed_action_id=action_id,
                    idempotency_key=idempotency_key,
                )
                .first()
            )
            if replay:
                return replay
            raise _error(
                409,
                "EXECUTION_CONFLICT",
                "Another executor changed this action; reload before retrying",
            ) from None
        try:
            result = self._run_adapter(action, trace_id)
            execution.status = "EXECUTED"
            execution.completed_at = _now()
            execution.result_summary = result
            action.status = "VERIFYING"
            action.executed_at = _now()
            verification = ActionVerification(
                tenant_id=self.identity.tenant_id,
                execution_id=execution.id,
                verification_type="INDEPENDENT_READ",
                status="PENDING",
                expected_result=result,
                observed_result={},
                evidence=[],
            )
            self.db.add(verification)
            self._audit(
                "action.executed", action, after=result, correlation_id=trace_id
            )
        except (ValueError, RuntimeError) as exc:
            execution.status = "FAILED"
            execution.completed_at = _now()
            execution.failure_code = "ADAPTER_FAILED"
            execution.failure_message = str(exc)[:500]
            execution.retryable = True
            action.status = "FAILED"
            action.failure_code = execution.failure_code
            action.failure_message = execution.failure_message
            self._audit(
                "action.execution_failed",
                action,
                after={"code": execution.failure_code},
                correlation_id=trace_id,
            )
        self.db.commit()
        self.db.refresh(execution)
        return execution

    def _run_adapter(self, action: ProposedAction, trace_id: str) -> dict:
        payload = dict(action.payload)
        if action.action_type == "CREATE_RAID_ITEM":
            allowed = set(DeliveryRAIDItem.__table__.columns.keys()) - {
                "id",
                "tenant_id",
                "created_at",
                "updated_at",
                "version",
                "created_by",
                "updated_by",
                "reference",
                "exposure_score",
                "exposure_band",
                "residual_exposure_score",
                "residual_exposure_band",
                "attention_score",
                "attention_reasons",
            }
            safe_payload = {
                key: value for key, value in payload.items() if key in allowed
            }
            for key in ("due_date", "review_date", "validation_due_date"):
                if isinstance(safe_payload.get(key), str):
                    safe_payload[key] = date.fromisoformat(safe_payload[key])
            item = RAIDRepository(
                self.db, self.identity.tenant_id, self.identity.actor_id
            ).create(safe_payload, trace_id=trace_id)
            action.raid_id = item.id
            action.target_entity_type = "RAID_ITEM"
            action.target_entity_id = item.id
            return {
                "targetEntityType": "RAID_ITEM",
                "targetEntityId": item.id,
                "reference": item.reference,
                "version": item.version,
            }
        if action.action_type == "UPDATE_RAID_ITEM":
            raid_id = action.target_entity_id or payload.pop("raid_id", None)
            expected_version = int(payload.pop("expected_version", 0))
            item = RAIDRepository(
                self.db, self.identity.tenant_id, self.identity.actor_id
            ).update(
                str(raid_id),
                payload,
                expected_version=expected_version,
                trace_id=trace_id,
            )
            return {
                "targetEntityType": "RAID_ITEM",
                "targetEntityId": item.id,
                "reference": item.reference,
                "version": item.version,
            }
        raise RuntimeError("No allowlisted adapter is registered")

    def verify(self, action_id: str, comment: str) -> ActionVerification:
        self._require("actions.verify")
        action = self._action(action_id)
        if action.status != "VERIFYING":
            raise _error(
                409, "INVALID_ACTION_TRANSITION", "Action is not awaiting verification"
            )
        execution = (
            self.db.query(ActionExecution)
            .filter_by(
                tenant_id=self.identity.tenant_id,
                proposed_action_id=action.id,
                status="EXECUTED",
            )
            .order_by(ActionExecution.started_at.desc())
            .first()
        )
        if execution is None:
            raise _error(
                409, "EXECUTION_NOT_FOUND", "No execution is available to verify"
            )
        if execution.executed_by == self.identity.actor_id:
            raise _error(
                403,
                "SEPARATION_OF_DUTIES",
                "Executor cannot verify their own execution",
            )
        verification = (
            self.db.query(ActionVerification)
            .filter_by(tenant_id=self.identity.tenant_id, execution_id=execution.id)
            .one()
        )
        target_id = execution.result_summary.get("targetEntityId")
        observed: dict[str, Any] = {"targetEntityId": target_id, "exists": False}
        if execution.result_summary.get("targetEntityType") == "RAID_ITEM":
            item = (
                self.db.query(DeliveryRAIDItem)
                .filter_by(tenant_id=self.identity.tenant_id, id=target_id)
                .first()
            )
            observed = {
                "targetEntityId": target_id,
                "exists": item is not None,
                "version": item.version if item else None,
                "reference": item.reference if item else None,
            }
        passed = bool(observed["exists"])
        verification.status = "VERIFIED" if passed else "VERIFICATION_FAILED"
        verification.verified_by = self.identity.actor_id
        verification.verified_at = _now()
        verification.observed_result = observed
        verification.evidence = [
            {"type": "INDEPENDENT_READ", "observedAt": _iso(_now())}
        ]
        verification.comment = comment or None
        action.status = "VERIFIED" if passed else "VERIFICATION_FAILED"
        action.verified_at = _now() if passed else None
        self._notify(
            str(action.requester_id),
            verification.status,
            f"Verification {verification.status.lower()}: {action.title}",
            comment or "Execution outcome was checked against the system of record.",
            f"/actions/{action.id}",
            action,
        )
        self._audit(
            "action.verified" if passed else "action.verification_failed",
            action,
            after=observed,
        )
        self.db.commit()
        self.db.refresh(verification)
        return verification

    def cancel(self, action_id: str, comment: str) -> ProposedAction:
        self._require("actions.cancel")
        action = self._action(action_id)
        if action.status in TERMINAL_ACTION_STATES or action.status in {
            "EXECUTING",
            "VERIFYING",
        }:
            raise _error(
                409,
                "INVALID_ACTION_TRANSITION",
                "Action cannot be cancelled in its current state",
            )
        if action.requester_id != self.identity.actor_id and not self.identity.allows(
            "actions.admin"
        ):
            raise _error(
                403, "PERMISSION_DENIED", "Only the requester can cancel this action"
            )
        action.status = "CANCELLED"
        action.cancelled_at = _now()
        for approval in self.db.query(ApprovalRequest).filter_by(
            tenant_id=self.identity.tenant_id,
            proposed_action_id=action.id,
            status="PENDING",
        ):
            approval.status = "CANCELLED"
            approval.decision_reason = comment or None
        self._audit("action.cancelled", action, after={"comment": comment})
        self.db.commit()
        self.db.refresh(action)
        return action

    def list_actions(
        self, status: str | None = None, risk: str | None = None
    ) -> list[ProposedAction]:
        self._require("actions.read")
        query = self.db.query(ProposedAction).filter_by(
            tenant_id=self.identity.tenant_id
        )
        if status:
            query = query.filter(ProposedAction.status == status.upper())
        if risk:
            query = query.filter(ProposedAction.risk_level == risk.upper())
        if not self.identity.allows("actions.read_all"):
            query = query.filter(ProposedAction.requester_id == self.identity.actor_id)
        return query.order_by(ProposedAction.updated_at.desc()).all()

    def list_approvals(self, status: str | None = None) -> list[ApprovalRequest]:
        self.approval_authorization.require_read_permission()
        query = self.db.query(ApprovalRequest).filter(
            ApprovalRequest.tenant_id == self.identity.tenant_id,
            ApprovalRequest.proposed_action_id.is_not(None),
        )
        if status:
            query = query.filter(ApprovalRequest.status == status.upper())
        query = query.filter(self.approval_authorization.visibility_filter())
        return query.order_by(ApprovalRequest.created_at.desc()).all()

    def list_policies(self) -> list[ActionPolicyDefinition]:
        self._require("policies.read")
        return (
            self.db.query(ActionPolicyDefinition)
            .filter_by(tenant_id=self.identity.tenant_id, status="ACTIVE")
            .order_by(ActionPolicyDefinition.action_type)
            .all()
        )

    def list_notifications(self, unread_only: bool = False) -> list[ActionNotification]:
        query = self.db.query(ActionNotification).filter_by(
            tenant_id=self.identity.tenant_id, user_id=self.identity.actor_id
        )
        if unread_only:
            query = query.filter_by(read=False)
        return query.order_by(ActionNotification.created_at.desc()).all()

    def read_notification(self, notification_id: str) -> ActionNotification:
        row = (
            self.db.query(ActionNotification)
            .filter_by(
                tenant_id=self.identity.tenant_id,
                user_id=self.identity.actor_id,
                id=notification_id,
            )
            .first()
        )
        if row is None:
            raise _error(404, "NOTIFICATION_NOT_FOUND", "Notification was not found")
        row.read = True
        row.read_at = _now()
        self.db.commit()
        self.db.refresh(row)
        return row

    def _notify(
        self,
        user_id: str,
        kind: str,
        title: str,
        message: str,
        route: str,
        action: ProposedAction,
        approval: ApprovalRequest | None = None,
    ) -> None:
        self.db.add(
            ActionNotification(
                tenant_id=self.identity.tenant_id,
                user_id=user_id,
                proposed_action_id=action.id,
                approval_request_id=approval.id if approval else None,
                notification_type=kind,
                title=title,
                message=message,
                route=route,
            )
        )

    def _audit(
        self,
        event: str,
        action: ProposedAction,
        *,
        before: Any = None,
        after: Any = None,
        correlation_id: str | None = None,
    ) -> None:
        append_audit_event(
            self.db,
            tenant_id=self.identity.tenant_id,
            actor_id=self.identity.actor_id,
            action=event,
            target_type="proposed_action",
            target_id=action.id,
            correlation_id=correlation_id or action.trace_id,
            before=before,
            after=after,
            metadata={"actionType": action.action_type, "version": action.version},
        )

    def action_item(self, action: ProposedAction) -> dict:
        evidence = self._evidence(action)
        executions = (
            self.db.query(ActionExecution)
            .filter_by(tenant_id=self.identity.tenant_id, proposed_action_id=action.id)
            .order_by(ActionExecution.started_at.desc())
            .all()
        )
        approvals = (
            self.db.query(ApprovalRequest)
            .filter_by(tenant_id=self.identity.tenant_id, proposed_action_id=action.id)
            .order_by(ApprovalRequest.created_at.desc())
            .all()
        )
        audit = (
            self.db.query(AuditLog)
            .filter_by(
                tenant_id=self.identity.tenant_id,
                target_type="proposed_action",
                target_id=action.id,
            )
            .order_by(AuditLog.id)
            .all()
        )
        return {
            "id": action.id,
            "actionType": action.action_type,
            "title": action.title,
            "description": action.description,
            "origin": action.origin,
            "requesterId": action.requester_id,
            "agentId": action.agent_id,
            "targetEntityType": action.target_entity_type,
            "targetEntityId": action.target_entity_id,
            "targetSystem": action.target_system,
            "payload": action.payload,
            "originalPayload": action.original_payload,
            "status": action.status,
            "riskLevel": action.risk_level,
            "policyId": action.policy_id,
            "policyVersion": action.policy_version,
            "approvalRequired": action.approval_required,
            "requiredApprovalCount": action.required_approval_count,
            "expiresAt": _iso(action.expires_at),
            "submittedAt": _iso(action.submitted_at),
            "approvedAt": _iso(action.approved_at),
            "executedAt": _iso(action.executed_at),
            "verifiedAt": _iso(action.verified_at),
            "failure": {"code": action.failure_code, "message": action.failure_message}
            if action.failure_code
            else None,
            "version": action.version,
            "createdAt": _iso(action.created_at),
            "updatedAt": _iso(action.updated_at),
            "evidence": [
                {
                    "id": row.id,
                    "title": row.title,
                    "sourceSystem": row.source_system,
                    "sourceUrl": row.source_url,
                    "capturedAt": _iso(row.captured_at),
                }
                for row in evidence
            ],
            "approvals": [self.approval_item(row) for row in approvals],
            "executions": [self.execution_item(row) for row in executions],
            "auditTrail": [
                {
                    "id": row.id,
                    "action": row.action,
                    "actorId": row.actor_id,
                    "occurredAt": _iso(row.created_at or row.timestamp),
                    "correlationId": row.correlation_id,
                }
                for row in audit
            ],
            "availableTransitions": self.available_transitions(action),
        }

    def approval_item(self, approval: ApprovalRequest) -> dict:
        capabilities = self.approval_authorization.capabilities(approval)
        decisions = (
            self.db.query(ApprovalDecision)
            .filter_by(
                tenant_id=self.identity.tenant_id, approval_request_id=approval.id
            )
            .order_by(ApprovalDecision.created_at)
            .all()
        )
        return {
            "id": approval.id,
            "proposedActionId": approval.proposed_action_id,
            "actionVersion": approval.action_version,
            "requesterId": approval.requester_id,
            "assignedApproverId": approval.assigned_approver_id,
            "delegatedFrom": approval.delegated_from,
            "delegatedTo": approval.delegated_to,
            "riskLevel": approval.risk_level,
            "status": approval.status,
            "safeActionSummary": approval.safe_action_summary,
            "requiredApprovalCount": approval.required_approval_count,
            "separationOfDuties": approval.separation_of_duties,
            "createdAt": _iso(approval.created_at),
            "expiresAt": _iso(approval.expires_at),
            "decidedAt": _iso(approval.decided_at),
            "decisionReason": approval.decision_reason,
            "capabilities": {
                "canView": capabilities.can_view,
                "canApprove": capabilities.can_approve,
                "canReject": capabilities.can_reject,
                "canRequestChanges": capabilities.can_request_changes,
                "canDelegate": capabilities.can_delegate,
                "denialReasonCode": capabilities.denial_reason_code,
            },
            "decisions": [
                {
                    "id": row.id,
                    "decision": row.decision,
                    "actorId": row.actor_id,
                    "comment": row.comment,
                    "createdAt": _iso(row.created_at),
                }
                for row in decisions
            ],
        }

    @staticmethod
    def execution_item(execution: ActionExecution) -> dict:
        return {
            "id": execution.id,
            "actionVersion": execution.action_version,
            "attemptNumber": execution.attempt_number,
            "adapter": execution.adapter,
            "status": execution.status,
            "startedAt": _iso(execution.started_at),
            "completedAt": _iso(execution.completed_at),
            "resultSummary": execution.result_summary,
            "failureCode": execution.failure_code,
            "failureMessage": execution.failure_message,
            "retryable": execution.retryable,
            "traceId": execution.trace_id,
            "executedBy": execution.executed_by,
        }

    @staticmethod
    def notification_item(row: ActionNotification) -> dict:
        return {
            "id": row.id,
            "type": row.notification_type,
            "title": row.title,
            "message": row.message,
            "route": row.route,
            "read": row.read,
            "createdAt": _iso(row.created_at),
        }

    @staticmethod
    def policy_item(row: ActionPolicyDefinition) -> dict:
        return {
            "id": row.id,
            "name": row.name,
            "version": row.version,
            "status": row.status,
            "actionType": row.action_type,
            "riskLevel": row.risk_level,
            "approvalRules": row.approval_rules,
            "verificationRules": row.verification_rules,
            "executionRules": row.execution_rules,
        }

    def available_transitions(self, action: ProposedAction) -> list[str]:
        transitions: dict[str, list[str]] = {
            "DRAFT": ["EDIT", "SUBMIT", "CANCEL"],
            "CHANGES_REQUESTED": ["EDIT", "SUBMIT", "CANCEL"],
            "PENDING_APPROVAL": ["CANCEL"],
            "APPROVED": ["EXECUTE", "CANCEL"],
            "FAILED": ["RETRY", "CANCEL"],
            "VERIFYING": ["VERIFY"],
        }
        return transitions.get(action.status, [])
