"""Text Embeddings Integration Package.

Provides provider-independent text embedding abstractions, schemas, exceptions,
and concrete implementations including Google Gemini Embedding 2 and Mock providers.
"""

from app.integrations.embeddings.base import BaseEmbeddingProvider
from app.integrations.embeddings.exceptions import (
    EmbeddingAuthError,
    EmbeddingConfigurationError,
    EmbeddingError,
    EmbeddingInvalidRequestError,
    EmbeddingQuotaExhaustedError,
    EmbeddingRateLimitError,
    EmbeddingTimeoutError,
    EmbeddingUnavailableError,
    EmbeddingValidationError,
)
from app.integrations.embeddings.gemini import GeminiEmbeddingProvider
from app.integrations.embeddings.mock import MockEmbeddingProvider
from app.integrations.embeddings.schemas import (
    EmbeddingBatchRequest,
    EmbeddingBatchResponse,
    EmbeddingRequest,
    EmbeddingResponse,
)

__all__ = [
    "BaseEmbeddingProvider",
    "GeminiEmbeddingProvider",
    "MockEmbeddingProvider",
    "EmbeddingRequest",
    "EmbeddingBatchRequest",
    "EmbeddingResponse",
    "EmbeddingBatchResponse",
    "EmbeddingError",
    "EmbeddingConfigurationError",
    "EmbeddingAuthError",
    "EmbeddingRateLimitError",
    "EmbeddingQuotaExhaustedError",
    "EmbeddingUnavailableError",
    "EmbeddingTimeoutError",
    "EmbeddingInvalidRequestError",
    "EmbeddingValidationError",
]
