from __future__ import annotations

import logging
import time
from collections.abc import Generator, Sequence
from typing import Any

from botocore.exceptions import (
    BotoCoreError,
    ClientError,
    ConnectTimeoutError,
    ReadTimeoutError,
)

from app.ai.adapters.bedrock_adapter import BedrockAdapter
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
from app.core.bedrock_client import get_bedrock_client
from app.core.config import settings
from app.metrics.metrics import (
    ai_errors_total,
    ai_latency_seconds,
    ai_requests_total,
    ai_tokens_total,
    completion_tokens_total,
    prompt_tokens_total,
    total_tokens_total,
)

logger = logging.getLogger(__name__)


class BedrockProvider(AIProvider):
    """
    Amazon Bedrock implementation of the AIProvider interface.

    The model can be provided when the provider is instantiated. If no model
    is provided, BEDROCK_MODEL_ID from the application settings is used.
    """

    def __init__(
        self,
        model: str | None = None,
    ) -> None:
        configured_model = model or settings.BEDROCK_MODEL_ID

        if not configured_model or not configured_model.strip():
            raise ValueError("Bedrock model must not be empty")

        self.model = configured_model.strip()

    @property
    def invocation_model(self) -> str:
        """Resolve the Bedrock resource used to invoke the published model."""
        if settings.BEDROCK_INFERENCE_PROFILE_ID:
            return settings.BEDROCK_INFERENCE_PROFILE_ID.strip()
        if self.model == "amazon.nova-lite-v1:0":
            if settings.AWS_REGION.startswith("us-"):
                return "us.amazon.nova-lite-v1:0"
            # Nova Lite is available for direct on-demand inference in the
            # production eu-west-2 region. Do not invent an `eu.` cross-region
            # profile identifier when no profile has been configured: Bedrock
            # rejects that identifier even though the base model is active.
        return self.model

    def ask(
        self,
        messages: Sequence[AIMessage],
    ) -> AIResponse:
        start = time.perf_counter()

        try:
            system_prompt, conversation = BedrockAdapter.to_messages(messages)

            request = self._build_request(
                system_prompt=system_prompt,
                conversation=conversation,
            )

            response = get_bedrock_client().converse(**request)

            latency = time.perf_counter() - start

            ai_requests_total.labels("bedrock", self.model, "success").inc()
            ai_latency_seconds.labels("bedrock", self.model).observe(latency)

            usage = self._build_usage(response)
            text = self._extract_text(response)

            response_metadata = response.get(
                "ResponseMetadata",
                {},
            )

            return AIResponse(
                text=text,
                response_id=response_metadata.get("RequestId"),
                model=self.model,
                latency_seconds=latency,
                usage=usage,
            )

        except ClientError as ex:
            ai_errors_total.labels(
                "bedrock", self.model, self._get_error_code(ex)
            ).inc()

            logger.exception(
                "Amazon Bedrock request failed",
                extra={
                    "provider": "bedrock",
                    "model": self.model,
                    "error_code": self._get_error_code(ex),
                    "aws_request_id": ex.response.get("ResponseMetadata", {}).get(
                        "RequestId"
                    ),
                    "exception_class": type(ex).__name__,
                },
            )

            self._raise_client_error(ex)

        except (ConnectTimeoutError, ReadTimeoutError) as ex:
            ai_errors_total.labels("bedrock", self.model, "timeout").inc()
            raise AITimeoutError("Amazon Bedrock request timed out") from ex

        except BotoCoreError as ex:
            ai_errors_total.labels("bedrock", self.model, type(ex).__name__).inc()

            logger.exception(
                "Amazon Bedrock SDK failure",
                extra={
                    "provider": "bedrock",
                    "model": self.model,
                },
            )

            raise AIUnknownError(str(ex)) from ex

        except AIProviderError:
            raise

        except Exception as ex:
            ai_errors_total.labels("bedrock", self.model, type(ex).__name__).inc()

            logger.exception(
                "Unexpected Amazon Bedrock request failure",
                extra={
                    "provider": "bedrock",
                    "model": self.model,
                },
            )

            raise AIUnknownError(str(ex)) from ex

    def stream(
        self,
        messages: Sequence[AIMessage],
    ) -> Generator[AIStreamEvent, None, None]:
        start = time.perf_counter()
        usage: AIUsage | None = None
        response_id: str | None = None

        try:
            ai_requests_total.labels("bedrock", self.model, "started").inc()

            system_prompt, conversation = BedrockAdapter.to_messages(messages)

            request = self._build_request(
                system_prompt=system_prompt,
                conversation=conversation,
            )

            response = get_bedrock_client().converse_stream(**request)

            response_metadata = response.get(
                "ResponseMetadata",
                {},
            )
            response_id = response_metadata.get("RequestId")

            yield AIStreamEvent(
                event_type="start",
                response_id=response_id,
                model=self.model,
            )

            for event in response["stream"]:
                if "contentBlockDelta" in event:
                    delta = event["contentBlockDelta"].get(
                        "delta",
                        {},
                    )

                    text = delta.get("text")

                    if text:
                        yield AIStreamEvent(
                            event_type="delta",
                            text=text,
                            response_id=response_id,
                            model=self.model,
                        )

                elif "metadata" in event:
                    usage = self._build_usage(event["metadata"])

                elif "internalServerException" in event:
                    message = event["internalServerException"].get(
                        "message",
                        "Amazon Bedrock streaming request failed",
                    )

                    raise AIProviderError(message)

                elif "modelStreamErrorException" in event:
                    message = event["modelStreamErrorException"].get(
                        "message",
                        "Amazon Bedrock model stream failed",
                    )

                    raise AIProviderError(message)

                elif "throttlingException" in event:
                    message = event["throttlingException"].get(
                        "message",
                        "Amazon Bedrock request was throttled",
                    )

                    raise AIRateLimitError(message)

                elif "validationException" in event:
                    message = event["validationException"].get(
                        "message",
                        "Amazon Bedrock request validation failed",
                    )

                    raise AIProviderError(message)

                elif "serviceUnavailableException" in event:
                    message = event["serviceUnavailableException"].get(
                        "message",
                        "Amazon Bedrock service is unavailable",
                    )

                    raise AIProviderError(message)

            latency = time.perf_counter() - start

            ai_latency_seconds.labels("bedrock", self.model).observe(latency)

            yield AIStreamEvent(
                event_type="completed",
                response_id=response_id,
                model=self.model,
                usage=usage,
            )

        except ClientError as ex:
            ai_errors_total.labels(
                "bedrock", self.model, self._get_error_code(ex)
            ).inc()

            logger.exception(
                "Amazon Bedrock streaming request failed",
                extra={
                    "provider": "bedrock",
                    "model": self.model,
                    "error_code": self._get_error_code(ex),
                    "aws_request_id": ex.response.get("ResponseMetadata", {}).get(
                        "RequestId"
                    ),
                    "exception_class": type(ex).__name__,
                },
            )

            self._raise_client_error(ex)

        except BotoCoreError as ex:
            ai_errors_total.labels("bedrock", self.model, type(ex).__name__).inc()

            logger.exception(
                "Amazon Bedrock streaming SDK failure",
                extra={
                    "provider": "bedrock",
                    "model": self.model,
                },
            )

            raise AIUnknownError(str(ex)) from ex

        except AIProviderError as ex:
            ai_errors_total.labels("bedrock", self.model, type(ex).__name__).inc()
            raise

        except Exception as ex:
            ai_errors_total.labels("bedrock", self.model, type(ex).__name__).inc()

            logger.exception(
                "Unexpected Amazon Bedrock streaming failure",
                extra={
                    "provider": "bedrock",
                    "model": self.model,
                },
            )

            raise AIUnknownError(str(ex)) from ex

    def _build_request(
        self,
        *,
        system_prompt: str | None,
        conversation: list[dict[str, Any]],
    ) -> dict[str, Any]:
        request: dict[str, Any] = {
            "modelId": self.invocation_model,
            "messages": conversation,
            "inferenceConfig": {
                "maxTokens": settings.BEDROCK_MAX_TOKENS,
                "temperature": settings.BEDROCK_TEMPERATURE,
                "topP": settings.BEDROCK_TOP_P,
            },
        }

        if system_prompt:
            request["system"] = [
                {
                    "text": system_prompt,
                }
            ]

        return request

    def _extract_text(
        self,
        response: dict[str, Any],
    ) -> str:
        output = response.get("output", {})
        message = output.get("message", {})
        content = message.get("content", [])

        return "".join(
            str(item.get("text", ""))
            for item in content
            if isinstance(item, dict) and "text" in item
        )

    def _build_usage(
        self,
        response: dict[str, Any],
    ) -> AIUsage | None:
        usage = response.get("usage")

        if not usage:
            return None

        input_tokens = int(usage.get("inputTokens", 0) or 0)
        output_tokens = int(usage.get("outputTokens", 0) or 0)
        total_tokens = int(
            usage.get(
                "totalTokens",
                input_tokens + output_tokens,
            )
            or input_tokens + output_tokens
        )

        prompt_tokens_total.inc(input_tokens)
        completion_tokens_total.inc(output_tokens)
        total_tokens_total.inc(total_tokens)
        ai_tokens_total.labels("bedrock", self.model, "prompt").inc(input_tokens)
        ai_tokens_total.labels("bedrock", self.model, "completion").inc(output_tokens)
        ai_tokens_total.labels("bedrock", self.model, "total").inc(total_tokens)

        logger.info(
            "bedrock_usage",
            extra={
                "provider": "bedrock",
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

    @staticmethod
    def _get_error_code(
        exception: ClientError,
    ) -> str:
        return str(
            exception.response.get(
                "Error",
                {},
            ).get(
                "Code",
                "Unknown",
            )
        )

    def _raise_client_error(
        self,
        exception: ClientError,
    ) -> None:
        error = exception.response.get("Error", {})
        error_code = str(error.get("Code", "Unknown"))
        error_message = str(error.get("Message", str(exception)))

        if error_code in {
            "ThrottlingException",
            "TooManyRequestsException",
            "ServiceQuotaExceededException",
        }:
            raise AIRateLimitError(error_message) from exception

        if error_code in {
            "AccessDeniedException",
            "UnauthorizedException",
            "UnrecognizedClientException",
            "InvalidSignatureException",
            "ExpiredTokenException",
        }:
            raise AIAuthenticationError(error_message) from exception

        raise AIProviderError(
            f"Amazon Bedrock error [{error_code}]: {error_message}"
        ) from exception
