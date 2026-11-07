"""SQLAlchemy model for Feedback Classification and Aspect-Based Sentiment Analysis.

Stores detailed LLM classification results, aspect sentiment, topics, pain points,
keywords, customer intent, model telemetry, review flags, and version history.
"""

from datetime import datetime, timezone
from typing import Any, Optional, TYPE_CHECKING
import uuid
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.feedback import Feedback


class FeedbackClassification(Base):
    """Detailed classification and sentiment analysis record for an individual feedback item."""

    __tablename__ = "feedback_classifications"
    __table_args__ = (
        UniqueConstraint(
            "feedback_id",
            "classification_version",
            "run_number",
            name="uq_feedback_classifications_feedback_version_run",
        ),
        CheckConstraint(
            "sentiment_score >= -1.0 AND sentiment_score <= 1.0",
            name="ck_feedback_classifications_sentiment_score",
        ),
        CheckConstraint(
            "confidence_score >= 0.0 AND confidence_score <= 1.0",
            name="ck_feedback_classifications_confidence_score",
        ),
        CheckConstraint(
            "overall_sentiment IN ('positive', 'negative', 'neutral', 'mixed')",
            name="ck_feedback_classifications_overall_sentiment",
        ),
        CheckConstraint(
            "sentiment_intensity IN ('low', 'medium', 'high')",
            name="ck_feedback_classifications_sentiment_intensity",
        ),
        CheckConstraint(
            "customer_intent IN ('complaint', 'suggestion', 'praise', 'question', 'feature_request', 'other')",
            name="ck_feedback_classifications_customer_intent",
        ),
        CheckConstraint(
            "status IN ('classified', 'failed', 'pending_review')",
            name="ck_feedback_classifications_status",
        ),
        Index(
            "ix_feedback_classifications_feedback_classified",
            "feedback_id",
            "classified_at",
        ),
        Index(
            "ix_feedback_classifications_sentiment_intent",
            "overall_sentiment",
            "customer_intent",
        ),
    )

    classification_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    feedback_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("feedback.feedback_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Foreign key to feedback record with cascade deletion",
    )
    classification_version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="1.0.0",
        comment="Algorithm / pipeline version for deterministic reclassification",
    )
    run_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        server_default="1",
        comment="Sequential execution run index per feedback item and algorithm version",
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="classified",
        index=True,
        comment="Lifecycle status: classified, failed, pending_review",
    )
    overall_sentiment: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Categorical overall sentiment: positive, negative, neutral, mixed",
    )
    sentiment_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Continuous overall sentiment score (-1.0 very negative to +1.0 very positive)",
    )
    sentiment_intensity: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="medium",
        comment="Sentiment intensity: low, medium, high",
    )
    customer_intent: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Primary customer intent: complaint, suggestion, praise, question, feature_request, other",
    )
    identified_product: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="Identified product or null if uncertain",
    )
    identified_feature: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="Identified feature or null if uncertain",
    )
    topics: Mapped[Optional[Any]] = mapped_column(
        JSON,
        nullable=True,
        comment="List of classified topic labels with confidence: [{'label': str, 'confidence': float}]",
    )
    aspects: Mapped[Optional[Any]] = mapped_column(
        JSON,
        nullable=True,
        comment="List of aspect sentiments: [{'aspect': str, 'sentiment': str, 'sentiment_score': float, 'confidence': float, 'evidence': str}]",
    )
    pain_points: Mapped[Optional[Any]] = mapped_column(
        JSON,
        nullable=True,
        comment="List of extracted customer pain points",
    )
    keywords: Mapped[Optional[Any]] = mapped_column(
        JSON,
        nullable=True,
        comment="List of salient keywords extracted from feedback",
    )
    confidence_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Model-estimated confidence score from 0.0 to 1.0",
    )
    needs_review: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="True if classification meets low-confidence or ambiguity review criteria",
    )
    review_reason: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Reason human review was triggered (e.g. low_confidence, ambiguous_sentiment)",
    )
    provider: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Responding AI provider name (e.g. gemini, openrouter, grok)",
    )
    model: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Specific model ID that executed the classification completion",
    )
    latency_ms: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Inference latency in milliseconds",
    )
    token_usage: Mapped[Optional[Any]] = mapped_column(
        JSON,
        nullable=True,
        comment="Token metrics: {'prompt_tokens': int, 'completion_tokens': int, 'total_tokens': int, 'cost_usd': float}",
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Safe error description if classification failed",
    )
    classified_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
        index=True,
        comment="Classification timestamp in UTC",
    )

    # Relationships
    feedback: Mapped["Feedback"] = relationship(
        "Feedback",
        back_populates="classifications",
    )
