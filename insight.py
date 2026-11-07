from datetime import datetime, timezone
from typing import List, TYPE_CHECKING
import uuid
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.feedback import Feedback


class InsightEvidence(Base):
    """Junction table linking synthesized insights with raw customer feedback evidence.

    Uses RESTRICT on feedback deletion to preserve evidence backing published insights.
    """

    __tablename__ = "insight_evidence"
    __table_args__ = (
        Index("ix_insight_evidence_feedback_id", "feedback_id"),
        Index("ix_insight_evidence_insight_id", "insight_id"),
    )

    insight_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("insights.insight_id", ondelete="CASCADE"),
        primary_key=True,
    )
    feedback_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("feedback.feedback_id", ondelete="RESTRICT"),
        primary_key=True,
    )
    evidence_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="direct_quote",
        comment="Type of evidence: direct_quote, supporting_metric, anomaly_example, recurring_pattern",
    )

    # Relationships
    insight: Mapped["Insight"] = relationship("Insight", back_populates="evidence")
    feedback: Mapped["Feedback"] = relationship("Feedback", back_populates="insight_evidence")


class Insight(Base):
    """Synthesized product intelligence, anomaly detection, and actionable recommendations."""

    __tablename__ = "insights"
    __table_args__ = (
        CheckConstraint(
            "confidence_score >= 0.0 AND confidence_score <= 1.0",
            name="ck_insights_confidence_score",
        ),
        Index("ix_insights_status_created", "status", "created_at"),
    )

    insight_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
        comment="Short executive title of the insight",
    )
    summary: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Detailed narrative analysis synthesizing multiple customer feedback points",
    )
    recommendation: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Actionable product or engineering recommendation",
    )
    confidence_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="Confidence score from 0.0 to 1.0 backing this insight",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
        index=True,
        comment="Synthesis timestamp in UTC",
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="active",
        index=True,
        comment="Lifecycle status: active, acknowledged, resolved, dismissed",
    )

    # Relationships
    evidence: Mapped[List["InsightEvidence"]] = relationship(
        "InsightEvidence",
        back_populates="insight",
        cascade="all, delete-orphan",
    )
    feedbacks: Mapped[List["Feedback"]] = relationship(
        "Feedback",
        secondary="insight_evidence",
        back_populates="insights",
        viewonly=True,
    )
