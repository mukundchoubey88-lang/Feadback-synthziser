from datetime import datetime
from typing import Optional
import uuid
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import AppException, EntityNotFoundError, InvalidUploadError, PayloadTooLargeError
from app.db.session import get_db
from app.schemas.classification import (
    BatchClassificationRequest,
    BatchClassificationResponse,
    ClassificationSummaryResponse,
    FeedbackClassificationRecord,
)
from app.schemas.embedding import (
    BatchEmbeddingRequest,
    BatchEmbeddingResponse,
    EmbeddingItemResult,
)
from app.models.feedback import Feedback
from datetime import timezone
from app.schemas.feedback import (
    FeedbackCreateRequest,
    BatchCleanResponse,
    FeedbackPaginationResponse,
    FeedbackQualityResponse,
    FeedbackResponse,
    QualitySummaryResponse,
    UploadJobResponse,
    UploadResponse,
)
from app.services.feedback_ingestion import FeedbackIngestionService
from app.services.feedback_cleaning import FeedbackCleaningService
from app.services.feedback_classification import FeedbackClassificationService
from app.services.embedding_service import EmbeddingService

router = APIRouter()

UPLOAD_CHUNK_SIZE = 64 * 1024  # 64 KB chunk size


async def read_bounded_file(file: UploadFile, max_bytes: int) -> bytes:
    """Read upload stream incrementally, terminating early if size ceiling is exceeded."""
    chunks: list[bytes] = []
    total_bytes = 0
    try:
        while True:
            chunk = await file.read(UPLOAD_CHUNK_SIZE)
            if not chunk:
                break
            total_bytes += len(chunk)
            if total_bytes > max_bytes:
                raise PayloadTooLargeError(
                    f"Uploaded file exceeds maximum allowed size limit of {max_bytes} bytes."
                )
            chunks.append(chunk)
    finally:
        await file.close()

    if total_bytes == 0:
        raise InvalidUploadError("Uploaded file is empty.")
    return b"".join(chunks)


@router.post(
    "/upload",
    response_model=UploadResponse,
    status_code=status.HTTP_200_OK,
    summary="Upload Feedback Dataset",
    description="Accepts CSV or JSON files via multipart/form-data, validates schema, prevents duplicates, and records an ingestion job.",
)
async def upload_feedback_file(
    file: UploadFile = File(..., description="CSV or JSON dataset file containing feedback records"),
    session: Session = Depends(get_db),
) -> UploadResponse:
    """Process multipart feedback file upload synchronously with bounded memory and atomic tracking."""
    if not file.filename:
        raise InvalidUploadError("Uploaded file must have a valid filename.")

    content_bytes = await read_bounded_file(file, settings.MAX_UPLOAD_FILE_SIZE_BYTES)

    try:
        job = FeedbackIngestionService.process_upload(
            session=session,
            filename=file.filename,
            content_bytes=content_bytes,
            content_type=file.content_type,
        )
    except AppException:
        raise
    except Exception as exc:
        raise AppException(
            message=f"Database or ingestion processing failure: {exc}",
            status_code=500,
            code="INTERNAL_SERVER_ERROR",
        )

    if job.status == "completed":
        message = f"Successfully ingested {job.inserted_records} feedback records."
    elif job.status == "completed_with_errors":
        message = (
            f"Ingestion completed with warnings: {job.inserted_records} inserted, "
            f"{job.duplicate_records} duplicates skipped, {job.rejected_records} rejected."
        )
    else:
        message = f"Ingestion failed: {job.error_summary or 'All records were rejected.'}"

    return UploadResponse(
        job_id=job.job_id,
        status=job.status,
        filename=job.filename,
        total_records=job.total_records,
        inserted_records=job.inserted_records,
        duplicate_records=job.duplicate_records,
        rejected_records=job.rejected_records,
        errors=job.errors,
        message=message,
    )


