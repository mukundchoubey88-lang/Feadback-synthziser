"""Tests for FeedbackClassification Model and Schema Invariants (Part 6 Step 1).

Covers table creation, CRUD operations, JSON fields, CASCADE deletion,
version uniqueness, multi-version history, check constraints, and migration callables.
"""

from datetime import datetime, timezone
import uuid
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from pathlib import Path
from alembic.config import Config
from alembic.script import ScriptDirectory

from app.db.base import Base
from app.models.feedback import Feedback
from app.models.classification import FeedbackClassification


@pytest.fixture
def db_session():
    """In-memory SQLite database session with PRAGMA foreign_keys enabled."""
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


def make_feedback(session: Session, text: str = "Great app, but loading is slow.") -> Feedback:
    """Helper to create and persist an active Feedback item."""
    fb = Feedback(
        feedback_id=uuid.uuid4(),
        source="csv",
        feedback_text=text,
        cleaned_feedback_text=text,
        product="Mobile App",
        feature="Dashboard",
        timestamp=datetime.now(timezone.utc),
        quality_status="clean",
        quality_score=95.0,
    )
    session.add(fb)
    session.commit()
    return fb


def test_feedback_classification_crud_and_json_fields(db_session):
    """Verify persisting and querying all classification fields including structured JSON."""
    fb = make_feedback(db_session)

    classification = FeedbackClassification(
        classification_id=uuid.uuid4(),
        feedback_id=fb.feedback_id,
        classification_version="1.0.0",
        status="classified",
        overall_sentiment="mixed",
        sentiment_score=0.15,
        sentiment_intensity="medium",
        customer_intent="complaint",
        identified_product="Mobile App",
        identified_feature="Dashboard",
        topics=[{"label": "performance", "confidence": 0.92}],
        aspects=[
            {
                "aspect": "application performance",
                "sentiment": "negative",
                "sentiment_score": -0.85,
                "confidence": 0.94,
                "evidence": "loading is slow",
            },
            {
                "aspect": "overall satisfaction",
                "sentiment": "positive",
                "sentiment_score": 0.80,
                "confidence": 0.90,
                "evidence": "Great app",
            },
        ],
        pain_points=["Application takes too long to load"],
        keywords=["great app", "slow loading"],
        confidence_score=0.91,
        needs_review=False,
        provider="gemini",
        model="gemini-2.0-flash",
        latency_ms=450.5,
        token_usage={"prompt_tokens": 120, "completion_tokens": 55, "total_tokens": 175},
    )
    db_session.add(classification)
    db_session.commit()

    # Query back
    fetched = db_session.get(FeedbackClassification, classification.classification_id)
    assert fetched is not None
    assert fetched.feedback_id == fb.feedback_id
    assert fetched.classification_version == "1.0.0"
    assert fetched.overall_sentiment == "mixed"
    assert fetched.sentiment_score == 0.15
    assert len(fetched.topics) == 1
    assert fetched.topics[0]["label"] == "performance"
    assert len(fetched.aspects) == 2
    assert fetched.aspects[0]["aspect"] == "application performance"
    assert fetched.pain_points == ["Application takes too long to load"]
    assert fetched.keywords == ["great app", "slow loading"]
    assert fetched.provider == "gemini"
    assert fetched.token_usage["total_tokens"] == 175


def test_feedback_classification_cascade_delete(db_session):
    """Verify that deleting parent feedback cascades to delete classification records."""
    fb = make_feedback(db_session)

    c = FeedbackClassification(
        classification_id=uuid.uuid4(),
        feedback_id=fb.feedback_id,
        classification_version="1.0.0",
        status="classified",
        overall_sentiment="positive",
        sentiment_score=0.8,
        sentiment_intensity="high",
        customer_intent="praise",
        confidence_score=0.95,
    )
    db_session.add(c)
    db_session.commit()

    cid = c.classification_id
    assert db_session.get(FeedbackClassification, cid) is not None

    # Delete parent feedback
    db_session.delete(fb)
    db_session.commit()

    assert db_session.get(FeedbackClassification, cid) is None


def test_feedback_classification_version_uniqueness(db_session):
    """Verify UniqueConstraint on (feedback_id, classification_version, run_number)."""
    fb = make_feedback(db_session)

    c1 = FeedbackClassification(
        classification_id=uuid.uuid4(),
        feedback_id=fb.feedback_id,
        classification_version="1.0.0",
        run_number=1,
        status="classified",
        overall_sentiment="positive",
        sentiment_score=0.8,
        customer_intent="praise",
        confidence_score=0.9,
    )
    db_session.add(c1)
    db_session.commit()

    # Attempt second record with identical feedback_id, classification_version, and run_number
    c2 = FeedbackClassification(
        classification_id=uuid.uuid4(),
        feedback_id=fb.feedback_id,
        classification_version="1.0.0",
        run_number=1,
        status="classified",
        overall_sentiment="neutral",
        sentiment_score=0.0,
        customer_intent="suggestion",
        confidence_score=0.85,
    )
    db_session.add(c2)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    # With distinct run_number=2, persists both executions under the same classification_version
    c3 = FeedbackClassification(
        classification_id=uuid.uuid4(),
        feedback_id=fb.feedback_id,
        classification_version="1.0.0",
        run_number=2,
        status="classified",
        overall_sentiment="neutral",
        sentiment_score=0.0,
        customer_intent="suggestion",
        confidence_score=0.85,
    )
    db_session.add(c3)
    db_session.commit()
    assert db_session.get(FeedbackClassification, c1.classification_id) is not None
    assert db_session.get(FeedbackClassification, c3.classification_id) is not None


