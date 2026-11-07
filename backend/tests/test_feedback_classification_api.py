"""Comprehensive API tests for Feedback Classification & Sentiment Analysis (Part 6 Step 4).

Tests endpoints:
- POST /api/feedback/classify (batch classification with isolated failures & bounds)
- POST /api/feedback/{feedback_id}/classify (single record reclassification & quality gatekeeping)
- GET /api/feedback/{feedback_id}/classification (deterministic latest retrieval)
- GET /api/classifications/summary (database-side aggregation, historical deduplication, date/product filters)
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch
import uuid
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.db.base import Base
from app.db.session import get_db
from app.integrations.ai.schemas import AIResponse, AIUsage
from app.main import app
from app.models.classification import FeedbackClassification
from app.models.feedback import Feedback
from app.models.sentiment import SentimentHistory
from app.schemas.classification import (
    AspectItem,
    AspectSentiment,
    BatchClassificationResponse,
    ClassificationSummaryResponse,
    CustomerIntent,
    FeedbackClassificationLLMOutput,
    FeedbackClassificationRecord,
    OverallSentiment,
    SentimentIntensity,
    TopicItem,
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_test_db():
    """Setup isolated in-memory SQLite database for each test with foreign keys enabled."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_get_db():
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()


def create_sample_feedback(
    text: str = "The dashboard is super fast and clean!",
    cleaned_text: str = "The dashboard is super fast and clean!",
    quality_status: str = "clean",
    product: str = "Analytics Dashboard",
    feature: str = "Performance",
    deleted: bool = False,
) -> uuid.UUID:
    """Helper to create a feedback row in the test DB."""
    fb_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    db = next(app.dependency_overrides[get_db]())
    feedback = Feedback(
        feedback_id=fb_id,
        source="csv",
        customer_id="cust-101",
        feedback_text=text,
        cleaned_feedback_text=cleaned_text,
        product=product,
        feature=feature,
        quality_status=quality_status,
        quality_score=90.0,
        cleaning_version="1.0.0",
        cleaned_at=now,
        deleted_at=now if deleted else None,
        created_at=now,
        timestamp=now,
    )
    db.add(feedback)
    db.commit()
    return fb_id


def build_mock_ai_response(
    sentiment: OverallSentiment = OverallSentiment.POSITIVE,
    score: float = 0.85,
    intensity: SentimentIntensity = SentimentIntensity.HIGH,
    intent: CustomerIntent = CustomerIntent.PRAISE,
    evidence: str = "super fast",
    product: str = "Analytics Dashboard",
    feature: str = "Performance",
    confidence: float = 0.92,
    needs_review: bool = False,
    review_reason: str = None,
) -> AIResponse:
    """Construct a mock AIResponse with valid structured data."""
    output = FeedbackClassificationLLMOutput(
        overall_sentiment=sentiment,
        sentiment_score=score,
        sentiment_intensity=intensity,
        customer_intent=intent,
        product=product,
        feature=feature,
        topics=[TopicItem(label="performance", confidence=0.95)],
        aspects=[
            AspectItem(
                aspect="speed",
                sentiment=AspectSentiment.POSITIVE,
                sentiment_score=0.9,
                confidence=0.95,
                evidence=evidence,
            )
        ],
        pain_points=[],
        keywords=["dashboard", "fast"],
        confidence_score=confidence,
        needs_review=needs_review,
        review_reason=review_reason,
    )
    return AIResponse(
        content="",
        structured_data=output,
        provider="gemini",
        model="gemini-2.5-flash",
        latency_ms=150.0,
        usage=AIUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150, cost_usd=0.0001),
    )


# ==============================================================================
# 1. Batch Classification Endpoint Tests (POST /api/feedback/classify)
# ==============================================================================


