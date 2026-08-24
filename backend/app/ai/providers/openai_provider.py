from __future__ import annotations

import logging
import time
from collections.abc import Generator, Sequence
from typing import Any

from openai import APITimeoutError, AuthenticationError, RateLimitError

from app.ai.adapters.openai_adapter import OpenAIAdapter
from app.ai.base import AIProvider
from app.ai.exceptions import (
    AIAuthenticationError,
    AIProviderError,
    AIRateLimitError,
    AITimeoutError,
    AIUnknownError,
)
from app.ai.models import (
    AIMessage,
    AIResponse,
    AIStreamEvent,
    AIUsage,
)
from app.core.config import settings
from app.core.openai_client import get_openai_client
from app.metrics.metrics import (
    completion_tokens_total,
    openai_errors_total,
    openai_latency_seconds,
    openai_requests_total,
    prompt_tokens_total,
    total_tokens_total,
)

logger = logging.getLogger(__name__)


class OpenAIProvider(AIProvider):
    """
    OpenAI implementation of the AIProvider interface.

    The model can be provided when the provider is created. If no model is
    supplied, the configured OPENAI_MODEL value is used.
    """

    def __init__(
        self,
        model: str | None = None,
    ) -> None:
        configured_model = model or settings.OPENAI_MODEL

        if not configured_model or not configured_model.strip():
            raise ValueError("OpenAI model must not be empty")

        self.model = configured_model.strip()

    def ask(
        self,
        messages: Sequence[AIMessage],
    ) -> AIResponse:
        start = time.perf_counter()

        try:
            response = get_openai_client().responses.create(
                model=self.model,
                input=OpenAIAdapter.to_input(messages),
            )

            latency = time.perf_counter() - start

            openai_requests_total.inc()
            openai_latency_seconds.observe(latency)

            usage = self._build_usage(response)

            return AIResponse(
                text=response.output_text or "",
                response_id=response.id,
                model=self.model,
                latency_seconds=latency,
                usage=usage,
            )

        except APITimeoutError as ex:
            openai_errors_total.inc()
            raise AITimeoutError("OpenAI request timed out") from ex

        except RateLimitError as ex:
            openai_errors_total.inc()

            logger.warning(
                "OpenAI rate limit exceeded",
                extra={
                    "provider": "openai",
                    "model": self.model,
                },
            )

            raise AIRateLimitError(str(ex)) from ex

        except AuthenticationError as ex:
            openai_errors_total.inc()

            logger.error(
                "OpenAI authentication failed",
                extra={
                    "provider": "openai",
                    "model": self.model,
                },
            )

            raise AIAuthenticationError(str(ex)) from ex

        except Exception as ex:
            openai_errors_total.inc()

            logger.exception(
                "Unexpected OpenAI request failure",
                extra={
                    "provider": "openai",
                    "model": self.model,
                },
            )

            raise AIUnknownError(str(ex)) from ex

    def stream(
        self,
        messages: Sequence[AIMessage],
    ) -> Generator[AIStreamEvent, None, None]:
        start = time.perf_counter()
        response_id: str | None = None
        completed = False

        try:
            openai_requests_total.inc()

            stream = get_openai_client().responses.create(
                model=self.model,
                input=OpenAIAdapter.to_input(messages),
                stream=True,
            )

            yield AIStreamEvent(
                event_type="start",
                model=self.model,
            )

            for event in stream:
                response = getattr(event, "response", None)

                if response is not None:
                    response_id = getattr(
                        response,
                        "id",
                        response_id,
                    )

                if event.type == "response.output_text.delta":
                    yield AIStreamEvent(
                        event_type="delta",
                        text=getattr(event, "delta", ""),
                        model=self.model,
                    )

                elif event.type == "response.completed":
                    latency = time.perf_counter() - start
                    openai_latency_seconds.observe(latency)

                    usage = None

                    if response is not None:
                        usage = self._build_usage(response)

                    completed = True

                    yield AIStreamEvent(
                        event_type="completed",
                        response_id=response_id,
                        model=self.model,
                        usage=usage,
                    )

                elif event.type == "response.failed":
                    error = getattr(event, "error", None)

                    message = (
                        getattr(error, "message", None) if error is not None else None
                    )

                    raise AIProviderError(message or "OpenAI stream failed")

            if not completed:
                latency = time.perf_counter() - start
                openai_latency_seconds.observe(latency)

                logger.warning(
                    "OpenAI stream ended without completed event",
                    extra={
                        "provider": "openai",
                        "model": self.model,
                        "response_id": response_id,
                    },
                )

        except AIProviderError:
            openai_errors_total.inc()
            raise

        except RateLimitError as ex:
            openai_errors_total.inc()

            logger.warning(
                "OpenAI streaming rate limit exceeded",
                extra={
                    "provider": "openai",
                    "model": self.model,
                },
            )

            raise AIRateLimitError(str(ex)) from ex

        except AuthenticationError as ex:
            openai_errors_total.inc()

            logger.error(
                "OpenAI streaming authentication failed",
                extra={
                    "provider": "openai",
                    "model": self.model,
                },
            )

            raise AIAuthenticationError(str(ex)) from ex

        except Exception as ex:
            openai_errors_total.inc()

            logger.exception(
                "Unexpected OpenAI streaming failure",
                extra={
                    "provider": "openai",
                    "model": self.model,
                },
            )

            raise AIUnknownError(str(ex)) from ex

    def _build_usage(
        self,
        response: Any,
    ) -> AIUsage | None:
        usage = getattr(response, "usage", None)

        if usage is None:
            return None

        input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
        output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
        total_tokens = int(
            getattr(
                usage,
                "total_tokens",
                input_tokens + output_tokens,
            )
            or input_tokens + output_tokens
        )

        prompt_tokens_total.inc(input_tokens)
        completion_tokens_total.inc(output_tokens)
        total_tokens_total.inc(total_tokens)

        logger.info(
            "openai_usage",
            extra={
                "provider": "openai",
                "model": self.model,
                "prompt_tokens": input_tokens,
                "completion_tokens": output_tokens,
                "total_tokens": total_tokens,
            },
        )

        return AIUsage(
            prompt_tokens=input_tokens,
            completion_tokens=output_tokens,
            total_tokens=total_tokens,
        )