def test_feedback_classification_multi_version_history(db_session):
    """Verify multiple classification versions can be preserved per feedback item."""
    fb = make_feedback(db_session)

    c_v1 = FeedbackClassification(
        classification_id=uuid.uuid4(),
        feedback_id=fb.feedback_id,
        classification_version="1.0.0",
        status="classified",
        overall_sentiment="negative",
        sentiment_score=-0.5,
        customer_intent="complaint",
        confidence_score=0.8,
    )
    c_v2 = FeedbackClassification(
        classification_id=uuid.uuid4(),
        feedback_id=fb.feedback_id,
        classification_version="2.0.0",
        status="classified",
        overall_sentiment="mixed",
        sentiment_score=-0.2,
        customer_intent="complaint",
        confidence_score=0.92,
    )
    db_session.add_all([c_v1, c_v2])
    db_session.commit()

    # Relationship query
    refreshed_fb = db_session.get(Feedback, fb.feedback_id)
    assert len(refreshed_fb.classifications) == 2
    versions = {c.classification_version for c in refreshed_fb.classifications}
    assert versions == {"1.0.0", "2.0.0"}


def test_feedback_classification_score_bounds_constraints(db_session):
    """Verify check constraints on sentiment_score (-1.0 to 1.0) and confidence (0.0 to 1.0)."""
    fb = make_feedback(db_session)

    # Sentiment score > 1.0
    c_invalid_sentiment = FeedbackClassification(
        classification_id=uuid.uuid4(),
        feedback_id=fb.feedback_id,
        classification_version="1.0.0",
        status="classified",
        overall_sentiment="positive",
        sentiment_score=1.5,
        customer_intent="praise",
        confidence_score=0.9,
    )
    db_session.add(c_invalid_sentiment)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    # Confidence score < 0.0
    c_invalid_confidence = FeedbackClassification(
        classification_id=uuid.uuid4(),
        feedback_id=fb.feedback_id,
        classification_version="1.0.0",
        status="classified",
        overall_sentiment="positive",
        sentiment_score=0.5,
        customer_intent="praise",
        confidence_score=-0.1,
    )
    db_session.add(c_invalid_confidence)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_feedback_classification_enum_constraints(db_session):
    """Verify check constraints for overall_sentiment, sentiment_intensity, and customer_intent."""
    fb = make_feedback(db_session)

    # Invalid sentiment enum
    c_invalid_sentiment = FeedbackClassification(
        classification_id=uuid.uuid4(),
        feedback_id=fb.feedback_id,
        classification_version="1.0.0",
        status="classified",
        overall_sentiment="super_positive",  # Invalid
        sentiment_score=0.5,
        customer_intent="praise",
        confidence_score=0.9,
    )
    db_session.add(c_invalid_sentiment)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    # Invalid customer intent
    c_invalid_intent = FeedbackClassification(
        classification_id=uuid.uuid4(),
        feedback_id=fb.feedback_id,
        classification_version="1.0.0",
        status="classified",
        overall_sentiment="positive",
        sentiment_score=0.5,
        customer_intent="spam_intent",  # Invalid
        confidence_score=0.9,
    )
    db_session.add(c_invalid_intent)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_feedback_classification_nullable_telemetry(db_session):
    """Verify classification can be persisted with null telemetry (offline/fallback mode)."""
    fb = make_feedback(db_session)

    c = FeedbackClassification(
        classification_id=uuid.uuid4(),
        feedback_id=fb.feedback_id,
        classification_version="1.0.0",
        status="pending_review",
        overall_sentiment="neutral",
        sentiment_score=0.0,
        customer_intent="question",
        confidence_score=0.65,
        needs_review=True,
        review_reason="low_confidence",
        provider=None,
        model=None,
        latency_ms=None,
        token_usage=None,
    )
    db_session.add(c)
    db_session.commit()

    fetched = db_session.get(FeedbackClassification, c.classification_id)
    assert fetched.needs_review is True
    assert fetched.provider is None
    assert fetched.model is None


def test_migration_d71a94e2b83c_callables():
    """Verify migration revision metadata and callable exports via Alembic ScriptDirectory."""
    backend_dir = Path(__file__).resolve().parent.parent
    ini_path = backend_dir / "alembic.ini"
    alembic_cfg = Config(str(ini_path))
    alembic_cfg.set_main_option("script_location", str(backend_dir / "alembic"))

    script_dir = ScriptDirectory.from_config(alembic_cfg)
    rev = script_dir.get_revision("d71a94e2b83c")
    assert rev is not None
    assert rev.down_revision == "f6b903e1a82d"
    module = rev.module
    assert hasattr(module, "upgrade") and callable(module.upgrade)
    assert hasattr(module, "downgrade") and callable(module.downgrade)

    rev_e8 = script_dir.get_revision("e82b95f3c94d")
    assert rev_e8 is not None
    assert rev_e8.down_revision == "d71a94e2b83c"
    module_e8 = rev_e8.module
    assert hasattr(module_e8, "upgrade") and callable(module_e8.upgrade)
    assert hasattr(module_e8, "downgrade") and callable(module_e8.downgrade)
