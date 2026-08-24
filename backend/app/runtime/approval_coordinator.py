from __future__ import annotations

import asyncio

from app.approval.approval_manager import (
    ApprovalManager,
    ApprovalRequest,
    ApprovalStatus,
)


class ApprovalRejectedError(RuntimeError):
    """
    Raised when an approval request is rejected.
    """


class ApprovalCancelledError(RuntimeError):
    """
    Raised when an approval request is cancelled.
    """


class ApprovalCoordinator:
    """
    Coordinates human approvals during workflow execution.

    Responsibilities
    ----------------
    • Create approval requests
    • Suspend workflow execution
    • Resume execution after approval
    • Reject execution
    • Cancel approvals
    • Expose approval queries

    Approval persistence is delegated to ApprovalManager.
    """

    def __init__(
        self,
        approval_manager: ApprovalManager | None = None,
    ) -> None:

        self._manager = (
            approval_manager if approval_manager is not None else ApprovalManager()
        )

        self._events: dict[str, asyncio.Event] = {}

    # ---------------------------------------------------------
    # Creation
    # ---------------------------------------------------------

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

        request = await self._manager.create(
            workflow_id=workflow_id,
            task_id=task_id,
            title=title,
            description=description,
            requested_by=requested_by,
            assigned_to=assigned_to,
        )

        self._events[request.id] = asyncio.Event()

        return request

    # ---------------------------------------------------------
    # Waiting
    # ---------------------------------------------------------

    async def wait_for_approval(
        self,
        approval_id: str,
        timeout_seconds: int | None = None,
    ) -> ApprovalRequest:
        """
        Wait until an approval reaches a terminal state.
        """

        event = self._events.get(approval_id)

        if event is None:
            raise ValueError(f"Approval '{approval_id}' is not registered.")

        if timeout_seconds is None:
            await event.wait()
        else:
            await asyncio.wait_for(
                event.wait(),
                timeout_seconds,
            )

        request = await self.get(approval_id)

        if request is None:
            raise ValueError(f"Approval '{approval_id}' not found.")

        if request.status == ApprovalStatus.APPROVED:
            return request

        if request.status == ApprovalStatus.REJECTED:
            raise ApprovalRejectedError(request.comments or "Approval rejected.")

        if request.status == ApprovalStatus.CANCELLED:
            raise ApprovalCancelledError("Approval cancelled.")

        raise RuntimeError("Approval finished in an invalid state.")

    # ---------------------------------------------------------
    # Approve
    # ---------------------------------------------------------

    async def approve(
        self,
        approval_id: str,
        comments: str | None = None,
    ) -> ApprovalRequest:

        request = await self._manager.approve(
            approval_id,
            comments,
        )

        self._signal(approval_id)

        return request

    # ---------------------------------------------------------
    # Reject
    # ---------------------------------------------------------

    async def reject(
        self,
        approval_id: str,
        comments: str | None = None,
    ) -> ApprovalRequest:

        request = await self._manager.reject(
            approval_id,
            comments,
        )

        self._signal(approval_id)

        return request

    # ---------------------------------------------------------
    # Cancel
    # ---------------------------------------------------------

    async def cancel(
        self,
        approval_id: str,
    ) -> ApprovalRequest:

        request = await self._manager.cancel(
            approval_id,
        )

        self._signal(approval_id)

        return request

    # ---------------------------------------------------------
    # Queries
    # ---------------------------------------------------------

    async def get(
        self,
        approval_id: str,
    ) -> ApprovalRequest | None:

        return await self._manager.get(
            approval_id,
        )

    async def pending(
        self,
    ) -> list[ApprovalRequest]:

        return await self._manager.pending()

    # ---------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------

    def _signal(
        self,
        approval_id: str,
    ) -> None:
        """
        Resume a workflow waiting on the approval.
        """

        event = self._events.get(approval_id)

        if event is not None:
            event.set()
