"""Pydantic schemas for feedback embedding service and API."""

from datetime import datetime
from typing import List, Optional
import uuid
from pydantic import BaseModel, Field


class EmbeddingItemResult(BaseModel):
    """Result of embedding an individual feedback record."""

    feedback_id: uuid.UUID
    embedding_id: uuid.UUID
    embedding_model: str
    embedding_dimensions: int
    status: str = Field(..., description="Status: 'cached', 'inserted', or 'updated'")
    is_cache_hit: bool = False
    input_hash: str
    created_at: datetime
    vector_preview: Optional[List[float]] = Field(
        default=None,
        description="First 5 elements of embedding vector for verification",
    )


class EmbeddingItemError(BaseModel):
    """Failure details for a specific feedback record."""

    feedback_id: uuid.UUID
    error: str
    error_code: str = "ELIGIBILITY_ERROR"


class SingleEmbeddingResponse(BaseModel):
    """Response schema for single feedback embedding operation."""

    success: bool
    result: Optional[EmbeddingItemResult] = None
    error: Optional[str] = None


class BatchEmbeddingRequest(BaseModel):
    """Request payload for batch feedback embedding."""

    feedback_ids: List[uuid.UUID] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="List of feedback IDs to embed",
    )
    dimensions: Optional[int] = Field(
        default=None,
        gt=0,
        description="Optional output dimension override",
    )
    force_refresh: bool = Field(
        default=False,
        description="Whether to force re-embedding and bypass matching cache hash",
    )


class BatchEmbeddingResponse(BaseModel):
    """Summary and details of batch embedding execution."""

    total: int
    processed: int
    cached: int
    inserted: int
    updated: int
    failed: int
    items: List[EmbeddingItemResult] = Field(default_factory=list)
    errors: List[EmbeddingItemError] = Field(default_factory=list)
