"""Tests for FeedbackClassificationService & Dual Persistence (Part 6 Step 3).

Validates end-to-end classification workflow with mocked AI providers:
- Valid classification across sentiments and customer intents
- Evidence grounding verification against source text
- Low-confidence and mixed-signals review policies
- Dual persistence to FeedbackClassification and SentimentHistory in one atomic transaction
- Idempotency, reclassification, and unique versioning enforcement
- Batch processing with per-record failure isolation
- Quality gatekeeping (rejected quality states, pending cleaning, missing text)
- Error handling and provider failover integration
"""

from datetime import datetime, timezone
import json
from typing import Any, Dict, Optional
import uuid
import httpx
import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

from app.core.exceptions import AppException, EntityNotFoundError
from app.db.base import Base
from app.integrations.ai.gemini import GeminiProvider
from app.integrations.ai.manager import AIProviderManager
from app.integrations.ai.openrouter import OpenRouterProvider
from app.models.classification import FeedbackClassification
from app.models.feedback import Feedback
from app.models.sentiment import SentimentHistory
from app.schemas.classification import (
    AspectSentiment,
    CustomerIntent,
    OverallSentiment,
)
from app.services.feedback_classification import (
    CURRENT_CLASSIFICATION_VERSION,
    FeedbackClassificationService,
    verify_evidence_grounding,
)


# --- Helper Fixtures & Mocks ---


@pytest.fixture
def db_session():
    """Isolated in-memory SQLite database session with foreign keys enabled."""
    engine = create_engine("sqlite:///:memory:", echo=False)

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def make_feedback(
    session: Session,
    text: str = "The new dashboard is super fast and clean!",
    cleaned_text: Optional[str] = None,
    quality_status: str = "clean",
    product: str = "Analytics Dashboard",
    feature: Optional[str] = "UI",
    deleted: bool = False,
) -> Feedback:
    """Helper to persist a test feedback item."""
    actual_cleaned = cleaned_text if cleaned_text is not None else (text if quality_status != "pending" else None)
    fb = Feedback(
        feedback_id=uuid.uuid4(),
        source="csv",
        feedback_text=text,
        cleaned_feedback_text=actual_cleaned,
        quality_status=quality_status,
        quality_score=95.0,
        product=product,
        feature=feature,
        timestamp=datetime.now(timezone.utc),
        deleted_at=datetime.now(timezone.utc) if deleted else None,
    )
    session.add(fb)
    session.commit()
    return fb


def make_mock_ai_manager(llm_data: Dict[str, Any], provider_name: str = "gemini") -> AIProviderManager:
    """Create an AIProviderManager with a mocked Gemini provider returning custom classification JSON."""
    llm_json_str = json.dumps(llm_data)

    def mock_handler(req: httpx.Request):
        return httpx.Response(
            status_code=200,
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [{"text": llm_json_str}],
                            "role": "model",
                        },
                        "finishReason": "STOP",
                    }
                ],
                "usageMetadata": {
                    "promptTokenCount": 110,
                    "candidatesTokenCount": 65,
                    "totalTokenCount": 175,
                },
            },
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))
    provider = GeminiProvider(api_key="mock-key", client=client)
    return AIProviderManager(providers={provider_name: provider}, priority_order=[provider_name])


# ============================================================================
# 1. Grounding Verification Unit Tests
# ============================================================================


def test_verify_evidence_grounding_exact_and_normalized():
    """Verify evidence substring detection handles exact match, case, and spacing."""
    source = "The application runs smoothly but the CSV export is extremely slow."

    assert verify_evidence_grounding("runs smoothly", source) is True
    assert verify_evidence_grounding("RUNS   SMOOTHLY", source) is True
    assert verify_evidence_grounding("extremely slow", source) is True
    assert verify_evidence_grounding("completely broken and crashed", source) is False
    assert verify_evidence_grounding("", source) is False
    assert verify_evidence_grounding("runs smoothly", "") is False


# ============================================================================
# 2. Service Functional & Dual Persistence Tests
# ============================================================================


