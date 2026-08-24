from __future__ import annotations

import inspect
import logging
from collections import defaultdict

from app.events.base import Event

logger = logging.getLogger(__name__)


class EventBus:
    """
    Async runtime event bus.

    Supports:
    - Multiple subscribers
    - Sync handlers
    - Async handlers
    """

    def __init__(self) -> None:

        self._handlers: dict[type[Event], list] = defaultdict(list)

    def subscribe(
        self,
        event_type: type[Event],
        handler,
    ) -> None:
        """
        Register an event handler.
        """

        self._handlers[event_type].append(handler)

    async def publish(
        self,
        event: Event,
    ) -> None:
        """
        Publish event to all subscribers.
        """

        handlers = self._handlers.get(
            type(event),
            [],
        )

        for handler in handlers:
            try:
                result = handler(event)
                if inspect.isawaitable(result):
                    await result
            except Exception:
                logger.exception(
                    "Runtime EventBus subscriber failed",
                    extra={
                        "event_type": type(event).__name__,
                        "subscriber": getattr(handler, "__qualname__", repr(handler)),
                    },
                )
