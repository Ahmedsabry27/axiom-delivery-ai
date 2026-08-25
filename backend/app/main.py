import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.action_center import router as action_center_router
from app.api.agent_executions import (
    agent_router as agent_execution_router,
)
from app.api.agent_executions import (
    execution_router as agent_continuation_router,
)
from app.api.agents_v1 import router as agents_v1_router
from app.api.agile_performance import router as agile_performance_router
from app.api.audit import router as audit_router
from app.api.auth import router as auth_router
from app.api.ceremonies import router as ceremonies_router
from app.api.chat import router as chat_router
from app.api.conversation import router as conversation_router
from app.api.copilot import router as copilot_router
from app.api.delivery import router as delivery_router
from app.api.dependencies import router as dependencies_router
from app.api.governance_operations import router as governance_operations_router
from app.api.governance_workflows import router as governance_workflows_router
from app.api.integrations import router as integrations_router
from app.api.knowledge import router as knowledge_router
from app.api.management import router as management_router
from app.api.mcp import router as mcp_router
from app.api.meetings import router as meetings_router
from app.api.native_tools import router as native_tools_router
from app.api.operations import router as operations_router
from app.api.portfolio import router as portfolio_router
from app.api.raid import router as raid_router
from app.api.releases import router as releases_router
from app.api.routers.dashboard import router as dashboard_router
from app.api.routers.workflows import router as workflows_router
from app.api.runtime import router as runtime_router
from app.api.settings import router as settings_router
from app.api.sprints import router as sprints_router
from app.api.tool_discovery import router as tool_discovery_router
from app.api.tools import router as tools_router
from app.auth.e2e import validate_e2e_environment
from app.core.config import settings
from app.database.base import Base
from app.database.migrations import require_current_schema
from app.database.models.action import Action  # noqa: F401
from app.database.models.agent import Agent  # noqa: F401
from app.database.models.ceremony import (  # noqa: F401
    Ceremony,
    CeremonyTemplate,
    Lesson,
)
from app.database.models.knowledge_source import KnowledgeSource  # noqa: F401
from app.database.models.mcp import MCPCapability, MCPServer, MCPSyncRun  # noqa: F401
from app.database.models.meeting import Meeting  # noqa: F401
from app.database.models.workflow import Workflow  # noqa: F401
from app.database.session import SessionLocal, engine
from app.integrations.runtime import load_integration_tools
from app.logging.logger import logger
from app.logging.middleware import LoggingMiddleware
from app.mcp_integration.service import load_mcp_tools
from app.metrics.db_metrics import setup_database_metrics

# Import models so SQLAlchemy registers them
from app.models.conversation import Conversation  # noqa: F401
from app.models.message import Message  # noqa: F401
from app.models.runtime_execution import RuntimeExecution  # noqa: F401
from app.security.headers import SecurityHeadersMiddleware
from app.security.trusted_hosts import HealthAwareTrustedHostMiddleware
from app.services.runtime_execution_service import (
    runtime_execution_service,
    runtime_recovery_service,
)
from app.tool_discovery.indexing import index_tools
from app.tool_sdk.service import registry, sync_catalog

# Prevent duplicate SQLAlchemy event registration
_db_metrics_initialized = False


# --------------------------------------------------
# Application Lifespan
# --------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _db_metrics_initialized

    validate_e2e_environment()
    logger.info("Starting Axiom Delivery AI...")

    try:
        if settings.RUN_SCHEMA_CREATE and not settings.production:
            Base.metadata.create_all(bind=engine)
            logger.warning("Development schema creation is enabled.")

        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        logger.info("Database connectivity verified.")
        if settings.production:
            require_current_schema(engine)
            logger.info("Database migration head verified.")

        with SessionLocal() as db:
            if settings.SYNC_TOOL_CATALOG_ON_STARTUP:
                sync_catalog(db)
                await index_tools(db, "default", batch_size=500)
            load_mcp_tools(db, registry)
            integration_tool_count = load_integration_tools(db, registry)
            logger.info("Integration capabilities loaded: %s", integration_tool_count)
        logger.info("Runtime tool registry loaded.")

        await runtime_recovery_service.start()
        logger.info("Runtime recovery reconciler started.")

        # Register database metrics once
        if not _db_metrics_initialized:
            setup_database_metrics(engine)
            _db_metrics_initialized = True
            logger.info("Database metrics initialized.")

    except SQLAlchemyError:
        logger.exception("Failed to initialize the application.")
        raise

    try:
        yield
    finally:
        await runtime_recovery_service.stop()
        local_tasks = list(runtime_execution_service._tasks.values())
        for task in local_tasks:
            task.cancel()
        if local_tasks:
            await asyncio.gather(*local_tasks, return_exceptions=True)
        logger.info("Axiom Delivery AI shutting down.")


