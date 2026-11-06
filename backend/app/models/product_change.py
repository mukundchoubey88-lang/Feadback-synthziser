from datetime import datetime
from typing import Optional
import uuid
from sqlalchemy import (
    DateTime,
    Index,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ProductChanges(Base):
    """Product release, deployment, or changelog event for correlation with feedback shifts."""

    __tablename__ = "product_changes"
    __table_args__ = (
        Index("ix_product_changes_product_date", "product", "release_date"),
        Index("ix_product_changes_product_version", "product", "version"),
    )

    release_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    product: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
        comment="Impacted product name or application",
    )
    feature: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="Specific feature or component modified",
    )
    release_description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Changelog, release notes, or summary of functional changes",
    )
    release_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="Release deployment timestamp in UTC",
    )
    version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Release semantic version or build tag",
    )
    change_category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Type of release: major, minor, patch, hotfix, redesign, feature_launch",
    )
