from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.database.models.workflow import Workflow


class WorkflowRepository:
    """
    Persistence layer for workflows.

    Responsibilities:

    - Create workflow records
    - Retrieve workflows
    - List workflows
    - Update workflow status
    - Complete workflows
    """

    @property
    def model(self):
        """
        Expose the SQLAlchemy model.

        Used by API routers and generic repository
        consumers.
        """
        return Workflow

    def __init__(
        self,
        db: Session,
    ) -> None:

        self._db = db

    def create_workflow(
        self,
        goal: str,
        created_by: str = "system",
    ) -> Workflow:
        """
        Create workflow record.

        created_by will later come from
        authenticated user context.
        """

        workflow = Workflow(
            goal=goal,
            status="RUNNING",
            created_by=created_by,
            created_at=datetime.now(UTC),
        )

        self._db.add(workflow)

        self._db.commit()

        self._db.refresh(workflow)

        return workflow

    def list_workflows(
        self,
    ) -> list[Workflow]:
        """
        Retrieve all workflows.
        """

        return self._db.query(Workflow).order_by(Workflow.created_at.desc()).all()

    def get_workflow(
        self,
        workflow_id: int,
    ) -> Workflow | None:
        """
        Retrieve workflow by ID.
        """

        return self._db.query(Workflow).filter(Workflow.id == workflow_id).first()

    def update_status(
        self,
        workflow_id: int,
        status: str,
    ) -> Workflow | None:
        """
        Update workflow state.
        """

        workflow = self.get_workflow(workflow_id)

        if workflow is None:
            return None

        workflow.status = status

        self._db.commit()

        self._db.refresh(workflow)

        return workflow

    def complete_workflow(
        self,
        workflow_id: int,
    ) -> Workflow | None:
        """
        Mark workflow completed.
        """

        workflow = self.get_workflow(workflow_id)

        if workflow is None:
            return None

        workflow.status = "COMPLETED"

        workflow.completed_at = datetime.now(UTC)

        self._db.commit()

        self._db.refresh(workflow)

        return workflow
