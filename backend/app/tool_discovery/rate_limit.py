from __future__ import annotations

import time
from collections import defaultdict, deque

from app.tool_discovery.errors import DiscoveryError


class DiscoveryRateLimiter:
    def __init__(self, limit=60, window=60):
        self.limit = limit
        self.window = window
        self._hits = defaultdict(deque)

    def check(self, key):
        now = time.monotonic()
        hits = self._hits[key]
        while hits and hits[0] < now - self.window:
            hits.popleft()
        if len(hits) >= self.limit:
            error = DiscoveryError("Discovery rate limit exceeded")
            error.code = "DISCOVERY_RATE_LIMITED"
            error.status_code = 429
            raise error
        hits.append(now)


limiter = DiscoveryRateLimiter()
