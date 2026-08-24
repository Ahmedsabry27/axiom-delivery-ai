from app.agents.default_agent import DefaultAgent
from app.agents.registry import AgentRegistry
from app.persistence.memory_workflow_repository import InMemoryWorkflowRepository
from app.planners.default_planner import DefaultPlanner
from app.runtime.event_bus import EventBus
from app.runtime.orchestrator import RuntimeOrchestrator
from app.workflow.default_workflow_engine import DefaultWorkflowEngine


def create_runtime() -> RuntimeOrchestrator:
    """Build the single runtime used by HTTP execution requests."""
    event_bus = EventBus()
    registry = AgentRegistry()
    registry.register(DefaultAgent(event_bus=event_bus))

    workflow_engine = DefaultWorkflowEngine(
        agent_registry=registry,
        repository=InMemoryWorkflowRepository(),
        event_bus=event_bus,
    )
    return RuntimeOrchestrator(
        planner=DefaultPlanner(),
        workflow_engine=workflow_engine,
        event_bus=event_bus,
    )


runtime = create_runtime()


def get_runtime() -> RuntimeOrchestrator:
    return runtime


def get_event_bus() -> EventBus:
    return runtime._event_bus


def get_workflow_engine() -> DefaultWorkflowEngine:
    return runtime._workflow_engine


def get_agent_registry() -> AgentRegistry:
    return runtime._workflow_engine._agent_registry
