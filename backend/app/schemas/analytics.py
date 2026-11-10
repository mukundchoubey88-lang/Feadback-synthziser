"""Pydantic v2 schemas for Sentiment & Temporal Analytics (Part 8 - Hackathon Prototype).

Defines structured response models for:
- Overall sentiment summary and percentages
- Time-series sentiment trends (continuous daily buckets)
- Aspect-based sentiment analysis
- Theme analytics and ranking
- Customer intent distribution
- Feedback volume comparisons across equivalent periods
"""

from datetime import date, datetime
from typing import Dict, List, Optional
import uuid
from pydantic import BaseModel, Field


class TimeRangeResponse(BaseModel):
    """Time boundary information for analytics queries."""

    start_date: datetime
    end_date: datetime
    days: Optional[int] = None


class SentimentBreakdown(BaseModel):
    """Categorical count and percentage breakdown for sentiments."""

    positive: int = Field(0, description="Positive feedback count")
    positive_percentage: float = Field(0.0, description="Percentage of classified feedback")
    negative: int = Field(0, description="Negative feedback count")
    negative_percentage: float = Field(0.0, description="Percentage of classified feedback")
    neutral: int = Field(0, description="Neutral feedback count")
    neutral_percentage: float = Field(0.0, description="Percentage of classified feedback")
    mixed: int = Field(0, description="Mixed feedback count")
    mixed_percentage: float = Field(0.0, description="Percentage of classified feedback")


class OverallAnalyticsOverview(BaseModel):
    """Overall sentiment and volume distribution overview."""

    product: Optional[str] = None
    time_range: TimeRangeResponse
    total_feedback_count: int = Field(0, description="Total feedback records in scope")
    classified_feedback_count: int = Field(0, description="Feedback records with valid classification")
    unclassified_feedback_count: int = Field(0, description="Feedback records pending or unclassified")
    sentiment_breakdown: SentimentBreakdown
    average_sentiment_score: Optional[float] = Field(
        None, description="Mean sentiment score across classified feedback (-1.0 to 1.0)"
    )


class DailySentimentTrendItem(BaseModel):
    """Single calendar day bucket for sentiment time-series."""

    date: str = Field(..., description="Calendar date in YYYY-MM-DD format")
    total_volume: int = Field(0, description="Total feedback records on this day")
    positive_count: int = Field(0, description="Positive feedback count")
    negative_count: int = Field(0, description="Negative feedback count")
    neutral_count: int = Field(0, description="Neutral feedback count")
    mixed_count: int = Field(0, description="Mixed feedback count")
    unclassified_count: int = Field(0, description="Unclassified feedback count")
    average_sentiment_score: Optional[float] = Field(
        None, description="Average continuous sentiment score on this day"
    )


class SentimentTrendsResponse(BaseModel):
    """Time-series trend response over a continuous date range."""

    product: Optional[str] = None
    time_range: TimeRangeResponse
    daily_trends: List[DailySentimentTrendItem] = Field(default_factory=list)


class AspectSentimentItem(BaseModel):
    """Aggregated aspect-level sentiment metrics."""

    aspect_name: str
    total_mentions: int = Field(..., description="Total feedback mentions of this aspect")
    positive_mentions: int = Field(0, description="Positive mentions")
    negative_mentions: int = Field(0, description="Negative mentions")
    neutral_mentions: int = Field(0, description="Neutral mentions")
    mixed_mentions: int = Field(0, description="Mixed mentions")
    average_sentiment_score: Optional[float] = Field(
        None, description="Average continuous sentiment score for this aspect"
    )


class AspectSentimentResponse(BaseModel):
    """Aspect-based sentiment analysis response ranked by negative feedback volume."""

    product: Optional[str] = None
    time_range: TimeRangeResponse
    total_aspects_identified: int
    aspects: List[AspectSentimentItem] = Field(default_factory=list)


class ThemeAnalyticsItem(BaseModel):
    """Aggregated metrics for an individual theme."""

    theme_id: uuid.UUID
    theme_name: str
    product: str
    status: str
    category: str
    feedback_count: int = Field(0, description="Total linked feedback records")
    positive_count: int = Field(0, description="Positive classified feedback count")
    negative_count: int = Field(0, description="Negative classified feedback count")
    neutral_count: int = Field(0, description="Neutral classified feedback count")
    mixed_count: int = Field(0, description="Mixed classified feedback count")
    average_sentiment_score: Optional[float] = Field(
        None, description="Average continuous sentiment score among member feedback"
    )


class ThemeAnalyticsResponse(BaseModel):
    """Theme analytics and rankings."""

    product: Optional[str] = None
    total_active_themes: int
    total_candidate_themes: int
    most_discussed_themes: List[ThemeAnalyticsItem] = Field(
        default_factory=list, description="Themes ranked by feedback count descending"
    )
    most_negative_themes: List[ThemeAnalyticsItem] = Field(
        default_factory=list, description="Themes ranked by negative feedback volume descending"
    )
    all_themes: List[ThemeAnalyticsItem] = Field(default_factory=list)


class CustomerIntentItem(BaseModel):
    """Breakdown of customer intent."""

    intent: str = Field(..., description="Primary intent identifier")
    count: int = Field(..., description="Feedback count with this intent")
    percentage_of_classified: float = Field(
        ..., description="Percentage of all classified feedback"
    )
    positive_count: int = 0
    negative_count: int = 0
    neutral_count: int = 0
    mixed_count: int = 0
    average_sentiment_score: Optional[float] = None


class CustomerIntentResponse(BaseModel):
    """Breakdown of customer intents across feedback."""

    product: Optional[str] = None
    time_range: TimeRangeResponse
    total_classified_feedback: int
    intents: List[CustomerIntentItem] = Field(default_factory=list)


class VolumeBucketItem(BaseModel):
    """Time-series bucket for feedback volume."""

    bucket_label: str = Field(..., description="Date or period label")
    volume: int = Field(0, description="Feedback count in this bucket")


class FeedbackVolumeResponse(BaseModel):
    """Feedback volume analytics with comparative period analytics."""

    product: Optional[str] = None
    current_period: TimeRangeResponse
    previous_period: TimeRangeResponse
    current_volume: int = Field(..., description="Feedback count in current period")
    previous_volume: int = Field(..., description="Feedback count in equivalent previous period")
    absolute_change: int = Field(
        ..., description="Current volume minus previous volume"
    )
    percentage_change: Optional[float] = Field(
        None, description="Percentage change (+/- %) relative to previous period"
    )
    is_growth: bool = Field(..., description="True if current volume >= previous volume")
    granularity: str = Field("daily", description="Time bucket granularity")
    volume_trend: List[VolumeBucketItem] = Field(default_factory=list)
