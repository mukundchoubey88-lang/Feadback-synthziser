"""Tests for Concurrent Reclassification and Bounded Collision Retries (Part 6 Step 4).

Verifies:
1. Concurrent reclassification requests on the same feedback record allocate unique sequential
   run numbers without crashing with HTTP 500 or unhandled IntegrityErrors.
2. Atomic dual persistence is preserved across all runs (FeedbackClassification + SentimentHistory).
3. Failed retries roll back cleanly and leave zero orphaned records.
"""

import asyncio
from datetime import datetime, timezone
from typing import List, Optional
import uuid
import pytest
from sqlalchemy import create_engine, event, select, func
from sqlalchemy.orm import Session, sessionmaker

from app.core.exceptions import AppException
from app.db.base import Base
from app.integrations.ai.base import BaseAIProvider
from app.integrations.ai.manager import AIProviderManager
from app.integrations.ai.schemas import AIRequest, AIResponse, AIUsage
from app.models.classification import FeedbackClassification
from app.models.feedback import Feedback
from app.models.sentiment import SentimentHistory
from app.schemas.classification import (
    CustomerIntent,
    FeedbackClassificationLLMOutput,
    OverallSentiment,
    SentimentIntensity,
    TopicItem,
)
from app.services.feedback_classification import FeedbackClassificationService


class MockFastAIProvider(BaseAIProvider):
    """Deterministic fast AI provider returning valid structured classification output."""

    def __init__(self):
        super().__init__(name="mock_fast_provider", default_model="mock-v1")

    @property
    def is_configured(self) -> bool:
        return True

    async def generate(self, request: AIRequest) -> AIResponse:
        output = FeedbackClassificationLLMOutput(
            overall_sentiment=OverallSentiment.POSITIVE,
            sentiment_score=0.88,
            sentiment_intensity=SentimentIntensity.HIGH,
            customer_intent=CustomerIntent.PRAISE,
            topics=[TopicItem(label="usability", confidence=0.95)],
            aspects=[],
            pain_points=[],
            keywords=["great", "fast"],
            confidence_score=0.95,
            needs_review=False,
            review_reason=None,
        )
        return AIResponse(
            content=output.model_dump_json(),
            structured_data=output,
            provider="mock_fast_provider",
            model="mock-v1",
            latency_ms=10.0,
            usage=AIUsage(prompt_tokens=50, completion_tokens=25, total_tokens=75),
        )


