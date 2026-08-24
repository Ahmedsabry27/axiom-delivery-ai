from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import or_

from app.agents.application_service import AgentIdentity
from app.database.models.governance_workflow import ApprovalRequest

APPROVAL_READ = "approvals.read"
APPROVAL_DECIDE = "approvals.approve"
APPROVAL_DELEGATE = "approvals.delegate"
APPROVAL_READ_ALL = "approvals.read_all"


def _denied(code: str, message: str) -> HTTPException:
    return HTTPException(403, {"code": code, "message": message})


@dataclass(frozen=True)
class ApprovalCapabilities:
    can_view: bool
    can_approve: bool
    can_reject: bool
    can_request_changes: bool
    can_delegate: bool
    denial_reason_code: str | None = None


class ApprovalAuthorizationService:
    """Canonical tenant-local visibility and decision policy for approvals."""

    def __init__(self, identity: AgentIdentity):
        self.identity = identity

    def require_read_permission(self) -> None:
        if not self.identity.allows(APPROVAL_READ):
            raise _denied("PERMISSION_DENIED", "approvals.read permission is required")

    def visibility_filter(self):
        """SQL predicate used by list/count queries after tenant scoping."""
        if self.identity.allows(APPROVAL_READ_ALL):
            return True
        relationships = [
            ApprovalRequest.requester_id == self.identity.actor_id,
            ApprovalRequest.assigned_approver_id == self.identity.actor_id,
            ApprovalRequest.delegated_to == self.identity.actor_id,
        ]
        memberships = self.identity.roles | self.identity.groups
        if memberships:
            relationships.append(ApprovalRequest.assigned_role.in_(memberships))
        return or_(*relationships)

    def assignment_type(self, approval: ApprovalRequest) -> str | None:
        if approval.assigned_approver_id == self.identity.actor_id:
            return "USER"
        if approval.delegated_to == self.identity.actor_id:
            return "DELEGATE"
        if approval.assigned_role and approval.assigned_role.lower() in (
            self.identity.roles | self.identity.groups
        ):
            return "ROLE_OR_GROUP"
        if approval.requester_id == self.identity.actor_id:
            return "REQUESTER"
        if self.identity.allows(APPROVAL_READ_ALL):
            return "TENANT_ADMIN"
        return None

    def require_view(self, approval: ApprovalRequest) -> None:
        self.require_read_permission()
        if self.assignment_type(approval) is None:
            raise _denied("PERMISSION_DENIED", "Approval is not visible")

    def is_valid_decision_assignee(self, approval: ApprovalRequest) -> bool:
        if approval.assigned_approver_id:
            return approval.assigned_approver_id == self.identity.actor_id
        if approval.assigned_role:
            return approval.assigned_role.lower() in (
                self.identity.roles | self.identity.groups
            )
        # An explicitly unassigned request is an approval-pool item. Permission,
        # tenant scope, human identity and separation-of-duties still apply.
        return True

    def require_decide(self, approval: ApprovalRequest) -> None:
        if not self.identity.allows(APPROVAL_DECIDE):
            raise _denied(
                "PERMISSION_DENIED", "approvals.approve permission is required"
            )
        if self.identity.subject_type != "user":
            raise _denied(
                "HUMAN_APPROVER_REQUIRED", "A human identity must decide approvals"
            )
        if not self.is_valid_decision_assignee(approval):
            raise _denied(
                "NOT_ASSIGNED_APPROVER", "Approval is assigned to another user"
            )

    def require_delegate(self, approval: ApprovalRequest) -> None:
        self.require_decide(approval)
        if not self.identity.allows(APPROVAL_DELEGATE):
            raise _denied(
                "PERMISSION_DENIED", "approvals.delegate permission is required"
            )

    def capabilities(self, approval: ApprovalRequest) -> ApprovalCapabilities:
        can_view = self.identity.allows(APPROVAL_READ) and (
            self.assignment_type(approval) is not None
        )
        expires_at = approval.expires_at
        if expires_at is not None and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        not_expired = expires_at is None or expires_at > datetime.now(UTC)
        can_decide = (
            can_view
            and self.identity.allows(APPROVAL_DECIDE)
            and self.identity.subject_type == "user"
            and self.is_valid_decision_assignee(approval)
            and approval.status == "PENDING"
            and not_expired
            and not (
                approval.separation_of_duties
                and approval.requester_id == self.identity.actor_id
            )
        )
        can_delegate = can_decide and self.identity.allows(APPROVAL_DELEGATE)
        reason = None
        if not can_view:
            reason = "NOT_VISIBLE"
        elif not can_decide:
            reason = "DECISION_NOT_ALLOWED"
        return ApprovalCapabilities(
            can_view=can_view,
            can_approve=can_decide,
            can_reject=can_decide,
            can_request_changes=can_decide,
            can_delegate=can_delegate,
            denial_reason_code=reason,
        )
