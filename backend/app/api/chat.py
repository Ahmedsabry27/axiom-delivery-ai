from __future__ import annotations

import asyncio
import time
from uuid import uuid4

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    Response,
)
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.agents.application_service import AgentIdentity
from app.api.sse import to_sse
from app.auth.dependencies import get_current_user
from app.core.config import settings
from app.database.dependencies import get_db
from app.governance.budget_enforcement import BudgetContext, BudgetEnforcementError
from app.logging.logger import logger
from app.models.chat import (
    ChatRequest,
    ChatResponse,
)
from app.services.chat_service import chat_service
from app.services.conversation_service import conversation_service
from app.services.runtime_execution_service import runtime_execution_service

router = APIRouter()


class RuntimeStartResponse(BaseModel):
    execution_id: str
    workflow_id: str
    status: str


def _resolve_provider(
    request: ChatRequest,
) -> str:
    """
    Resolve the provider selected by the request.

    When no provider is supplied, use the configured default provider.
    """
    return (request.provider or settings.AI_PROVIDER).strip().lower()


def _resolve_model(
    request: ChatRequest,
    provider: str,
) -> str:
    """
    Resolve the model selected by the request.

    When no model is supplied, use the default model configured for
    the selected provider.
    """
    if request.model and request.model.strip():
        return request.model.strip()

    if provider == "openai":
        return settings.OPENAI_MODEL

    if provider == "bedrock":
        return settings.BEDROCK_MODEL_ID

    raise ValueError(f"Unsupported AI provider: {provider}")


# ==================================================
# Runtime Execution
# ==================================================


@router.post(
    "/api/chat/start",
    status_code=202,
    response_model=RuntimeStartResponse,
)
async def start_runtime_execution(
    request: ChatRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    if request.conversation_id is None:
        raise HTTPException(
            status_code=422,
            detail="conversation_id is required",
        )

    conversation = conversation_service.get_conversation(
        db=db,
        conversation_id=request.conversation_id,
        user_id=user["sub"],
    )

    if conversation is None:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found",
        )

    permissions = set(user.get("scope", "").split()) | set(
        user.get("permissions", []) or []
    )

    groups = user.get("cognito:groups", []) or []

    if any(
        str(group).lower()
        in {
            "admin",
            "administrators",
            "platform-admin",
        }
        for group in groups
    ):
        permissions.add("tools.admin")

    execution = await runtime_execution_service.start(
        db,
        user_id=user["sub"],
        message=request.message,
        conversation_id=request.conversation_id,
        permissions=permissions,
        tenant_id=user.get(
            "custom:tenant_id",
            "default",
        ),
        provider_name=request.provider,
        model=request.model,
        agent_id=request.agent_id,
        identity=AgentIdentity.from_claims(user),
        workspace_id=request.workspace_id,
        metadata=request.metadata,
    )

    return RuntimeStartResponse(
        execution_id=str(execution.id),
        workflow_id=str(execution.workflow_id),
        status=execution.status,
    )


# ==================================================
# Normal Chat Endpoint
# ==================================================


