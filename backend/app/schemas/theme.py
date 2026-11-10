"""Pydantic v2 schemas for Theme Lifecycle Management (Part 7 - Hackathon Prototype).

Defines request and response schemas for theme candidate discovery,
theme listing, activation, discarding, merging, and sentiment summaries.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, Field


class RepresentativeFeedbackItem(BaseModel):
    """Exemplar feedback item associated with a theme."""

    feedback_id: uuid.UUID
    feedback_text: str
    cleaned_feedback_text: Optional[str] = None
    aspect_sentiment: Optional[str] = None


class ThemeSentimentSummary(BaseModel):
    """Basic aggregated sentiment and intent statistics for a theme."""

    total_feedbacks: int = Field(0, description="Total feedback items linked to this theme")
    classified_feedbacks: int = Field(0, description="Feedback items with valid classifications")
    positive: int = Field(0, description="Count of positive classifications")
    negative: int = Field(0, description="Count of negative classifications")
    neutral: int = Field(0, description="Count of neutral classifications")
    mixed: int = Field(0, description="Count of mixed classifications")
    average_sentiment_score: Optional[float] = Field(
        None, description="Average continuous sentiment score (-1.0 to 1.0)"
    )
    dominant_intent: Optional[str] = Field(
        None, description="Most frequent customer intent among member feedbacks"
    )


class ThemeResponse(BaseModel):
    """Core response schema for an active, candidate, merged, or discarded theme."""

    theme_id: uuid.UUID
    product: str
    theme_name: str
    description: Optional[str] = None
    category: str
    status: str
    created_at: datetime
    feedback_count: int = 0
    merged_into_id: Optional[uuid.UUID] = None
    representative_feedback: List[RepresentativeFeedbackItem] = Field(default_factory=list)
    sentiment_summary: Optional[ThemeSentimentSummary] = None


class DiscoverThemesRequest(BaseModel):
    """Request payload to trigger theme clustering discovery for a product."""

    product: str = Field(..., description="Target product identifier")
    similarity_threshold: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Cosine similarity threshold for clustering"
    )
    min_cluster_size: Optional[int] = Field(
        None, ge=2, description="Minimum feedback count to form a theme cluster"
    )
    max_batch_size: Optional[int] = Field(
        None, ge=1, le=150, description="Optional override ceiling for clustering batch size"
    )


class DiscoverThemesResponse(BaseModel):
    """Result payload from candidate theme discovery."""

    product: str
    discovered_count: int = Field(..., description="Total qualifying candidate clusters discovered")
    new_candidates_staged: int = Field(..., description="New candidate themes persisted to database")
    existing_candidates_skipped: int = Field(..., description="Duplicate candidate clusters skipped")
    candidates: List[ThemeResponse] = Field(default_factory=list)


class ActivateThemeRequest(BaseModel):
    """Request payload to promote a candidate theme to active status."""

    custom_name: Optional[str] = Field(
        None, max_length=150, description="Optional operator-specified theme name"
    )
    category: Optional[str] = Field(None, max_length=100, description="Optional updated category")
    description: Optional[str] = Field(None, description="Optional updated description")


class MergeThemesRequest(BaseModel):
    """Request payload to merge two themes within the same product."""

    source_theme_id: uuid.UUID = Field(..., description="Theme to be merged and retired")
    target_theme_id: uuid.UUID = Field(..., description="Destination active theme")


class MergeThemesResponse(BaseModel):
    """Response payload detailing outcome of a theme merge."""

    target_theme_id: uuid.UUID
    source_theme_id: uuid.UUID
    status: str = "merged"
    merged_feedback_count: int
    total_target_feedback_count: int
    message: str