@pytest.mark.anyio
async def test_classify_single_record_success_and_dual_persistence(db_session):
    """Verify classification creates both FeedbackClassification and SentimentHistory atomically."""
    fb = make_feedback(db_session, text="The dashboard loads quickly and looks great!")

    mock_data = {
        "overall_sentiment": "positive",
        "sentiment_score": 0.88,
        "sentiment_intensity": "high",
        "customer_intent": "praise",
        "product": "Analytics Dashboard",
        "feature": "UI",
        "topics": [{"label": "performance", "confidence": 0.95}],
        "aspects": [
            {
                "aspect": "dashboard speed",
                "sentiment": "positive",
                "sentiment_score": 0.90,
                "confidence": 0.94,
                "evidence": "loads quickly",
            }
        ],
        "pain_points": [],
        "keywords": ["dashboard", "loads quickly"],
        "confidence_score": 0.92,
        "needs_review": False,
    }
    ai_mgr = make_mock_ai_manager(mock_data)

    rec = await FeedbackClassificationService.classify_single_record(
        session=db_session,
        feedback_id=fb.feedback_id,
        provider_manager=ai_mgr,
    )

    # 1. Check FeedbackClassification record
    assert rec.overall_sentiment == "positive"
    assert rec.sentiment_score == 0.88
    assert rec.customer_intent == "praise"
    assert rec.provider == "gemini"
    assert rec.needs_review is False
    assert rec.topics[0]["label"] == "performance"
    assert rec.aspects[0]["aspect"] == "dashboard speed"

    # 2. Check database persistence for FeedbackClassification
    stored_fc = db_session.execute(
        select(FeedbackClassification).where(FeedbackClassification.feedback_id == fb.feedback_id)
    ).scalar_one()
    assert stored_fc.classification_version == CURRENT_CLASSIFICATION_VERSION
    assert stored_fc.token_usage["total_tokens"] == 175

    # 3. Check database persistence for SentimentHistory
    stored_sh = db_session.execute(
        select(SentimentHistory).where(SentimentHistory.feedback_id == fb.feedback_id)
    ).scalar_one()
    assert stored_sh.sentiment_label == "positive"
    assert stored_sh.sentiment_score == 0.88
    assert stored_sh.confidence_score == 0.92
    assert stored_sh.theme_id is None


@pytest.mark.anyio
async def test_classify_evidence_grounding_failure_flags_review(db_session):
    """Verify that fabricated / ungrounded aspect evidence triggers needs_review."""
    fb = make_feedback(db_session, text="The dashboard is okay.")

    # Model fabricates evidence not present in text
    mock_data = {
        "overall_sentiment": "positive",
        "sentiment_score": 0.80,
        "customer_intent": "praise",
        "topics": [{"label": "performance", "confidence": 0.90}],
        "aspects": [
            {
                "aspect": "customer support",
                "sentiment": "positive",
                "sentiment_score": 0.85,
                "confidence": 0.90,
                "evidence": "Customer support agent Alex was amazing and fixed my ticket",  # Fabricated!
            }
        ],
        "keywords": ["dashboard"],
        "confidence_score": 0.90,
        "needs_review": False,
    }
    ai_mgr = make_mock_ai_manager(mock_data)

    rec = await FeedbackClassificationService.classify_single_record(
        session=db_session,
        feedback_id=fb.feedback_id,
        provider_manager=ai_mgr,
    )

    # Must be flagged for human review due to ungrounded evidence
    assert rec.needs_review is True
    assert "ungrounded_evidence" in rec.review_reason
    assert rec.confidence_score <= 0.50  # Confidence lowered


@pytest.mark.anyio
async def test_classify_low_confidence_and_mixed_sentiment_policy(db_session):
    """Verify low-confidence and mixed sentiment trigger needs_review."""
    fb = make_feedback(db_session, text="I love the interface but the reports are totally broken.")

    mock_data = {
        "overall_sentiment": "mixed",
        "sentiment_score": 0.05,
        "sentiment_intensity": "medium",
        "customer_intent": "complaint",
        "topics": [{"label": "reporting", "confidence": 0.65}],
        "aspects": [
            {
                "aspect": "interface",
                "sentiment": "positive",
                "sentiment_score": 0.8,
                "confidence": 0.85,
                "evidence": "love the interface",
            },
            {
                "aspect": "reports",
                "sentiment": "negative",
                "sentiment_score": -0.9,
                "confidence": 0.85,
                "evidence": "reports are totally broken",
            },
        ],
        "pain_points": ["Broken reports"],
        "keywords": ["interface", "broken reports"],
        "confidence_score": 0.65,  # Below default 0.70 threshold
        "needs_review": False,
    }
    ai_mgr = make_mock_ai_manager(mock_data)

    rec = await FeedbackClassificationService.classify_single_record(
        session=db_session,
        feedback_id=fb.feedback_id,
        provider_manager=ai_mgr,
        low_confidence_threshold=0.70,
    )

    assert rec.needs_review is True
    assert "mixed_signals" in rec.review_reason or "low_confidence" in rec.review_reason


