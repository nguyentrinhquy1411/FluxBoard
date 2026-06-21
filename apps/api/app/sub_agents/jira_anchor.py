from __future__ import annotations

import hashlib
import math
from typing import Protocol

from app.schemas.validation import GroundingCandidate, GroundingResult
from app.sub_agents.schema_pruner import InProcessTTLCache, TTLCache


class EmbeddingProvider(Protocol):
    async def embed(self, text: str) -> list[float]: ...


class DeterministicEmbeddingProvider:
    def __init__(self, dimensions: int = 16) -> None:
        self.dimensions = dimensions

    async def embed(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        for token in text.lower().replace("-", " ").replace("_", " ").split():
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            vector[digest[0] % self.dimensions] += 1.0
            vector[digest[1] % self.dimensions] += 0.5
        return vector


class JiraAnchor:
    def __init__(
        self,
        embedding_provider: EmbeddingProvider | None = None,
        cache: TTLCache | None = None,
    ) -> None:
        self.embedding_provider = embedding_provider or DeterministicEmbeddingProvider()
        self.cache = cache or InProcessTTLCache()

    async def ground(
        self,
        field: str,
        query_fragment: str,
        candidates: list[str],
        limit: int = 3,
    ) -> GroundingResult:
        cache_key = f"jira-anchor:{field}:{query_fragment}:{'|'.join(candidates)}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        query_vector = await self.embedding_provider.embed(query_fragment)
        scored: list[GroundingCandidate] = []
        for candidate in candidates:
            candidate_vector = await self.embedding_provider.embed(candidate)
            scored.append(
                GroundingCandidate(
                    value=candidate,
                    score=cosine_similarity(query_vector, candidate_vector),
                )
            )
        scored.sort(key=lambda item: item.score, reverse=True)
        result = GroundingResult(
            field=field,
            query_fragment=query_fragment,
            candidates=scored[:limit],
            best_value=scored[0].value if scored else None,
        )
        self.cache.set(cache_key, result)
        return result


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        raise ValueError("vectors must have the same dimensionality")
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)
