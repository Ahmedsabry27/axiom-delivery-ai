from app.workflows.services.workflow_repository import (
    WorkflowRepository,
)


def test_create_workflow(
    db_session,
):

    repository = WorkflowRepository(db_session)

    workflow = repository.create_workflow(goal="Generate deployment report")

    assert workflow.goal == ("Generate deployment report")

    assert workflow.status == ("RUNNING")


def test_update_workflow_status(
    db_session,
):

    repository = WorkflowRepository(db_session)

    workflow = repository.create_workflow(goal="Test workflow")

    updated = repository.update_status(
        workflow.id,
        "COMPLETED",
    )

    assert updated.status == ("COMPLETED")
