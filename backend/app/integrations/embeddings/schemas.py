"""Provider-independent schemas for text embedding requests and responses."""

from typing import List, Optional
from pydantic import BaseModel, Field


class EmbeddingRequest(BaseModel):
    """Request schema for embedding a single text string."""

    text: str = Field(..., description="Non-empty text content to embed")
    dimensions: Optional[int] = Field(
        default=None,
        gt=0,
        description="Target output dimensions (e.g. 768 for gemini-embedding-2 MRL)",
    )


class EmbeddingBatchRequest(BaseModel):
    """Request schema for embedding multiple text strings in a batch."""

    texts: List[str] = Field(
        ...,
        min_length=1,
        description="List of non-empty text contents to embed",
    )
    dimensions: Optional[int] = Field(
        default=None,
        gt=0,
        description="Target output dimensions for all vectors in batch",
    )


class EmbeddingResponse(BaseModel):
    """Normalized response schema for a single text embedding."""

    vector: List[float] = Field(..., description="Embedding vector as list of finite floats")
    dimensions: int = Field(..., gt=0, description="Dimensionality of the vector")
    provider: str = Field(..., description="Canonical name of the embedding provider")
    model: str = Field(..., description="Model identifier used to produce embedding")
    latency_ms: float = Field(..., ge=0.0, description="Execution time in milliseconds")


class EmbeddingBatchResponse(BaseModel):
    """Normalized response schema for a batch of text embeddings."""

    vectors: List[List[float]] = Field(
        ..., description="List of embedding vectors strictly matching input order"
    )
    dimensions: int = Field(..., gt=0, description="Dimensionality of each vector in batch")
    provider: str = Field(..., description="Canonical name of the embedding provider")
    model: str = Field(..., description="Model identifier used to produce embeddings")
    count: int = Field(..., ge=0, description="Number of vectors returned")
    latency_ms: float = Field(..., ge=0.0, description="Total execution time in milliseconds")
