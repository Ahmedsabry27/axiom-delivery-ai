from uuid import uuid4

import pytest

from app.runtime.context import RuntimeContext
from app.runtime.runtime_state import RuntimeState
from app.services.runtime_service import runtime


@pytest.mark.asyncio
async def test_runtime_executes_workflow() -> None:
    """
    End-to-end integration test for the runtime.

    Verifies the following execution flow:

    RuntimeContext
        ↓
    RuntimeOrchestrator
        ↓
    DefaultPlanner
        ↓
    Workflow
        ↓
    DefaultWorkflowEngine
        ↓
    AgentRegistry
        ↓
    DefaultAgent
        ↓
    WorkflowResult
    """

    context = RuntimeContext(
        request_id=uuid4(),
        workflow_id=uuid4(),
        session_id=uuid4(),
        conversation_id=uuid4(),
        tenant_id="demo",
        user_id="ahmed",
        goal="Generate a deployment report",
        trace_id=str(uuid4()),
        metadata={},
        available_agents=["default-agent"],
        available_tools=[],
    )

    result = await runtime.run(context)

    assert result.success is True

    assert result.output["workflow_id"] == str(context.workflow_id)
    assert result.output["state"] == RuntimeState.COMPLETED.value
    assert result.output["tasks_executed"] == 1

    results = result.output["results"]

    assert len(results) == 1

    task_result = results[0]

    assert task_result["task"] == "Generate governed response"
    assert task_result["agent"] == "default-agent"
    assert task_result["success"] is True

    assert task_result["output"]["goal"] == context.goal
    assert task_result["output"]["workflow_id"] == str(context.workflow_id)
    assert task_result["output"]["request_id"] == str(context.request_id)
