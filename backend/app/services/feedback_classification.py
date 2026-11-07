"""Feedback Classification and Sentiment Analysis Service.

Coordinates AI-driven multi-topic classification, aspect-based sentiment analysis,
evidence grounding verification, low-confidence review policies, and atomic dual
persistence to FeedbackClassification and SentimentHistory.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
import uuid
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import AppException, EntityNotFoundError
from app.integrations.ai.manager import AIProviderManager
from app.integrations.ai.schemas import AIRequest, AIResponse
from app.models.classification import FeedbackClassification
from app.models.feedback import Feedback
from app.models.sentiment import SentimentHistory
from app.schemas.classification import (
    BatchClassificationResponse,
    ClassificationItemError,
    ClassificationSummaryResponse,
    FeedbackClassificationLLMOutput,
    FeedbackClassificationRecord,
    OverallSentiment,
    ReviewReason,
)
from app.services.classification_prompts import (
    PROMPT_VERSION,
    build_classification_prompt,
)
from app.services.feedback_cleaning import FeedbackCleaningService

logger = logging.getLogger("feedback_classification_service")

CURRENT_CLASSIFICATION_VERSION = PROMPT_VERSION  # "v1.0.0"
DEFAULT_LOW_CONFIDENCE_THRESHOLD = 0.70
MAX_BATCH_SIZE = 50
VALID_CLASSIFICATION_STATUSES = ("classified", "pending_review")


def verify_evidence_grounding(evidence: str, source_text: str) -> bool:
    """Verify that an aspect evidence excerpt is genuinely grounded in the source text.

    Performs whitespace-collapsed, case-insensitive substring checking.
    """
    if not evidence or not source_text:
        return False
    norm_evidence = " ".join(evidence.strip().lower().split())
    norm_source = " ".join(source_text.strip().lower().split())
    return norm_evidence in norm_source


class FeedbackClassificationService:
    """Service orchestrating AI classification and atomic dual persistence."""

    @classmethod
    async def classify_single_record(
        cls,
        session: Session,
        feedback_id: uuid.UUID,
        provider_manager: Optional[AIProviderManager] = None,
        reprocess: bool = False,
        low_confidence_threshold: float = DEFAULT_LOW_CONFIDENCE_THRESHOLD,
    ) -> FeedbackClassificationRecord:
        """Classify a single feedback record with evidence grounding and atomic persistence.

        Args:
            session: SQLAlchemy database session.
            feedback_id: UUID of the target feedback record.
            provider_manager: AIProviderManager instance (or default if None).
            reprocess: If True, forces reclassification if already classified at current version.
            low_confidence_threshold: Threshold below which classifications require human review.

        Returns:
            FeedbackClassificationRecord representation of persisted classification.
        """
        feedback = session.get(Feedback, feedback_id)
        if feedback is None:
            raise EntityNotFoundError(f"Feedback record '{feedback_id}' was not found.")

        if feedback.deleted_at is not None:
            raise AppException(
                message=f"Cannot classify soft-deleted feedback record '{feedback_id}'.",
                status_code=400,
                code="FEEDBACK_DELETED",
            )

        # Gatekeeper: check quality status and cleaned text availability
        if feedback.quality_status in ("rejected", "failed"):
            raise AppException(
                message=f"Feedback record '{feedback_id}' has quality_status='{feedback.quality_status}' and cannot be classified.",
                status_code=422,
                code="UNSUITABLE_QUALITY_STATUS",
            )

        # Policy: if cleaned text is missing, handle safely without silently bypassing Part 4
        if not feedback.cleaned_feedback_text or not feedback.cleaned_feedback_text.strip():
            if feedback.quality_status == "pending":
                logger.info("Feedback '%s' has pending quality; triggering deterministic cleaning", feedback_id)
                FeedbackCleaningService.clean_single_record(feedback)
                session.flush()

            if (
                feedback.quality_status in ("rejected", "failed")
                or not feedback.cleaned_feedback_text
                or not feedback.cleaned_feedback_text.strip()
            ):
                raise AppException(
                    message=f"Feedback record '{feedback_id}' has no cleaned text available for classification (quality_status='{feedback.quality_status}').",
                    status_code=422,
                    code="UNSUITABLE_FEEDBACK_TEXT",
                )

        source_text = feedback.cleaned_feedback_text

        # Check existing classification for current version
        existing_stmt = (
            select(FeedbackClassification)
            .where(
                FeedbackClassification.feedback_id == feedback_id,
                FeedbackClassification.classification_version == CURRENT_CLASSIFICATION_VERSION,
                FeedbackClassification.status.in_(VALID_CLASSIFICATION_STATUSES),
            )
            .order_by(FeedbackClassification.run_number.desc())
            .limit(1)
        )
        existing = session.execute(existing_stmt).scalar_one_or_none()

        if existing is not None and not reprocess:
            logger.info(
                "Feedback '%s' already classified at version '%s' (run %s); returning existing",
                feedback_id,
                CURRENT_CLASSIFICATION_VERSION,
                existing.run_number,
            )
            return FeedbackClassificationRecord.model_validate(existing)

        # Build injection-shielded prompt
        system_instruction, user_prompt = build_classification_prompt(
            feedback_text=source_text,
            product_context=feedback.product,
            feature_context=feedback.feature,
            app_version_context=feedback.app_version,
        )

        manager = provider_manager or AIProviderManager()
        req = AIRequest(
            prompt=user_prompt,
            system_instruction=system_instruction,
            response_schema=FeedbackClassificationLLMOutput,
            correlation_id=f"classify-{feedback_id}",
        )

        ai_response: AIResponse = await manager.generate(req)
        llm_output: FeedbackClassificationLLMOutput = ai_response.structured_data  # Guaranteed valid

        # Evidence Grounding Verification
        needs_review = llm_output.needs_review
        review_reason = llm_output.review_reason
        effective_confidence = llm_output.confidence_score

        ungrounded_aspects = []
        for asp in llm_output.aspects:
            if not verify_evidence_grounding(asp.evidence, source_text):
                ungrounded_aspects.append(asp.aspect)

        if ungrounded_aspects:
            needs_review = True
            ungrounded_msg = f"ungrounded_evidence: [{', '.join(ungrounded_aspects)}]"
            review_reason = f"{review_reason}; {ungrounded_msg}" if review_reason else ungrounded_msg
            effective_confidence = min(effective_confidence, 0.50)
            logger.warning(
                "Classification for '%s' contains %d ungrounded aspect evidence excerpt(s). Flagged for review.",
                feedback_id,
                len(ungrounded_aspects),
            )

        # Low-Confidence & Ambiguity Review Policy
        if effective_confidence < low_confidence_threshold:
            needs_review = True
            if not review_reason:
                review_reason = ReviewReason.LOW_CONFIDENCE.value

        if llm_output.overall_sentiment == OverallSentiment.MIXED:
            needs_review = True
            if not review_reason:
                review_reason = ReviewReason.MIXED_SIGNALS.value

        # Prepare JSON structures
        topics_json = [t.model_dump() for t in llm_output.topics] if llm_output.topics else None
        aspects_json = [a.model_dump() for a in llm_output.aspects] if llm_output.aspects else None
        pain_points_json = llm_output.pain_points if llm_output.pain_points else None
        keywords_json = llm_output.keywords if llm_output.keywords else None
        token_usage_json = ai_response.usage.model_dump() if ai_response.usage else None

        now = datetime.now(timezone.utc)
        max_persist_retries = 5
        classification_record = None

        for attempt in range(max_persist_retries):
            try:
                # 1. Row-level lock on the Feedback row (PostgreSQL serialization)
                # In PostgreSQL, with_for_update() serializes concurrent reclassifications of the same feedback item.
                # In SQLite, with_for_update() is safely ignored by the dialect without error.
                try:
                    session.execute(
                        select(Feedback.feedback_id)
                        .where(Feedback.feedback_id == feedback_id)
                        .with_for_update()
                    )
                except Exception:
                    # Ignore if the dialect or test session does not support row locking
                    pass

                # 2. Determine sequential execution run index per (feedback_id, classification_version)
                max_run = session.execute(
                    select(func.coalesce(func.max(FeedbackClassification.run_number), 0)).where(
                        FeedbackClassification.feedback_id == feedback_id,
                        FeedbackClassification.classification_version == CURRENT_CLASSIFICATION_VERSION,
                    )
                ).scalar() or 0
                new_run_number = max_run + 1

                # 3. Construct records for atomic dual persistence
                classification_record = FeedbackClassification(
                    classification_id=uuid.uuid4(),
                    feedback_id=feedback.feedback_id,
                    classification_version=CURRENT_CLASSIFICATION_VERSION,
                    run_number=new_run_number,
                    status="classified",
                    overall_sentiment=llm_output.overall_sentiment.value,
                    sentiment_score=llm_output.sentiment_score,
                    sentiment_intensity=llm_output.sentiment_intensity.value,
                    customer_intent=llm_output.customer_intent.value,
                    identified_product=llm_output.product,
                    identified_feature=llm_output.feature,
                    topics=topics_json,
                    aspects=aspects_json,
                    pain_points=pain_points_json,
                    keywords=keywords_json,
                    confidence_score=effective_confidence,
                    needs_review=needs_review,
                    review_reason=review_reason,
                    provider=ai_response.provider,
                    model=ai_response.model,
                    latency_ms=ai_response.latency_ms,
                    token_usage=token_usage_json,
                    error_message=None,
                    classified_at=now,
                )

                sentiment_record = SentimentHistory(
                    sentiment_id=uuid.uuid4(),
                    feedback_id=feedback.feedback_id,
                    theme_id=None,
                    sentiment_label=llm_output.overall_sentiment.value,
                    sentiment_score=llm_output.sentiment_score,
                    confidence_score=effective_confidence,
                    analysed_at=now,
                )

                session.add(classification_record)
                session.add(sentiment_record)

                # 4. Atomic Commit
                session.commit()
                session.refresh(classification_record)
                break

            except IntegrityError as ie:
                # Rollback immediately to clear pending objects and prevent orphaned records
                session.rollback()
                err_msg = str(ie).lower()
                is_unique_collision = (
                    "uq_feedback_classifications_feedback_version_run" in err_msg
                    or "unique constraint" in err_msg
                    or "unique" in err_msg
                )
                if is_unique_collision and attempt < max_persist_retries - 1:
                    logger.warning(
                        "Concurrent reclassification collision for feedback '%s' on attempt %d/%d; retrying run_number allocation",
                        feedback_id,
                        attempt + 1,
                        max_persist_retries,
                    )
                    continue
                else:
                    logger.error(
                        "Integrity error persisting classification for feedback '%s' on attempt %d: %s",
                        feedback_id,
                        attempt + 1,
                        ie,
                    )
                    raise AppException(
                        message=f"Concurrent reclassification conflict for feedback '{feedback_id}'. Please retry.",
                        status_code=409,
                        code="CONCURRENT_RECLASSIFICATION_CONFLICT",
                    ) from ie
            except Exception:
                session.rollback()
                raise

        if classification_record is None:
            raise AppException(
                message=f"Failed to allocate run_number for feedback '{feedback_id}' after {max_persist_retries} attempts.",
                status_code=409,
                code="CONCURRENT_RECLASSIFICATION_FAILED",
            )

        logger.info(
            "Feedback '%s' successfully classified [sentiment=%s, intent=%s, provider=%s, review=%s]",
            feedback_id,
            classification_record.overall_sentiment,
            classification_record.customer_intent,
            classification_record.provider,
            classification_record.needs_review,
        )

        return FeedbackClassificationRecord.model_validate(classification_record)

    @classmethod
    async def classify_batch(
        cls,
        session: Session,
        feedback_ids: List[uuid.UUID],
        provider_manager: Optional[AIProviderManager] = None,
        reprocess: bool = False,
        max_batch_size: int = MAX_BATCH_SIZE,
        low_confidence_threshold: float = DEFAULT_LOW_CONFIDENCE_THRESHOLD,
    ) -> BatchClassificationResponse:
        """Classify a batch of feedback records with isolated record-level failure boundaries.

        Args:
            session: SQLAlchemy database session.
            feedback_ids: List of target feedback UUIDs.
            provider_manager: Optional AIProviderManager.
            reprocess: Whether to force reclassification of previously processed items.
            max_batch_size: Ceiling for batch size to prevent unbounded asynchronous loads.
            low_confidence_threshold: Heuristic review threshold.

        Returns:
            BatchClassificationResponse with detailed results and isolated item errors.
        """
        if len(feedback_ids) > max_batch_size:
            raise AppException(
                message=f"Batch size {len(feedback_ids)} exceeds maximum allowed limit of {max_batch_size}.",
                status_code=400,
                code="BATCH_TOO_LARGE",
            )

        results: List[FeedbackClassificationRecord] = []
        errors: List[ClassificationItemError] = []
        skipped_count = 0

        for fid in feedback_ids:
            try:
                rec = await cls.classify_single_record(
                    session=session,
                    feedback_id=fid,
                    provider_manager=provider_manager,
                    reprocess=reprocess,
                    low_confidence_threshold=low_confidence_threshold,
                )
                results.append(rec)
            except AppException as ae:
                session.rollback()
                logger.warning("Record-level failure on feedback '%s': %s", fid, str(ae))
                errors.append(ClassificationItemError(feedback_id=fid, error=str(ae)))
            except Exception as e:
                session.rollback()
                logger.error("Unexpected failure on feedback '%s': %s", fid, str(e))
                errors.append(ClassificationItemError(feedback_id=fid, error=str(e)))

        return BatchClassificationResponse(
            total_requested=len(feedback_ids),
            successful_count=len(results),
            failed_count=len(errors),
            skipped_count=skipped_count,
            results=results,
            errors=errors,
        )

    @classmethod
    def get_latest_classification(
        cls,
        session: Session,
        feedback_id: uuid.UUID,
    ) -> FeedbackClassificationRecord:
        """Retrieve the latest valid classification record for a given feedback item.

        Considers 'classified' and 'pending_review' as valid statuses.
        Failed attempts never hide a previous valid classification.
        Uses deterministic ordering by classified_at desc, classification_id desc.
        """
        feedback = session.get(Feedback, feedback_id)
        if feedback is None:
            raise EntityNotFoundError(f"Feedback record '{feedback_id}' was not found.")

        stmt = (
            select(FeedbackClassification)
            .where(
                FeedbackClassification.feedback_id == feedback_id,
                FeedbackClassification.status.in_(VALID_CLASSIFICATION_STATUSES),
            )
            .order_by(
                FeedbackClassification.classified_at.desc(),
                FeedbackClassification.classification_id.desc(),
            )
            .limit(1)
        )
        classification = session.execute(stmt).scalar_one_or_none()
        if classification is None:
            raise EntityNotFoundError(f"No valid classification found for feedback '{feedback_id}'.")

        return FeedbackClassificationRecord.model_validate(classification)

    @classmethod
    def get_classification_summary(
        cls,
        session: Session,
        product: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> ClassificationSummaryResponse:
        """Compute aggregate classification and sentiment distribution statistics.

        Uses PostgreSQL/SQL database-side aggregations.
        - Valid classifications ('classified', 'pending_review') drive sentiment,
          intent, aspect, review, and latest_classified_count metrics.
        - Failed attempts never hide previous valid classifications in content analytics.
        - Operational status_distribution tracks the latest attempt per feedback item
          so failed attempts remain fully visible.
        """
        if start_date and end_date and start_date > end_date:
            raise AppException(
                message="start_date must be before or equal to end_date.",
                status_code=400,
                code="INVALID_DATE_RANGE",
            )

        # 1. Total historical classification records (filtered across all versions and runs)
        hist_query = session.query(FeedbackClassification).join(
            Feedback, FeedbackClassification.feedback_id == Feedback.feedback_id
        )
        if product:
            hist_query = hist_query.filter(Feedback.product == product)
        if start_date:
            hist_query = hist_query.filter(FeedbackClassification.classified_at >= start_date)
        if end_date:
            hist_query = hist_query.filter(FeedbackClassification.classified_at <= end_date)

        total_classifications = (
            hist_query.with_entities(func.count(FeedbackClassification.classification_id)).scalar() or 0
        )

        # 2. Latest VALID classification per feedback (classified or pending_review)
        rn_valid_subq = (
            select(
                FeedbackClassification.classification_id,
                func.row_number()
                .over(
                    partition_by=FeedbackClassification.feedback_id,
                    order_by=(
                        FeedbackClassification.classified_at.desc(),
                        FeedbackClassification.classification_id.desc(),
                    ),
                )
                .label("rn"),
            )
            .where(FeedbackClassification.status.in_(VALID_CLASSIFICATION_STATUSES))
        ).subquery()

        latest_valid_query = (
            session.query(FeedbackClassification)
            .join(
                rn_valid_subq,
                (FeedbackClassification.classification_id == rn_valid_subq.c.classification_id)
                & (rn_valid_subq.c.rn == 1),
            )
            .join(Feedback, FeedbackClassification.feedback_id == Feedback.feedback_id)
        )
        if product:
            latest_valid_query = latest_valid_query.filter(Feedback.product == product)
        if start_date:
            latest_valid_query = latest_valid_query.filter(FeedbackClassification.classified_at >= start_date)
        if end_date:
            latest_valid_query = latest_valid_query.filter(FeedbackClassification.classified_at <= end_date)

        latest_classified_count = (
            latest_valid_query.with_entities(func.count(FeedbackClassification.classification_id)).scalar() or 0
        )

        # 3. Sentiment distribution on latest valid classifications
        sentiment_distribution: Dict[str, int] = {
            "positive": 0,
            "negative": 0,
            "neutral": 0,
            "mixed": 0,
        }
        for s_label, count in (
            latest_valid_query.with_entities(
                FeedbackClassification.overall_sentiment,
                func.count(FeedbackClassification.classification_id),
            )
            .group_by(FeedbackClassification.overall_sentiment)
            .all()
        ):
            if s_label in sentiment_distribution:
                sentiment_distribution[s_label] = count
            else:
                sentiment_distribution[s_label] = count

        # 4. Customer intent distribution on latest valid classifications
        intent_distribution: Dict[str, int] = {
            "complaint": 0,
            "suggestion": 0,
            "praise": 0,
            "question": 0,
            "feature_request": 0,
            "other": 0,
        }
        for intent, count in (
            latest_valid_query.with_entities(
                FeedbackClassification.customer_intent,
                func.count(FeedbackClassification.classification_id),
            )
            .group_by(FeedbackClassification.customer_intent)
            .all()
        ):
            if intent in intent_distribution:
                intent_distribution[intent] = count
            else:
                intent_distribution[intent] = count

        # 5. Latest ATTEMPT per feedback item for operational status tracking
        rn_attempt_subq = (
            select(
                FeedbackClassification.classification_id,
                func.row_number()
                .over(
                    partition_by=FeedbackClassification.feedback_id,
                    order_by=(
                        FeedbackClassification.classified_at.desc(),
                        FeedbackClassification.classification_id.desc(),
                    ),
                )
                .label("rn"),
            )
        ).subquery()

        latest_attempt_query = (
            session.query(FeedbackClassification)
            .join(
                rn_attempt_subq,
                (FeedbackClassification.classification_id == rn_attempt_subq.c.classification_id)
                & (rn_attempt_subq.c.rn == 1),
            )
            .join(Feedback, FeedbackClassification.feedback_id == Feedback.feedback_id)
        )
        if product:
            latest_attempt_query = latest_attempt_query.filter(Feedback.product == product)
        if start_date:
            latest_attempt_query = latest_attempt_query.filter(FeedbackClassification.classified_at >= start_date)
        if end_date:
            latest_attempt_query = latest_attempt_query.filter(FeedbackClassification.classified_at <= end_date)

        # Status distribution reflects latest classification attempt per feedback item
        # ensuring operational awareness of failed attempts without silent suppression
        status_distribution: Dict[str, int] = {
            "classified": 0,
            "failed": 0,
            "pending_review": 0,
        }
        for st, count in (
            latest_attempt_query.with_entities(
                FeedbackClassification.status,
                func.count(FeedbackClassification.classification_id),
            )
            .group_by(FeedbackClassification.status)
            .all()
        ):
            if st in status_distribution:
                status_distribution[st] = count
            else:
                status_distribution[st] = count

        # 6. Needs review count (from latest valid classifications)
        needs_review_count = (
            latest_valid_query.filter(FeedbackClassification.needs_review.is_(True))
            .with_entities(func.count(FeedbackClassification.classification_id))
            .scalar()
            or 0
        )

        # 7. Aspect sentiment distribution (from latest valid classifications, only JSON column loaded)
        aspect_sentiment_distribution: Dict[str, int] = {
            "positive": 0,
            "negative": 0,
            "neutral": 0,
            "mixed": 0,
        }
        aspect_records = (
            latest_valid_query.filter(FeedbackClassification.aspects.isnot(None))
            .with_entities(FeedbackClassification.aspects)
            .all()
        )
        for (aspects_list,) in aspect_records:
            if aspects_list and isinstance(aspects_list, list):
                for asp in aspects_list:
                    if isinstance(asp, dict) and "sentiment" in asp:
                        asp_sentiment = str(asp["sentiment"]).lower()
                        if asp_sentiment in aspect_sentiment_distribution:
                            aspect_sentiment_distribution[asp_sentiment] += 1
                        else:
                            aspect_sentiment_distribution[asp_sentiment] = 1

        # 8. Feedback quality status distribution (from Feedback table)
        fb_query = session.query(Feedback).filter(Feedback.deleted_at.is_(None))
        if product:
            fb_query = fb_query.filter(Feedback.product == product)

        quality_distribution: Dict[str, int] = {
            "clean": 0,
            "flagged": 0,
            "pending": 0,
            "rejected": 0,
            "failed": 0,
        }
        for q_status, count in (
            fb_query.with_entities(Feedback.quality_status, func.count(Feedback.feedback_id))
            .group_by(Feedback.quality_status)
            .all()
        ):
            if q_status in quality_distribution:
                quality_distribution[q_status] = count
            else:
                quality_distribution[q_status] = count

        return ClassificationSummaryResponse(
            total_classifications=total_classifications,
            latest_classified_count=latest_classified_count,
            sentiment_distribution=sentiment_distribution,
            intent_distribution=intent_distribution,
            aspect_sentiment_distribution=aspect_sentiment_distribution,
            needs_review_count=needs_review_count,
            status_distribution=status_distribution,
            feedback_quality_status_distribution=quality_distribution,
        )