@pytest.mark.anyio
async def test_idempotency_and_reclassification(db_session):
    """Verify idempotent response when already classified, and in-place update on reprocess."""
    fb = make_feedback(db_session, text="Everything is running smoothly.")

    mock_data_v1 = {
        "overall_sentiment": "positive",
        "sentiment_score": 0.80,
        "customer_intent": "praise",
        "confidence_score": 0.90,
    }
    ai_mgr = make_mock_ai_manager(mock_data_v1)

    # First run
    rec1 = await FeedbackClassificationService.classify_single_record(
        session=db_session,
        feedback_id=fb.feedback_id,
        provider_manager=ai_mgr,
    )
    assert rec1.sentiment_score == 0.80

    # Second run without reprocess: returns existing without calling AI
    fail_mgr = AIProviderManager(providers={}, priority_order=[])  # Empty provider manager
    rec2 = await FeedbackClassificationService.classify_single_record(
        session=db_session,
        feedback_id=fb.feedback_id,
        provider_manager=fail_mgr,
        reprocess=False,
    )
    assert rec2.classification_id == rec1.classification_id

    # Third run with reprocess=True: preserves run 1 and creates run 2 without overwrite
    mock_data_v2 = {
        "overall_sentiment": "positive",
        "sentiment_score": 0.95,  # Updated score
        "customer_intent": "praise",
        "confidence_score": 0.98,
    }
    ai_mgr2 = make_mock_ai_manager(mock_data_v2)
    rec3 = await FeedbackClassificationService.classify_single_record(
        session=db_session,
        feedback_id=fb.feedback_id,
        provider_manager=ai_mgr2,
        reprocess=True,
    )
    assert rec3.classification_id != rec1.classification_id
    assert rec3.run_number == 2
    assert rec3.sentiment_score == 0.95

    # Verify original run 1 remains completely unchanged in the database
    run1_stored = db_session.get(FeedbackClassification, rec1.classification_id)
    assert run1_stored is not None
    assert run1_stored.run_number == 1
    assert run1_stored.sentiment_score == 0.80

    # Verify run 2 is stored in the database
    run2_stored = db_session.get(FeedbackClassification, rec3.classification_id)
    assert run2_stored is not None
    assert run2_stored.run_number == 2
    assert run2_stored.sentiment_score == 0.95


@pytest.mark.anyio
async def test_quality_gatekeeping_rejected_and_pending_records(db_session):
    """Verify gatekeeper rejects rejected feedback and deterministically cleans pending feedback."""
    # Case A: Rejected quality record
    fb_rejected = make_feedback(
        db_session,
        text="buy cheap meds at spam.com",
        quality_status="rejected",
    )
    with pytest.raises(AppException) as exc:
        await FeedbackClassificationService.classify_single_record(
            session=db_session,
            feedback_id=fb_rejected.feedback_id,
        )
    assert "quality_status='rejected'" in str(exc.value)

    # Case B: Pending cleaning feedback with cleanable text
    fb_pending = make_feedback(
        db_session,
        text="Great application, contact me at user@test.com",
        cleaned_text=None,
        quality_status="pending",
    )
    mock_data = {
        "overall_sentiment": "positive",
        "sentiment_score": 0.85,
        "customer_intent": "praise",
        "confidence_score": 0.90,
    }
    ai_mgr = make_mock_ai_manager(mock_data)

    rec = await FeedbackClassificationService.classify_single_record(
        session=db_session,
        feedback_id=fb_pending.feedback_id,
        provider_manager=ai_mgr,
    )
    assert rec.overall_sentiment == "positive"
    # Verify feedback was cleaned
    refreshed_fb = db_session.get(Feedback, fb_pending.feedback_id)
    assert refreshed_fb.cleaned_feedback_text is not None
    assert "[EMAIL]" in refreshed_fb.cleaned_feedback_text


