"""Sentiment & Temporal Analytics Service (Part 8 - Hackathon Prototype).

Provides high-performance product intelligence queries over feedback,
latest valid classification records, aspect sentiments, and themes.
"""

from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
import logging
from typing import Any, Dict, List, Optional, Set, Tuple
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import AppException
from app.models.classification import FeedbackClassification
from app.models.feedback import Feedback, FeedbackThemes
from app.models.theme import Theme
from app.schemas.analytics import (
    AspectSentimentItem,
    AspectSentimentResponse,
    CustomerIntentItem,
    CustomerIntentResponse,
    DailySentimentTrendItem,
    FeedbackVolumeResponse,
    OverallAnalyticsOverview,
    SentimentBreakdown,
    SentimentTrendsResponse,
    ThemeAnalyticsItem,
    ThemeAnalyticsResponse,
    TimeRangeResponse,
    VolumeBucketItem,
)

logger = logging.getLogger("analytics_service")

VALID_STATUSES = ("classified", "pending_review")


def resolve_time_range(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    days: Optional[int] = None,
    default_days: int = 30,
) -> Tuple[datetime, datetime, int]:
    """Resolve and validate timezone-aware start and end timestamps."""
    now_utc = datetime.now(timezone.utc)

    if start_date and end_date:
        if start_date.tzinfo is None:
            start_date = start_date.replace(tzinfo=timezone.utc)
        if end_date.tzinfo is None:
            end_date = end_date.replace(tzinfo=timezone.utc)

        if start_date > end_date:
            raise AppException(
                message="start_date must be before or equal to end_date.",
                status_code=400,
                code="INVALID_DATE_RANGE",
            )
        duration_days = max(1, (end_date - start_date).days)
        return start_date, end_date, duration_days

    if start_date and not end_date:
        if start_date.tzinfo is None:
            start_date = start_date.replace(tzinfo=timezone.utc)
        if start_date > now_utc:
            raise AppException(
                message="start_date cannot be in the future.",
                status_code=400,
                code="INVALID_DATE_RANGE",
            )
        duration_days = max(1, (now_utc - start_date).days)
        return start_date, now_utc, duration_days

    if end_date and not start_date:
        if end_date.tzinfo is None:
            end_date = end_date.replace(tzinfo=timezone.utc)
        d = days if (days and days > 0) else default_days
        start_date = end_date - timedelta(days=d)
        return start_date, end_date, d

    # Neither provided
    d = days if (days and days > 0) else default_days
    start_date = now_utc - timedelta(days=d)
    return start_date, now_utc, d


def get_latest_classification_subquery():
    """Build subquery strictly selecting the single latest valid classification per feedback item."""
    rn_subq = (
        select(
            FeedbackClassification.classification_id,
            FeedbackClassification.feedback_id,
            FeedbackClassification.overall_sentiment,
            FeedbackClassification.sentiment_score,
            FeedbackClassification.customer_intent,
            FeedbackClassification.aspects,
            FeedbackClassification.classified_at,
            func.row_number()
            .over(
                partition_by=FeedbackClassification.feedback_id,
                order_by=(
                    FeedbackClassification.classified_at.desc(),
                    FeedbackClassification.run_number.desc(),
                    FeedbackClassification.classification_id.desc(),
                ),
            )
            .label("rn"),
        )
        .where(FeedbackClassification.status.in_(VALID_STATUSES))
    ).subquery()

    return (
        select(rn_subq)
        .where(rn_subq.c.rn == 1)
    ).subquery()


