from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
import uuid

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.feedback import Feedback
from app.services.text_normalization import normalize_text
from app.services.pii_detector import PIIDetector
from app.services.spam_detector import SpamAndQualityDetector
from app.services.quality_scorer import QualityScorer

logger = logging.getLogger("app.services.cleaning")

CURRENT_CLEANING_VERSION = "1.0.0"


class FeedbackCleaningService:
    """Service orchestrating text normalization, PII redaction, spam filtering, and quality scoring."""

    @classmethod
    def clean_single_record(
        cls,
        feedback: Feedback,
        reprocess: bool = False,
        version: str = CURRENT_CLEANING_VERSION,
    ) -> Feedback:
        """Run the data cleaning pipeline deterministically on a single feedback record.

        Critical Invariant:
        The original `feedback.feedback_text` is NEVER modified or overwritten.
        """
        # Idempotency check: skip if already cleaned under this version unless reprocess is requested
        if feedback.processing_status == "processed" and feedback.cleaning_version == version and not reprocess:
            return feedback

        try:
            # 1. Text Normalization
            normalized_text = normalize_text(feedback.feedback_text)

            # 2. PII Detection and Redaction
            redacted_text, pii_detected, pii_types = PIIDetector.redact_pii(normalized_text)

            # 3. Spam & Quality Assessment
            quality_status, quality_flags = SpamAndQualityDetector.assess_quality(
                text=redacted_text,
                original_raw_text=feedback.feedback_text,
            )

            if pii_detected:
                quality_flags.append("PII_PRESENT")

            # 4. Metadata Deductions & Flags
            has_customer_id = bool(feedback.customer_id and feedback.customer_id.strip())
            has_feature = bool(feedback.feature and feedback.feature.strip())
            has_app_version = bool(feedback.app_version and feedback.app_version.strip())

            if not has_customer_id:
                quality_flags.append("MISSING_CUSTOMER_ID")
            if not has_feature:
                quality_flags.append("MISSING_FEATURE")
            if not has_app_version:
                quality_flags.append("MISSING_APP_VERSION")

            # Deduplicate flags while preserving stable sorted order
            quality_flags = sorted(list(set(quality_flags)))

            # 5. Data Quality Scoring (Content Quality vs. Metadata Completeness)
            overall_score, content_score, meta_score = QualityScorer.calculate_score(
                text=redacted_text,
                quality_status=quality_status,
                quality_flags=quality_flags,
                has_customer_id=has_customer_id,
                has_feature=has_feature,
                has_app_version=has_app_version,
            )

            # 6. Persist results in processed columns
            feedback.cleaned_feedback_text = redacted_text
            feedback.quality_status = quality_status
            feedback.quality_score = overall_score
            feedback.content_quality_score = content_score
            feedback.metadata_completeness_score = meta_score
            feedback.quality_flags = quality_flags
            feedback.pii_detected = pii_detected
            feedback.pii_types = pii_types
            feedback.cleaning_version = version
            feedback.cleaned_at = datetime.now(timezone.utc)
            feedback.processing_status = "processed"
            feedback.processing_error = None

            return feedback

        except Exception as exc:
            logger.exception("Error executing cleaning pipeline on feedback %s: %s", feedback.feedback_id, exc)
            feedback.processing_status = "failed"
            feedback.quality_status = "failed"
            feedback.processing_error = f"Cleaning pipeline error: {exc}"
            return feedback

    @classmethod
    def clean_feedback_batch(
        cls,
        session: Session,
        limit: int = 50,
        reprocess: bool = False,
        product: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Process a bounded batch of feedback records atomically with row-level concurrency protection."""
        query = session.query(Feedback).filter(Feedback.deleted_at.is_(None))

        if product:
            query = query.filter(Feedback.product == product.strip())

        if not reprocess:
            query = query.filter(Feedback.processing_status != "processed")

        # In PostgreSQL environments, acquire row-level locks with SKIP LOCKED to prevent duplicate processing
        bind = session.get_bind()
        if bind is not None and bind.dialect.name == "postgresql":
            query = query.with_for_update(skip_locked=True)

        # Bounded query
        records: List[Feedback] = query.order_by(Feedback.created_at.asc()).limit(limit).all()

        processed = 0
        skipped = 0
        clean_count = 0
        flagged_count = 0
        rejected_count = 0
        failed_count = 0

        for fb in records:
            try:
                cls.clean_single_record(fb, reprocess=reprocess)

                if fb.processing_status == "processed":
                    processed += 1
                    if fb.quality_status == "clean":
                        clean_count += 1
                    elif fb.quality_status == "flagged":
                        flagged_count += 1
                    elif fb.quality_status == "rejected":
                        rejected_count += 1
                elif fb.processing_status == "failed":
                    failed_count += 1
                else:
                    skipped += 1
            except Exception as exc:
                logger.exception("Error processing feedback record %s in batch: %s", fb.feedback_id, exc)
                fb.processing_status = "failed"
                fb.quality_status = "failed"
                fb.processing_error = str(exc)
                failed_count += 1

        session.commit()

        return {
            "total_considered": len(records),
            "processed": processed,
            "skipped": skipped,
            "clean_count": clean_count,
            "flagged_count": flagged_count,
            "rejected_count": rejected_count,
            "failed_count": failed_count,
        }

    @classmethod
    def get_quality_summary(
        cls,
        session: Session,
        product: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Calculate aggregate quality, PII, and flag distributions using SQL aggregations."""
        query = session.query(Feedback).filter(Feedback.deleted_at.is_(None))
        if product:
            query = query.filter(Feedback.product == product.strip())

        # 1. Total records (COUNT)
        total = query.with_entities(func.count(Feedback.feedback_id)).scalar() or 0

        # 2. Quality status counts (GROUP BY)
        status_counts: Dict[str, int] = {
            "pending": 0,
            "clean": 0,
            "flagged": 0,
            "rejected": 0,
            "failed": 0,
        }
        for st, count in query.with_entities(Feedback.quality_status, func.count(Feedback.feedback_id)).group_by(Feedback.quality_status).all():
            if st in status_counts:
                status_counts[st] = count
            else:
                status_counts[st] = count

        # 3. Processing status counts (GROUP BY)
        processing_counts: Dict[str, int] = {
            "unprocessed": 0,
            "processing": 0,
            "processed": 0,
            "failed": 0,
        }
        for ps, count in query.with_entities(Feedback.processing_status, func.count(Feedback.feedback_id)).group_by(Feedback.processing_status).all():
            if ps in processing_counts:
                processing_counts[ps] = count
            else:
                processing_counts[ps] = count

        # 4. PII detected count (COUNT with filter)
        pii_count = (
            query.filter(Feedback.pii_detected.is_(True))
            .with_entities(func.count(Feedback.feedback_id))
            .scalar()
            or 0
        )

        # 5. Average quality score (SQL AVG)
        avg_score_raw = (
            query.filter(Feedback.quality_score.isnot(None))
            .with_entities(func.avg(Feedback.quality_score))
            .scalar()
        )
        avg_score = round(float(avg_score_raw), 1) if avg_score_raw is not None else 0.0

        # 6. Flag distribution (fetches only the JSON flag list column, avoiding loading full entity or large text)
        flag_distribution: Dict[str, int] = {}
        flags_records = (
            query.filter(Feedback.quality_flags.isnot(None))
            .with_entities(Feedback.quality_flags)
            .all()
        )
        for (flags_list,) in flags_records:
            if flags_list:
                for fl in flags_list:
                    flag_distribution[fl] = flag_distribution.get(fl, 0) + 1

        return {
            "total_records": total,
            "quality_status_counts": status_counts,
            "processing_status_counts": processing_counts,
            "pii_detected_count": pii_count,
            "average_quality_score": avg_score,
            "flag_distribution": flag_distribution,
        }
