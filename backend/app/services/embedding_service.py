"""Feedback Embedding Service.

Coordinates deterministic input preparation, SHA-256 caching, vector dimension
and numeric validation, provider-agnostic batch embedding, and PostgreSQL persistence.
"""

from datetime import datetime, timezone
import hashlib
import logging
import math
from typing import Any, Dict, List, Optional, Tuple
import uuid
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import AppException, EntityNotFoundError
from app.integrations.embeddings.base import BaseEmbeddingProvider
from app.integrations.embeddings.exceptions import (
    EmbeddingAuthError,
    EmbeddingError,
    EmbeddingQuotaExhaustedError,
    EmbeddingRateLimitError,
    EmbeddingTimeoutError,
    EmbeddingUnavailableError,
    EmbeddingValidationError,
)
from app.integrations.embeddings.gemini import GeminiEmbeddingProvider
from app.models.feedback import Feedback
from app.models.feedback_embeddings import FeedbackEmbedding
from app.schemas.embedding import (
    BatchEmbeddingResponse,
    EmbeddingItemError,
    EmbeddingItemResult,
)

logger = logging.getLogger("embedding_service")

EMBEDDING_INPUT_VERSION = "v1.0"
DEFAULT_BATCH_SIZE = 50
MAX_BATCH_SIZE = 100


def prepare_embedding_input(product: str, cleaned_text: str) -> str:
    """Deterministically format embedding input using product context and cleaned feedback text.

    Excludes raw customer identifiers or sensitive PII to safeguard privacy.
    """
    clean_p = product.strip()
    clean_t = cleaned_text.strip()
    return f"Product: {clean_p}\nFeedback: {clean_t}"


def compute_embedding_hash(
    product: str,
    cleaned_text: str,
    model: str,
    dimensions: int,
    input_version: str = EMBEDDING_INPUT_VERSION,
) -> str:
    """Compute deterministic SHA-256 hash across all parameters that dictate the vector representation."""
    raw_payload = f"{product.strip()}::{cleaned_text.strip()}::{model.strip()}::{dimensions}::{input_version}"
    return hashlib.sha256(raw_payload.encode("utf-8")).hexdigest()


def check_feedback_eligibility(feedback: Feedback) -> Tuple[bool, Optional[str]]:
    """Verify that a feedback record satisfies all business rules for text embedding.

    Requirements:
    - Must not be soft-deleted.
    - Quality status must not be 'rejected' or 'failed'.
    - Cleaned feedback text must be present and non-empty.
    - Product line identifier must be present and non-empty.
    """
    if feedback.deleted_at is not None:
        return False, "Feedback record is soft-deleted"

    if feedback.quality_status in ("rejected", "failed"):
        return False, f"Feedback has '{feedback.quality_status}' quality status"

    if not feedback.cleaned_feedback_text or not feedback.cleaned_feedback_text.strip():
        return False, "Cleaned feedback text is missing or empty"

    if not feedback.product or not feedback.product.strip():
        return False, "Product line identifier is missing or empty"

    return True, None


def validate_vector_values(vector: List[float], expected_dimensions: int) -> None:
    """Validate that vector length matches expected dimensions and all elements are finite floats."""
    if not isinstance(vector, (list, tuple)):
        raise EmbeddingValidationError(f"Vector must be a list of floats, got {type(vector).__name__}")
    if len(vector) != expected_dimensions:
        raise EmbeddingValidationError(
            f"Expected embedding dimension {expected_dimensions}, got {len(vector)}"
        )
    for idx, val in enumerate(vector):
        try:
            f_val = float(val)
        except (ValueError, TypeError) as e:
            raise EmbeddingValidationError(
                f"Vector value at index {idx} cannot be converted to float: {val}"
            ) from e
        if not math.isfinite(f_val):
            raise EmbeddingValidationError(
                f"Vector contains non-finite value ({f_val}) at index {idx}"
            )


