from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterable

from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.types import Receive, Scope, Send


class HealthAwareTrustedHostMiddleware(TrustedHostMiddleware):
    """Keep host validation enabled while permitting load-balancer probes."""

    def __init__(
        self,
        app: Callable[[Scope, Receive, Send], Awaitable[None]],
        allowed_hosts: Iterable[str],
        *,
        health_paths: Iterable[str] = ("/health", "/ready"),
        www_redirect: bool = True,
    ) -> None:
        super().__init__(
            app, allowed_hosts=list(allowed_hosts), www_redirect=www_redirect
        )
        self.health_paths = frozenset(health_paths)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        # ALB health checks use the target's private IP address in the Host header.
        # Target IPs change as ECS replaces tasks, so only the dedicated health
        # endpoints bypass host validation; all application routes remain protected.
        if scope["type"] == "http" and scope.get("path") in self.health_paths:
            await self.app(scope, receive, send)
            return

        await super().__call__(scope, receive, send)
