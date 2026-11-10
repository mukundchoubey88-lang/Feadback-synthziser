"""Pydantic schemas for Hindsight Persistent Memory Integration (Part 9).

Provides request and response validation for Memory Sync, Recall, Reflect,
and Status endpoints, maintaining rigorous separation between Hindsight's
cognitive/semantic reasoning and PostgreSQL's authoritative structured state.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field


class MemoryItemResponse(BaseModel):
    """Unified representation of a memory item with provenance metadata."""

    model_config = ConfigDict(from_attributes=True)

    memory_id: Optional[uuid.UUID] = Field(
        default=None,
        description="Local PostgreSQL UUID primary key in memory_metadata if mapped",
    )
    bank_id: str = Field(..., description="Hindsight memory bank identifier")
    hindsight_memory_id: Optional[str] = Field(
        default=None,
        description="External identifier returned by Hindsight platform",
    )
    memory_type: str = Field(
        ...,
        description="Cognitive memory type (customer_feedback, theme_trajectory, temporal_shift, product_release, synthesized_insight)",
    )
    source_entity_type: str = Field(
        ...,
        description="Originating PostgreSQL model category (feedback, snapshot, theme_snapshot, insight, reflection, external)",
    )
    source_reference: Optional[str] = Field(
        default=None,
        description="Deterministic provenance reference string (e.g., feedback:<uuid>, theme:<uuid>)",
    )
    content: str = Field(..., description="Narrative content of the memory")
    context: Optional[str] = Field(
        default=None,
        description="Supplementary contextual metadata associated with the memory",
    )
    created_at: Optional[datetime] = Field(
        default=None,
        description="Timestamp when memory was recorded in UTC",
    )


class MemoryRecallRequest(BaseModel):
    """Request payload for semantic memory recall."""

    product: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Product name whose bank should be searched",
    )
    query: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Semantic recall query or problem description",
    )
    limit: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum number of historical memories to recall",
    )


class MemoryRecallResponse(BaseModel):
    """Response payload for semantic memory recall."""

    product: str = Field(..., description="Product scoped for recall")
    bank_id: str = Field(..., description="Hindsight memory bank ID searched")
    query: str = Field(..., description="Original recall query")
    available: bool = Field(
        ...,
        description="Whether Hindsight persistent memory service is currently online and available",
    )
    memories: List[MemoryItemResponse] = Field(
        default_factory=list,
        description="Recalled memories with linked PostgreSQL provenance",
    )
    error: Optional[str] = Field(
        default=None,
        description="Error or degradation description if Hindsight was unreachable",
    )


class MemoryReflectRequest(BaseModel):
    """Request payload for historical synthesis and cognitive reflection."""

    product: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Product name whose bank will be reflected upon",
    )
    query: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="High-level analytical question or historical reflection prompt",
    )


class MemoryReflectResponse(BaseModel):
    """Response payload for historical reflection."""

    product: str = Field(..., description="Product scoped for reflection")
    bank_id: str = Field(..., description="Hindsight memory bank ID")
    query: str = Field(..., description="Original reflection query")
    available: bool = Field(
        ...,
        description="Whether Hindsight reflection engine is online and available",
    )
    reasoning: Optional[str] = Field(
        default=None,
        description="Synthesized historical narrative and reasoning produced by Hindsight",
    )
    supporting_memories: List[MemoryItemResponse] = Field(
        default_factory=list,
        description="Supporting memory citations retrieved during reflection",
    )
    error: Optional[str] = Field(
        default=None,
        description="Degradation error if Hindsight reflection was unreachable",
    )
    disclaimer: str = Field(
        default="Hindsight reflections provide semantic synthesis. Numerical aggregations are derived authoritatively from PostgreSQL.",
        description="Mandatory contract disclaimer separating AI reasoning from SQL metrics",
    )


class MemorySyncRequest(BaseModel):
    """Request payload to trigger selective PostgreSQL-to-Hindsight memory synchronization."""

    product: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Target product name to synchronize memories for",
    )
    dry_run: bool = Field(
        default=False,
        description="If True, evaluates and counts sync candidates without retaining to Hindsight or database",
    )


class MemorySyncResponse(BaseModel):
    """Summary of memory curation, deduplication, and retention results."""

    product: str = Field(..., description="Product synchronized")
    bank_id: str = Field(..., description="Hindsight memory bank identifier")
    dry_run: bool = Field(..., description="Whether this was a simulation")
    synced_count: int = Field(..., description="Number of new memories retained")
    skipped_count: int = Field(
        ...,
        description="Number of existing memories skipped due to deduplication",
    )
    failed_count: int = Field(
        ...,
        description="Number of memories that failed retention",
    )
    details: Dict[str, int] = Field(
        default_factory=dict,
        description="Retention count breakdown by memory_type",
    )
    error: Optional[str] = Field(
        default=None,
        description="Error details if sync completed with degradation",
    )


class MemoryStatusResponse(BaseModel):
    """Health, configuration, and storage status for Hindsight integration."""

    configured: bool = Field(
        ...,
        description="Whether HINDSIGHT_BASE_URL is configured in application settings",
    )
    available: bool = Field(
        ...,
        description="Whether live ping/health check to Hindsight server succeeded",
    )
    base_url: Optional[str] = Field(
        default=None,
        description="Configured Hindsight service URL (with secrets redacted)",
    )
    total_synced_memories: int = Field(
        ...,
        description="Total number of memories indexed in local MemoryMetadata",
    )
    bank_count: int = Field(
        ...,
        description="Number of distinct product memory banks tracked locally",
    )
