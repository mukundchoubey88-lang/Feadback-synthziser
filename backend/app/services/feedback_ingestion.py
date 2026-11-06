import csv
from datetime import datetime, timezone
import io
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
import uuid

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import InvalidUploadError
from app.models.feedback import Feedback
from app.models.upload_job import UploadJob

logger = logging.getLogger("app.services.ingestion")

REQUIRED_CSV_HEADERS: Set[str] = {"source", "product", "feedback_text", "timestamp"}

ALLOWED_CSV_CONTENT_TYPES: Set[str] = {
    "text/csv",
    "text/plain",
    "application/csv",
    "application/vnd.ms-excel",
    "text/x-csv",
    "application/octet-stream",
}

ALLOWED_JSON_CONTENT_TYPES: Set[str] = {
    "application/json",
    "text/json",
    "application/x-json",
    "text/plain",
    "application/octet-stream",
}


def parse_utc_timestamp(val: Any) -> Optional[datetime]:
    """Parse an ISO 8601 timestamp string into a timezone-aware UTC datetime.

    Strict validation rules:
    - Accepts ISO 8601 strings with explicit UTC indicator ('Z' / 'z') or explicit timezone offset (e.g., '+05:30', '-04:00').
    - Converts accepted timestamps with non-UTC offsets to timezone-aware UTC.
    - Rejects naive timestamps without timezone information (never silently defaults to UTC).
    - Rejects invalid dates, empty values, or malformed strings by returning None.
    """
    if val is None:
        return None

    if isinstance(val, datetime):
        if val.tzinfo is None:
            return None  # Naive datetime object rejected
        return val.astimezone(timezone.utc)

    val_str = str(val).strip()
    if not val_str:
        return None

    # Normalize Z / z to +00:00 for fromisoformat
    if val_str.endswith("Z") or val_str.endswith("z"):
        val_str = val_str[:-1] + "+00:00"

    try:
        dt = datetime.fromisoformat(val_str)
        # Reject naive timestamps that had no timezone offset
        if dt.tzinfo is None:
            return None
        return dt.astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None


def sanitize_str(val: Any, max_len: Optional[int] = None) -> Optional[str]:
    """Trim surrounding whitespace and clamp string length."""
    if val is None:
        return None
    s = str(val).strip()
    if not s:
        return None
    if max_len is not None and len(s) > max_len:
        s = s[:max_len]
    return s


def parse_csv_content(content_str: str, max_records: int) -> List[Dict[str, Any]]:
    """Parse raw CSV text into a list of row dictionaries with header and limit enforcement."""
    try:
        reader = csv.DictReader(io.StringIO(content_str))
        if reader.fieldnames is None:
            return []

        # Normalize and validate required headers
        normalized_headers = [f.strip() if f else "" for f in reader.fieldnames]
        missing_headers = REQUIRED_CSV_HEADERS - set(normalized_headers)
        if missing_headers:
            raise InvalidUploadError(
                f"CSV file is missing required header(s): {', '.join(sorted(missing_headers))}."
            )

        reader.fieldnames = normalized_headers
        rows: List[Dict[str, Any]] = []
        for row in reader:
            # Check if entire row is empty
            if not any(v and str(v).strip() for v in row.values()):
                continue

            # Bounded limit enforcement during row parsing
            if len(rows) >= max_records:
                raise InvalidUploadError(
                    f"Record count exceeds the maximum allowed batch size of {max_records} records."
                )

            rows.append(dict(row))
        return rows
    except InvalidUploadError:
        raise
    except Exception as exc:
        raise InvalidUploadError(f"Malformed CSV content: {exc}")


def parse_json_content(content_str: str, max_records: int) -> List[Dict[str, Any]]:
    """Parse raw JSON text into a list of row dictionaries with limit enforcement."""
    try:
        data = json.loads(content_str)
    except json.JSONDecodeError as exc:
        raise InvalidUploadError(f"Malformed JSON content: {exc.msg} at line {exc.lineno} col {exc.colno}")

    if not isinstance(data, list):
        raise InvalidUploadError("JSON root must be an array of feedback objects.")

    if len(data) > max_records:
        raise InvalidUploadError(
            f"Record count ({len(data)}) exceeds the maximum allowed batch size of {max_records} records."
        )

    rows: List[Dict[str, Any]] = []
    for item in data:
        if not isinstance(item, dict):
            raise InvalidUploadError("Each element in the JSON array must be an object representing feedback.")
        rows.append(item)
    return rows


