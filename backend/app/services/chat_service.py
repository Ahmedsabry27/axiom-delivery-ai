from __future__ import annotations

import logging
import time
from collections.abc import Generator
from contextlib import nullcontext
from uuid import UUID

from sqlalchemy.orm import Session

from app.ai.builders.conversation_builder import ConversationBuilder
from app.ai.factory import AIProviderFactory
from app.ai.governed_provider import (
    authorized_provider_invocation,
    provider_invocation_authorized,
)
from app.ai.models import (
    AIResponse,
    AIStreamEvent,
)
from app.core.config import settings
from app.governance.budget_enforcement import (
    BudgetContext,
    budget_enforcement_service,
)
from app.metrics.metrics import (
    chat_errors_total,
    chat_requests_total,
    messages_processed_total,
)
from app.services.conversation_service import conversation_service

logger = logging.getLogger(__name__)


class ChatService:
    """
    Provider-agnostic chat orchestration service.

    Responsibilities:
    - Validate conversation ownership
    - Persist user messages
    - Build conversation history
    - Resolve the requested AI provider and model
    - Delegate synchronous or streaming inference
    - Persist assistant responses
    """

    def __init__(self) -> None:
        # The provider is intentionally not initialized here.
        # It is resolved independently for every request so OpenAI
        # and Amazon Bedrock can operate side by side.
        self.builder = ConversationBuilder()

    # --------------------------------------------------
    # Validation
    # --------------------------------------------------

    def _validate_conversation(
        self,
        db: Session,
        conversation_id: UUID,
        user_id: str,
    ) -> None:
        conversation = conversation_service.get_conversation(
            db=db,
            conversation_id=conversation_id,
            user_id=user_id,
        )

        if conversation is None:
            raise ValueError("Conversation not found or access denied.")

    # --------------------------------------------------
    # Helpers
    # --------------------------------------------------

    def _load_conversation(
        self,
        db: Session,
        conversation_id: UUID,
        user_id: str,
    ):
        history = conversation_service.get_messages(
            db=db,
            conversation_id=conversation_id,
            user_id=user_id,
        )

        return self.builder.build(history)

    def _save_user_message(
        self,
        db: Session,
        conversation_id: UUID,
        user_id: str,
        message: str,
    ) -> None:
        conversation_service.save_user_message(
            db=db,
            conversation_id=conversation_id,
            content=message,
        )

        conversation_service.touch_conversation(
            db=db,
            conversation_id=conversation_id,
            user_id=user_id,
        )

    def _save_assistant_message(
        self,
        db: Session,
        conversation_id: UUID,
        user_id: str,
        response: AIResponse,
    ) -> None:
        conversation_service.save_assistant_message(
            db=db,
            conversation_id=conversation_id,
            content=response.text,
            response_id=response.response_id,
        )

        conversation_service.touch_conversation(
            db=db,
            conversation_id=conversation_id,
            user_id=user_id,
        )

    @staticmethod
    def _resolve_provider_name(
        provider_name: str | None,
    ) -> str:
        return (provider_name or settings.AI_PROVIDER).strip().lower()

    @staticmethod
    def _resolve_model(
        provider_name: str,
        model: str | None,
    ) -> str:
        if model and model.strip():
            return model.strip()

        if provider_name == "bedrock":
            return settings.BEDROCK_MODEL_ID

        if provider_name == "openai":
            return settings.OPENAI_MODEL

        raise ValueError(f"Unsupported AI provider: {provider_name}")

    # --------------------------------------------------
    # Synchronous Chat
    # --------------------------------------------------

    def ask(
        self,
        db: Session,
        user_id: str,
        message: str,
        conversation_id: UUID | None = None,
        provider_name: str | None = None,
        model: str | None = None,
        persist_user: bool = True,
        budget_context: BudgetContext | None = None,
    ) -> AIResponse:
        """
        Process a synchronous chat request.

        Provider and model are resolved per request. When they are omitted,
        application defaults from Settings are used.
        """

        resolved_provider = self._resolve_provider_name(provider_name)
        resolved_model = self._resolve_model(
            provider_name=resolved_provider,
            model=model,
        )

        logger.info(
            "chat_request_started",
            extra={
                "user_id": user_id,
                "conversation_id": (str(conversation_id) if conversation_id else None),
                "provider": resolved_provider,
                "model": resolved_model,
            },
        )

        chat_requests_total.inc()
        messages_processed_total.inc()

        try:
            if conversation_id is None:
                raise ValueError("conversation_id is required.")

            self._validate_conversation(
                db=db,
                conversation_id=conversation_id,
                user_id=user_id,
            )

            if persist_user:
                self._save_user_message(
                    db=db,
                    conversation_id=conversation_id,
                    user_id=user_id,
                    message=message,
                )

            conversation = self._load_conversation(
                db=db,
                conversation_id=conversation_id,
                user_id=user_id,
            )

            reservation = None
            inherited_authorization = provider_invocation_authorized()
            if budget_context is not None:
                reservation = budget_enforcement_service.reserve(db, budget_context)
                resolved_model = reservation.model.provider_model_id
                resolved_provider = reservation.model.provider

            provider = AIProviderFactory.get_provider(
                provider_name=resolved_provider,
                model=resolved_model,
            )

            try:
                invocation = (
                    authorized_provider_invocation()
                    if reservation is not None or inherited_authorization
                    else nullcontext()
                )
                with invocation:
                    response = provider.ask(messages=conversation)
            except Exception:
                if budget_context is not None and reservation is not None:
                    budget_enforcement_service.release(
                        db, budget_context, "PROVIDER_FAILED_BEFORE_USAGE"
                    )
                raise

            if (
                budget_context is not None
                and reservation is not None
                and not inherited_authorization
            ):
                usage = None
                if response.usage is not None:
                    usage = {
                        "prompt_tokens": response.usage.prompt_tokens,
                        "completion_tokens": response.usage.completion_tokens,
                    }
                budget_enforcement_service.settle(db, budget_context, usage)

            self._save_assistant_message(
                db=db,
                conversation_id=conversation_id,
                user_id=user_id,
                response=response,
            )

            logger.info(
                "chat_request_completed",
                extra={
                    "user_id": user_id,
                    "conversation_id": str(conversation_id),
                    "provider": resolved_provider,
                    "model": response.model,
                    "latency_seconds": round(
                        response.latency_seconds,
                        3,
                    ),
                },
            )

            return response

        except Exception:
            chat_errors_total.inc()

            logger.exception(
                "chat_request_failed",
                extra={
                    "user_id": user_id,
                    "conversation_id": (
                        str(conversation_id) if conversation_id else None
                    ),
                    "provider": resolved_provider,
                    "model": resolved_model,
                },
            )

            raise

    # --------------------------------------------------
    # Streaming Chat
    # --------------------------------------------------

    def stream(
        self,
        db: Session,
        user_id: str,
        message: str,
        conversation_id: UUID | None = None,
        provider_name: str | None = None,
        model: str | None = None,
    ) -> Generator[AIStreamEvent, None, None]:
        """
        Stream a response from the selected AI provider.

        Provider and model are resolved per request. The complete assistant
        response is persisted after streaming finishes.
        """

        resolved_provider = self._resolve_provider_name(provider_name)
        resolved_model = self._resolve_model(
            provider_name=resolved_provider,
            model=model,
        )

        logger.info(
            "stream_request_started",
            extra={
                "user_id": user_id,
                "conversation_id": (str(conversation_id) if conversation_id else None),
                "provider": resolved_provider,
                "model": resolved_model,
            },
        )

        chat_requests_total.inc()
        messages_processed_total.inc()

        assistant_text = ""
        final_response_id: str | None = None
        final_model = resolved_model
        final_usage = None
        start = time.perf_counter()

        try:
            if conversation_id is None:
                raise ValueError("conversation_id is required.")

            self._validate_conversation(
                db=db,
                conversation_id=conversation_id,
                user_id=user_id,
            )

            self._save_user_message(
                db=db,
                conversation_id=conversation_id,
                user_id=user_id,
                message=message,
            )

            conversation = self._load_conversation(
                db=db,
                conversation_id=conversation_id,
                user_id=user_id,
            )

            provider = AIProviderFactory.get_provider(
                provider_name=resolved_provider,
                model=resolved_model,
            )

            for event in provider.stream(
                messages=conversation,
            ):
                if event.text:
                    assistant_text += event.text

                if event.response_id:
                    final_response_id = event.response_id

                if event.model:
                    final_model = event.model

                if event.usage:
                    final_usage = event.usage

                yield event

            latency = time.perf_counter() - start

            response = AIResponse(
                text=assistant_text,
                response_id=final_response_id,
                model=final_model,
                latency_seconds=latency,
                usage=final_usage,
            )

            self._save_assistant_message(
                db=db,
                conversation_id=conversation_id,
                user_id=user_id,
                response=response,
            )

            logger.info(
                "stream_request_completed",
                extra={
                    "user_id": user_id,
                    "conversation_id": str(conversation_id),
                    "provider": resolved_provider,
                    "model": final_model,
                    "latency_seconds": round(latency, 3),
                },
            )

        except Exception:
            chat_errors_total.inc()

            logger.exception(
                "stream_request_failed",
                extra={
                    "user_id": user_id,
                    "conversation_id": (
                        str(conversation_id) if conversation_id else None
                    ),
                    "provider": resolved_provider,
                    "model": resolved_model,
                },
            )

            raise


# --------------------------------------------------
# Singleton
# --------------------------------------------------

chat_service = ChatService()
