from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from uuid import uuid4


class ApprovalStatus(str, Enum):
    """
    Approval request status.
    """

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


@dataclass(slots=True)
class ApprovalRequest:
    """
    Represents a human approval request.
    """

    id: str = field(default_factory=lambda: str(uuid4()))

    workflow_id: str = ""

    task_id: str = ""

    title: str = ""

    description: str = ""

    requested_by: str = ""

    assigned_to: str = ""

    status: ApprovalStatus = ApprovalStatus.PENDING

    comments: str | None = None

    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    responded_at: datetime | None = None


class ApprovalManager:
    """
    Manages human approval requests.

    This class only manages approval state.
    Notification delivery (Teams, Email, Slack, etc.)
    should be implemented separately.
    """

    def __init__(self) -> None:
        self._requests: dict[str, ApprovalRequest] = {}

    async def create(
        self,
        workflow_id: str,
        task_id: str,
        title: str,
        description: str,
        requested_by: str,
        assigned_to: str,
    ) -> ApprovalRequest:
        """
        Create a new approval request.
        """

        request = ApprovalRequest(
            workflow_id=workflow_id,
            task_id=task_id,
            title=title,
            description=description,
            requested_by=requested_by,
            assigned_to=assigned_to,
        )

        self._requests[request.id] = request

        return request

    async def approve(
        self,
        approval_id: str,
        comments: str | None = None,
    ) -> ApprovalRequest:
        """
        Approve a pending request.
        """

        request = self._get(approval_id)

        request.status = ApprovalStatus.APPROVED
        request.comments = comments
        request.responded_at = datetime.now(UTC)

        return request

    async def reject(
        self,
        approval_id: str,
        comments: str | None = None,
    ) -> ApprovalRequest:
        """
        Reject a pending request.
        """

        request = self._get(approval_id)

        request.status = ApprovalStatus.REJECTED
        request.comments = comments
        request.responded_at = datetime.now(UTC)

        return request

    async def cancel(
        self,
        approval_id: str,
    ) -> ApprovalRequest:
        """
        Cancel a pending approval request.
        """

        request = self._get(approval_id)

        request.status = ApprovalStatus.CANCELLED
        request.responded_at = datetime.now(UTC)

        return request

    async def get(
        self,
        approval_id: str,
    ) -> ApprovalRequest | None:
        """
        Get an approval request.
        """

        return self._requests.get(approval_id)

    async def pending(
        self,
    ) -> list[ApprovalRequest]:
        """
        Return all pending approval requests.
        """

        return [
            request
            for request in self._requests.values()
            if request.status == ApprovalStatus.PENDING
        ]

    def _get(
        self,
        approval_id: str,
    ) -> ApprovalRequest:
        """
        Get an approval request or raise.
        """

        request = self._requests.get(approval_id)

        if request is None:
            raise ValueError(f"Approval '{approval_id}' was not found.")

        return request
