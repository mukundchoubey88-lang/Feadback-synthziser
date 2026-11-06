from datetime import datetime, timezone, timedelta
import uuid
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.base import Base
from app.models import (
    Feedback,
    Theme,
    ThemeSnapshot,
    Insight,
    InsightEvidence,
    MemoryMetadata,
    SentimentHistory,
)


@pytest.fixture
def sqlite_db_session():
    """Create an in-memory SQLite database session with foreign key pragma enabled."""
    engine = create_engine("sqlite:///:memory:", echo=False)

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_product_scoped_theme_uniqueness_across_products(sqlite_db_session: Session):
    """Verify that identical theme names can exist across different products."""
    theme1 = Theme(
        theme_id=uuid.uuid4(),
        product="Billing Portal",
        theme_name="Login Failure",
        category="auth",
        status="active",
    )
    theme2 = Theme(
        theme_id=uuid.uuid4(),
        product="Mobile App",
        theme_name="Login Failure",
        category="auth",
        status="active",
    )
    sqlite_db_session.add_all([theme1, theme2])
    sqlite_db_session.commit()

    # Query both themes back
    t1 = sqlite_db_session.get(Theme, theme1.theme_id)
    t2 = sqlite_db_session.get(Theme, theme2.theme_id)
    assert t1 is not None and t2 is not None
    assert t1.theme_name == t2.theme_name == "Login Failure"
    assert t1.product != t2.product


def test_duplicate_theme_name_within_same_product_rejected(sqlite_db_session: Session):
    """Verify that duplicate theme names within the same product trigger an IntegrityError."""
    theme1 = Theme(
        theme_id=uuid.uuid4(),
        product="Analytics Dashboard",
        theme_name="Latency Spike",
        category="performance",
        status="active",
    )
    theme2 = Theme(
        theme_id=uuid.uuid4(),
        product="Analytics Dashboard",
        theme_name="Latency Spike",
        category="performance",
        status="active",
    )
    sqlite_db_session.add(theme1)
    sqlite_db_session.commit()

    sqlite_db_session.add(theme2)
    with pytest.raises(IntegrityError):
        sqlite_db_session.commit()
    sqlite_db_session.rollback()


def test_feedback_soft_deletion(sqlite_db_session: Session):
    """Verify soft deletion workflow: deleted_at marks feedback as inactive while preserving history."""
    fb = Feedback(
        feedback_id=uuid.uuid4(),
        source="zendesk",
        customer_id="cust-202",
        feedback_text="Checkout fails on Safari browser.",
        product="Storefront",
        feature="Checkout",
        timestamp=datetime.now(timezone.utc),
    )
    sqlite_db_session.add(fb)
    sqlite_db_session.commit()

    assert fb.deleted_at is None

    # Attach sentiment history
    sh = SentimentHistory(
        sentiment_id=uuid.uuid4(),
        feedback_id=fb.feedback_id,
        sentiment_label="negative",
        sentiment_score=-0.8,
        confidence_score=0.95,
        analysed_at=datetime.now(timezone.utc),
    )
    sqlite_db_session.add(sh)
    sqlite_db_session.commit()

    # Soft delete the feedback
    fb.deleted_at = datetime.now(timezone.utc)
    sqlite_db_session.commit()

    retrieved = sqlite_db_session.get(Feedback, fb.feedback_id)
    assert retrieved is not None
    assert retrieved.deleted_at is not None
    # Historical sentiment remains intact
    assert len(retrieved.sentiment_history) == 1
    assert retrieved.sentiment_history[0].sentiment_label == "negative"


def test_insight_evidence_restrictive_deletion(sqlite_db_session: Session):
    """Verify that hard-deleting Feedback linked to active InsightEvidence is rejected by RESTRICT."""
    fb = Feedback(
        feedback_id=uuid.uuid4(),
        source="csv",
        feedback_text="Crucial bug quote used as evidence.",
        product="Core Platform",
        timestamp=datetime.now(timezone.utc),
    )
    insight = Insight(
        insight_id=uuid.uuid4(),
        title="High Severity Bug Pattern",
        summary="Multiple users reporting crash on launch.",
        recommendation="Deploy hotfix immediately.",
        confidence_score=0.98,
        status="active",
    )
    sqlite_db_session.add_all([fb, insight])
    sqlite_db_session.commit()

    evidence = InsightEvidence(
        insight_id=insight.insight_id,
        feedback_id=fb.feedback_id,
        evidence_type="direct_quote",
    )
    sqlite_db_session.add(evidence)
    sqlite_db_session.commit()

    # Attempting hard delete on feedback must fail because InsightEvidence references it with RESTRICT
    sqlite_db_session.delete(fb)
    with pytest.raises(IntegrityError):
        sqlite_db_session.commit()
    sqlite_db_session.rollback()


