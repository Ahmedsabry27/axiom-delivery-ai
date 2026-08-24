from app.runtime.task import Task
from app.runtime.task_state import TaskState
from app.runtime.workflow import Workflow


def test_workflow_creation():

    workflow = Workflow(
        goal="Generate report",
        tasks=[
            Task(
                name="Extract Data",
                agent="data_agent",
            )
        ],
    )

    assert workflow.goal == "Generate report"

    assert len(workflow.tasks) == 1


def test_task_initial_state():

    task = Task(
        name="Test Task",
        agent="test_agent",
    )

    assert task.state == TaskState.PENDING
