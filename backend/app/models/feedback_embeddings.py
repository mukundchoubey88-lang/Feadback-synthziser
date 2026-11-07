"""Feedback Embedding Database Model.

Persists individual feedback embedding vectors alongside model provenance,
input text hash for idempotent generation, and vector dimensions.
"""

from datetime import datetime, timezone
from typing import List, TYPE_CHECKING
import uuid

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import PortableVector

if TYPE_CHECKING:
    from app.models.feedback import Feedback


class FeedbackEmbedding(Base):
    """Normalized feedback embedding vector with model provenance and hash idempotency."""

    __tablename__ = "feedback_embeddings"
    __table_args__ = (
        UniqueConstraint("feedback_id", "embedding_model", name="uq_feedback_embeddings_feedback_model"),
        Index("ix_feedback_embeddings_input_hash", "input_hash"),
        Index("ix_feedback_embeddings_model", "embedding_model"),
    )

    embedding_id: Mapped[uuid.UUID] = mapped_column(
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
    embedding_model: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="Embedding model identifier (e.g. gemini-embedding-2)",
    )
    embedding_dimensions: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Vector dimension count (e.g. 768)",
    )
    embedding_vector: Mapped[List[float]] = mapped_column(
        PortableVector(768),
        nullable=False,
        comment="Float vector representation (pgvector vector(768) on PG, JSON on SQLite)",
    )
    input_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        comment="SHA-256 hash of input text, product, and parameters for idempotent caching",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
        comment="Timestamp of vector generation in UTC",
    )

    # Relationship to Feedback
    feedback: Mapped["Feedback"] = relationship(
        "Feedback",
        back_populates="embeddings",
    )
