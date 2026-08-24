from app.workflows.services.task_repository import (
    TaskRepository,
)
from app.workflows.services.workflow_repository import (
    WorkflowRepository,
)


def test_create_task(
    db_session,
):

    workflow_repo = WorkflowRepository(db_session)

    task_repo = TaskRepository(db_session)

    workflow = workflow_repo.create_workflow(
        goal="Deployment",
    )

    task = task_repo.create_task(
        workflow_id=workflow.id,
        name="Generate Report",
    )

    assert task.workflow_id == workflow.id

    assert task.name == "Generate Report"

    assert task.status == "PENDING"


def test_assign_agent(
    db_session,
):

    workflow_repo = WorkflowRepository(db_session)

    task_repo = TaskRepository(db_session)

    workflow = workflow_repo.create_workflow(
        goal="Deployment",
    )

    task = task_repo.create_task(
        workflow_id=workflow.id,
        name="Generate Report",
    )

    updated = task_repo.assign_agent(
        task.id,
        "default-agent",
    )

    assert updated.agent == "default-agent"


def test_complete_task(
    db_session,
):

    workflow_repo = WorkflowRepository(db_session)

    task_repo = TaskRepository(db_session)

    workflow = workflow_repo.create_workflow(
        goal="Deployment",
    )

    task = task_repo.create_task(
        workflow_id=workflow.id,
        name="Generate Report",
    )

    task_repo.update_status(
        task.id,
        "RUNNING",
    )

    completed = task_repo.complete_task(task.id)

    assert completed.status == "COMPLETED"

    assert completed.completed_at is not None
