"""API routes for Sentiment & Temporal Analytics (Part 8 - Hackathon Prototype)."""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.analytics import (
    AspectSentimentResponse,
    CustomerIntentResponse,
    FeedbackVolumeResponse,
    OverallAnalyticsOverview,
    SentimentTrendsResponse,
    ThemeAnalyticsResponse,
)
from app.services.analytics_service import AnalyticsService

router = APIRouter()


@router.get(
    "/overview",
    response_model=OverallAnalyticsOverview,
    status_code=status.HTTP_200_OK,
    summary="Overall Analytics Overview",
    description="Retrieve high-level feedback counts, sentiment distribution, and percentages.",
)
def get_analytics_overview(
    product: Optional[str] = Query(None, description="Filter by product name"),
    start_date: Optional[datetime] = Query(None, description="Start date in ISO format"),
    end_date: Optional[datetime] = Query(None, description="End date in ISO format"),
    days: Optional[int] = Query(None, ge=1, le=365, description="Lookback window in days (e.g., 7, 30, 90)"),
    session: Session = Depends(get_db),
) -> OverallAnalyticsOverview:
    """Compute overall sentiment and feedback volume overview."""
    return AnalyticsService.get_overview(
        session=session,
        product=product,
        start_date=start_date,
        end_date=end_date,
        days=days,
    )


@router.get(
    "/sentiment-trends",
    response_model=SentimentTrendsResponse,
    status_code=status.HTTP_200_OK,
    summary="Daily Sentiment Trends",
    description="Retrieve continuous daily time-series buckets of feedback volume and sentiment distribution.",
)
def get_sentiment_trends(
    product: Optional[str] = Query(None, description="Filter by product name"),
    start_date: Optional[datetime] = Query(None, description="Start date in ISO format"),
    end_date: Optional[datetime] = Query(None, description="End date in ISO format"),
    days: Optional[int] = Query(None, ge=1, le=365, description="Lookback window in days (default: 30)"),
    session: Session = Depends(get_db),
) -> SentimentTrendsResponse:
    """Compute continuous daily sentiment trends."""
    return AnalyticsService.get_sentiment_trends(
        session=session,
        product=product,
        start_date=start_date,
        end_date=end_date,
        days=days,
    )


@router.get(
    "/aspects",
    response_model=AspectSentimentResponse,
    status_code=status.HTTP_200_OK,
    summary="Aspect-Based Sentiment Analytics",
    description="Retrieve product aspects ranked by negative feedback volume.",
)
def get_aspect_analytics(
    product: Optional[str] = Query(None, description="Filter by product name"),
    start_date: Optional[datetime] = Query(None, description="Start date in ISO format"),
    end_date: Optional[datetime] = Query(None, description="End date in ISO format"),
    days: Optional[int] = Query(None, ge=1, le=365, description="Lookback window in days"),
    limit: int = Query(20, ge=1, le=100, description="Maximum number of aspects to return"),
    session: Session = Depends(get_db),
) -> AspectSentimentResponse:
    """Identify product aspects receiving feedback and rank by negative volume."""
    return AnalyticsService.get_aspect_sentiment(
        session=session,
        product=product,
        start_date=start_date,
        end_date=end_date,
        days=days,
        limit=limit,
    )


@router.get(
    "/themes",
    response_model=ThemeAnalyticsResponse,
    status_code=status.HTTP_200_OK,
    summary="Theme Analytics and Rankings",
    description="Retrieve theme-level sentiment distribution, most discussed themes, and most negative themes.",
)
def get_theme_analytics(
    product: Optional[str] = Query(None, description="Filter by product name"),
    limit: int = Query(20, ge=1, le=100, description="Maximum themes to return in rankings"),
    session: Session = Depends(get_db),
) -> ThemeAnalyticsResponse:
    """Compute theme metrics, discussion volume, and negative rankings."""
    return AnalyticsService.get_theme_analytics(
        session=session,
        product=product,
        limit=limit,
    )


@router.get(
    "/intents",
    response_model=CustomerIntentResponse,
    status_code=status.HTTP_200_OK,
    summary="Customer Intent Distribution",
    description="Retrieve breakdown of detected customer intents and sentiment per intent.",
)
def get_customer_intents(
    product: Optional[str] = Query(None, description="Filter by product name"),
    start_date: Optional[datetime] = Query(None, description="Start date in ISO format"),
    end_date: Optional[datetime] = Query(None, description="End date in ISO format"),
    days: Optional[int] = Query(None, ge=1, le=365, description="Lookback window in days"),
    session: Session = Depends(get_db),
) -> CustomerIntentResponse:
    """Compute customer intent distribution and sentiment metrics."""
    return AnalyticsService.get_customer_intents(
        session=session,
        product=product,
        start_date=start_date,
        end_date=end_date,
        days=days,
    )


@router.get(
    "/feedback-volume",
    response_model=FeedbackVolumeResponse,
    status_code=status.HTTP_200_OK,
    summary="Feedback Volume Comparison",
    description="Retrieve feedback volume trends and comparative growth metrics with the previous equivalent period.",
)
def get_feedback_volume(
    product: Optional[str] = Query(None, description="Filter by product name"),
    start_date: Optional[datetime] = Query(None, description="Start date in ISO format"),
    end_date: Optional[datetime] = Query(None, description="End date in ISO format"),
    days: Optional[int] = Query(None, ge=1, le=365, description="Lookback window in days (default: 30)"),
    granularity: str = Query("daily", description="Aggregation bucket granularity: daily or weekly"),
    session: Session = Depends(get_db),
) -> FeedbackVolumeResponse:
    """Compute volume trends and comparative period growth metrics."""
    return AnalyticsService.get_feedback_volume(
        session=session,
        product=product,
        start_date=start_date,
        end_date=end_date,
        days=days,
        granularity=granularity,
    )
