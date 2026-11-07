from datetime import datetime, timezone
from typing import Any, Optional, TYPE_CHECKING
import uuid
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.theme import Theme, ThemeSnapshot
    from app.models.feedback import Feedback
    from app.models.insight import Insight

SUPPORTED_SOURCE_ENTITY_TYPES = {
    "feedback",
    "snapshot",
    "theme_snapshot",
    "insight",
    "reflection",
    "external",
}


class MemoryMetadata(Base):
    """Local tracking and mapping layer for Hindsight persistent memories.

    Differentiates internal PostgreSQL identifiers from external Hindsight memory
    and memory bank identifiers. Maintains strongly typed foreign keys to source
    entities (feedback, snapshots, insights, themes) for relational integrity,
    alongside a flexible source_entity_type and source_reference for external or
    aggregate memories.
    """

    __tablename__ = "memory_metadata"
    __table_args__ = (
        CheckConstraint(
            "(feedback_id IS NULL OR source_entity_type = 'feedback') AND "
            "(snapshot_id IS NULL OR source_entity_type IN ('snapshot', 'theme_snapshot')) AND "
            "(insight_id IS NULL OR source_entity_type = 'insight')",
            name="ck_memory_metadata_provenance",
        ),
        Index("ix_memory_type_created", "memory_type", "created_at"),
        Index("ix_memory_source_entity", "source_entity_type", "created_at"),
    )

    memory_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Local PostgreSQL UUID primary key",
    )
    bank_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        default="default",
        index=True,
        comment="Hindsight memory bank identifier (e.g., product or workspace bank)",
    )
    hindsight_memory_id: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        index=True,
        comment="External identifier returned by Hindsight platform upon memory retention",
    )
    memory_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Type of cognitive memory, e.g., theme_reflection, historical_shift, customer_trajectory",
    )
    source_entity_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Categorical source entity type: feedback, theme_snapshot, insight, reflection, external",
    )

    # Typed nullable foreign keys to original PostgreSQL records
    feedback_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("feedback.feedback_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Direct link to source Feedback record, if memory is feedback-derived",
    )
    snapshot_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("theme_snapshots.snapshot_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Direct link to source ThemeSnapshot record, if memory is snapshot-derived",
    )
    insight_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("insights.insight_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Direct link to source Insight record, if memory is insight-derived",
    )
    related_theme: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("themes.theme_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Optional foreign key link to associated Theme",
    )

    source_reference: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        index=True,
        comment="Supplementary URI, external doc reference, or raw provenance tag",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
        index=True,
        comment="Initial memory creation timestamp in UTC",
    )
    last_updated: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        default=lambda: datetime.now(timezone.utc),
        index=True,
        comment="Timestamp of latest reflection, update, or reconciliation in UTC",
    )

    # Relationships
    theme: Mapped[Optional["Theme"]] = relationship("Theme", back_populates="memories")
    feedback: Mapped[Optional["Feedback"]] = relationship("Feedback")
    snapshot: Mapped[Optional["ThemeSnapshot"]] = relationship("ThemeSnapshot")
    insight: Mapped[Optional["Insight"]] = relationship("Insight")

    @validates("source_entity_type", "feedback_id", "snapshot_id", "insight_id")
    def validate_provenance(self, key: str, value: Any) -> Any:
        """Enforce provenance consistency between source_entity_type and typed source FKs."""
        if key == "source_entity_type" and value is not None:
            if value not in SUPPORTED_SOURCE_ENTITY_TYPES:
                raise ValueError(
                    f"Unsupported source_entity_type '{value}'. "
                    f"Supported types are: {', '.join(sorted(SUPPORTED_SOURCE_ENTITY_TYPES))}."
                )

        if key == "feedback_id" and value is not None:
            entity_type = getattr(self, "source_entity_type", None)
            if entity_type is not None and entity_type != "feedback":
                raise ValueError(
                    f"Cannot set feedback_id when source_entity_type is '{entity_type}'"
                )
        elif key == "snapshot_id" and value is not None:
            entity_type = getattr(self, "source_entity_type", None)
            if entity_type is not None and entity_type not in ("snapshot", "theme_snapshot"):
                raise ValueError(
                    f"Cannot set snapshot_id when source_entity_type is '{entity_type}'"
                )
        elif key == "insight_id" and value is not None:
            entity_type = getattr(self, "source_entity_type", None)
            if entity_type is not None and entity_type != "insight":
                raise ValueError(
                    f"Cannot set insight_id when source_entity_type is '{entity_type}'"
                )
        elif key == "source_entity_type" and value is not None:
            if value == "feedback":
                if getattr(self, "snapshot_id", None) is not None or getattr(self, "insight_id", None) is not None:
                    raise ValueError("source_entity_type 'feedback' conflicts with non-null snapshot_id or insight_id")
            elif value in ("snapshot", "theme_snapshot"):
                if getattr(self, "feedback_id", None) is not None or getattr(self, "insight_id", None) is not None:
                    raise ValueError(f"source_entity_type '{value}' conflicts with non-null feedback_id or insight_id")
            elif value == "insight":
                if getattr(self, "feedback_id", None) is not None or getattr(self, "snapshot_id", None) is not None:
                    raise ValueError("source_entity_type 'insight' conflicts with non-null feedback_id or snapshot_id")
        return value