def test_theme_snapshot_period_ordering_constraint(sqlite_db_session: Session):
    """Verify that ThemeSnapshot rejects period_start > period_end."""
    theme = Theme(
        theme_id=uuid.uuid4(),
        product="Cloud Service",
        theme_name="API Rate Limiting",
        category="networking",
    )
    sqlite_db_session.add(theme)
    sqlite_db_session.commit()

    now = datetime.now(timezone.utc)
    invalid_snapshot = ThemeSnapshot(
        snapshot_id=uuid.uuid4(),
        theme_id=theme.theme_id,
        period_start=now,
        period_end=now - timedelta(days=7),  # Invalid: end is before start
        feedback_count=5,
        positive_count=1,
        negative_count=3,
        neutral_count=1,
        sentiment_average=-0.4,
    )
    sqlite_db_session.add(invalid_snapshot)
    with pytest.raises(IntegrityError):
        sqlite_db_session.commit()
    sqlite_db_session.rollback()


def test_theme_snapshot_count_consistency_constraint(sqlite_db_session: Session):
    """Verify that ThemeSnapshot rejects positive + negative + neutral > feedback_count."""
    theme = Theme(
        theme_id=uuid.uuid4(),
        product="Cloud Service",
        theme_name="Memory Leaks",
        category="performance",
    )
    sqlite_db_session.add(theme)
    sqlite_db_session.commit()

    now = datetime.now(timezone.utc)
    # Total feedback_count is 10, but category sum is 6 + 6 + 2 = 14 > 10
    inconsistent_snapshot = ThemeSnapshot(
        snapshot_id=uuid.uuid4(),
        theme_id=theme.theme_id,
        period_start=now - timedelta(days=7),
        period_end=now,
        feedback_count=10,
        positive_count=6,
        negative_count=6,
        neutral_count=2,
        sentiment_average=0.0,
    )
    sqlite_db_session.add(inconsistent_snapshot)
    with pytest.raises(IntegrityError):
        sqlite_db_session.commit()
    sqlite_db_session.rollback()


def test_memory_metadata_provenance_and_bank_mapping(sqlite_db_session: Session):
    """Verify MemoryMetadata distinguishes bank_id, external memory ID, and typed source links."""
    theme = Theme(
        theme_id=uuid.uuid4(),
        product="Search Engine",
        theme_name="Relevance Accuracy",
        category="quality",
    )
    fb = Feedback(
        feedback_id=uuid.uuid4(),
        source="survey",
        feedback_text="Search results are irrelevant for medical queries.",
        product="Search Engine",
        timestamp=datetime.now(timezone.utc),
    )
    sqlite_db_session.add_all([theme, fb])
    sqlite_db_session.commit()

    # Memory derived from feedback and linked to theme
    memory = MemoryMetadata(
        memory_id=uuid.uuid4(),
        bank_id="search-engine-memories",
        hindsight_memory_id="hs_mem_987abc123",
        memory_type="customer_trajectory",
        source_entity_type="feedback",
        feedback_id=fb.feedback_id,
        related_theme=theme.theme_id,
        source_reference="survey-batch-2026-q1",
    )
    sqlite_db_session.add(memory)
    sqlite_db_session.commit()

    retrieved = sqlite_db_session.get(MemoryMetadata, memory.memory_id)
    assert retrieved is not None
    assert retrieved.bank_id == "search-engine-memories"
    assert retrieved.hindsight_memory_id == "hs_mem_987abc123"
    assert retrieved.source_entity_type == "feedback"
    assert retrieved.feedback is not None
    assert retrieved.theme is not None
    assert retrieved.feedback.feedback_text == "Search results are irrelevant for medical queries."
    assert retrieved.theme.theme_name == "Relevance Accuracy"