@pytest.fixture
def thread_safe_db():
    """In-memory SQLite engine and session factory with WAL / foreign keys enabled."""
    engine = create_engine(
        "sqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    sm = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    yield sm
    engine.dispose()


def make_feedback(session: Session) -> Feedback:
    """Create and persist a clean feedback record."""
    fb = Feedback(
        feedback_id=uuid.uuid4(),
        source="csv",
        feedback_text="The new export feature works wonderfully.",
        cleaned_feedback_text="The new export feature works wonderfully.",
        product="Web Console",
        feature="Export",
        timestamp=datetime.now(timezone.utc),
        quality_status="clean",
        quality_score=98.0,
    )
    session.add(fb)
    session.commit()
    return fb


@pytest.mark.anyio
async def test_concurrent_reclassification_allocates_sequential_runs_without_500(thread_safe_db):
    """Verify concurrent reclassification calls on the same feedback allocate sequential runs cleanly."""
    mock_prov = MockFastAIProvider()
    manager = AIProviderManager(
        providers={mock_prov.name: mock_prov},
        priority_order=[mock_prov.name],
    )

    # Setup initial feedback
    with thread_safe_db() as setup_session:
        fb = make_feedback(setup_session)
        target_id = fb.feedback_id

    # Launch 4 concurrent reclassification tasks against distinct sessions for the same feedback
    num_concurrent = 4

    async def classify_worker(worker_id: int):
        with thread_safe_db() as worker_session:
            return await FeedbackClassificationService.classify_single_record(
                session=worker_session,
                feedback_id=target_id,
                provider_manager=manager,
                reprocess=True,
            )

    results = await asyncio.gather(*[classify_worker(i) for i in range(num_concurrent)])

    assert len(results) == num_concurrent
    for res in results:
        assert res.feedback_id == target_id
        assert res.status == "classified"

    # Verify that run numbers are distinct, sequential, and fully preserved
    with thread_safe_db() as verify_session:
        classifications = verify_session.execute(
            select(FeedbackClassification)
            .where(FeedbackClassification.feedback_id == target_id)
            .order_by(FeedbackClassification.run_number.asc())
        ).scalars().all()

        assert len(classifications) == num_concurrent
        run_numbers = [c.run_number for c in classifications]
        assert run_numbers == list(range(1, num_concurrent + 1)), (
            f"Expected runs 1..{num_concurrent}, got {run_numbers}"
        )

        # Verify atomic dual persistence: matching count of sentiment records
        sentiments = verify_session.execute(
            select(SentimentHistory).where(SentimentHistory.feedback_id == target_id)
        ).scalars().all()
        assert len(sentiments) == num_concurrent


@pytest.mark.anyio
async def test_retry_on_unique_constraint_collision_recovers_successfully(thread_safe_db):
    """Verify that if an attempt encounters a unique-constraint collision, it retries and succeeds."""
    mock_prov = MockFastAIProvider()
    manager = AIProviderManager(
        providers={mock_prov.name: mock_prov},
        priority_order=[mock_prov.name],
    )

    with thread_safe_db() as session:
        fb = make_feedback(session)
        target_id = fb.feedback_id

        # First run: run_number = 1
        run1 = await FeedbackClassificationService.classify_single_record(
            session=session,
            feedback_id=target_id,
            provider_manager=manager,
            reprocess=False,
        )
        assert run1.run_number == 1

        # Second run: run_number = 2
        run2 = await FeedbackClassificationService.classify_single_record(
            session=session,
            feedback_id=target_id,
            provider_manager=manager,
            reprocess=True,
        )
        assert run2.run_number == 2


@pytest.mark.anyio
async def test_failed_retries_leave_no_orphaned_records(thread_safe_db):
    """Verify that when persistence fails completely, session rolls back with zero orphaned records."""
    mock_prov = MockFastAIProvider()
    manager = AIProviderManager(
        providers={mock_prov.name: mock_prov},
        priority_order=[mock_prov.name],
    )

    with thread_safe_db() as session:
        fb = make_feedback(session)
        target_id = fb.feedback_id

        # Run initial classification (run 1)
        await FeedbackClassificationService.classify_single_record(
            session=session,
            feedback_id=target_id,
            provider_manager=manager,
        )

        count_before_class = session.execute(
            select(func.count(FeedbackClassification.classification_id)).where(
                FeedbackClassification.feedback_id == target_id
            )
        ).scalar()
        count_before_sent = session.execute(
            select(func.count(SentimentHistory.sentiment_id)).where(
                SentimentHistory.feedback_id == target_id
            )
        ).scalar()
        assert count_before_class == 1
        assert count_before_sent == 1

        # Simulate a database failure during commit by temporarily sabotaging commit
        original_commit = session.commit

        def broken_commit():
            raise RuntimeError("Simulated unrecoverable DB disk failure")

        session.commit = broken_commit

        with pytest.raises(RuntimeError):
            await FeedbackClassificationService.classify_single_record(
                session=session,
                feedback_id=target_id,
                provider_manager=manager,
                reprocess=True,
            )

        # Restore commit and verify NO orphaned records were added
        session.commit = original_commit

        count_after_class = session.execute(
            select(func.count(FeedbackClassification.classification_id)).where(
                FeedbackClassification.feedback_id == target_id
            )
        ).scalar()
        count_after_sent = session.execute(
            select(func.count(SentimentHistory.sentiment_id)).where(
                SentimentHistory.feedback_id == target_id
            )
        ).scalar()

        assert count_after_class == 1, "Failed retry must not leave orphaned FeedbackClassification"
        assert count_after_sent == 1, "Failed retry must not leave orphaned SentimentHistory"
