"""Feedback classification model for AI-driven sentiment and semantic synthesis."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, TYPE_CHECKING
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
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.feedback import Feedback


class FeedbackClassification(Base):
    """Stores AI classification results, sentiment, semantic extractions, and execution telemetry."""

    __tablename__ = "feedback_classifications"
    __table_args__ = (
        CheckConstraint(
            "status IN ('classified', 'failed', 'pending_review')",
            name="ck_feedback_classifications_status",
        ),
        CheckConstraint(
            "overall_sentiment IS NULL OR overall_sentiment IN ('positive', 'negative', 'neutral', 'mixed')",
            name="ck_feedback_classifications_overall_sentiment",
        ),
        CheckConstraint(
            "sentiment_score IS NULL OR (sentiment_score >= -1.0 AND sentiment_score <= 1.0)",
            name="ck_feedback_classifications_sentiment_score",
        ),
        CheckConstraint(
            "sentiment_intensity IS NULL OR sentiment_intensity IN ('low', 'medium', 'high')",
            name="ck_feedback_classifications_sentiment_intensity",
        ),
        CheckConstraint(
            "customer_intent IS NULL OR customer_intent IN ('complaint', 'suggestion', 'praise', 'question', 'feature_request', 'other')",
            name="ck_feedback_classifications_customer_intent",
        ),
        CheckConstraint(
            "confidence_score IS NULL OR (confidence_score >= 0.0 AND confidence_score <= 1.0)",
            name="ck_feedback_classifications_confidence_score",
        ),
        CheckConstraint(
            "latency_ms IS NULL OR latency_ms >= 0",
            name="ck_feedback_classifications_latency_ms",
        ),
        # Non-unique indexes for fast querying and history traversal
        Index("ix_feedback_classifications_feedback_id", "feedback_id"),
        Index("ix_feedback_classifications_classified_at", "classified_at"),
        Index("ix_feedback_classifications_version", "classification_version"),
        Index("ix_feedback_classifications_feedback_version", "feedback_id", "classification_version"),
        Index("ix_feedback_classifications_status", "status"),
    )

    # Identifiers
    classification_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    feedback_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("feedback.feedback_id", ondelete="CASCADE"),
        nullable=False,
    )

    # Classification versioning & state
    classification_version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Classification model or prompt version string, e.g. v1.0.0",
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="classified",
        comment="Classification result status: classified, failed, pending_review",
    )

    # Sentiment analysis
    overall_sentiment: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Categorical sentiment label: positive, negative, neutral, mixed",
    )
    sentiment_score: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Continuous sentiment score between -1.0 and 1.0",
    )
    sentiment_intensity: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Sentiment intensity level: low, medium, high",
    )

    # Semantics & intent
    customer_intent: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Customer intent category: complaint, suggestion, praise, question, feature_request, other",
    )
    identified_product: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Identified product name if detected in feedback content",
    )
    identified_feature: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Identified feature or component if detected in feedback content",
    )

    # Structured JSON extractions with callable defaults for mutable values
    topics: Mapped[Optional[List[str]]] = mapped_column(
        JSON,
        nullable=True,
        default=list,
        comment="Extracted topics list",
    )
    aspects: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(
        JSON,
        nullable=True,
        default=list,
        comment="Extracted aspect-based sentiment evaluations",
    )
    pain_points: Mapped[Optional[List[str]]] = mapped_column(
        JSON,
        nullable=True,
        default=list,
        comment="Extracted customer friction points",
    )
    keywords: Mapped[Optional[List[str]]] = mapped_column(
        JSON,
        nullable=True,
        default=list,
        comment="Extracted keywords and key phrases",
    )

    # Confidence and review triage
    confidence_score: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Overall classification confidence score between 0.0 and 1.0",
    )
    needs_review: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Flag indicating human review is recommended",
    )
    review_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Explanation of why review is needed",
    )

    # AI execution metadata & telemetry
    provider: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="AI provider used for classification, e.g. gemini, openrouter, grok",
    )
    model_name: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="AI model name or identifier",
    )
    latency_ms: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Inference latency in milliseconds",
    )
    token_usage: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        default=dict,
        comment="Token consumption breakdown: prompt_tokens, completion_tokens, total_tokens",
    )
    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Sanitized error details if classification failed",
    )

    # Execution timestamp in UTC
    classified_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
        comment="Timestamp when classification was executed in UTC",
    )

    # Relationships
    feedback: Mapped["Feedback"] = relationship(
        "Feedback",
        back_populates="classifications",
    )
