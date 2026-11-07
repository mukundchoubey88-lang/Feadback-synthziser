from datetime import datetime, timezone
from typing import Any, List, Optional, TYPE_CHECKING
import uuid
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    JSON,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.theme import Theme
    from app.models.sentiment import SentimentHistory
    from app.models.insight import Insight, InsightEvidence
    from app.models.classification import FeedbackClassification
    from app.models.feedback_embeddings import FeedbackEmbedding


class FeedbackThemes(Base):
    """Junction table associating Feedback with Themes including relevance and aspect sentiment."""

    __tablename__ = "feedback_themes"
    __table_args__ = (
        CheckConstraint(
            "relevance_score >= 0.0 AND relevance_score <= 1.0",
            name="ck_feedback_themes_relevance_score",
        ),
        Index("ix_feedback_themes_theme_id", "theme_id"),
        Index("ix_feedback_themes_feedback_id", "feedback_id"),
    )

    feedback_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("feedback.feedback_id", ondelete="CASCADE"),
        primary_key=True,
    )
    theme_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("themes.theme_id", ondelete="CASCADE"),
        primary_key=True,
    )
    relevance_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=1.0,
        comment="Theme relevance score from 0.0 to 1.0",
    )
    aspect_sentiment: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Aspect sentiment label: positive, negative, neutral, mixed",
    )

    # Relationships
    feedback: Mapped["Feedback"] = relationship("Feedback", back_populates="feedback_themes")
    theme: Mapped["Theme"] = relationship("Theme", back_populates="feedback_themes")


class Feedback(Base):
    """Customer feedback entity storing raw customer comments, source metadata, and soft-delete state."""

    __tablename__ = "feedback"
    __table_args__ = (
        CheckConstraint(
            "quality_status IN ('pending', 'clean', 'flagged', 'rejected', 'failed')",
            name="ck_feedback_quality_status",
        ),
        CheckConstraint(
            "processing_status IN ('unprocessed', 'processing', 'processed', 'failed')",
            name="ck_feedback_processing_status",
        ),
        Index("ix_feedback_product_timestamp", "product", "timestamp"),
        Index("ix_feedback_product_feature", "product", "feature"),
        Index("ix_feedback_quality_status", "quality_status"),
        Index("ix_feedback_processing_status", "processing_status"),
    )

    feedback_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    source: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Source of feedback, e.g., csv, json, zendesk, app_store",
    )
    customer_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        index=True,
        comment="External customer or account identifier",
    )
    feedback_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Original unedited feedback content",
    )
    product: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Product line or application name",
    )
    feature: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="Specific feature or component identified",
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="Original timestamp when feedback was provided by user",
    )
    app_version: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        index=True,
        comment="Application or client release version",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
        comment="Ingestion timestamp in UTC",
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
        index=True,
        comment="Soft deletion timestamp in UTC; null if active",
    )

    # Part 4 Data Cleaning and Quality Pipeline fields
    cleaned_feedback_text: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Normalized and PII-redacted feedback copy",
    )
    quality_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="pending",
        comment="Quality classification: pending, clean, flagged, rejected, failed",
    )
    quality_score: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Deterministic quality score from 0.0 to 100.0",
    )
    content_quality_score: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Content usefulness score from 0.0 to 100.0 without metadata penalties",
    )
    metadata_completeness_score: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Completeness of optional metadata fields from 0.0 to 100.0",
    )
    quality_flags: Mapped[Optional[Any]] = mapped_column(
        JSON,
        nullable=True,
        comment="List of diagnostic quality and anomaly flags",
    )
    pii_detected: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Flag indicating presence of sensitive PII in original text",
    )
    pii_types: Mapped[Optional[Any]] = mapped_column(
        JSON,
        nullable=True,
        comment="Categories of PII discovered (e.g., email, phone, url)",
    )
    cleaning_version: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Algorithm version used for cleaning and redaction",
    )
    cleaned_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp when cleaning pipeline executed in UTC",
    )
    processing_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="unprocessed",
        comment="Pipeline execution state: unprocessed, processing, processed, failed",
    )
    processing_error: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Error details if cleaning pipeline failed",
    )

    # Relationships
    feedback_themes: Mapped[List["FeedbackThemes"]] = relationship(
        "FeedbackThemes",
        back_populates="feedback",
        cascade="all, delete-orphan",
    )
    themes: Mapped[List["Theme"]] = relationship(
        "Theme",
        secondary="feedback_themes",
        back_populates="feedbacks",
        viewonly=True,
    )
    sentiment_history: Mapped[List["SentimentHistory"]] = relationship(
        "SentimentHistory",
        back_populates="feedback",
        cascade="all, delete-orphan",
    )
    insight_evidence: Mapped[List["InsightEvidence"]] = relationship(
        "InsightEvidence",
        back_populates="feedback",
        passive_deletes=True,
    )
    insights: Mapped[List["Insight"]] = relationship(
        "Insight",
        secondary="insight_evidence",
        back_populates="feedbacks",
        viewonly=True,
    )
    classifications: Mapped[List["FeedbackClassification"]] = relationship(
        "FeedbackClassification",
        back_populates="feedback",
        cascade="all, delete-orphan",
        order_by="desc(FeedbackClassification.classified_at)",
    )
    embeddings: Mapped[List["FeedbackEmbedding"]] = relationship(
        "FeedbackEmbedding",
        back_populates="feedback",
        cascade="all, delete-orphan",
    )
