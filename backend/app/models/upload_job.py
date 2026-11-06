from datetime import datetime, timezone
from typing import Any, Optional
import uuid
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Integer,
    JSON,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UploadJob(Base):
    """Tracks asynchronous or synchronous feedback file ingestion jobs."""

    __tablename__ = "upload_jobs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'processing', 'completed', 'completed_with_errors', 'failed')",
            name="ck_upload_jobs_status",
        ),
    )

    job_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Unique identifier for the ingestion job",
    )
    filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Original uploaded file name",
    )
    format: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="File format: csv or json",
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="pending",
        index=True,
        comment="Job lifecycle status: pending, processing, completed, completed_with_errors, failed",
    )
    total_records: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Total records discovered in the upload payload",
    )
    inserted_records: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Total valid records successfully persisted to the database",
    )
    rejected_records: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Total records failing validation or malformed",
    )
    duplicate_records: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Total records flagged as duplicates (intra-file or existing database)",
    )
    error_summary: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="High-level description of overall failure or issue",
    )
    errors: Mapped[Optional[Any]] = mapped_column(
        JSON,
        nullable=True,
        comment="Structured list of row-level errors and validation diagnostics",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
        index=True,
        comment="Job submission timestamp in UTC",
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Job resolution timestamp in UTC",
    )