class FeedbackIngestionService:
    """Service handling feedback ingestion, duplicate detection, and upload job lifecycle."""

    @staticmethod
    def process_upload(
        session: Session,
        filename: str,
        content_bytes: bytes,
        content_type: Optional[str] = None,
    ) -> UploadJob:
        """Process an uploaded feedback file (CSV or JSON), creating a trackable UploadJob.

        Handles validation, duplicate detection, and database persistence atomically.
        """
        # 1. File Extension & Format Validation
        file_ext = Path(filename).suffix.lower()
        if file_ext not in (".csv", ".json"):
            raise InvalidUploadError(
                f"Unsupported file extension '{file_ext}'. Allowed formats are .csv and .json."
            )

        format_type = "csv" if file_ext == ".csv" else "json"

        # 2. Content-Type Validation
        if content_type:
            raw_ct = content_type.split(";")[0].strip().lower()
            if raw_ct and raw_ct != "application/octet-stream":
                if format_type == "csv" and raw_ct not in ALLOWED_CSV_CONTENT_TYPES:
                    raise InvalidUploadError(
                        f"Incompatible Content-Type '{content_type}' for CSV upload."
                    )
                elif format_type == "json" and raw_ct not in ALLOWED_JSON_CONTENT_TYPES:
                    raise InvalidUploadError(
                        f"Incompatible Content-Type '{content_type}' for JSON upload."
                    )

        # 3. File Size Limit Verification
        if len(content_bytes) > settings.MAX_UPLOAD_FILE_SIZE_BYTES:
            raise InvalidUploadError(
                f"File size ({len(content_bytes)} bytes) exceeds the maximum allowed limit of "
                f"{settings.MAX_UPLOAD_FILE_SIZE_BYTES} bytes."
            )

        # 4. Decode UTF-8 (handling BOM)
        try:
            content_str = content_bytes.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise InvalidUploadError(
                f"Invalid file encoding. Files must be UTF-8 or UTF-8 with BOM encoded: {exc}"
            )

        # 5. Initialize and persist the UploadJob record immediately
        job = UploadJob(
            job_id=uuid.uuid4(),
            filename=filename,
            format=format_type,
            status="processing",
            total_records=0,
            inserted_records=0,
            rejected_records=0,
            duplicate_records=0,
            errors=[],
        )
        session.add(job)
        session.commit()

        # 6. Parse rows with bounded limit and header validation
        try:
            if format_type == "csv":
                raw_rows = parse_csv_content(content_str, max_records=settings.MAX_UPLOAD_RECORDS)
            else:
                raw_rows = parse_json_content(content_str, max_records=settings.MAX_UPLOAD_RECORDS)

            job.total_records = len(raw_rows)

            # 7. Row Validation & Ingestion Loop
            inserted_records = 0
            duplicate_records = 0
            rejected_records = 0
            row_errors: List[Dict[str, Any]] = []
            feedback_to_insert: List[Feedback] = []

            # In-memory tracking for intra-batch duplicate detection
            # Key: (source, product, (customer_id or None), timestamp, feedback_text)
            seen_in_batch: Set[Tuple[str, str, Optional[str], datetime, str]] = set()

            for idx, row in enumerate(raw_rows, start=1):
                raw_source = row.get("source")
                raw_product = row.get("product")
                raw_text = row.get("feedback_text")
                raw_timestamp = row.get("timestamp")
                raw_customer_id = row.get("customer_id")
                raw_feature = row.get("feature")
                raw_app_version = row.get("app_version")

                # Field: source (required)
                source = sanitize_str(raw_source, max_len=100)
                if not source:
                    rejected_records += 1
                    row_errors.append({
                        "row": idx,
                        "field": "source",
                        "error": "Field 'source' is required and cannot be empty.",
                        "value": str(raw_source) if raw_source is not None else None,
                    })
                    continue

                # Field: product (required)
                product = sanitize_str(raw_product, max_len=100)
                if not product:
                    rejected_records += 1
                    row_errors.append({
                        "row": idx,
                        "field": "product",
                        "error": "Field 'product' is required and cannot be empty.",
                        "value": str(raw_product) if raw_product is not None else None,
                    })
                    continue

                # Field: feedback_text (required)
                text = sanitize_str(raw_text)
                if not text:
                    rejected_records += 1
                    row_errors.append({
                        "row": idx,
                        "field": "feedback_text",
                        "error": "Field 'feedback_text' is required and cannot be empty.",
                        "value": None,
                    })
                    continue

                if len(text) > settings.MAX_FEEDBACK_TEXT_LENGTH:
                    rejected_records += 1
                    row_errors.append({
                        "row": idx,
                        "field": "feedback_text",
                        "error": f"Field 'feedback_text' exceeds maximum length of {settings.MAX_FEEDBACK_TEXT_LENGTH} chars.",
                        "value": text[:50] + "...",
                    })
                    continue

                # Field: timestamp (required, strict explicit rule)
                ts = parse_utc_timestamp(raw_timestamp)
                if ts is None:
                    rejected_records += 1
                    row_errors.append({
                        "row": idx,
                        "field": "timestamp",
                        "error": "Field 'timestamp' is required and must be an ISO 8601 string with explicit timezone (e.g. '2026-11-01T12:00:00Z' or '+05:30'). Naive timestamps without timezone are rejected.",
                        "value": str(raw_timestamp) if raw_timestamp is not None else None,
                    })
                    continue

                # Optional fields
                customer_id = sanitize_str(raw_customer_id, max_len=255)
                feature = sanitize_str(raw_feature, max_len=100)
                app_version = sanitize_str(raw_app_version, max_len=50)

                # Duplicate Detection Strategy
                # Key includes source to prevent cross-channel feedback collision
                dedup_key = (source, product, customer_id, ts, text)

                # 1. Intra-batch duplicate check
                if dedup_key in seen_in_batch:
                    duplicate_records += 1
                    continue

                # 2. Database duplicate check (active records with matching source, product, customer_id, timestamp, text)
                db_query = session.query(Feedback.feedback_id).filter(
                    Feedback.source == source,
                    Feedback.product == product,
                    Feedback.timestamp == ts,
                    Feedback.feedback_text == text,
                    Feedback.deleted_at.is_(None),
                )
                if customer_id is not None:
                    db_query = db_query.filter(Feedback.customer_id == customer_id)
                else:
                    db_query = db_query.filter(Feedback.customer_id.is_(None))

                if db_query.first() is not None:
                    duplicate_records += 1
                    continue

                # Mark as seen in current batch and stage record
                seen_in_batch.add(dedup_key)

                fb = Feedback(
                    feedback_id=uuid.uuid4(),
                    source=source,
                    customer_id=customer_id,
                    feedback_text=text,
                    product=product,
                    feature=feature,
                    timestamp=ts,
                    app_version=app_version,
                )
                feedback_to_insert.append(fb)
                inserted_records += 1

            # 8. Commit Feedback Batch and Finalize UploadJob
            if feedback_to_insert:
                session.add_all(feedback_to_insert)
                session.flush()

            job.inserted_records = inserted_records
            job.duplicate_records = duplicate_records
            job.rejected_records = rejected_records
            job.errors = row_errors
            job.completed_at = datetime.now(timezone.utc)

            if rejected_records > 0 and inserted_records == 0 and duplicate_records == 0:
                job.status = "failed"
                job.error_summary = "All rows in the upload failed validation."
            elif rejected_records > 0 or duplicate_records > 0:
                job.status = "completed_with_errors"
            else:
                job.status = "completed"

            session.commit()
            return job

        except InvalidUploadError as exc:
            session.rollback()
            try:
                job.status = "failed"
                job.error_summary = exc.message
                job.completed_at = datetime.now(timezone.utc)
                session.commit()
            except Exception:
                session.rollback()
            raise exc

        except Exception as exc:
            session.rollback()
            logger.exception("Unexpected error during feedback upload job %s: %s", job.job_id, exc)
            try:
                job.status = "failed"
                job.error_summary = "An unexpected error occurred during file ingestion."
                job.completed_at = datetime.now(timezone.utc)
                session.commit()
            except Exception:
                session.rollback()
            raise exc

    @staticmethod
    def list_feedback(
        session: Session,
        page: int = 1,
        page_size: int = 50,
        product: Optional[str] = None,
        source: Optional[str] = None,
    ) -> Tuple[List[Feedback], int, int]:
        """List active feedback records with pagination and optional filtering."""
        query = session.query(Feedback).filter(Feedback.deleted_at.is_(None))

        if product:
            query = query.filter(Feedback.product == product.strip())
        if source:
            query = query.filter(Feedback.source == source.strip())

        total = query.count()
        total_pages = (total + page_size - 1) // page_size if total > 0 else 0

        items = (
            query.order_by(Feedback.timestamp.desc(), Feedback.feedback_id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return items, total, total_pages

    @staticmethod
    def get_feedback_by_id(session: Session, feedback_id: uuid.UUID) -> Optional[Feedback]:
        """Fetch a single active feedback record by UUID."""
        return (
            session.query(Feedback)
            .filter(Feedback.feedback_id == feedback_id, Feedback.deleted_at.is_(None))
            .first()
        )

    @staticmethod
    def get_upload_job_by_id(session: Session, job_id: uuid.UUID) -> Optional[UploadJob]:
        """Fetch an upload job record by UUID."""
        return session.query(UploadJob).filter(UploadJob.job_id == job_id).first()
