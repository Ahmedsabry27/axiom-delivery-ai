from __future__ import annotations

from collections.abc import Generator, MutableMapping, Sequence
from contextlib import contextmanager
from contextvars import ContextVar

from app.ai.base import AIProvider
from app.ai.models import AIMessage, AIResponse, AIStreamEvent

_authorized: ContextVar[bool] = ContextVar(
    "budget_authorized_provider_call", default=False
)
_usage_collector: ContextVar[MutableMapping[str, int] | None] = ContextVar(
    "budget_authorized_usage_collector", default=None
)


@contextmanager
def provider_invocation_authorized() -> bool:
    return _authorized.get()


@contextmanager
def authorized_provider_invocation(
    usage_collector: MutableMapping[str, int] | None = None,
):
    if usage_collector is None and _authorized.get():
        usage_collector = _usage_collector.get()
    token = _authorized.set(True)
    usage_token = _usage_collector.set(usage_collector)
    try:
        yield
    finally:
        _usage_collector.reset(usage_token)
        _authorized.reset(token)


class GovernedProvider(AIProvider):
    """Last-line guard preventing production provider bypass."""

    def __init__(self, provider: AIProvider) -> None:
        self._provider = provider

    def _require_reservation(self) -> None:
        if not _authorized.get():
            raise RuntimeError(
                "Provider invocation rejected: no committed budget authorization"
            )

    def ask(self, messages: Sequence[AIMessage]) -> AIResponse:
        self._require_reservation()
        response = self._provider.ask(messages)
        collector = _usage_collector.get()
        if collector is not None and response.usage is not None:
            for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
                value = getattr(response.usage, key, 0)
                collector[key] = collector.get(key, 0) + int(value or 0)
        return response

    def stream(
        self, messages: Sequence[AIMessage]
    ) -> Generator[AIStreamEvent, None, None]:
        self._require_reservation()
        yield from self._provider.stream(messages)