def test_batch_classification_success():
    """POST /api/feedback/classify successfully processes a bounded batch of feedback."""
    fb1 = create_sample_feedback(text="The dashboard is super fast and clean!")
    fb2 = create_sample_feedback(text="Great UI experience and super fast sync.")

    mock_resp = build_mock_ai_response()
    with patch("app.integrations.ai.manager.AIProviderManager.generate", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = mock_resp

        payload = {"feedback_ids": [str(fb1), str(fb2)], "reprocess": False}
        res = client.post(f"{settings.API_V1_PREFIX}/feedback/classify", json=payload)

        assert res.status_code == 200
        data = res.json()
        validated = BatchClassificationResponse.model_validate(data)
        assert validated.total_requested == 2
        assert validated.successful_count == 2
        assert validated.failed_count == 0
        assert validated.skipped_count == 0
        assert len(validated.results) == 2
        assert len(validated.errors) == 0
        assert validated.results[0].overall_sentiment == "positive"


def test_batch_classification_batch_size_limit():
    """POST /api/feedback/classify rejects requests exceeding max batch limit."""
    # Send 51 UUIDs when max batch size is 50
    excessive_ids = [str(uuid.uuid4()) for _ in range(51)]
    payload = {"feedback_ids": excessive_ids}
    res = client.post(f"{settings.API_V1_PREFIX}/feedback/classify", json=payload)

    assert res.status_code == 400
    data = res.json()
    assert data["error"]["code"] == "BATCH_TOO_LARGE"
    assert "exceeds maximum allowed limit" in data["error"]["message"]


def test_batch_classification_empty_batch():
    """POST /api/feedback/classify with empty batch returns empty summary cleanly."""
    payload = {"feedback_ids": []}
    res = client.post(f"{settings.API_V1_PREFIX}/feedback/classify", json=payload)

    assert res.status_code == 200
    data = res.json()
    validated = BatchClassificationResponse.model_validate(data)
    assert validated.total_requested == 0
    assert validated.successful_count == 0
    assert validated.failed_count == 0
    assert len(validated.results) == 0


def test_batch_classification_invalid_uuids():
    """POST /api/feedback/classify returns 422 for malformed UUID identifiers."""
    payload = {"feedback_ids": ["invalid-uuid-1234"]}
    res = client.post(f"{settings.API_V1_PREFIX}/feedback/classify", json=payload)

    assert res.status_code == 422


def test_batch_classification_partial_and_missing_failure():
    """POST /api/feedback/classify isolates failures: 1 valid, 1 missing, 1 rejected."""
    fb_valid = create_sample_feedback(text="The dashboard is super fast.")
    fb_missing = uuid.uuid4()
    fb_rejected = create_sample_feedback(
        text="asdf qwert",
        cleaned_text="asdf qwert",
        quality_status="rejected",
    )

    mock_resp = build_mock_ai_response()
    with patch("app.integrations.ai.manager.AIProviderManager.generate", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = mock_resp

        payload = {"feedback_ids": [str(fb_valid), str(fb_missing), str(fb_rejected)]}
        res = client.post(f"{settings.API_V1_PREFIX}/feedback/classify", json=payload)

        assert res.status_code == 200
        validated = BatchClassificationResponse.model_validate(res.json())
        assert validated.total_requested == 3
        assert validated.successful_count == 1
        assert validated.failed_count == 2
        assert len(validated.results) == 1
        assert len(validated.errors) == 2

        error_fids = {err.feedback_id for err in validated.errors}
        assert fb_missing in error_fids
        assert fb_rejected in error_fids


def test_batch_classification_all_record_failure():
    """POST /api/feedback/classify reports all errors if every item in batch fails."""
    fb_missing1 = uuid.uuid4()
    fb_missing2 = uuid.uuid4()

    payload = {"feedback_ids": [str(fb_missing1), str(fb_missing2)]}
    res = client.post(f"{settings.API_V1_PREFIX}/feedback/classify", json=payload)

    assert res.status_code == 200
    validated = BatchClassificationResponse.model_validate(res.json())
    assert validated.total_requested == 2
    assert validated.successful_count == 0
    assert validated.failed_count == 2


# ==============================================================================
# 2. Individual Classification Endpoint Tests (POST /api/feedback/{id}/classify)
# ==============================================================================


def test_individual_classification_success():
    """POST /api/feedback/{id}/classify classifies record and verifies dual persistence."""
    fb_id = create_sample_feedback(text="The dashboard is super fast and clean!")

    mock_resp = build_mock_ai_response()
    with patch("app.integrations.ai.manager.AIProviderManager.generate", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = mock_resp

        res = client.post(f"{settings.API_V1_PREFIX}/feedback/{fb_id}/classify")
        assert res.status_code == 200
        rec = FeedbackClassificationRecord.model_validate(res.json())
        assert rec.feedback_id == fb_id
        assert rec.overall_sentiment == "positive"
        assert rec.sentiment_intensity == "high"
        assert rec.customer_intent == "praise"
        assert rec.status == "classified"

        # Verify dual persistence in SentimentHistory
        db = next(app.dependency_overrides[get_db]())
        histories = db.execute(
            select(SentimentHistory).where(SentimentHistory.feedback_id == fb_id)
        ).scalars().all()
        assert len(histories) == 1
        assert histories[0].sentiment_label == "positive"


def test_individual_reclassification_and_historical_preservation():
    """POST /api/feedback/{id}/classify supports reprocess=True and preserves history."""
    fb_id = create_sample_feedback(text="The dashboard is super fast.")

    mock_resp1 = build_mock_ai_response(sentiment=OverallSentiment.POSITIVE, score=0.8)
    mock_resp2 = build_mock_ai_response(sentiment=OverallSentiment.MIXED, score=0.1)

    with patch("app.integrations.ai.manager.AIProviderManager.generate", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = mock_resp1
        res1 = client.post(f"{settings.API_V1_PREFIX}/feedback/{fb_id}/classify")
        assert res1.status_code == 200

        # Without reprocess=True, returns existing classification without re-calling AI
        mock_gen.return_value = mock_resp2
        res2 = client.post(f"{settings.API_V1_PREFIX}/feedback/{fb_id}/classify")
        assert res2.status_code == 200
        assert res2.json()["overall_sentiment"] == "positive"
        assert mock_gen.call_count == 1

        # With reprocess=True, invokes AI, creates a new run without overwriting, and appends to SentimentHistory
        res3 = client.post(f"{settings.API_V1_PREFIX}/feedback/{fb_id}/classify?reprocess=true")
        assert res3.status_code == 200
        assert res3.json()["overall_sentiment"] == "mixed"
        assert res3.json()["run_number"] == 2
        assert res3.json()["classification_id"] != res1.json()["classification_id"]
        assert mock_gen.call_count == 2

        db = next(app.dependency_overrides[get_db]())
        # Both execution runs are preserved in feedback_classifications
        classifications = db.execute(
            select(FeedbackClassification).where(FeedbackClassification.feedback_id == fb_id).order_by(FeedbackClassification.run_number)
        ).scalars().all()
        assert len(classifications) == 2
        assert classifications[0].run_number == 1
        assert classifications[0].overall_sentiment == "positive"
        assert classifications[1].run_number == 2
        assert classifications[1].overall_sentiment == "mixed"

        histories = db.execute(
            select(SentimentHistory).where(SentimentHistory.feedback_id == fb_id)
        ).scalars().all()
        assert len(histories) == 2  # Dual persistence records history for each run


def test_individual_classification_missing_feedback():
    """POST /api/feedback/{id}/classify returns 404 for nonexistent feedback."""
    missing_id = uuid.uuid4()
    res = client.post(f"{settings.API_V1_PREFIX}/feedback/{missing_id}/classify")
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "NOT_FOUND"


def test_individual_classification_soft_deleted():
    """POST /api/feedback/{id}/classify returns 400 for soft-deleted feedback."""
    deleted_id = create_sample_feedback(deleted=True)
    res = client.post(f"{settings.API_V1_PREFIX}/feedback/{deleted_id}/classify")
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "FEEDBACK_DELETED"


def test_individual_classification_unsuitable_quality():
    """POST /api/feedback/{id}/classify returns 422 for rejected or failed quality feedback."""
    rejected_id = create_sample_feedback(quality_status="rejected")
    res = client.post(f"{settings.API_V1_PREFIX}/feedback/{rejected_id}/classify")
    assert res.status_code == 422
    assert res.json()["error"]["code"] == "UNSUITABLE_QUALITY_STATUS"


# ==============================================================================
# 3. Retrieve Latest Classification Endpoint (GET /api/feedback/{id}/classification)
# ==============================================================================


def test_get_latest_classification_success():
    """GET /api/feedback/{id}/classification returns the latest classification record."""
    fb_id = create_sample_feedback(text="The dashboard is super fast.")
    mock_resp = build_mock_ai_response()

    with patch("app.integrations.ai.manager.AIProviderManager.generate", new_callable=AsyncMock) as mock_gen:
        mock_gen.return_value = mock_resp
        client.post(f"{settings.API_V1_PREFIX}/feedback/{fb_id}/classify")

    res = client.get(f"{settings.API_V1_PREFIX}/feedback/{fb_id}/classification")
    assert res.status_code == 200
    rec = FeedbackClassificationRecord.model_validate(res.json())
    assert rec.feedback_id == fb_id
    assert rec.overall_sentiment == "positive"
    assert rec.sentiment_intensity == "high"
    assert rec.customer_intent == "praise"
    assert rec.identified_product == "Analytics Dashboard"
    assert rec.identified_feature == "Performance"
    assert rec.confidence_score == 0.92
    assert rec.provider == "gemini"
    assert rec.model == "gemini-2.5-flash"


def test_get_latest_classification_not_classified():
    """GET /api/feedback/{id}/classification returns 404 when record has no classification."""
    fb_id = create_sample_feedback()
    res = client.get(f"{settings.API_V1_PREFIX}/feedback/{fb_id}/classification")
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "NOT_FOUND"


def test_get_latest_classification_feedback_not_found():
    """GET /api/feedback/{id}/classification returns 404 when feedback does not exist."""
    res = client.get(f"{settings.API_V1_PREFIX}/feedback/{uuid.uuid4()}/classification")
    assert res.status_code == 404


def test_get_latest_classification_deterministic_ordering():
    """GET /api/feedback/{id}/classification retrieves the newest record by classified_at."""
    fb_id = create_sample_feedback()
    db = next(app.dependency_overrides[get_db]())
    now = datetime.now(timezone.utc)

    # Insert older classification (v0.9.0)
    old_c = FeedbackClassification(
        classification_id=uuid.uuid4(),
        feedback_id=fb_id,
        classification_version="v0.9.0",
        status="classified",
        overall_sentiment="negative",
        sentiment_score=-0.8,
        sentiment_intensity="high",
        customer_intent="complaint",
        confidence_score=0.85,
        needs_review=False,
        classified_at=now - timedelta(days=2),
    )
    # Insert newer classification (v1.0.0)
    new_c = FeedbackClassification(
        classification_id=uuid.uuid4(),
        feedback_id=fb_id,
        classification_version="v1.0.0",
        status="classified",
        overall_sentiment="positive",
        sentiment_score=0.9,
        sentiment_intensity="high",
        customer_intent="praise",
        confidence_score=0.95,
        needs_review=False,
        classified_at=now,
    )
    db.add_all([old_c, new_c])
    db.commit()

    res = client.get(f"{settings.API_V1_PREFIX}/feedback/{fb_id}/classification")
    assert res.status_code == 200
    rec = FeedbackClassificationRecord.model_validate(res.json())
    assert rec.classification_version == "v1.0.0"
    assert rec.overall_sentiment == "positive"


# ==============================================================================
# 4. Summary & Aggregate Analytics (GET /api/classifications/summary)
# ==============================================================================


def test_summary_empty_database():
    """GET /api/classifications/summary on empty database returns zeroed metrics."""
    res = client.get(f"{settings.API_V1_PREFIX}/classifications/summary")
    assert res.status_code == 200
    summary = ClassificationSummaryResponse.model_validate(res.json())
    assert summary.total_classifications == 0
    assert summary.latest_classified_count == 0
    assert summary.needs_review_count == 0
    assert summary.sentiment_distribution == {"positive": 0, "negative": 0, "neutral": 0, "mixed": 0}
    assert summary.aspect_sentiment_distribution == {"positive": 0, "negative": 0, "neutral": 0, "mixed": 0}


def test_summary_aggregations_and_historical_deduplication():
    """GET /api/classifications/summary distinguishes historical runs and prevents double-counting."""
    db = next(app.dependency_overrides[get_db]())
    now = datetime.now(timezone.utc)

    # Record 1: has 2 historical classifications (complaint -> praise)
    fb1 = create_sample_feedback(text="fb 1", product="Analytics")
    c1_old = FeedbackClassification(
        classification_id=uuid.uuid4(),
        feedback_id=fb1,
        classification_version="v0.8.0",
        status="classified",
        overall_sentiment="negative",
        sentiment_score=-0.7,
        sentiment_intensity="high",
        customer_intent="complaint",
        confidence_score=0.8,
        needs_review=False,
        aspects=[{"aspect": "speed", "sentiment": "negative"}],
        classified_at=now - timedelta(days=5),
    )
    c1_latest = FeedbackClassification(
        classification_id=uuid.uuid4(),
        feedback_id=fb1,
        classification_version="v1.0.0",
        status="classified",
        overall_sentiment="positive",
        sentiment_score=0.8,
        sentiment_intensity="high",
        customer_intent="praise",
        confidence_score=0.9,
        needs_review=False,
        aspects=[{"aspect": "speed", "sentiment": "positive"}],
        classified_at=now - timedelta(days=1),
    )

    # Record 2: has 1 classification (needs review, mixed sentiment)
    fb2 = create_sample_feedback(text="fb 2", product="Analytics")
    c2 = FeedbackClassification(
        classification_id=uuid.uuid4(),
        feedback_id=fb2,
        classification_version="v1.0.0",
        status="classified",
        overall_sentiment="mixed",
        sentiment_score=0.1,
        sentiment_intensity="medium",
        customer_intent="suggestion",
        confidence_score=0.6,
        needs_review=True,
        review_reason="mixed_signals",
        aspects=[
            {"aspect": "ui", "sentiment": "positive"},
            {"aspect": "price", "sentiment": "negative"},
        ],
        classified_at=now,
    )

    db.add_all([c1_old, c1_latest, c2])
    db.commit()

    res = client.get(f"{settings.API_V1_PREFIX}/classifications/summary")
    assert res.status_code == 200
    summary = ClassificationSummaryResponse.model_validate(res.json())

    # Total historical classifications = 3 (c1_old + c1_latest + c2)
    assert summary.total_classifications == 3
    # Latest classified items count = 2 (fb1 and fb2)
    assert summary.latest_classified_count == 2
    # Latest sentiment: 1 positive (fb1 latest), 1 mixed (fb2), 0 negative (historical c1_old excluded)
    assert summary.sentiment_distribution["positive"] == 1
    assert summary.sentiment_distribution["mixed"] == 1
    assert summary.sentiment_distribution["negative"] == 0
    # Latest customer intent: 1 praise, 1 suggestion (c1_old complaint excluded)
    assert summary.intent_distribution["praise"] == 1
    assert summary.intent_distribution["suggestion"] == 1
    assert summary.intent_distribution["complaint"] == 0
    # Needs review: 1
    assert summary.needs_review_count == 1
    # Aspect sentiments aggregated from latest:
    # fb1 latest: 1 positive ("speed")
    # fb2: 1 positive ("ui"), 1 negative ("price")
    assert summary.aspect_sentiment_distribution["positive"] == 2
    assert summary.aspect_sentiment_distribution["negative"] == 1


def test_summary_product_and_date_filtering():
    """GET /api/classifications/summary filters correctly by product and date range."""
    db = next(app.dependency_overrides[get_db]())
    now = datetime.now(timezone.utc)

    fb_product_a = create_sample_feedback(product="ProductA")
    fb_product_b = create_sample_feedback(product="ProductB")

    c_a = FeedbackClassification(
        classification_id=uuid.uuid4(),
        feedback_id=fb_product_a,
        classification_version="v1.0.0",
        status="classified",
        overall_sentiment="positive",
        sentiment_score=0.9,
        sentiment_intensity="high",
        customer_intent="praise",
        confidence_score=0.9,
        needs_review=False,
        classified_at=now - timedelta(days=10),
    )
    c_b = FeedbackClassification(
        classification_id=uuid.uuid4(),
        feedback_id=fb_product_b,
        classification_version="v1.0.0",
        status="classified",
        overall_sentiment="negative",
        sentiment_score=-0.8,
        sentiment_intensity="high",
        customer_intent="complaint",
        confidence_score=0.9,
        needs_review=False,
        classified_at=now - timedelta(days=1),
    )
    db.add_all([c_a, c_b])
    db.commit()

    # Product filter for ProductA
    res_a = client.get(f"{settings.API_V1_PREFIX}/classifications/summary?product=ProductA")
    assert res_a.status_code == 200
    summary_a = ClassificationSummaryResponse.model_validate(res_a.json())
    assert summary_a.total_classifications == 1
    assert summary_a.latest_classified_count == 1
    assert summary_a.sentiment_distribution["positive"] == 1
    assert summary_a.sentiment_distribution["negative"] == 0

    # Date filter: only classifications within last 5 days
    start_5d = (now - timedelta(days=5)).isoformat()
    res_date = client.get(f"{settings.API_V1_PREFIX}/classifications/summary?start_date={start_5d}")
    assert res_date.status_code == 200
    summary_date = ClassificationSummaryResponse.model_validate(res_date.json())
    assert summary_date.total_classifications == 1
    assert summary_date.sentiment_distribution["negative"] == 1


def test_summary_invalid_date_range():
    """GET /api/classifications/summary returns 400 when start_date > end_date."""
    now = datetime.now(timezone.utc)
    start = now.isoformat()
    end = (now - timedelta(days=5)).isoformat()

    res = client.get(f"{settings.API_V1_PREFIX}/classifications/summary?start_date={start}&end_date={end}")
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "INVALID_DATE_RANGE"


# ==============================================================================
# 5. Error Sanitization & Transaction Rollback
# ==============================================================================


def test_provider_failure_sanitization_and_rollback():
    """Provider network failure sanitizes message and rolls back database changes."""
    fb_id = create_sample_feedback()

    # Simulate provider throwing an exception containing sensitive internal info
    with patch("app.integrations.ai.manager.AIProviderManager.generate", new_callable=AsyncMock) as mock_gen:
        mock_gen.side_effect = RuntimeError("OpenRouter connection failure: upstream server 503")

        # In batch classification, per-record failure is isolated safely
        res_batch = client.post(
            f"{settings.API_V1_PREFIX}/feedback/classify",
            json={"feedback_ids": [str(fb_id)]},
        )
        assert res_batch.status_code == 200
        batch_data = res_batch.json()
        assert batch_data["failed_count"] == 1
        assert "OpenRouter connection failure" in batch_data["errors"][0]["error"]

        # In individual classification, generic 500 handler sanitizes raw message
        res_single = client.post(f"{settings.API_V1_PREFIX}/feedback/{fb_id}/classify")
        assert res_single.status_code == 500
        single_data = res_single.json()
        # Verify no credentials leaked and generic safe message returned
        assert "An unexpected error occurred" in single_data["error"]["message"]

        # Verify nothing persisted to database
        db = next(app.dependency_overrides[get_db]())
        assert db.execute(select(FeedbackClassification)).scalars().all() == []
        assert db.execute(select(SentimentHistory)).scalars().all() == []


# ==============================================================================
# 6. Part 6 Step 4 Audit Corrections Verification
# ==============================================================================


def test_repeated_reprocessing_preserves_execution_history():
    """Verify repeated reprocessing under same algorithm version creates run 1, 2, 3 without overwrites."""
    fb_id = create_sample_feedback(text="The performance is consistently blazing fast.")

    mock1 = build_mock_ai_response(sentiment=OverallSentiment.POSITIVE, score=0.80)
    mock2 = build_mock_ai_response(sentiment=OverallSentiment.NEUTRAL, score=0.00)
    mock3 = build_mock_ai_response(sentiment=OverallSentiment.MIXED, score=0.10)

    with patch("app.integrations.ai.manager.AIProviderManager.generate", new_callable=AsyncMock) as mock_gen:
        # Run 1
        mock_gen.return_value = mock1
        r1 = client.post(f"{settings.API_V1_PREFIX}/feedback/{fb_id}/classify")
        assert r1.status_code == 200
        assert r1.json()["run_number"] == 1
        assert r1.json()["sentiment_score"] == 0.80
        id1 = r1.json()["classification_id"]

        # Run 2
        mock_gen.return_value = mock2
        r2 = client.post(f"{settings.API_V1_PREFIX}/feedback/{fb_id}/classify?reprocess=true")
        assert r2.status_code == 200
        assert r2.json()["run_number"] == 2
        assert r2.json()["sentiment_score"] == 0.00
        id2 = r2.json()["classification_id"]
        assert id2 != id1

        # Run 3
        mock_gen.return_value = mock3
        r3 = client.post(f"{settings.API_V1_PREFIX}/feedback/{fb_id}/classify?reprocess=true")
        assert r3.status_code == 200
        assert r3.json()["run_number"] == 3
        assert r3.json()["sentiment_score"] == 0.10
        id3 = r3.json()["classification_id"]
        assert id3 != id2 and id3 != id1

    # Verify all 3 runs exist unchanged in the database
    db = next(app.dependency_overrides[get_db]())
    records = db.execute(
        select(FeedbackClassification)
        .where(FeedbackClassification.feedback_id == fb_id)
        .order_by(FeedbackClassification.run_number)
    ).scalars().all()

    assert len(records) == 3
    assert records[0].run_number == 1
    assert records[0].sentiment_score == 0.80
    assert records[0].classification_id == uuid.UUID(id1)

    assert records[1].run_number == 2
    assert records[1].sentiment_score == 0.00
    assert records[1].classification_id == uuid.UUID(id2)

    assert records[2].run_number == 3
    assert records[2].sentiment_score == 0.10
    assert records[2].classification_id == uuid.UUID(id3)

    # Latest retrieval returns run 3 (most recent valid classification)
    r_latest = client.get(f"{settings.API_V1_PREFIX}/feedback/{fb_id}/classification")
    assert r_latest.status_code == 200
    assert r_latest.json()["run_number"] == 3
    assert r_latest.json()["sentiment_score"] == 0.10


def test_failed_attempt_does_not_hide_previous_valid_classification():
    """Verify that a subsequent failed attempt does not hide a prior valid classification in retrieval or summary."""
    fb_id = create_sample_feedback(text="The search bar works wonderfully.", product="Catalog")
    db = next(app.dependency_overrides[get_db]())
    now = datetime.now(timezone.utc)

    # 1. Day 1: Valid successful classification (status='classified')
    valid_c = FeedbackClassification(
        classification_id=uuid.uuid4(),
        feedback_id=fb_id,
        classification_version="v1.0.0",
        run_number=1,
        status="classified",
        overall_sentiment="positive",
        sentiment_score=0.92,
        sentiment_intensity="high",
        customer_intent="praise",
        identified_product="Catalog",
        topics=[{"label": "search", "confidence": 0.95}],
        aspects=[{"aspect": "search bar", "sentiment": "positive", "sentiment_score": 0.9, "confidence": 0.95, "evidence": "works wonderfully"}],
        confidence_score=0.95,
        needs_review=False,
        classified_at=now - timedelta(days=2),
    )
    db.add(valid_c)
    db.commit()

    # 2. Day 2: Failed classification attempt (status='failed')
    failed_c = FeedbackClassification(
        classification_id=uuid.uuid4(),
        feedback_id=fb_id,
        classification_version="v1.0.0",
        run_number=2,
        status="failed",
        overall_sentiment="neutral",
        sentiment_score=0.0,
        sentiment_intensity="low",
        customer_intent="other",
        identified_product="Catalog",
        confidence_score=0.0,
        needs_review=False,
        error_message="Provider timeout after 30 seconds",
        classified_at=now,
    )
    db.add(failed_c)
    db.commit()

    # A. GET /api/feedback/{id}/classification MUST return the valid classification (Day 1), NOT the failed attempt
    res = client.get(f"{settings.API_V1_PREFIX}/feedback/{fb_id}/classification")
    assert res.status_code == 200
    rec = FeedbackClassificationRecord.model_validate(res.json())
    assert rec.status == "classified"
    assert rec.run_number == 1
    assert rec.overall_sentiment == "positive"
    assert rec.sentiment_score == 0.92
    assert rec.customer_intent == "praise"

    # B. GET /api/classifications/summary:
    # - latest_classified_count == 1 (from valid_c)
    # - sentiment_distribution has 1 positive (not hidden by failed attempt)
    # - intent_distribution has 1 praise
    # - aspect_sentiment_distribution has 1 positive
    # - status_distribution tracks the latest operational attempt, visibly exposing "failed": 1
    # - total_classifications == 2 (both attempts preserved in historical total)
    res_summary = client.get(f"{settings.API_V1_PREFIX}/classifications/summary")
    assert res_summary.status_code == 200
    summary = ClassificationSummaryResponse.model_validate(res_summary.json())

    assert summary.total_classifications == 2
    assert summary.latest_classified_count == 1
    assert summary.sentiment_distribution["positive"] == 1
    assert summary.sentiment_distribution["neutral"] == 0
    assert summary.intent_distribution["praise"] == 1
    assert summary.aspect_sentiment_distribution["positive"] == 1

    # Failed attempt is NOT silently discarded; operational status distribution tracks it
    assert summary.status_distribution["failed"] == 1
    assert summary.status_distribution["classified"] == 0