# --------------------------------------------------
# FastAPI App
# --------------------------------------------------
app = FastAPI(
    title="Axiom Delivery AI API",
    description=(
        "API for enterprise delivery intelligence, governance, "
        "AI agents, and evidence-backed decision support."
    ),
    version="1.2.0",
    lifespan=lifespan,
    docs_url="/docs" if settings.ENABLE_API_DOCS else None,
    redoc_url="/redoc" if settings.ENABLE_API_DOCS else None,
    openapi_url="/openapi.json" if settings.ENABLE_API_DOCS else None,
)


# --------------------------------------------------
# CORS Configuration
# --------------------------------------------------
origins = settings.cors_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=[
        "GET",
        "POST",
        "PUT",
        "PATCH",
        "DELETE",
        "OPTIONS",
    ],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)

if settings.trusted_hosts:
    app.add_middleware(
        HealthAwareTrustedHostMiddleware,
        allowed_hosts=settings.trusted_hosts,
    )


# --------------------------------------------------
# Custom Middleware
# --------------------------------------------------
app.add_middleware(LoggingMiddleware)
app.add_middleware(SecurityHeadersMiddleware, production=settings.production)


# --------------------------------------------------
# API Routes
# --------------------------------------------------
app.include_router(auth_router, tags=["Authentication"])
app.include_router(chat_router, tags=["Chat"])
app.include_router(conversation_router, tags=["Conversations"])
app.include_router(copilot_router)
app.include_router(delivery_router)
app.include_router(dependencies_router)
app.include_router(raid_router)
app.include_router(releases_router)
app.include_router(sprints_router)
app.include_router(runtime_router)
app.include_router(audit_router)
app.include_router(operations_router)
app.include_router(action_center_router)
app.include_router(agile_performance_router)
app.include_router(meetings_router)
app.include_router(ceremonies_router)
app.include_router(knowledge_router)
app.include_router(management_router)
app.include_router(agents_v1_router)
app.include_router(agent_execution_router)
app.include_router(agent_continuation_router)
app.include_router(dashboard_router)
app.include_router(workflows_router)
app.include_router(tools_router)
app.include_router(native_tools_router)
app.include_router(mcp_router)
app.include_router(tool_discovery_router)
app.include_router(governance_workflows_router)
app.include_router(governance_operations_router)
app.include_router(portfolio_router)
app.include_router(integrations_router)
app.include_router(settings_router)


# --------------------------------------------------
# Root Endpoint
# --------------------------------------------------
@app.get("/")
def root():
    logger.info("Root endpoint called.")

    return {
        "message": "Axiom Delivery AI API is running.",
        "version": "1.2.0",
    }


# --------------------------------------------------
# Health Endpoint
# --------------------------------------------------
@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "enterprise-ai-backend",
        "version": "1.2.0",
    }


@app.get("/ready")
def readiness(response: Response):
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "not_ready", "service": "enterprise-ai-backend"}
    return {"status": "ready", "service": "enterprise-ai-backend"}


# --------------------------------------------------
# Detailed Health Check
# --------------------------------------------------
@app.get("/health/details")
def health_details():
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        database = "healthy"

    except SQLAlchemyError:
        logger.exception("Database health check failed.")
        database = "unavailable"

    response_status = "healthy" if database == "healthy" else "degraded"
    return {
        "status": response_status,
        "service": "enterprise-ai-backend",
        "database": database,
        "version": "1.2.0",
    }


# --------------------------------------------------
# Prometheus Metrics Endpoint
# --------------------------------------------------
@app.get("/metrics")
def metrics():
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )


# --------------------------------------------------
# AWS Lambda Handler
# --------------------------------------------------
handler = Mangum(app)
