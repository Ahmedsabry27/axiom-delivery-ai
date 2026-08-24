from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database.postgres import get_db
from app.workflows.services.workflow_repository import (
    WorkflowRepository,
)

router = APIRouter(
    prefix="/workflows",
    tags=["workflows"],
)


class WorkflowRunRequest(BaseModel):
    goal: str


@router.post("/run")
def run_workflow(
    request: WorkflowRunRequest | None = None,
    goal: str | None = Query(default=None),
    db: Session = Depends(get_db),
):

    workflow_goal = request.goal if request else goal

    if workflow_goal is None:
        return {"error": "goal is required"}

    repository = WorkflowRepository(db)

    workflow = repository.create_workflow(goal=workflow_goal)

    return {
        "workflow_id": workflow.id,
        "status": workflow.status,
        "current_task": None,
    }


@router.get("")
def list_workflows(
    db: Session = Depends(get_db),
):

    repository = WorkflowRepository(db)

    workflows = db.query(repository.model).all()

    return [
        {
            "id": workflow.id,
            "goal": workflow.goal,
            "status": workflow.status,
            "created_at": workflow.created_at,
        }
        for workflow in workflows
    ]


@router.get("/{workflow_id}")
def get_workflow(
    workflow_id: int,
    db: Session = Depends(get_db),
):

    repository = WorkflowRepository(db)

    workflow = repository.get_workflow(workflow_id)

    if workflow is None:
        return {"error": "workflow not found"}

    return workflow