@pytest.mark.anyio
async def test_soft_deleted_feedback_rejected(db_session):
    """Verify soft-deleted feedback cannot be classified."""
    fb_deleted = make_feedback(db_session, text="Active feedback", deleted=True)
    with pytest.raises(AppException) as exc:
        await FeedbackClassificationService.classify_single_record(
            session=db_session,
            feedback_id=fb_deleted.feedback_id,
        )
    assert "soft-deleted" in str(exc.value)


@pytest.mark.anyio
async def test_unknown_feedback_id_raises_not_found(db_session):
    """Verify unknown UUID raises EntityNotFoundError."""
    random_id = uuid.uuid4()
    with pytest.raises(EntityNotFoundError):
        await FeedbackClassificationService.classify_single_record(
            session=db_session,
            feedback_id=random_id,
        )


@pytest.mark.anyio
async def test_provider_failover_during_classification(db_session):
    """Verify that if Gemini fails (e.g. quota exhausted), OpenRouter succeeds seamlessly."""
    fb = make_feedback(db_session, text="The billing system works properly.")

    # Gemini returns 429 daily quota limit
    gemini_client = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda req: httpx.Response(
                429,
                json={
                    "error": {
                        "code": 429,
                        "message": "Daily quota limit reached",
                        "status": "RESOURCE_EXHAUSTED",
                        "details": [{"reason": "QUOTA_EXCEEDED"}],
                    }
                },
            )
        )
    )

    # OpenRouter returns valid classification
    openrouter_json = json.dumps({
        "overall_sentiment": "positive",
        "sentiment_score": 0.75,
        "customer_intent": "praise",
        "confidence_score": 0.88,
    })
    openrouter_client = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda req: httpx.Response(
                200,
                json={
                    "id": "gen-openrouter-123",
                    "model": "google/gemini-2.0-flash-001",
                    "choices": [{"message": {"role": "assistant", "content": openrouter_json}}],
                    "usage": {"prompt_tokens": 50, "completion_tokens": 25, "total_tokens": 75},
                },
            )
        )
    )

    gemini_prov = GeminiProvider(api_key="key1", client=gemini_client)
    openrouter_prov = OpenRouterProvider(api_key="key2", client=openrouter_client)

    manager = AIProviderManager(
        providers={"gemini": gemini_prov, "openrouter": openrouter_prov},
        priority_order=["gemini", "openrouter"],
    )

    rec = await FeedbackClassificationService.classify_single_record(
        session=db_session,
        feedback_id=fb.feedback_id,
        provider_manager=manager,
    )

    assert rec.provider == "openrouter"
    assert rec.sentiment_score == 0.75


@pytest.mark.anyio
async def test_batch_classification_record_level_isolation(db_session):
    """Verify that failure on one record in a batch does not abort other valid records."""
    fb_valid_1 = make_feedback(db_session, text="Feature A is awesome!")
    fb_rejected = make_feedback(db_session, text="Spam link", quality_status="rejected")
    fb_valid_2 = make_feedback(db_session, text="Feature B is also great!")

    mock_data = {
        "overall_sentiment": "positive",
        "sentiment_score": 0.90,
        "customer_intent": "praise",
        "confidence_score": 0.92,
    }
    ai_mgr = make_mock_ai_manager(mock_data)

    batch_resp = await FeedbackClassificationService.classify_batch(
        session=db_session,
        feedback_ids=[fb_valid_1.feedback_id, fb_rejected.feedback_id, fb_valid_2.feedback_id],
        provider_manager=ai_mgr,
    )

    assert batch_resp.total_requested == 3
    assert batch_resp.successful_count == 2
    assert batch_resp.failed_count == 1
    assert len(batch_resp.results) == 2
    assert len(batch_resp.errors) == 1
    assert batch_resp.errors[0].feedback_id == fb_rejected.feedback_id
    assert "quality_status='rejected'" in batch_resp.errors[0].error
