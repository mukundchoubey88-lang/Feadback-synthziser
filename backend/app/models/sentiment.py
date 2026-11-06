from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING
import uuid
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.feedback import Feedback
    from app.models.theme import Theme


class SentimentHistory(Base):
    """Historical sentiment analysis record for feedback entries and optional theme aspects."""

    __tablename__ = "sentiment_history"
    __table_args__ = (
        CheckConstraint(
            "sentiment_score >= -1.0 AND sentiment_score <= 1.0",
            name="ck_sentiment_history_score",
        ),
        CheckConstraint(
            "confidence_score >= 0.0 AND confidence_score <= 1.0",
            name="ck_sentiment_history_confidence",
        ),
        Index("ix_sentiment_feedback_analysed", "feedback_id", "analysed_at"),
        Index("ix_sentiment_theme_analysed", "theme_id", "analysed_at"),
    )

    sentiment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    feedback_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("feedback.feedback_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    theme_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("themes.theme_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Specific theme or aspect analyzed; null if overall document sentiment",
    )
    sentiment_label: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Categorical sentiment label: positive, negative, neutral, mixed",
    )
    sentiment_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Continuous sentiment score between -1.0 (very negative) and +1.0 (very positive)",
    )
    confidence_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Model confidence in sentiment classification (0.0 to 1.0)",
    )
    analysed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
        index=True,
        comment="Analysis execution timestamp in UTC",
    )

    # Relationships
    feedback: Mapped["Feedback"] = relationship("Feedback", back_populates="sentiment_history")
    theme: Mapped[Optional["Theme"]] = relationship("Theme", back_populates="sentiment_history")