class AnalyticsService:
    """Service providing aggregated dashboard analytics."""

    @classmethod
    def get_overview(
        cls,
        session: Session,
        product: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        days: Optional[int] = None,
    ) -> OverallAnalyticsOverview:
        """Compute high-level feedback counts, sentiment distribution, and percentages."""
        start_utc, end_utc, duration = resolve_time_range(start_date, end_date, days, default_days=30)
        latest_cls = get_latest_classification_subquery()

        stmt = (
            select(
                Feedback.feedback_id,
                latest_cls.c.overall_sentiment,
                latest_cls.c.sentiment_score,
            )
            .outerjoin(latest_cls, Feedback.feedback_id == latest_cls.c.feedback_id)
            .where(
                Feedback.deleted_at.is_(None),
                Feedback.timestamp >= start_utc,
                Feedback.timestamp <= end_utc,
            )
        )
        if product:
            stmt = stmt.where(Feedback.product == product)

        rows = session.execute(stmt).all()
        total_count = len(rows)

        classified_rows = [r for r in rows if r[1] is not None]
        classified_count = len(classified_rows)
        unclassified_count = total_count - classified_count

        sentiments = Counter(r[1] for r in classified_rows)
        pos = sentiments.get("positive", 0)
        neg = sentiments.get("negative", 0)
        neu = sentiments.get("neutral", 0)
        mix = sentiments.get("mixed", 0)

        def pct(count: int) -> float:
            if classified_count == 0:
                return 0.0
            return round((count / classified_count) * 100.0, 1)

        avg_score: Optional[float] = None
        if classified_count > 0:
            avg_score = round(sum(r[2] for r in classified_rows) / classified_count, 4)

        return OverallAnalyticsOverview(
            product=product,
            time_range=TimeRangeResponse(start_date=start_utc, end_date=end_utc, days=duration),
            total_feedback_count=total_count,
            classified_feedback_count=classified_count,
            unclassified_feedback_count=unclassified_count,
            sentiment_breakdown=SentimentBreakdown(
                positive=pos,
                positive_percentage=pct(pos),
                negative=neg,
                negative_percentage=pct(neg),
                neutral=neu,
                neutral_percentage=pct(neu),
                mixed=mix,
                mixed_percentage=pct(mix),
            ),
            average_sentiment_score=avg_score,
        )

    @classmethod
    def get_sentiment_trends(
        cls,
        session: Session,
        product: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        days: Optional[int] = None,
    ) -> SentimentTrendsResponse:
        """Compute continuous daily time-series buckets for sentiment distribution and volume."""
        start_utc, end_utc, duration = resolve_time_range(start_date, end_date, days, default_days=30)
        latest_cls = get_latest_classification_subquery()

        stmt = (
            select(
                Feedback.feedback_id,
                Feedback.timestamp,
                latest_cls.c.overall_sentiment,
                latest_cls.c.sentiment_score,
            )
            .outerjoin(latest_cls, Feedback.feedback_id == latest_cls.c.feedback_id)
            .where(
                Feedback.deleted_at.is_(None),
                Feedback.timestamp >= start_utc,
                Feedback.timestamp <= end_utc,
            )
        )
        if product:
            stmt = stmt.where(Feedback.product == product)

        rows = session.execute(stmt).all()

        # Group rows by date
        grouped: Dict[date, List[Any]] = defaultdict(list)
        for r in rows:
            ts = r[1]
            if isinstance(ts, datetime):
                grouped[ts.date()].append(r)

        # Generate continuous daily buckets from start_date to end_date
        daily_trends: List[DailySentimentTrendItem] = []
        curr_d = start_utc.date()
        end_d = end_utc.date()

        while curr_d <= end_d:
            day_rows = grouped.get(curr_d, [])
            total_vol = len(day_rows)
            pos, neg, neu, mix, unclass = 0, 0, 0, 0, 0
            scores: List[float] = []

            for row in day_rows:
                sentiment = row[2]
                score = row[3]
                if sentiment == "positive":
                    pos += 1
                elif sentiment == "negative":
                    neg += 1
                elif sentiment == "neutral":
                    neu += 1
                elif sentiment == "mixed":
                    mix += 1
                else:
                    unclass += 1

                if score is not None:
                    scores.append(score)

            day_avg = round(sum(scores) / len(scores), 4) if scores else None

            daily_trends.append(
                DailySentimentTrendItem(
                    date=curr_d.isoformat(),
                    total_volume=total_vol,
                    positive_count=pos,
                    negative_count=neg,
                    neutral_count=neu,
                    mixed_count=mix,
                    unclassified_count=unclass,
                    average_sentiment_score=day_avg,
                )
            )
            curr_d += timedelta(days=1)

        return SentimentTrendsResponse(
            product=product,
            time_range=TimeRangeResponse(start_date=start_utc, end_date=end_utc, days=duration),
            daily_trends=daily_trends,
        )

    @classmethod
    def get_aspect_sentiment(
        cls,
        session: Session,
        product: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        days: Optional[int] = None,
        limit: int = 20,
    ) -> AspectSentimentResponse:
        """Extract and aggregate aspect-level feedback, ranked by negative feedback volume."""
        start_utc, end_utc, duration = resolve_time_range(start_date, end_date, days, default_days=30)
        latest_cls = get_latest_classification_subquery()

        stmt = (
            select(latest_cls.c.aspects)
            .select_from(Feedback)
            .join(latest_cls, Feedback.feedback_id == latest_cls.c.feedback_id)
            .where(
                Feedback.deleted_at.is_(None),
                Feedback.timestamp >= start_utc,
                Feedback.timestamp <= end_utc,
                latest_cls.c.aspects.is_not(None),
            )
        )
        if product:
            stmt = stmt.where(Feedback.product == product)

        aspect_stats: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {"total": 0, "pos": 0, "neg": 0, "neu": 0, "mix": 0, "scores": []}
        )

        for (aspects_json,) in session.execute(stmt):
            if not aspects_json or not isinstance(aspects_json, list):
                continue
            for item in aspects_json:
                if not isinstance(item, dict):
                    continue
                raw_name = str(item.get("aspect", "")).strip().lower()
                if not raw_name:
                    continue
                sent = str(item.get("sentiment", "neutral")).lower()
                score = item.get("sentiment_score")

                stat = aspect_stats[raw_name]
                stat["total"] += 1
                if sent == "positive":
                    stat["pos"] += 1
                elif sent == "negative":
                    stat["neg"] += 1
                elif sent == "neutral":
                    stat["neu"] += 1
                elif sent == "mixed":
                    stat["mix"] += 1

                if score is not None:
                    try:
                        stat["scores"].append(float(score))
                    except (ValueError, TypeError):
                        pass

        # Build aspect items
        items: List[AspectSentimentItem] = []
        for name, stat in aspect_stats.items():
            scores = stat["scores"]
            avg_score = round(sum(scores) / len(scores), 4) if scores else None
            items.append(
                AspectSentimentItem(
                    aspect_name=name,
                    total_mentions=stat["total"],
                    positive_mentions=stat["pos"],
                    negative_mentions=stat["neg"],
                    neutral_mentions=stat["neu"],
                    mixed_mentions=stat["mix"],
                    average_sentiment_score=avg_score,
                )
            )

        # Rank primarily by negative mentions descending, then total mentions descending
        items.sort(key=lambda x: (x.negative_mentions, x.total_mentions), reverse=True)

        return AspectSentimentResponse(
            product=product,
            time_range=TimeRangeResponse(start_date=start_utc, end_date=end_utc, days=duration),
            total_aspects_identified=len(items),
            aspects=items[:limit],
        )

    @classmethod
    def get_theme_analytics(
        cls,
        session: Session,
        product: Optional[str] = None,
        limit: int = 20,
    ) -> ThemeAnalyticsResponse:
        """Compute theme-level sentiment distribution, feedback volume, and negative rankings."""
        stmt = select(Theme).where(Theme.status.in_(["active", "candidate"]))
        if product:
            stmt = stmt.where(Theme.product == product)
        stmt = stmt.order_by(Theme.created_at.desc())

        themes = session.execute(stmt).scalars().all()
        total_active = sum(1 for t in themes if t.status == "active")
        total_candidate = sum(1 for t in themes if t.status == "candidate")

        if not themes:
            return ThemeAnalyticsResponse(
                product=product,
                total_active_themes=0,
                total_candidate_themes=0,
                most_discussed_themes=[],
                most_negative_themes=[],
                all_themes=[],
            )

        latest_cls = get_latest_classification_subquery()
        theme_items: List[ThemeAnalyticsItem] = []

        for t in themes:
            # Query linked feedback and their latest classifications
            link_stmt = (
                select(
                    FeedbackThemes.feedback_id,
                    latest_cls.c.overall_sentiment,
                    latest_cls.c.sentiment_score,
                )
                .join(Feedback, FeedbackThemes.feedback_id == Feedback.feedback_id)
                .outerjoin(latest_cls, FeedbackThemes.feedback_id == latest_cls.c.feedback_id)
                .where(
                    FeedbackThemes.theme_id == t.theme_id,
                    Feedback.deleted_at.is_(None),
                )
            )
            rows = session.execute(link_stmt).all()
            fb_count = len(rows)

            pos, neg, neu, mix = 0, 0, 0, 0
            scores: List[float] = []

            for r in rows:
                sent = r[1]
                score = r[2]
                if sent == "positive":
                    pos += 1
                elif sent == "negative":
                    neg += 1
                elif sent == "neutral":
                    neu += 1
                elif sent == "mixed":
                    mix += 1

                if score is not None:
                    scores.append(score)

            avg_score = round(sum(scores) / len(scores), 4) if scores else None

            theme_items.append(
                ThemeAnalyticsItem(
                    theme_id=t.theme_id,
                    theme_name=t.theme_name,
                    product=t.product,
                    status=t.status,
                    category=t.category,
                    feedback_count=fb_count,
                    positive_count=pos,
                    negative_count=neg,
                    neutral_count=neu,
                    mixed_count=mix,
                    average_sentiment_score=avg_score,
                )
            )

        # Most discussed: feedback count desc
        most_discussed = sorted(theme_items, key=lambda x: x.feedback_count, reverse=True)

        # Most negative: negative count desc, then feedback count desc
        most_negative = sorted(theme_items, key=lambda x: (x.negative_count, x.feedback_count), reverse=True)

        return ThemeAnalyticsResponse(
            product=product,
            total_active_themes=total_active,
            total_candidate_themes=total_candidate,
            most_discussed_themes=most_discussed[:limit],
            most_negative_themes=most_negative[:limit],
            all_themes=theme_items[:limit],
        )

    @classmethod
    def get_customer_intents(
        cls,
        session: Session,
        product: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        days: Optional[int] = None,
    ) -> CustomerIntentResponse:
        """Break down feedback by detected customer intent and sentiment."""
        start_utc, end_utc, duration = resolve_time_range(start_date, end_date, days, default_days=30)
        latest_cls = get_latest_classification_subquery()

        stmt = (
            select(
                latest_cls.c.customer_intent,
                latest_cls.c.overall_sentiment,
                latest_cls.c.sentiment_score,
            )
            .select_from(Feedback)
            .join(latest_cls, Feedback.feedback_id == latest_cls.c.feedback_id)
            .where(
                Feedback.deleted_at.is_(None),
                Feedback.timestamp >= start_utc,
                Feedback.timestamp <= end_utc,
                latest_cls.c.customer_intent.is_not(None),
            )
        )
        if product:
            stmt = stmt.where(Feedback.product == product)

        rows = session.execute(stmt).all()
        total_classified = len(rows)

        if total_classified == 0:
            return CustomerIntentResponse(
                product=product,
                time_range=TimeRangeResponse(start_date=start_utc, end_date=end_utc, days=duration),
                total_classified_feedback=0,
                intents=[],
            )

        intent_stats: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {"count": 0, "pos": 0, "neg": 0, "neu": 0, "mix": 0, "scores": []}
        )

        for intent, sent, score in rows:
            stat = intent_stats[intent]
            stat["count"] += 1
            if sent == "positive":
                stat["pos"] += 1
            elif sent == "negative":
                stat["neg"] += 1
            elif sent == "neutral":
                stat["neu"] += 1
            elif sent == "mixed":
                stat["mix"] += 1

            if score is not None:
                stat["scores"].append(score)

        items: List[CustomerIntentItem] = []
        for intent_name, stat in intent_stats.items():
            cnt = stat["count"]
            pct = round((cnt / total_classified) * 100.0, 1)
            scores = stat["scores"]
            avg_score = round(sum(scores) / len(scores), 4) if scores else None

            items.append(
                CustomerIntentItem(
                    intent=intent_name,
                    count=cnt,
                    percentage_of_classified=pct,
                    positive_count=stat["pos"],
                    negative_count=stat["neg"],
                    neutral_count=stat["neu"],
                    mixed_count=stat["mix"],
                    average_sentiment_score=avg_score,
                )
            )

        items.sort(key=lambda x: x.count, reverse=True)

        return CustomerIntentResponse(
            product=product,
            time_range=TimeRangeResponse(start_date=start_utc, end_date=end_utc, days=duration),
            total_classified_feedback=total_classified,
            intents=items,
        )

    @classmethod
    def get_feedback_volume(
        cls,
        session: Session,
        product: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        days: Optional[int] = None,
        granularity: str = "daily",
    ) -> FeedbackVolumeResponse:
        """Compute feedback volume time-series and comparative metrics with previous equivalent period."""
        start_utc, end_utc, duration = resolve_time_range(start_date, end_date, days, default_days=30)

        # Previous equivalent period
        prev_start_utc = start_utc - timedelta(days=duration)
        prev_end_utc = start_utc

        # Current period volume
        curr_stmt = (
            select(func.count(Feedback.feedback_id)).where(
                Feedback.deleted_at.is_(None),
                Feedback.timestamp >= start_utc,
                Feedback.timestamp <= end_utc,
            )
        )
        if product:
            curr_stmt = curr_stmt.where(Feedback.product == product)
        curr_vol = session.execute(curr_stmt).scalar() or 0

        # Previous period volume
        prev_stmt = (
            select(func.count(Feedback.feedback_id)).where(
                Feedback.deleted_at.is_(None),
                Feedback.timestamp >= prev_start_utc,
                Feedback.timestamp < prev_end_utc,
            )
        )
        if product:
            prev_stmt = prev_stmt.where(Feedback.product == product)
        prev_vol = session.execute(prev_stmt).scalar() or 0

        # Absolute & Percentage Change without division-by-zero
        abs_change = curr_vol - prev_vol
        pct_change: Optional[float] = None
        if prev_vol > 0:
            pct_change = round(((curr_vol - prev_vol) / prev_vol) * 100.0, 1)
        elif curr_vol > 0:
            pct_change = 100.0
        else:
            pct_change = 0.0

        is_growth = curr_vol >= prev_vol

        # Time-series volume trend for current period
        ts_stmt = (
            select(Feedback.timestamp)
            .where(
                Feedback.deleted_at.is_(None),
                Feedback.timestamp >= start_utc,
                Feedback.timestamp <= end_utc,
            )
        )
        if product:
            ts_stmt = ts_stmt.where(Feedback.product == product)

        ts_rows = session.execute(ts_stmt).scalars().all()
        counts_by_date = Counter()
        for ts in ts_rows:
            if isinstance(ts, datetime):
                counts_by_date[ts.date()] += 1

        volume_trend: List[VolumeBucketItem] = []
        curr_d = start_utc.date()
        end_d = end_utc.date()

        while curr_d <= end_d:
            volume_trend.append(
                VolumeBucketItem(
                    bucket_label=curr_d.isoformat(),
                    volume=counts_by_date.get(curr_d, 0),
                )
            )
            curr_d += timedelta(days=1)

        return FeedbackVolumeResponse(
            product=product,
            current_period=TimeRangeResponse(start_date=start_utc, end_date=end_utc, days=duration),
            previous_period=TimeRangeResponse(start_date=prev_start_utc, end_date=prev_end_utc, days=duration),
            current_volume=curr_vol,
            previous_volume=prev_vol,
            absolute_change=abs_change,
            percentage_change=pct_change,
            is_growth=is_growth,
            granularity=granularity,
            volume_trend=volume_trend,
        )