class EmbeddingService:
    """Service orchestrating provider-agnostic feedback embedding generation and persistence."""

    @classmethod
    def get_default_provider(cls) -> BaseEmbeddingProvider:
        """Instantiate the default configured embedding provider."""
        provider_name = settings.AI_EMBEDDING_PROVIDER.lower()
        if provider_name == "gemini":
            return GeminiEmbeddingProvider(
                api_key=settings.GEMINI_API_KEY,
                model=settings.AI_EMBEDDING_MODEL,
                dimensions=settings.AI_EMBEDDING_DIMENSIONS,
                timeout_seconds=settings.AI_EMBEDDING_TIMEOUT,
                max_retries=settings.AI_EMBEDDING_MAX_RETRIES,
            )
        raise AppException(
            message=f"Unsupported embedding provider: '{provider_name}'",
            status_code=500,
            code="UNSUPPORTED_PROVIDER",
        )

    @classmethod
    async def embed_single_feedback(
        cls,
        session: Session,
        feedback_id: uuid.UUID,
        provider: Optional[BaseEmbeddingProvider] = None,
        dimensions: Optional[int] = None,
        force_refresh: bool = False,
    ) -> EmbeddingItemResult:
        """Generate, validate, and persist an embedding for an individual feedback record."""
        feedback = session.get(Feedback, feedback_id)
        if feedback is None:
            raise EntityNotFoundError("Feedback", feedback_id)

        is_eligible, reason = check_feedback_eligibility(feedback)
        if not is_eligible:
            raise AppException(
                message=f"Feedback '{feedback_id}' is ineligible for embedding: {reason}",
                status_code=400,
                code="FEEDBACK_INELIGIBLE",
            )

        active_provider = provider or cls.get_default_provider()
        model_name = active_provider.default_model
        target_dims = dimensions or active_provider.default_dimensions

        # Deterministic text and hash
        prepared_text = prepare_embedding_input(feedback.product, feedback.cleaned_feedback_text)
        input_hash = compute_embedding_hash(
            product=feedback.product,
            cleaned_text=feedback.cleaned_feedback_text,
            model=model_name,
            dimensions=target_dims,
        )

        # 1. Check existing cached embedding
        existing = session.execute(
            select(FeedbackEmbedding).where(
                FeedbackEmbedding.feedback_id == feedback.feedback_id,
                FeedbackEmbedding.embedding_model == model_name,
            )
        ).scalar_one_or_none()

        if (
            existing is not None
            and not force_refresh
            and existing.input_hash == input_hash
            and existing.embedding_dimensions == target_dims
        ):
            logger.info(
                "Embedding cache hit for feedback '%s' [model=%s, dims=%d]",
                feedback_id,
                model_name,
                target_dims,
            )
            return EmbeddingItemResult(
                feedback_id=feedback.feedback_id,
                embedding_id=existing.embedding_id,
                embedding_model=model_name,
                embedding_dimensions=target_dims,
                status="cached",
                is_cache_hit=True,
                input_hash=input_hash,
                created_at=existing.created_at,
                vector_preview=existing.embedding_vector[:5],
            )

        # 2. Call provider to generate vector
        try:
            response = await active_provider.embed_text(prepared_text, dimensions=target_dims)
        except EmbeddingError as ee:
            logger.error("Embedding provider error for feedback '%s': %s", feedback_id, ee)
            raise AppException(
                message=f"Embedding provider failure: {ee.message}",
                status_code=502 if ee.is_transient else 400,
                code="EMBEDDING_PROVIDER_ERROR",
            ) from ee

        validate_vector_values(response.vector, target_dims)

        # 3. Persist atomically with concurrency retry
        max_retries = 3
        for attempt in range(max_retries):
            try:
                if existing is not None:
                    # Update existing record in place
                    existing.embedding_vector = response.vector
                    existing.embedding_dimensions = target_dims
                    existing.input_hash = input_hash
                    existing.created_at = datetime.now(timezone.utc)
                    session.commit()
                    session.refresh(existing)
                    result_record = existing
                    status_label = "updated"
                else:
                    new_emb = FeedbackEmbedding(
                        embedding_id=uuid.uuid4(),
                        feedback_id=feedback.feedback_id,
                        embedding_model=model_name,
                        embedding_dimensions=target_dims,
                        embedding_vector=response.vector,
                        input_hash=input_hash,
                    )
                    session.add(new_emb)
                    session.commit()
                    session.refresh(new_emb)
                    result_record = new_emb
                    status_label = "inserted"

                logger.info(
                    "Persisted embedding for feedback '%s' [status=%s, model=%s, dims=%d]",
                    feedback_id,
                    status_label,
                    model_name,
                    target_dims,
                )

                return EmbeddingItemResult(
                    feedback_id=feedback.feedback_id,
                    embedding_id=result_record.embedding_id,
                    embedding_model=model_name,
                    embedding_dimensions=target_dims,
                    status=status_label,
                    is_cache_hit=False,
                    input_hash=input_hash,
                    created_at=result_record.created_at,
                    vector_preview=result_record.embedding_vector[:5],
                )

            except IntegrityError as ie:
                session.rollback()
                if attempt < max_retries - 1:
                    logger.warning(
                        "Concurrent insertion collision for feedback '%s'; retrying update...",
                        feedback_id,
                    )
                    existing = session.execute(
                        select(FeedbackEmbedding).where(
                            FeedbackEmbedding.feedback_id == feedback.feedback_id,
                            FeedbackEmbedding.embedding_model == model_name,
                        )
                    ).scalar_one_or_none()
                    continue
                raise AppException(
                    message=f"Database integrity conflict persisting embedding for feedback '{feedback_id}'",
                    status_code=409,
                    code="EMBEDDING_PERSISTENCE_CONFLICT",
                ) from ie
            except Exception:
                session.rollback()
                raise

        raise AppException(
            message=f"Failed to persist embedding for feedback '{feedback_id}'",
            status_code=500,
            code="EMBEDDING_PERSISTENCE_FAILED",
        )

    @classmethod
    async def embed_batch(
        cls,
        session: Session,
        feedback_ids: List[uuid.UUID],
        provider: Optional[BaseEmbeddingProvider] = None,
        dimensions: Optional[int] = None,
        force_refresh: bool = False,
        max_batch_size: int = MAX_BATCH_SIZE,
    ) -> BatchEmbeddingResponse:
        """Execute bounded batch feedback embedding with cache filtering and isolated failure handling."""
        if not feedback_ids:
            return BatchEmbeddingResponse(
                total=0,
                processed=0,
                cached=0,
                inserted=0,
                updated=0,
                failed=0,
                items=[],
                errors=[],
            )

        if len(feedback_ids) > max_batch_size:
            raise AppException(
                message=f"Batch size {len(feedback_ids)} exceeds maximum allowed limit of {max_batch_size}.",
                status_code=400,
                code="BATCH_TOO_LARGE",
            )

        active_provider = provider or cls.get_default_provider()
        model_name = active_provider.default_model
        target_dims = dimensions or active_provider.default_dimensions

        # Fetch all requested feedback records
        stmt = select(Feedback).where(Feedback.feedback_id.in_(feedback_ids))
        feedbacks = session.scalars(stmt).all()
        fb_map = {fb.feedback_id: fb for fb in feedbacks}

        # Pre-fetch existing embeddings
        existing_stmt = select(FeedbackEmbedding).where(
            FeedbackEmbedding.feedback_id.in_(feedback_ids),
            FeedbackEmbedding.embedding_model == model_name,
        )
        existing_embeddings = session.scalars(existing_stmt).all()
        existing_map = {emb.feedback_id: emb for emb in existing_embeddings}

        results: List[EmbeddingItemResult] = []
        errors: List[EmbeddingItemError] = []

        # Items that must be requested from the provider
        # Tuple: (original_index, feedback, prepared_text, input_hash, existing_record)
        to_embed: List[Tuple[int, Feedback, str, str, Optional[FeedbackEmbedding]]] = []

        # 1. Screen eligibility and filter cache hits
        for idx, fid in enumerate(feedback_ids):
            fb = fb_map.get(fid)
            if fb is None:
                errors.append(
                    EmbeddingItemError(
                        feedback_id=fid,
                        error="Feedback record not found",
                        error_code="NOT_FOUND",
                    )
                )
                continue

            is_eligible, reason = check_feedback_eligibility(fb)
            if not is_eligible:
                errors.append(
                    EmbeddingItemError(
                        feedback_id=fid,
                        error=reason or "Ineligible feedback",
                        error_code="INELIGIBLE",
                    )
                )
                continue

            prepared_text = prepare_embedding_input(fb.product, fb.cleaned_feedback_text)
            input_hash = compute_embedding_hash(
                product=fb.product,
                cleaned_text=fb.cleaned_feedback_text,
                model=model_name,
                dimensions=target_dims,
            )

            existing = existing_map.get(fid)
            if (
                existing is not None
                and not force_refresh
                and existing.input_hash == input_hash
                and existing.embedding_dimensions == target_dims
            ):
                results.append(
                    EmbeddingItemResult(
                        feedback_id=fid,
                        embedding_id=existing.embedding_id,
                        embedding_model=model_name,
                        embedding_dimensions=target_dims,
                        status="cached",
                        is_cache_hit=True,
                        input_hash=input_hash,
                        created_at=existing.created_at,
                        vector_preview=existing.embedding_vector[:5],
                    )
                )
            else:
                to_embed.append((idx, fb, prepared_text, input_hash, existing))

        # 2. Call provider for un-embedded items
        if to_embed:
            texts_to_call = [item[2] for item in to_embed]
            try:
                batch_response = await active_provider.embed_batch(
                    texts_to_call,
                    dimensions=target_dims,
                )
                returned_vectors = batch_response.vectors

                # Validate vectors count
                if len(returned_vectors) != len(to_embed):
                    raise EmbeddingValidationError(
                        f"Provider returned {len(returned_vectors)} vectors for {len(to_embed)} inputs"
                    )

                staged_results: List[EmbeddingItemResult] = []

                for (_, fb, _, input_hash, existing), vec in zip(to_embed, returned_vectors):
                    try:
                        validate_vector_values(vec, target_dims)
                    except Exception as val_exc:
                        logger.error(
                            "Vector validation failure for feedback '%s': %s",
                            fb.feedback_id,
                            val_exc,
                        )
                        errors.append(
                            EmbeddingItemError(
                                feedback_id=fb.feedback_id,
                                error=str(val_exc),
                                error_code="VALIDATION_ERROR",
                            )
                        )
                        continue

                    # Stage database insertion or update within an isolated savepoint
                    try:
                        with session.begin_nested():
                            if existing is not None:
                                existing.embedding_vector = vec
                                existing.embedding_dimensions = target_dims
                                existing.input_hash = input_hash
                                existing.created_at = datetime.now(timezone.utc)
                                rec_id = existing.embedding_id
                                rec_created_at = existing.created_at
                                status_label = "updated"
                            else:
                                new_emb = FeedbackEmbedding(
                                    embedding_id=uuid.uuid4(),
                                    feedback_id=fb.feedback_id,
                                    embedding_model=model_name,
                                    embedding_dimensions=target_dims,
                                    embedding_vector=vec,
                                    input_hash=input_hash,
                                )
                                session.add(new_emb)
                                rec_id = new_emb.embedding_id
                                rec_created_at = new_emb.created_at or datetime.now(timezone.utc)
                                status_label = "inserted"

                            session.flush()

                        staged_results.append(
                            EmbeddingItemResult(
                                feedback_id=fb.feedback_id,
                                embedding_id=rec_id,
                                embedding_model=model_name,
                                embedding_dimensions=target_dims,
                                status=status_label,
                                is_cache_hit=False,
                                input_hash=input_hash,
                                created_at=rec_created_at,
                                vector_preview=vec[:5],
                            )
                        )

                    except IntegrityError as ie:
                        # Savepoint rolled back automatically by context manager.
                        # Bounded recovery: attempt to re-read existing row (in case of concurrent insert)
                        try:
                            with session.begin_nested():
                                existing_row = session.execute(
                                    select(FeedbackEmbedding).where(
                                        FeedbackEmbedding.feedback_id == fb.feedback_id,
                                        FeedbackEmbedding.embedding_model == model_name,
                                    )
                                ).scalar_one_or_none()

                                if existing_row is not None:
                                    if (
                                        existing_row.input_hash == input_hash
                                        and existing_row.embedding_dimensions == target_dims
                                    ):
                                        # Identical embedding concurrently persisted
                                        staged_results.append(
                                            EmbeddingItemResult(
                                                feedback_id=fb.feedback_id,
                                                embedding_id=existing_row.embedding_id,
                                                embedding_model=model_name,
                                                embedding_dimensions=target_dims,
                                                status="cached",
                                                is_cache_hit=True,
                                                input_hash=input_hash,
                                                created_at=existing_row.created_at,
                                                vector_preview=existing_row.embedding_vector[:5],
                                            )
                                        )
                                    else:
                                        # Different hash concurrently persisted; update in place
                                        existing_row.embedding_vector = vec
                                        existing_row.embedding_dimensions = target_dims
                                        existing_row.input_hash = input_hash
                                        existing_row.created_at = datetime.now(timezone.utc)
                                        session.flush()
                                        staged_results.append(
                                            EmbeddingItemResult(
                                                feedback_id=fb.feedback_id,
                                                embedding_id=existing_row.embedding_id,
                                                embedding_model=model_name,
                                                embedding_dimensions=target_dims,
                                                status="updated",
                                                is_cache_hit=False,
                                                input_hash=input_hash,
                                                created_at=existing_row.created_at,
                                                vector_preview=vec[:5],
                                            )
                                        )
                                else:
                                    raise ie
                        except Exception as recovery_exc:
                            logger.error(
                                "Failed to recover from integrity collision for feedback '%s': %s",
                                fb.feedback_id,
                                recovery_exc,
                            )
                            errors.append(
                                EmbeddingItemError(
                                    feedback_id=fb.feedback_id,
                                    error=f"Integrity conflict: {str(recovery_exc)}",
                                    error_code="PERSISTENCE_CONFLICT",
                                )
                            )

                    except Exception as item_exc:
                        logger.error(
                            "Error staging embedding for feedback '%s': %s",
                            fb.feedback_id,
                            item_exc,
                        )
                        errors.append(
                            EmbeddingItemError(
                                feedback_id=fb.feedback_id,
                                error=str(item_exc),
                                error_code="PERSISTENCE_ERROR",
                            )
                        )

                # Commit only if there are successfully staged results
                if staged_results:
                    try:
                        session.commit()
                        # Crucial consistency guarantee: only report staged items as succeeded AFTER commit
                        results.extend(staged_results)
                    except Exception as commit_exc:
                        logger.error("Failed to commit batch embeddings: %s", commit_exc)
                        session.rollback()
                        for staged in staged_results:
                            errors.append(
                                EmbeddingItemError(
                                    feedback_id=staged.feedback_id,
                                    error=f"Persistence commit failure: {str(commit_exc)}",
                                    error_code="COMMIT_ERROR",
                                )
                            )

            except EmbeddingError as ee:
                logger.error("Batch embedding provider error: %s", ee)
                for _, fb, _, _, _ in to_embed:
                    errors.append(
                        EmbeddingItemError(
                            feedback_id=fb.feedback_id,
                            error=f"Provider error: {ee.message}",
                            error_code="PROVIDER_ERROR",
                        )
                    )
            except Exception as batch_exc:
                logger.error("Unexpected error during batch embedding processing: %s", batch_exc)
                for _, fb, _, _, _ in to_embed:
                    errors.append(
                        EmbeddingItemError(
                            feedback_id=fb.feedback_id,
                            error=f"Processing error: {str(batch_exc)}",
                            error_code="PROCESSING_ERROR",
                        )
                    )

        # Count metrics
        cached_count = sum(1 for r in results if r.status == "cached")
        inserted_count = sum(1 for r in results if r.status == "inserted")
        updated_count = sum(1 for r in results if r.status == "updated")

        logger.info(
            "Batch embedding complete: total=%d, processed=%d, cached=%d, inserted=%d, updated=%d, failed=%d",
            len(feedback_ids),
            len(results),
            cached_count,
            inserted_count,
            updated_count,
            len(errors),
        )

        return BatchEmbeddingResponse(
            total=len(feedback_ids),
            processed=len(results),
            cached=cached_count,
            inserted=inserted_count,
            updated=updated_count,
            failed=len(errors),
            items=results,
            errors=errors,
        )
