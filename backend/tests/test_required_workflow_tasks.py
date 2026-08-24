from uuid import uuid4

import pytest

from app.runtime.task import Task
from app.runtime.task_graph import TaskGraph
from app.runtime.task_state import TaskState
from app.runtime.workflow import Workflow
from app.workflow.default_workflow_engine import DefaultWorkflowEngine


def test_required_failed_task_prevents_workflow_completion():
    task = Task(name="required", state=TaskState.FAILED)
    workflow = Workflow(id=uuid4(), goal="test", tasks=[task])
    graph = TaskGraph([task])
    graph.mark_failed(task.id)

    with pytest.raises(RuntimeError, match="Required workflow tasks"):
        DefaultWorkflowEngine._assert_required_tasks_succeeded(workflow, graph)


def test_required_blocked_task_prevents_workflow_completion():
    failed = Task(name="upstream", state=TaskState.FAILED)
    blocked = Task(name="downstream", depends_on=[failed.id])
    workflow = Workflow(goal="test", tasks=[failed, blocked])
    graph = TaskGraph(workflow.tasks)
    graph.mark_failed(failed.id)

    with pytest.raises(RuntimeError, match="Required workflow tasks"):
        DefaultWorkflowEngine._assert_required_tasks_succeeded(workflow, graph)


def test_optional_failure_does_not_prevent_required_success():
    required = Task(name="required", state=TaskState.COMPLETED)
    optional = Task(
        name="optional", state=TaskState.FAILED, metadata={"required": False}
    )
    workflow = Workflow(goal="test", tasks=[required, optional])
    graph = TaskGraph(workflow.tasks)
    graph.mark_completed(required.id)
    graph.mark_failed(optional.id)

    DefaultWorkflowEngine._assert_required_tasks_succeeded(workflow, graph)
