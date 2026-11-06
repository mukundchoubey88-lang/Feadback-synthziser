from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field


class FeedbackResponse(BaseModel):
    """Pydantic model representing an ingested feedback record with cleaning state."""

    model_config = ConfigDict(from_attributes=True)

    feedback_id: uuid.UUID
    source: str
    customer_id: Optional[str] = None
    feedback_text: str
    product: str
    feature: Optional[str] = None
    timestamp: datetime
    app_version: Optional[str] = None
    created_at: datetime
    deleted_at: Optional[datetime] = None

    # Cleaning and Quality Fields
    cleaned_feedback_text: Optional[str] = None
    quality_status: str = "pending"
    quality_score: Optional[float] = None
    content_quality_score: Optional[float] = None
    metadata_completeness_score: Optional[float] = None
    quality_flags: Optional[List[str]] = None
    pii_detected: bool = False
    pii_types: Optional[List[str]] = None
    cleaning_version: Optional[str] = None
    cleaned_at: Optional[datetime] = None
    processing_status: str = "unprocessed"
    processing_error: Optional[str] = None


class FeedbackPaginationResponse(BaseModel):
    """Paginated list of feedback records with metadata."""

    items: List[FeedbackResponse]
    total: int = Field(..., ge=0, description="Total active feedback records matching filters")
    page: int = Field(..., ge=1, description="Current page number (1-indexed)")
    page_size: int = Field(..., ge=1, description="Items per page")
    total_pages: int = Field(..., ge=0, description="Total pages available")


class UploadRowError(BaseModel):
    """Structured description of an individual record validation error."""

    row: int = Field(..., description="1-indexed row number from the upload payload")
    field: Optional[str] = Field(None, description="Field name failing validation if known")
    error: str = Field(..., description="Human-readable explanation of the validation failure")
    value: Optional[str] = Field(None, description="Rejected value representation")


class UploadJobResponse(BaseModel):
    """Response schema representing stored upload job status and counters."""

    model_config = ConfigDict(from_attributes=True)

    job_id: uuid.UUID
    filename: str
    format: str
    status: str
    total_records: int
    inserted_records: int
    rejected_records: int
    duplicate_records: int
    error_summary: Optional[str] = None
    errors: Optional[List[Dict[str, Any]]] = None
    created_at: datetime
    completed_at: Optional[datetime] = None


class UploadResponse(BaseModel):
    """Response payload immediately returned upon completing synchronous file ingestion."""

    model_config = ConfigDict(from_attributes=True)

    job_id: uuid.UUID
    status: str
    filename: str
    total_records: int
    inserted_records: int
    duplicate_records: int
    rejected_records: int
    errors: Optional[List[Dict[str, Any]]] = None
    message: str


class BatchCleanResponse(BaseModel):
    """Result summary of a batch data cleaning execution."""

    total_considered: int
    processed: int
    skipped: int
    clean_count: int
    flagged_count: int
    rejected_count: int
    failed_count: int


class FeedbackQualityResponse(BaseModel):
    """Detailed quality inspection schema for an individual feedback item."""

    model_config = ConfigDict(from_attributes=True)

    feedback_id: uuid.UUID
    original_feedback_text: str
    cleaned_feedback_text: Optional[str] = None
    quality_status: str
    quality_score: Optional[float] = None
    content_quality_score: Optional[float] = None
    metadata_completeness_score: Optional[float] = None
    quality_flags: Optional[List[str]] = None
    pii_detected: bool = False
    pii_types: Optional[List[str]] = None
    cleaning_version: Optional[str] = None
    cleaned_at: Optional[datetime] = None
    processing_status: str
    processing_error: Optional[str] = None


class QualitySummaryResponse(BaseModel):
    """Aggregate statistics on quality statuses, PII, and diagnostic flags."""

    total_records: int
    quality_status_counts: Dict[str, int]
    processing_status_counts: Dict[str, int]
    pii_detected_count: int
    average_quality_score: float
    flag_distribution: Dict[str, int]
