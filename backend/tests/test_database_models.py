from app.database.models import (
    Task,
    User,
    Workflow,
)


def test_user_model():

    user = User(
        email="test@test.com",
        name="Test User",
        role="ADMIN",
        tenant_id="tenant1",
    )

    assert user.email == "test@test.com"


def test_workflow_model():

    workflow = Workflow(
        goal="Generate report",
        created_by="user1",
    )

    assert workflow.goal == "Generate report"


def test_task_model():

    task = Task(
        workflow_id=1,
        name="Generate Report",
        agent="default-agent",
    )

    assert task.agent == "default-agent"
