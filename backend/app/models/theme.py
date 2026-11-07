from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, TYPE_CHECKING
import uuid
from sqlalchemy import (
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
from app.db.types import PortableVector

if TYPE_CHECKING:
    from app.models.feedback import Feedback, FeedbackThemes
    from app.models.sentiment import SentimentHistory
    from app.models.memory import MemoryMetadata


class Theme(Base):
    """Categorical feedback theme or problem area discovered or assigned, scoped by product."""

    __tablename__ = "themes"
    __table_args__ = (
        UniqueConstraint("product", "theme_name", name="uq_themes_product_theme_name"),
        Index("ix_themes_product_category", "product", "category"),
        Index("ix_themes_product_status", "product", "status"),
        Index("ix_themes_category_status", "category", "status"),
    )

    theme_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    product: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Product line or application owning this theme",
    )
    theme_name: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
        index=True,
        comment="Human-readable theme or issue title within product scope",
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Detailed definition and scope of this theme",
    )
    category: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Broad classification, e.g., usability, bug, billing, performance",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
        comment="Creation timestamp in UTC",
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="active",
        index=True,
        comment="Status: candidate, active, merged, archived",
    )
    centroid_vector: Mapped[Optional[List[float]]] = mapped_column(
        PortableVector(768),
        nullable=True,
        comment="Normalized centroid embedding vector of member feedbacks (pgvector vector(768) on PG, JSON on SQLite)",
    )
    merged_into_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("themes.theme_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Target theme if this theme was merged into another",
    )
    split_from_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("themes.theme_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Parent theme if this theme was split from another",
    )
    lineage_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        comment="Audit trail and lineage history for merges, splits, and reactivations",
    )

    # Self-referencing relationships
    merged_into: Mapped[Optional["Theme"]] = relationship(
        "Theme",
        remote_side=[theme_id],
        foreign_keys=[merged_into_id],
        backref="merged_sources",
    )
    split_from: Mapped[Optional["Theme"]] = relationship(
        "Theme",
        remote_side=[theme_id],
        foreign_keys=[split_from_id],
        backref="split_children",
    )

    # Relationships
    feedback_themes: Mapped[List["FeedbackThemes"]] = relationship(
        "FeedbackThemes",
        back_populates="theme",
        cascade="all, delete-orphan",
    )
    feedbacks: Mapped[List["Feedback"]] = relationship(
        "Feedback",
        secondary="feedback_themes",
        back_populates="themes",
        viewonly=True,
    )
    sentiment_history: Mapped[List["SentimentHistory"]] = relationship(
        "SentimentHistory",
        back_populates="theme",
    )
    snapshots: Mapped[List["ThemeSnapshot"]] = relationship(
        "ThemeSnapshot",
        back_populates="theme",
        cascade="all, delete-orphan",
    )
    memories: Mapped[List["MemoryMetadata"]] = relationship(
        "MemoryMetadata",
        back_populates="theme",
    )


class ThemeSnapshot(Base):
    """Aggregated snapshot of theme activity, sentiment, and volume over a discrete period."""

    __tablename__ = "theme_snapshots"
    __table_args__ = (
        CheckConstraint("period_start <= period_end", name="ck_theme_snapshots_period_order"),
        CheckConstraint(
            "positive_count + negative_count + neutral_count <= feedback_count",
            name="ck_theme_snapshots_count_consistency",
        ),
        CheckConstraint("feedback_count >= 0", name="ck_theme_snapshots_feedback_count"),
        CheckConstraint("positive_count >= 0", name="ck_theme_snapshots_positive_count"),
        CheckConstraint("negative_count >= 0", name="ck_theme_snapshots_negative_count"),
        CheckConstraint("neutral_count >= 0", name="ck_theme_snapshots_neutral_count"),
        CheckConstraint(
            "sentiment_average >= -1.0 AND sentiment_average <= 1.0",
            name="ck_theme_snapshots_sentiment_avg",
        ),
        Index("ix_theme_snapshots_theme_period", "theme_id", "period_start", "period_end"),
    )

    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    theme_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("themes.theme_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    period_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="Start timestamp of aggregation window (inclusive)",
    )
    period_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="End timestamp of aggregation window (inclusive)",
    )
    feedback_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Total feedbacks received in period for theme",
    )
    positive_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Count of positive sentiment feedbacks",
    )
    negative_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Count of negative sentiment feedbacks",
    )
    neutral_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Count of neutral sentiment feedbacks",
    )
    sentiment_average: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
        comment="Mean sentiment score for the window (-1.0 to 1.0)",
    )

    # Relationships
    theme: Mapped["Theme"] = relationship("Theme", back_populates="snapshots")