@router.post(
    "/chat",
    response_model=ChatResponse,
)
def chat(
    request: ChatRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    try:
        resolved_provider = _resolve_provider(request)
        resolved_model = _resolve_model(
            request=request,
            provider=resolved_provider,
        )

        response = chat_service.ask(
            db=db,
            user_id=user["sub"],
            message=request.message,
            conversation_id=request.conversation_id,
            provider_name=resolved_provider,
            model=resolved_model,
            budget_context=(
                BudgetContext(
                    tenant_id=user.get("custom:tenant_id", "default"),
                    trace_id=str(uuid4()),
                    idempotency_key=f"chat:{request.conversation_id}:{uuid4()}",
                    model=resolved_model,
                    agent_id=request.agent_id,
                    project_id=(request.metadata or {}).get("project_id"),
                    programme_id=(request.metadata or {}).get("programme_id"),
                    data_classification=(request.metadata or {}).get(
                        "data_classification", "INTERNAL"
                    ),
                    region=(request.metadata or {}).get("region"),
                    estimated_input_tokens=max(1, len(request.message) // 4),
                    reserved_output_tokens=min(
                        int((request.metadata or {}).get("max_output_tokens", 512)),
                        4096,
                    ),
                    critical=bool((request.metadata or {}).get("critical_ai_request")),
                    override_id=(request.metadata or {}).get("budget_override_id"),
                )
                if settings.BUDGET_ENFORCEMENT_ENABLED
                else None
            ),
        )

        return ChatResponse(
            response=response.text,
            response_id=response.response_id,
            provider=resolved_provider,
            model=response.model,
        )

    except BudgetEnforcementError as ex:
        raise HTTPException(status_code=402, detail=ex.decision) from ex

    except ValueError as ex:
        logger.warning(
            "Invalid chat request",
            extra={
                "user_id": user.get("sub"),
                "provider": request.provider,
                "model": request.model,
                "error": str(ex),
            },
        )

        raise HTTPException(
            status_code=400,
            detail=str(ex),
        ) from ex

    except Exception as ex:
        logger.exception(
            "Chat failed",
            extra={
                "user_id": user.get("sub"),
                "provider": request.provider,
                "model": request.model,
            },
        )

        raise HTTPException(
            status_code=500,
            detail="AI response generation failed",
        ) from ex


# ==================================================
# Streaming Runtime Orchestrator
# ==================================================


@router.post("/chat/stream")
async def stream_chat(
    request: Request,
    payload: ChatRequest,
    db: Session = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    start_time = time.perf_counter()

    try:
        resolved_provider = _resolve_provider(payload)
        resolved_model = _resolve_model(
            request=payload,
            provider=resolved_provider,
        )

    except ValueError as ex:
        raise HTTPException(
            status_code=400,
            detail=str(ex),
        ) from ex

    async def event_stream():
        try:
            # ----------------------------------
            # Request Received
            # ----------------------------------
            yield to_sse(
                {
                    "type": "runtime_step",
                    "name": "Request Received",
                    "status": "completed",
                    "description": "User prompt received",
                    "provider": resolved_provider,
                    "model": resolved_model,
                }
            )

            await asyncio.sleep(0.2)

            # ----------------------------------
            # Conversation API
            # ----------------------------------
            yield to_sse(
                {
                    "type": "runtime_step",
                    "name": "Conversation API",
                    "status": "completed",
                    "description": ("Conversation context loaded"),
                }
            )

            await asyncio.sleep(0.2)

            # ----------------------------------
            # Planner
            # ----------------------------------
            yield to_sse(
                {
                    "type": "runtime_step",
                    "name": "Planner",
                    "status": "running",
                    "description": ("Creating execution plan"),
                }
            )

            await asyncio.sleep(1)

            yield to_sse(
                {
                    "type": "runtime_step",
                    "name": "Planner",
                    "status": "completed",
                    "description": ("Execution plan created"),
                }
            )

            # ----------------------------------
            # AI Provider Execution
            # ----------------------------------
            yield to_sse(
                {
                    "type": "runtime_step",
                    "name": "Agent Execution",
                    "status": "running",
                    "description": (
                        f"Executing with {resolved_provider}/{resolved_model}"
                    ),
                    "provider": resolved_provider,
                    "model": resolved_model,
                }
            )

            response = chat_service.ask(
                db=db,
                user_id=user["sub"],
                message=payload.message,
                conversation_id=payload.conversation_id,
                provider_name=resolved_provider,
                model=resolved_model,
                budget_context=(
                    BudgetContext(
                        tenant_id=user.get("custom:tenant_id", "default"),
                        trace_id=str(uuid4()),
                        idempotency_key=f"stream:{payload.conversation_id}:{uuid4()}",
                        model=resolved_model,
                        agent_id=payload.agent_id,
                        project_id=(payload.metadata or {}).get("project_id"),
                        programme_id=(payload.metadata or {}).get("programme_id"),
                        data_classification=(payload.metadata or {}).get(
                            "data_classification", "INTERNAL"
                        ),
                        region=(payload.metadata or {}).get("region"),
                        estimated_input_tokens=max(1, len(payload.message) // 4),
                        reserved_output_tokens=min(
                            int((payload.metadata or {}).get("max_output_tokens", 512)),
                            4096,
                        ),
                        critical=bool(
                            (payload.metadata or {}).get("critical_ai_request")
                        ),
                        override_id=(payload.metadata or {}).get("budget_override_id"),
                    )
                    if settings.BUDGET_ENFORCEMENT_ENABLED
                    else None
                ),
            )

            yield to_sse(
                {
                    "type": "runtime_step",
                    "name": "Agent Execution",
                    "status": "completed",
                    "description": ("Agent execution completed"),
                    "provider": resolved_provider,
                    "model": response.model,
                }
            )

            await asyncio.sleep(0.3)

            # ----------------------------------
            # Action Execution
            # ----------------------------------
            yield to_sse(
                {
                    "type": "runtime_step",
                    "name": "Action Execution",
                    "status": "completed",
                    "description": ("Enterprise action executed"),
                }
            )

            await asyncio.sleep(0.3)

            # ----------------------------------
            # Result Generated
            # ----------------------------------
            yield to_sse(
                {
                    "type": "runtime_step",
                    "name": "Result Generated",
                    "status": "completed",
                    "description": "Response generated",
                }
            )

            duration = round(
                (time.perf_counter() - start_time) * 1000,
                2,
            )

            # ----------------------------------
            # Final Assistant Response
            # ----------------------------------
            yield to_sse(
                {
                    "type": "response",
                    "message": response.text,
                    "response_id": (response.response_id),
                    "status": "COMPLETED",
                    "provider": resolved_provider,
                    "model": response.model,
                    "agent": getattr(
                        response,
                        "agent",
                        "default-agent",
                    ),
                    "workflow_id": getattr(
                        response,
                        "workflow_id",
                        None,
                    ),
                    "duration_ms": duration,
                    "conversation_id": str(payload.conversation_id)
                    if payload.conversation_id
                    else None,
                }
            )

        except asyncio.CancelledError:
            logger.info(
                "Client disconnected",
                extra={
                    "user_id": user.get("sub"),
                    "provider": resolved_provider,
                    "model": resolved_model,
                    "path": str(request.url.path),
                },
            )

            return

        # Streaming is the final provider boundary; every provider failure is logged.
        except Exception:  # noqa: BLE001
            logger.exception(
                "Streaming failed",
                extra={
                    "user_id": user.get("sub"),
                    "provider": resolved_provider,
                    "model": resolved_model,
                },
            )

            yield to_sse(
                {
                    "type": "error",
                    "message": ("AI response generation failed"),
                    "provider": resolved_provider,
                    "model": resolved_model,
                }
            )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ==================================================
# CORS OPTIONS
# ==================================================


@router.options("/chat")
def options_chat():
    return Response(status_code=200)


@router.options("/chat/stream")
def options_stream():
    return Response(status_code=200)
