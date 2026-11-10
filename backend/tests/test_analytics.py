"""Unit and API integration tests for Sentiment & Temporal Analytics (Part 8 - Hackathon Prototype).

Tests coverage:
1. Overall sentiment distribution and counts.
2. Accurate sentiment percentages based on classified feedback.
3. Daily sentiment trends with continuous calendar days (no gaps).
4. Empty database behaviour (zero counts, empty lists, no crashes).
5. Aspect-based sentiment aggregation (ranking by negative mentions).
6. Theme analytics (active vs candidate, feedback count, discussion & negative rankings).
7. Customer intent distribution with sentiment breakdown per intent.
8. Feedback volume comparison (handling zero in previous period without division-by-zero).
9. Multiple classification runs without duplicate counting (window function rn == 1).
10. Invalid date range handling (start_date > end_date returns HTTP 400).
11. Product isolation across all analytics endpoints.
12. Exclusion of soft-deleted feedback records.
13. FastAPI analytics endpoints tested via TestClient.
"""

from datetime import datetime, timedelta, timezone
from typing import List, Optional
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.exceptions import AppException
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.classification import FeedbackClassification
from app.models.feedback import Feedback, FeedbackThemes
from app.models.theme import Theme
from app.services.analytics_service import AnalyticsService


# ---------------------------------------------------------------------------
# Test Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db_session():
    """Create isolated SQLite in-memory database and session for tests."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )

    @event.listens_for(engine, "connect")
    def do_connect(dbapi_connection, connection_record):
        dbapi_connection.isolation_level = None

    @event.listens_for(engine, "begin")
    def do_begin(conn):
        conn.exec_driver_sql("BEGIN")

    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_session):
    """FastAPI TestClient with overridden get_db dependency."""
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    test_client = TestClient(app)
    yield test_client
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def seed_feedback(
    session: Session,
    product: str = "AnalyticsApp",
    text: str = "Test feedback comment",
    days_ago: int = 0,
    deleted: bool = False,
) -> Feedback:
    """Helper to persist a feedback row with customizable timestamp."""
    fb_id = uuid.uuid4()
    ts = datetime.now(timezone.utc) - timedelta(days=days_ago)
    deleted_at = datetime.now(timezone.utc) if deleted else None

    fb = Feedback(
        feedback_id=fb_id,
        product=product,
        feedback_text=text,
        cleaned_feedback_text=text,
        source="customer_support",
        quality_status="clean",
        timestamp=ts,
        created_at=ts,
        deleted_at=deleted_at,
    )
    session.add(fb)
    session.commit()
    return fb


def seed_classification(
    session: Session,
    feedback_id: uuid.UUID,
    sentiment: str = "positive",
    score: float = 0.8,
    intent: str = "praise",
    aspects: Optional[List[dict]] = None,
    run_number: int = 1,
    status: str = "classified",
    classified_at: Optional[datetime] = None,
) -> FeedbackClassification:
    """Helper to persist a classification run."""
    c = FeedbackClassification(
        classification_id=uuid.uuid4(),
        feedback_id=feedback_id,
        classification_version="1.0.0",
        run_number=run_number,
        status=status,
        overall_sentiment=sentiment,
        sentiment_score=score,
        sentiment_intensity="medium",
        customer_intent=intent,
        aspects=aspects,
        confidence_score=0.95,
        classified_at=classified_at or datetime.now(timezone.utc),
    )
    session.add(c)
    session.commit()
    return c


# ---------------------------------------------------------------------------
# Test Cases: Empty Database Behavior
# ---------------------------------------------------------------------------

def test_analytics_empty_database(db_session):
    """Verify all analytics methods return structured zeroed responses on an empty database."""
    overview = AnalyticsService.get_overview(session=db_session, product="EmptyApp")
    assert overview.total_feedback_count == 0
    assert overview.classified_feedback_count == 0
    assert overview.unclassified_feedback_count == 0
    assert overview.sentiment_breakdown.positive == 0
    assert overview.average_sentiment_score is None

    trends = AnalyticsService.get_sentiment_trends(session=db_session, product="EmptyApp", days=7)
    assert len(trends.daily_trends) >= 7
    assert all(d.total_volume == 0 for d in trends.daily_trends)

    aspects = AnalyticsService.get_aspect_sentiment(session=db_session, product="EmptyApp")
    assert aspects.total_aspects_identified == 0
    assert aspects.aspects == []

    themes = AnalyticsService.get_theme_analytics(session=db_session, product="EmptyApp")
    assert themes.total_active_themes == 0
    assert themes.most_discussed_themes == []

    intents = AnalyticsService.get_customer_intents(session=db_session, product="EmptyApp")
    assert intents.total_classified_feedback == 0
    assert intents.intents == []

    volume = AnalyticsService.get_feedback_volume(session=db_session, product="EmptyApp", days=14)
    assert volume.current_volume == 0
    assert volume.previous_volume == 0
    assert volume.percentage_change == 0.0


# ---------------------------------------------------------------------------
# Test Cases: Overall Sentiment & Percentages
# ---------------------------------------------------------------------------

def test_overall_sentiment_distribution_and_percentages(db_session):
    """Verify counts and percentages for positive, negative, neutral, mixed, and unclassified."""
    fb_pos = seed_feedback(db_session, product="AppX", text="Loved it", days_ago=1)
    fb_neg = seed_feedback(db_session, product="AppX", text="Hated it", days_ago=2)
    fb_neu = seed_feedback(db_session, product="AppX", text="It is ok", days_ago=3)
    fb_mix = seed_feedback(db_session, product="AppX", text="Good but slow", days_ago=4)
    fb_unclass = seed_feedback(db_session, product="AppX", text="Pending classification", days_ago=5)

    seed_classification(db_session, fb_pos.feedback_id, sentiment="positive", score=0.8)
    seed_classification(db_session, fb_neg.feedback_id, sentiment="negative", score=-0.6)
    seed_classification(db_session, fb_neu.feedback_id, sentiment="neutral", score=0.0)
    seed_classification(db_session, fb_mix.feedback_id, sentiment="mixed", score=0.1)

    overview = AnalyticsService.get_overview(session=db_session, product="AppX", days=10)

    assert overview.total_feedback_count == 5
    assert overview.classified_feedback_count == 4
    assert overview.unclassified_feedback_count == 1

    sb = overview.sentiment_breakdown
    assert sb.positive == 1
    assert sb.positive_percentage == 25.0
    assert sb.negative == 1
    assert sb.negative_percentage == 25.0
    assert sb.neutral == 1
    assert sb.neutral_percentage == 25.0
    assert sb.mixed == 1
    assert sb.mixed_percentage == 25.0

    # Average score: (0.8 - 0.6 + 0.0 + 0.1) / 4 = 0.3 / 4 = 0.075
    assert overview.average_sentiment_score == 0.075


# ---------------------------------------------------------------------------
# Test Cases: Deduplicating Multiple Classification Runs
# ---------------------------------------------------------------------------

def test_deduplicates_multiple_classification_runs(db_session):
    """Verify that multiple classification runs for a feedback item do not inflate counts."""
    fb = seed_feedback(db_session, product="AppDedupe", text="Reclassified item", days_ago=1)

    # First run was negative (score -0.9)
    seed_classification(
        db_session,
        fb.feedback_id,
        sentiment="negative",
        score=-0.9,
        run_number=1,
        classified_at=datetime.now(timezone.utc) - timedelta(hours=2),
    )

    # Second run was positive (score 0.95, later run_number and classified_at)
    seed_classification(
        db_session,
        fb.feedback_id,
        sentiment="positive",
        score=0.95,
        run_number=2,
        classified_at=datetime.now(timezone.utc) - timedelta(hours=1),
    )

    overview = AnalyticsService.get_overview(session=db_session, product="AppDedupe", days=7)

    # Must count strictly 1 classified feedback, and its latest sentiment (positive)
    assert overview.total_feedback_count == 1
    assert overview.classified_feedback_count == 1
    assert overview.sentiment_breakdown.positive == 1
    assert overview.sentiment_breakdown.negative == 0
    assert overview.average_sentiment_score == 0.95


# ---------------------------------------------------------------------------
# Test Cases: Exclusion of Soft-Deleted Feedback
# ---------------------------------------------------------------------------

def test_excludes_soft_deleted_feedback(db_session):
    """Verify that soft-deleted feedback is excluded from analytics."""
    fb_active = seed_feedback(db_session, product="AppDel", text="Active", days_ago=1, deleted=False)
    fb_deleted = seed_feedback(db_session, product="AppDel", text="Deleted", days_ago=1, deleted=True)

    seed_classification(db_session, fb_active.feedback_id, sentiment="positive", score=0.9)
    seed_classification(db_session, fb_deleted.feedback_id, sentiment="positive", score=0.9)

    overview = AnalyticsService.get_overview(session=db_session, product="AppDel", days=7)
    assert overview.total_feedback_count == 1
    assert overview.classified_feedback_count == 1


# ---------------------------------------------------------------------------
# Test Cases: Product Isolation
# ---------------------------------------------------------------------------

def test_product_isolation(db_session):
    """Verify that analytics strictly filter by the requested product."""
    fb_a = seed_feedback(db_session, product="ProductA", text="Good A", days_ago=1)
    fb_b = seed_feedback(db_session, product="ProductB", text="Bad B", days_ago=1)

    seed_classification(db_session, fb_a.feedback_id, sentiment="positive", score=0.8)
    seed_classification(db_session, fb_b.feedback_id, sentiment="negative", score=-0.8)

    overview_a = AnalyticsService.get_overview(session=db_session, product="ProductA", days=7)
    assert overview_a.total_feedback_count == 1
    assert overview_a.sentiment_breakdown.positive == 1
    assert overview_a.sentiment_breakdown.negative == 0

    overview_b = AnalyticsService.get_overview(session=db_session, product="ProductB", days=7)
    assert overview_b.total_feedback_count == 1
    assert overview_b.sentiment_breakdown.positive == 0
    assert overview_b.sentiment_breakdown.negative == 1


# ---------------------------------------------------------------------------
# Test Cases: Sentiment Trends (Continuous Daily Buckets)
# ---------------------------------------------------------------------------

def test_daily_sentiment_trends_no_gaps(db_session):
    """Verify daily trends generate a continuous sequence of days with no gaps."""
    # Seed feedback on day 1 ago and day 3 ago (day 2 has 0 feedback)
    fb1 = seed_feedback(db_session, product="AppTrend", text="Day 1", days_ago=1)
    fb3 = seed_feedback(db_session, product="AppTrend", text="Day 3", days_ago=3)

    seed_classification(db_session, fb1.feedback_id, sentiment="positive", score=0.7)
    seed_classification(db_session, fb3.feedback_id, sentiment="negative", score=-0.5)

    trends = AnalyticsService.get_sentiment_trends(session=db_session, product="AppTrend", days=4)

    # 4 days lookback yields 5 calendar day buckets (days_ago 4, 3, 2, 1, 0)
    assert len(trends.daily_trends) >= 4

    total_vol = sum(d.total_volume for d in trends.daily_trends)
    assert total_vol == 2

    # Verify that the day with 0 feedback is represented with 0 counts and None score
    zero_days = [d for d in trends.daily_trends if d.total_volume == 0]
    assert len(zero_days) > 0
    assert zero_days[0].positive_count == 0
    assert zero_days[0].average_sentiment_score is None


# ---------------------------------------------------------------------------
# Test Cases: Aspect-Based Sentiment Analytics
# ---------------------------------------------------------------------------

def test_aspect_sentiment_aggregation_and_ranking(db_session):
    """Verify aspect sentiment extraction, scoring, and ranking by negative mentions."""
    fb1 = seed_feedback(db_session, product="AppAspect", text="Search is slow and billing is bad", days_ago=1)
    fb2 = seed_feedback(db_session, product="AppAspect", text="Search crashes constantly", days_ago=1)
    fb3 = seed_feedback(db_session, product="AppAspect", text="UI looks fantastic", days_ago=1)

    seed_classification(
        db_session,
        fb1.feedback_id,
        aspects=[
            {"aspect": "Search", "sentiment": "negative", "sentiment_score": -0.8},
            {"aspect": "Billing", "sentiment": "negative", "sentiment_score": -0.9},
        ],
    )
    seed_classification(
        db_session,
        fb2.feedback_id,
        aspects=[
            {"aspect": "Search", "sentiment": "negative", "sentiment_score": -1.0},
        ],
    )
    seed_classification(
        db_session,
        fb3.feedback_id,
        aspects=[
            {"aspect": "UI", "sentiment": "positive", "sentiment_score": 0.95},
        ],
    )

    resp = AnalyticsService.get_aspect_sentiment(session=db_session, product="AppAspect", days=7)

    assert resp.total_aspects_identified == 3
    aspect_names = [a.aspect_name for a in resp.aspects]
    assert "search" in aspect_names
    assert "billing" in aspect_names
    assert "ui" in aspect_names

    # Ranked by negative mentions: search (2 negative) must rank #1
    top_aspect = resp.aspects[0]
    assert top_aspect.aspect_name == "search"
    assert top_aspect.total_mentions == 2
    assert top_aspect.negative_mentions == 2
    assert top_aspect.average_sentiment_score == -0.9  # (-0.8 + -1.0) / 2

    ui_aspect = next(a for a in resp.aspects if a.aspect_name == "ui")
    assert ui_aspect.positive_mentions == 1
    assert ui_aspect.negative_mentions == 0


# ---------------------------------------------------------------------------
# Test Cases: Theme Analytics
# ---------------------------------------------------------------------------

def test_theme_analytics(db_session):
    """Verify theme analytics, discussion ranking, and negative ranking."""
    fb1 = seed_feedback(db_session, product="AppTheme", text="Crash on login")
    fb2 = seed_feedback(db_session, product="AppTheme", text="Login timeout")
    fb3 = seed_feedback(db_session, product="AppTheme", text="UI color suggestion")

    seed_classification(db_session, fb1.feedback_id, sentiment="negative", score=-0.8)
    seed_classification(db_session, fb2.feedback_id, sentiment="negative", score=-0.6)
    seed_classification(db_session, fb3.feedback_id, sentiment="neutral", score=0.0)

    # Theme 1 (Login issues - 2 feedbacks, both negative)
    t1 = Theme(
        theme_id=uuid.uuid4(),
        product="AppTheme",
        theme_name="Login Failures",
        category="auth",
        status="active",
    )
    # Theme 2 (UI Polish - 1 feedback, neutral)
    t2 = Theme(
        theme_id=uuid.uuid4(),
        product="AppTheme",
        theme_name="UI Styling",
        category="ui",
        status="candidate",
    )
    db_session.add_all([t1, t2])
    db_session.commit()

    db_session.add_all([
        FeedbackThemes(feedback_id=fb1.feedback_id, theme_id=t1.theme_id),
        FeedbackThemes(feedback_id=fb2.feedback_id, theme_id=t1.theme_id),
        FeedbackThemes(feedback_id=fb3.feedback_id, theme_id=t2.theme_id),
    ])
    db_session.commit()

    resp = AnalyticsService.get_theme_analytics(session=db_session, product="AppTheme")

    assert resp.total_active_themes == 1
    assert resp.total_candidate_themes == 1

    # Most discussed: t1 (2 members) should be first
    assert resp.most_discussed_themes[0].theme_id == t1.theme_id
    assert resp.most_discussed_themes[0].feedback_count == 2

    # Most negative: t1 (2 negative) should be first
    assert resp.most_negative_themes[0].theme_id == t1.theme_id
    assert resp.most_negative_themes[0].negative_count == 2
    assert resp.most_negative_themes[0].average_sentiment_score == -0.7


# ---------------------------------------------------------------------------
# Test Cases: Customer Intent Analytics
# ---------------------------------------------------------------------------

def test_customer_intent_analytics(db_session):
    """Verify breakdown of customer intents and percentages."""
    fb1 = seed_feedback(db_session, product="AppIntent", text="Feature please", days_ago=1)
    fb2 = seed_feedback(db_session, product="AppIntent", text="Another feature please", days_ago=1)
    fb3 = seed_feedback(db_session, product="AppIntent", text="Broken bug", days_ago=1)

    seed_classification(db_session, fb1.feedback_id, intent="feature_request", sentiment="positive", score=0.7)
    seed_classification(db_session, fb2.feedback_id, intent="feature_request", sentiment="neutral", score=0.0)
    seed_classification(db_session, fb3.feedback_id, intent="complaint", sentiment="negative", score=-0.9)

    resp = AnalyticsService.get_customer_intents(session=db_session, product="AppIntent", days=7)

    assert resp.total_classified_feedback == 3
    assert len(resp.intents) == 2

    feat_intent = next(i for i in resp.intents if i.intent == "feature_request")
    assert feat_intent.count == 2
    assert feat_intent.percentage_of_classified == 66.7
    assert feat_intent.positive_count == 1
    assert feat_intent.neutral_count == 1

    complaint_intent = next(i for i in resp.intents if i.intent == "complaint")
    assert complaint_intent.count == 1
    assert complaint_intent.percentage_of_classified == 33.3
    assert complaint_intent.negative_count == 1


# ---------------------------------------------------------------------------
# Test Cases: Feedback Volume & Period Comparison
# ---------------------------------------------------------------------------

def test_feedback_volume_comparison_and_zero_division_safety(db_session):
    """Verify comparative feedback volume and safe zero-division handling."""
    # Seed 3 items in the current period (last 7 days)
    seed_feedback(db_session, product="AppVol", text="V1", days_ago=1)
    seed_feedback(db_session, product="AppVol", text="V2", days_ago=2)
    seed_feedback(db_session, product="AppVol", text="V3", days_ago=3)

    # Previous period (8-14 days ago) has 0 feedback
    resp = AnalyticsService.get_feedback_volume(session=db_session, product="AppVol", days=7)

    assert resp.current_volume == 3
    assert resp.previous_volume == 0
    assert resp.absolute_change == 3
    # When previous volume is 0 and current > 0, percentage change is safely reported as 100.0% without ZeroDivisionError
    assert resp.percentage_change == 100.0
    assert resp.is_growth is True


def test_feedback_volume_comparison_with_prior_data(db_session):
    """Verify percentage change calculation when previous period has records."""
    # Current period (last 7 days): 4 items
    for _ in range(4):
        seed_feedback(db_session, product="AppVol2", text="Now", days_ago=2)

    # Previous period (8-14 days ago): 2 items
    for _ in range(2):
        seed_feedback(db_session, product="AppVol2", text="Past", days_ago=9)

    resp = AnalyticsService.get_feedback_volume(session=db_session, product="AppVol2", days=7)

    assert resp.current_volume == 4
    assert resp.previous_volume == 2
    assert resp.absolute_change == 2
    # ((4 - 2) / 2) * 100 = 100.0%
    assert resp.percentage_change == 100.0


# ---------------------------------------------------------------------------
# Test Cases: Invalid Date Range
# ---------------------------------------------------------------------------

def test_invalid_date_range_raises_app_exception(db_session):
    """Verify that start_date > end_date raises AppException with HTTP 400."""
    start = datetime(2026, 11, 10, tzinfo=timezone.utc)
    end = datetime(2026, 11, 5, tzinfo=timezone.utc)

    with pytest.raises(AppException) as exc_info:
        AnalyticsService.get_overview(session=db_session, start_date=start, end_date=end)
    assert exc_info.value.code == "INVALID_DATE_RANGE"
    assert exc_info.value.status_code == 400


# ---------------------------------------------------------------------------
# Test Cases: FastAPI Endpoints via TestClient
# ---------------------------------------------------------------------------

def test_api_analytics_endpoints(client, db_session):
    """Test all 6 analytics REST endpoints via TestClient."""
    fb = seed_feedback(db_session, product="ApiTestApp", text="Api feedback", days_ago=1)
    seed_classification(
        db_session,
        fb.feedback_id,
        sentiment="positive",
        score=0.9,
        intent="praise",
        aspects=[{"aspect": "Performance", "sentiment": "positive", "sentiment_score": 0.9}],
    )

    theme = Theme(
        theme_id=uuid.uuid4(),
        product="ApiTestApp",
        theme_name="Performance Excellence",
        category="perf",
        status="active",
    )
    db_session.add(theme)
    db_session.commit()
    db_session.add(FeedbackThemes(feedback_id=fb.feedback_id, theme_id=theme.theme_id))
    db_session.commit()

    # 1. GET /api/analytics/overview
    resp_overview = client.get("/api/analytics/overview?product=ApiTestApp&days=30")
    assert resp_overview.status_code == 200
    data_overview = resp_overview.json()
    assert data_overview["total_feedback_count"] == 1
    assert data_overview["classified_feedback_count"] == 1
    assert data_overview["sentiment_breakdown"]["positive"] == 1

    # 2. GET /api/analytics/sentiment-trends
    resp_trends = client.get("/api/analytics/sentiment-trends?product=ApiTestApp&days=7")
    assert resp_trends.status_code == 200
    data_trends = resp_trends.json()
    assert len(data_trends["daily_trends"]) >= 7

    # 3. GET /api/analytics/aspects
    resp_aspects = client.get("/api/analytics/aspects?product=ApiTestApp&days=30")
    assert resp_aspects.status_code == 200
    data_aspects = resp_aspects.json()
    assert data_aspects["total_aspects_identified"] == 1
    assert data_aspects["aspects"][0]["aspect_name"] == "performance"

    # 4. GET /api/analytics/themes
    resp_themes = client.get("/api/analytics/themes?product=ApiTestApp")
    assert resp_themes.status_code == 200
    data_themes = resp_themes.json()
    assert data_themes["total_active_themes"] == 1
    assert len(data_themes["most_discussed_themes"]) == 1

    # 5. GET /api/analytics/intents
    resp_intents = client.get("/api/analytics/intents?product=ApiTestApp&days=30")
    assert resp_intents.status_code == 200
    data_intents = resp_intents.json()
    assert data_intents["total_classified_feedback"] == 1
    assert data_intents["intents"][0]["intent"] == "praise"

    # 6. GET /api/analytics/feedback-volume
    resp_volume = client.get("/api/analytics/feedback-volume?product=ApiTestApp&days=30")
    assert resp_volume.status_code == 200
    data_volume = resp_volume.json()
    assert data_volume["current_volume"] == 1


def test_api_analytics_invalid_date_range(client):
    """Test GET /api/analytics/overview returns 400 for invalid date range."""
    resp = client.get("/api/analytics/overview?start_date=2026-11-10T00:00:00Z&end_date=2026-11-01T00:00:00Z")
    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "INVALID_DATE_RANGE"
