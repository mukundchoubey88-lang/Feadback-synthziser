"""Mock Embedding Provider for deterministic testing."""

import asyncio
import hashlib
import math
import time
from typing import Any, List, Optional, Union

from app.integrations.embeddings.base import BaseEmbeddingProvider
from app.integrations.embeddings.exceptions import (
    EmbeddingConfigurationError,
)
from app.integrations.embeddings.schemas import (
    EmbeddingBatchRequest,
    EmbeddingBatchResponse,
    EmbeddingRequest,
    EmbeddingResponse,
)


def generate_deterministic_vector(text: str, dimensions: int) -> List[float]:
    """Generate a reproducible, unit-normalized float vector from input text."""
    seed = hashlib.sha256(text.encode("utf-8")).digest()
    raw_vals: List[float] = []
    block = 0
    while len(raw_vals) < dimensions:
        block_bytes = hashlib.sha256(seed + block.to_bytes(4, byteorder="big")).digest()
        for b in block_bytes:
            raw_vals.append((float(b) / 127.5) - 1.0)
            if len(raw_vals) == dimensions:
                break
        block += 1

    norm = math.sqrt(sum(v * v for v in raw_vals)) or 1.0
    return [v / norm for v in raw_vals]


class MockEmbeddingProvider(BaseEmbeddingProvider):
    """Deterministic mock embedding provider for tests."""

    def __init__(
        self,
        name: str = "mock",
        default_model: str = "gemini-embedding-2",
        default_dimensions: int = 768,
        is_configured_override: bool = True,
        simulate_error: Optional[Exception] = None,
        transient_failures_remaining: int = 0,
        transient_error_factory: Optional[Any] = None,
        simulate_delay: float = 0.0,
    ):
        super().__init__(
            name=name,
            default_model=default_model,
            default_dimensions=default_dimensions,
            timeout_seconds=5.0,
            max_retries=2,
        )
        self._is_configured = is_configured_override
        self.simulate_error = simulate_error
        self.transient_failures_remaining = transient_failures_remaining
        self.transient_error_factory = transient_error_factory
        self.simulate_delay = simulate_delay
        self.call_count = 0

    @property
    def is_configured(self) -> bool:
        return self._is_configured

    async def embed_text(
        self,
        text: Union[str, EmbeddingRequest],
        dimensions: Optional[int] = None,
    ) -> EmbeddingResponse:
        self.call_count += 1

        if not self.is_configured:
            raise EmbeddingConfigurationError("Mock provider is not configured", provider=self.name)

        if self.simulate_delay > 0:
            await asyncio.sleep(self.simulate_delay)

        if self.transient_failures_remaining > 0:
            self.transient_failures_remaining -= 1
            if self.transient_error_factory:
                raise self.transient_error_factory()

        if self.simulate_error is not None:
            raise self.simulate_error

        if isinstance(text, EmbeddingRequest):
            raw_text = text.text
            requested_dims = text.dimensions or dimensions
        else:
            raw_text = text
            requested_dims = dimensions

        validated_text = self.validate_text(raw_text)
        target_dims = self.validate_dimensions(requested_dims)

        start = time.perf_counter()
        vector = generate_deterministic_vector(validated_text, target_dims)
        validated_vector = self.validate_vector(vector, target_dims)
        latency_ms = (time.perf_counter() - start) * 1000.0

        return EmbeddingResponse(
            vector=validated_vector,
            dimensions=target_dims,
            provider=self.name,
            model=self.default_model,
            latency_ms=latency_ms,
        )

    async def embed_batch(
        self,
        texts: Union[List[str], EmbeddingBatchRequest],
        dimensions: Optional[int] = None,
    ) -> EmbeddingBatchResponse:
        self.call_count += 1

        if not self.is_configured:
            raise EmbeddingConfigurationError("Mock provider is not configured", provider=self.name)

        if self.simulate_delay > 0:
            await asyncio.sleep(self.simulate_delay)

        if self.transient_failures_remaining > 0:
            self.transient_failures_remaining -= 1
            if self.transient_error_factory:
                raise self.transient_error_factory()

        if self.simulate_error is not None:
            raise self.simulate_error

        if isinstance(texts, EmbeddingBatchRequest):
            raw_texts = texts.texts
            requested_dims = texts.dimensions or dimensions
        else:
            raw_texts = texts
            requested_dims = dimensions

        validated_texts = self.validate_batch_texts(raw_texts)
        target_dims = self.validate_dimensions(requested_dims)

        start = time.perf_counter()
        vectors = [
            self.validate_vector(generate_deterministic_vector(t, target_dims), target_dims)
            for t in validated_texts
        ]
        latency_ms = (time.perf_counter() - start) * 1000.0

        return EmbeddingBatchResponse(
            vectors=vectors,
            dimensions=target_dims,
            provider=self.name,
            model=self.default_model,
            count=len(vectors),
            latency_ms=latency_ms,
        )
