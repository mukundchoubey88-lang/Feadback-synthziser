"""External third-party integrations package (Gemini AI, Hindsight Memory, Text Embeddings)."""

from app.integrations.embeddings import (
    BaseEmbeddingProvider,
    GeminiEmbeddingProvider,
    MockEmbeddingProvider,
)

__all__ = [
    "BaseEmbeddingProvider",
    "GeminiEmbeddingProvider",
    "MockEmbeddingProvider",
]
