from __future__ import annotations

import asyncio
import hashlib
import math
import re
from abc import ABC, abstractmethod


class EmbeddingProvider(ABC):
    model = "unknown"
    dimensions = 0

    @abstractmethod
    async def embed_documents(self, texts: list[str]) -> list[list[float]]: ...
    @abstractmethod
    async def embed_query(self, text: str) -> list[float]: ...


class HashEmbeddingProvider(EmbeddingProvider):
    """Deterministic, offline-safe feature hashing; replaceable without domain changes."""

    model = "feature-hash-v1"

    def __init__(self, dimensions=128):
        self.dimensions = dimensions
        self._cache = {}

    def _embed(self, text):
        safe = text[:16000]
        key = hashlib.sha256(safe.encode()).hexdigest()
        if key in self._cache:
            return self._cache[key]
        vector = [0.0] * self.dimensions
        for token in re.findall(r"[a-z0-9_]+", safe.lower()):
            digest = hashlib.sha256(token.encode()).digest()
            idx = int.from_bytes(digest[:4], "big") % self.dimensions
            vector[idx] += 1 if digest[4] % 2 else -1
        norm = math.sqrt(sum(x * x for x in vector)) or 1
        result = [round(x / norm, 8) for x in vector]
        self._cache[key] = result
        return result

    async def embed_documents(self, texts):
        return await asyncio.to_thread(lambda: [self._embed(x) for x in texts])

    async def embed_query(self, text):
        return (await self.embed_documents([text]))[0]


def cosine(a, b):
    if len(a) != len(b):
        return 0.0
    return max(0.0, min(1.0, sum(x * y for x, y in zip(a, b, strict=False))))


provider = HashEmbeddingProvider()
