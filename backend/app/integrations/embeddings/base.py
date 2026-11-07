"""Base Embedding Provider Interface.

Defines the abstract base class, validation logic, and common utilities
for all embedding providers.
"""

from abc import ABC, abstractmethod
import logging
import math
import random
from typing import Any, List, Optional, Union

from app.integrations.embeddings.exceptions import (
    EmbeddingInvalidRequestError,
    EmbeddingValidationError,
)
from app.integrations.embeddings.schemas import (
    EmbeddingBatchRequest,
    EmbeddingBatchResponse,
    EmbeddingRequest,
    EmbeddingResponse,
)

logger = logging.getLogger("embedding_provider")


class BaseEmbeddingProvider(ABC):
    """Abstract base class for provider-independent text embedding."""

    def __init__(
        self,
        name: str,
        default_model: str,
        default_dimensions: int = 768,
        timeout_seconds: float = 30.0,
        max_retries: int = 2,
    ):
        self._name = name.lower()
        self._default_model = default_model
        self._default_dimensions = default_dimensions
        self._timeout_seconds = timeout_seconds
        self._max_retries = max_retries

    @property
    def name(self) -> str:
        """Canonical lower-case name of the provider."""
        return self._name

    @property
    def default_model(self) -> str:
        """Default embedding model identifier."""
        return self._default_model

    @property
    def default_dimensions(self) -> int:
        """Default output dimensions for embeddings."""
        return self._default_dimensions

    @property
    def timeout_seconds(self) -> float:
        """Configured timeout in seconds per HTTP call."""
        return self._timeout_seconds

    @property
    def max_retries(self) -> int:
        """Maximum number of retry attempts for transient errors."""
        return self._max_retries

    @property
    @abstractmethod
    def is_configured(self) -> bool:
        """Return True if all required credentials and settings are present."""
        pass

    def validate_text(self, text: Any) -> str:
        """Validate that input text is a non-empty, non-whitespace string."""
        if not isinstance(text, str):
            raise EmbeddingInvalidRequestError(
                f"Embedding text must be a string, got {type(text).__name__}",
                provider=self.name,
            )
        stripped = text.strip()
        if not stripped:
            raise EmbeddingInvalidRequestError(
                "Embedding text cannot be empty or whitespace-only",
                provider=self.name,
            )
        return stripped

    def validate_batch_texts(self, texts: Any) -> List[str]:
        """Validate that batch inputs are a non-empty list of valid strings."""
        if not isinstance(texts, list):
            raise EmbeddingInvalidRequestError(
                f"Embedding batch must be a list, got {type(texts).__name__}",
                provider=self.name,
            )
        if len(texts) == 0:
            raise EmbeddingInvalidRequestError(
                "Embedding batch cannot be empty",
                provider=self.name,
            )
        validated: List[str] = []
        for idx, item in enumerate(texts):
            if not isinstance(item, str):
                raise EmbeddingInvalidRequestError(
                    f"Embedding text at index {idx} must be a string, got {type(item).__name__}",
                    provider=self.name,
                )
            stripped = item.strip()
            if not stripped:
                raise EmbeddingInvalidRequestError(
                    f"Embedding text at index {idx} cannot be empty or whitespace-only",
                    provider=self.name,
                )
            validated.append(stripped)
        return validated

    def validate_dimensions(self, dimensions: Optional[int]) -> int:
        """Validate requested output dimensions or fall back to default."""
        if dimensions is None:
            return self.default_dimensions
        if not isinstance(dimensions, int) or dimensions <= 0:
            raise EmbeddingInvalidRequestError(
                f"Embedding dimensions must be a positive integer, got {dimensions}",
                provider=self.name,
            )
        return dimensions

    def validate_vector(self, vector: Any, expected_dimensions: int) -> List[float]:
        """Validate embedding vector dimensions and ensure all values are finite floats."""
        if not isinstance(vector, (list, tuple)):
            raise EmbeddingValidationError(
                f"Vector must be a list of floats, got {type(vector).__name__}",
                provider=self.name,
            )
        if len(vector) != expected_dimensions:
            raise EmbeddingValidationError(
                f"Expected embedding dimension {expected_dimensions}, got {len(vector)}",
                provider=self.name,
            )
        validated: List[float] = []
        for idx, val in enumerate(vector):
            try:
                f_val = float(val)
            except (ValueError, TypeError) as e:
                raise EmbeddingValidationError(
                    f"Vector value at index {idx} cannot be converted to float: {val}",
                    provider=self.name,
                ) from e
            if not math.isfinite(f_val):
                raise EmbeddingValidationError(
                    f"Vector contains non-finite value ({f_val}) at index {idx}",
                    provider=self.name,
                )
            validated.append(f_val)
        return validated

    def calculate_backoff(self, attempt: int, retry_after: Optional[float] = None) -> float:
        """Calculate backoff duration in seconds using Retry-After or jittered exponential backoff."""
        if retry_after is not None and retry_after > 0:
            return min(self.timeout_seconds, float(retry_after))
        base = 0.5 * (2**attempt)
        jitter = random.uniform(0.05, 0.2)
        return min(self.timeout_seconds, base + jitter)

    @abstractmethod
    async def embed_text(
        self,
        text: Union[str, EmbeddingRequest],
        dimensions: Optional[int] = None,
    ) -> EmbeddingResponse:
        """Generate an embedding for a single text input."""
        pass

    @abstractmethod
    async def embed_batch(
        self,
        texts: Union[List[str], EmbeddingBatchRequest],
        dimensions: Optional[int] = None,
    ) -> EmbeddingBatchResponse:
        """Generate embeddings for multiple independent text inputs preserving exact order."""
        pass