@router.get(
    "",
    response_model=FeedbackPaginationResponse,
    summary="List Feedback",
    description="Retrieve paginated list of active feedback records with optional filtering by product and source.",
)
def list_feedback(
    page: int = Query(1, ge=1, description="Page number, 1-indexed"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    product: Optional[str] = Query(None, description="Filter by product name"),
    source: Optional[str] = Query(None, description="Filter by feedback source"),
    session: Session = Depends(get_db),
) -> FeedbackPaginationResponse:
    """List active feedback ordered newest first."""
    items, total, total_pages = FeedbackIngestionService.list_feedback(
        session=session,
        page=page,
        page_size=page_size,
        product=product,
        source=source,
    )
    return FeedbackPaginationResponse(
        items=[FeedbackResponse.model_validate(fb) for fb in items],
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@router.post(
    "",
    response_model=FeedbackResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit Single Feedback Record",
    description="Directly submit an individual customer feedback record.",
)
def create_feedback(
    payload: FeedbackCreateRequest,
    session: Session = Depends(get_db),
) -> FeedbackResponse:
    """Create single feedback item."""
    fb = Feedback(
        product=payload.product,
        feedback_text=payload.feedback_text,
        source=payload.source,
        feature=payload.feature,
        app_version=payload.app_version,
        customer_id=payload.customer_id,
        timestamp=payload.timestamp or datetime.now(timezone.utc),
        quality_status="pending",
        processing_status="unprocessed",
    )
    session.add(fb)
    session.commit()
    session.refresh(fb)
    return FeedbackResponse.model_validate(fb)


@router.get(
    "/jobs/{job_id}",
    response_model=UploadJobResponse,
    summary="Get Ingestion Job Status",
    description="Retrieve status, record counts, and diagnostics for an upload job.",
)
def get_upload_job(
    job_id: uuid.UUID,
    session: Session = Depends(get_db),
) -> UploadJobResponse:
    """Retrieve detailed upload job state."""
    job = FeedbackIngestionService.get_upload_job_by_id(session, job_id)
    if job is None:
        raise EntityNotFoundError(f"Upload job '{job_id}' was not found.")
    return UploadJobResponse.model_validate(job)


@router.post(
    "/clean",
    response_model=BatchCleanResponse,
    summary="Batch Clean Feedback",
    description="Run text normalization, PII redaction, spam detection, and quality scoring over a bounded batch of feedback records.",
)
def clean_feedback_batch(
    limit: int = Query(50, ge=1, le=500, description="Maximum number of records to process in batch"),
    reprocess: bool = Query(False, description="Reprocess already cleaned records if true"),
    product: Optional[str] = Query(None, description="Optional product filter"),
    session: Session = Depends(get_db),
) -> BatchCleanResponse:
    """Execute batch data cleaning pipeline."""
    result = FeedbackCleaningService.clean_feedback_batch(
        session=session,
        limit=limit,
        reprocess=reprocess,
        product=product,
    )
    return BatchCleanResponse(**result)


@router.get(
    "/quality/summary",
    response_model=QualitySummaryResponse,
    summary="Data Quality and PII Summary",
    description="Retrieve aggregate distributions of quality statuses, average score, PII counts, and diagnostic flags.",
)
def get_quality_summary(
    product: Optional[str] = Query(None, description="Optional product filter"),
    session: Session = Depends(get_db),
) -> QualitySummaryResponse:
    """Retrieve quality statistics across feedback datasets."""
    stats = FeedbackCleaningService.get_quality_summary(session=session, product=product)
    return QualitySummaryResponse(**stats)


@router.get(
    "/{feedback_id}",
    response_model=FeedbackResponse,
    summary="Get Feedback by ID",
    description="Retrieve a single active feedback record by its UUID.",
)
def get_feedback(
    feedback_id: uuid.UUID,
    session: Session = Depends(get_db),
) -> FeedbackResponse:
    """Retrieve feedback record details by UUID."""
    feedback = FeedbackIngestionService.get_feedback_by_id(session, feedback_id)
    if feedback is None:
        raise EntityNotFoundError(f"Feedback record '{feedback_id}' was not found.")
    return FeedbackResponse.model_validate(feedback)


@router.post(
    "/{feedback_id}/clean",
    response_model=FeedbackResponse,
    summary="Clean Single Feedback Record",
    description="Run the data cleaning pipeline deterministically on an individual feedback record.",
)
def clean_single_feedback(
    feedback_id: uuid.UUID,
    reprocess: bool = Query(False, description="Force reprocessing if already cleaned"),
    session: Session = Depends(get_db),
) -> FeedbackResponse:
    """Clean a single feedback item and update its quality metadata."""
    feedback = FeedbackIngestionService.get_feedback_by_id(session, feedback_id)
    if feedback is None:
        raise EntityNotFoundError(f"Feedback record '{feedback_id}' was not found.")

    FeedbackCleaningService.clean_single_record(feedback, reprocess=reprocess)
    session.commit()
    return FeedbackResponse.model_validate(feedback)


@router.get(
    "/{feedback_id}/quality",
    response_model=FeedbackQualityResponse,
    summary="Get Feedback Quality Inspection",
    description="Retrieve detailed quality score, flags, and PII status for a feedback record.",
)
def get_feedback_quality(
    feedback_id: uuid.UUID,
    session: Session = Depends(get_db),
) -> FeedbackQualityResponse:
    """Retrieve detailed quality diagnostics for a feedback record."""
    feedback = FeedbackIngestionService.get_feedback_by_id(session, feedback_id)
    if feedback is None:
        raise EntityNotFoundError(f"Feedback record '{feedback_id}' was not found.")

    return FeedbackQualityResponse(
        feedback_id=feedback.feedback_id,
        original_feedback_text=feedback.feedback_text,
        cleaned_feedback_text=feedback.cleaned_feedback_text,
        quality_status=feedback.quality_status,
        quality_score=feedback.quality_score,
        content_quality_score=feedback.content_quality_score,
        metadata_completeness_score=feedback.metadata_completeness_score,
        quality_flags=feedback.quality_flags,
        pii_detected=feedback.pii_detected,
        pii_types=feedback.pii_types,
        cleaning_version=feedback.cleaning_version,
        cleaned_at=feedback.cleaned_at,
        processing_status=feedback.processing_status,
        processing_error=feedback.processing_error,
    )


# --- Classification & Sentiment Analysis Endpoints (Part 6) ---


@router.post(
    "/classify",
    response_model=BatchClassificationResponse,
    status_code=status.HTTP_200_OK,
    summary="Batch Classify Feedback Records",
    description="Run multi-topic classification, aspect-based sentiment analysis, and intent detection over a bounded batch of feedback records.",
)
async def classify_feedback_batch(
    payload: BatchClassificationRequest,
    session: Session = Depends(get_db),
) -> BatchClassificationResponse:
    """Execute AI classification on a bounded batch of feedback records with isolated per-record error handling."""
    if len(payload.feedback_ids) > settings.MAX_CLASSIFICATION_BATCH_SIZE:
        raise AppException(
            message=f"Batch size {len(payload.feedback_ids)} exceeds maximum allowed limit of {settings.MAX_CLASSIFICATION_BATCH_SIZE}.",
            status_code=status.HTTP_400_BAD_REQUEST,
            code="BATCH_TOO_LARGE",
        )

    return await FeedbackClassificationService.classify_batch(
        session=session,
        feedback_ids=payload.feedback_ids,
        reprocess=payload.reprocess,
        max_batch_size=settings.MAX_CLASSIFICATION_BATCH_SIZE,
    )


@router.post(
    "/{feedback_id}/classify",
    response_model=FeedbackClassificationRecord,
    status_code=status.HTTP_200_OK,
    summary="Classify Individual Feedback Record",
    description="Execute AI classification, aspect-based sentiment, and dual persistence on an individual feedback record.",
)
async def classify_single_feedback(
    feedback_id: uuid.UUID,
    reprocess: bool = Query(False, description="Force reclassification if already classified under current version"),
    session: Session = Depends(get_db),
) -> FeedbackClassificationRecord:
    """Classify a single feedback record with grounding verification and atomic dual persistence."""
    try:
        return await FeedbackClassificationService.classify_single_record(
            session=session,
            feedback_id=feedback_id,
            reprocess=reprocess,
        )
    except AppException:
        raise
    except Exception as exc:
        raise AppException(
            message="An unexpected error occurred during classification. Please try again later.",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            code="INTERNAL_SERVER_ERROR",
        )


@router.get(
    "/{feedback_id}/classification",
    response_model=FeedbackClassificationRecord,
    status_code=status.HTTP_200_OK,
    summary="Get Latest Feedback Classification",
    description="Retrieve the latest persisted classification, aspects, topics, and intent for a feedback item.",
)
def get_feedback_classification(
    feedback_id: uuid.UUID,
    session: Session = Depends(get_db),
) -> FeedbackClassificationRecord:
    """Retrieve the latest classification result for a feedback item by UUID."""
    return FeedbackClassificationService.get_latest_classification(
        session=session,
        feedback_id=feedback_id,
    )


@router.get(
    "/classifications/summary",
    response_model=ClassificationSummaryResponse,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
def get_feedback_classifications_summary_alias(
    product: Optional[str] = Query(None, description="Optional product filter"),
    start_date: Optional[str] = Query(None, description="Optional start timestamp filter"),
    end_date: Optional[str] = Query(None, description="Optional end timestamp filter"),
    session: Session = Depends(get_db),
) -> ClassificationSummaryResponse:
    """Alias for /api/classifications/summary."""
    from app.api.routes.classification import parse_iso_datetime

    return FeedbackClassificationService.get_classification_summary(
        session=session,
        product=product,
        start_date=parse_iso_datetime(start_date),
        end_date=parse_iso_datetime(end_date),
    )


@router.post(
    "/embed",
    response_model=BatchEmbeddingResponse,
    status_code=status.HTTP_200_OK,
    summary="Batch Generate Feedback Embeddings",
    description="Generate and persist embeddings for a bounded batch of feedback records using cleaned text.",
)
async def embed_feedback_batch(
    payload: BatchEmbeddingRequest,
    session: Session = Depends(get_db),
) -> BatchEmbeddingResponse:
    """Generate, validate, and persist embeddings for a bounded batch of feedback records."""
    return await EmbeddingService.embed_batch(
        session=session,
        feedback_ids=payload.feedback_ids,
        dimensions=payload.dimensions,
        force_refresh=payload.force_refresh,
    )


@router.post(
    "/{feedback_id}/embed",
    response_model=EmbeddingItemResult,
    status_code=status.HTTP_200_OK,
    summary="Generate Individual Feedback Embedding",
    description="Generate, validate, and persist an embedding for an individual feedback record.",
)
async def embed_single_feedback(
    feedback_id: uuid.UUID,
    force_refresh: bool = Query(False, description="Force re-embedding even if cached hash matches"),
    session: Session = Depends(get_db),
) -> EmbeddingItemResult:
    """Generate and persist an embedding for an individual feedback record."""
    return await EmbeddingService.embed_single_feedback(
        session=session,
        feedback_id=feedback_id,
        force_refresh=force_refresh,
    )
