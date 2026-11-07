"""Pydantic v2 schemas for Theme Clustering Engine (Part 7 Step 4).

Defines strict typed contracts for Candidate Clusters, Unassigned Feedback,
and Overall Clustering Results.
"""

from datetime import datetime, timezone
import math
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, Field, model_validator


class TopicAggregationItem(BaseModel):
    """Aggregated topic metadata across member feedbacks in a candidate cluster."""

    label: str
    count: int = Field(..., ge=1, description="Number of feedback records tagged with this topic")
    average_confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Average model confidence score for this topic",
    )


class CandidateClusterItem(BaseModel):
    """In-memory candidate cluster representing a potential emerging or active theme."""

    cluster_id: uuid.UUID = Field(
        ...,
        description="Deterministic UUID5 generated from product, algorithm version, and sorted members",
    )
    product: str = Field(..., description="Product line owning this candidate cluster")
    member_feedback_ids: List[uuid.UUID] = Field(
        ...,
        min_length=1,
        description="Unique feedback UUIDs belonging to this cluster",
    )
    size: int = Field(..., ge=1, description="Total count of member feedback items")
    representative_feedback_ids: List[uuid.UUID] = Field(
        ...,
        min_length=1,
        description="Exemplar feedback IDs closest to centroid (centroid_nearest_representative)",
    )
    centroid_vector: List[float] = Field(
        ...,
        description="Unit-normalized arithmetic mean vector of member embeddings",
    )
    average_similarity: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Mean pairwise cosine similarity within the cluster, clamped to [0.0, 1.0] for presentation",
    )
    cohesion_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Mean cosine similarity of member vectors to centroid, clamped to [0.0, 1.0] for presentation",
    )
    dominant_topics: List[TopicAggregationItem] = Field(
        default_factory=list,
        description="Top extracted topics aggregated from member classifications",
    )
    dominant_intent: Optional[str] = Field(
        default=None,
        description="Most frequent customer intent among member classifications",
    )

    @model_validator(mode="after")
    def validate_cluster_integrity(self) -> "CandidateClusterItem":
        # 1. Size must equal member count
        if self.size != len(self.member_feedback_ids):
            raise ValueError(f"size ({self.size}) must equal len(member_feedback_ids) ({len(self.member_feedback_ids)})")

        # 2. Member IDs must be unique
        if len(set(self.member_feedback_ids)) != len(self.member_feedback_ids):
            raise ValueError("member_feedback_ids must contain unique UUIDs")

        # 3. Representative IDs must be members of the cluster
        member_set = set(self.member_feedback_ids)
        for rep_id in self.representative_feedback_ids:
            if rep_id not in member_set:
                raise ValueError(f"Representative ID {rep_id} is not in member_feedback_ids")

        # 4. Centroid vector values must be finite floats
        for idx, val in enumerate(self.centroid_vector):
            if not math.isfinite(val):
                raise ValueError(f"Non-finite value at index {idx} in centroid_vector: {val}")

        return self


class UnassignedFeedbackItem(BaseModel):
    """Feedback item not grouped into any qualifying candidate cluster."""

    feedback_id: uuid.UUID
    reason: str = Field(
        ...,
        description="Reason for exclusion: 'CLUSTER_BELOW_MIN_SIZE', 'BELOW_SIMILARITY_THRESHOLD', or 'NO_COMPATIBLE_CLUSTER'",
    )
    nearest_cluster_id: Optional[uuid.UUID] = Field(
        default=None,
        description="Cluster ID of closest candidate cluster, if one exists",
    )
    nearest_similarity: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Cosine similarity to nearest cluster centroid, clamped to [0.0, 1.0] for presentation, if compared",
    )


class ThemeClusteringResult(BaseModel):
    """Complete summary and detailed results of a theme clustering execution."""

    clustering_run_id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        description="Unique execution identifier for this clustering run",
    )
    product: str = Field(..., description="Product line analyzed")
    algorithm: str = Field(default="agglomerative_average_linkage")
    algorithm_version: str = Field(default="1.0.0")
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Configured parameters: similarity_threshold, min_cluster_size, etc.",
    )
    total_feedback_evaluated: int = Field(..., ge=0)
    clustered_feedback_count: int = Field(..., ge=0)
    unassigned_feedback_count: int = Field(..., ge=0)
    clusters: List[CandidateClusterItem] = Field(default_factory=list)
    unassigned: List[UnassignedFeedbackItem] = Field(default_factory=list)
    duration_ms: float = Field(..., ge=0.0)
    executed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode="after")
    def validate_counts_consistency(self) -> "ThemeClusteringResult":
        expected_total = self.clustered_feedback_count + self.unassigned_feedback_count
        if self.total_feedback_evaluated != expected_total:
            raise ValueError(
                f"total_feedback_evaluated ({self.total_feedback_evaluated}) != "
                f"clustered ({self.clustered_feedback_count}) + unassigned ({self.unassigned_feedback_count})"
            )

        actual_clustered = sum(c.size for c in self.clusters)
        if self.clustered_feedback_count != actual_clustered:
            raise ValueError(
                f"clustered_feedback_count ({self.clustered_feedback_count}) != "
                f"sum of cluster sizes ({actual_clustered})"
            )

        if self.unassigned_feedback_count != len(self.unassigned):
            raise ValueError(
                f"unassigned_feedback_count ({self.unassigned_feedback_count}) != "
                f"len(unassigned) ({len(self.unassigned)})"
            )

        return self
