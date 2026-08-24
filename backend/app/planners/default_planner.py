from __future__ import annotations

from uuid import uuid4

from app.contracts.planner import Planner
from app.contracts.tool_models import ExecutionContext
from app.database.session import SessionLocal
from app.runtime.context import RuntimeContext
from app.runtime.execution_plan import ExecutionPlan
from app.runtime.task import Task
from app.tool_discovery.engine import engine
from app.tool_discovery.schemas import DiscoveryRequest


class DefaultPlanner(Planner):
    """
    Default planner implementation.

    Generates agent-aware execution plans.

    Responsibilities:
    - Understand the user goal
    - Create executable tasks
    - Define required capabilities

    The planner does NOT select agents.
    Agent selection is handled by AgentRegistry.
    """

    async def plan(
        self,
        context: RuntimeContext,
    ) -> ExecutionPlan:
        """
        Generate execution plan from runtime context.
        """

        intent = context.metadata.get("structured_intent") or {}
        required_capabilities = list(intent.get("required_capabilities") or [])
        selected_tool = (
            intent.get("selected_tool")
            if intent.get("selected_tool") in context.available_tools
            else None
        )
        if selected_tool and not required_capabilities:
            required_capabilities = [selected_tool]
        try:
            permissions = set(context.metadata.get("permissions", []))
            with SessionLocal() as db:
                discovery = await engine.discover(
                    DiscoveryRequest(
                        query=context.goal,
                        required_capabilities=required_capabilities,
                        expected_input=context.metadata.get("inputs") or {},
                        explicit_tool=selected_tool,
                        risk_tolerance="write" if selected_tool else "read",
                        max_candidates=min(
                            int(context.metadata.get("discovery_top_n", 5)), 10
                        ),
                    ),
                    ExecutionContext(
                        actor_id=context.user_id,
                        tenant_id=context.tenant_id,
                        permissions=permissions,
                        conversation_id=str(context.conversation_id),
                        agent_id="default-agent",
                    ),
                    db,
                )
                if discovery["outcome"] in {
                    "selected",
                    "input_required",
                    "clarification_required",
                } and discovery.get("selected"):
                    selected_tool = discovery["selected"]["tool_name"]
                    required_capabilities = [selected_tool]
        except Exception:  # noqa: BLE001 -- optional discovery must not prevent safe fallback planning
            # Preserve a validated explicit selection if the discovery index is unavailable.
            selected_tool = (
                selected_tool if selected_tool in context.available_tools else None
            )

        if not required_capabilities:
            required_capabilities = (
                [selected_tool] if selected_tool else ["general-execution"]
            )

        task = Task(
            id=uuid4(),
            name=selected_tool or "Generate governed response",
            description=(
                f"Execute registered capability {selected_tool}"
                if selected_tool
                else f"Respond to goal: {context.goal}"
            ),
            # Dynamic routing:
            # AgentRegistry will select
            # the best matching agent.
            agent=None if selected_tool else "default-agent",
            required_capabilities=(required_capabilities),
            tool=selected_tool,
        )

        return ExecutionPlan(
            goal=context.goal,
            tasks=[task],
            required_capabilities=(required_capabilities),
            agent_requirements={task.name: required_capabilities},
            estimated_duration_seconds=1.0,
            estimated_cost=0.0,
        )
