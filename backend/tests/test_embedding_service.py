"""Comprehensive unit and integration tests for Feedback EmbeddingService.

Tests cover:
- Eligibility rules (soft-delete, quality_status, missing cleaned text, missing product).
- Deterministic input preparation and SHA-256 caching.
- Cache hits vs hash-invalidation updates.
- Provider integration and MockEmbeddingProvider injection.
- Vector dimension and finite-number validation.
- Concurrency conflict handling and atomic rollback.
- Bounded batch embedding with isolated failure reporting.
- Feedback record immutability.
- FastApi HTTP endpoints: POST /api/feedback/{id}/embed and POST /api/feedback/embed.
"""

from datetime import datetime, timezone
import math
from typing import List, Optional
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.exceptions import AppException, EntityNotFoundError
from app.db.base import Base
from app.db.types import PortableVector
from app.integrations.embeddings.exceptions import (
    EmbeddingQuotaExhaustedError,
    EmbeddingTimeoutError,
    EmbeddingUnavailableError,
    EmbeddingValidationError,
)
from app.integrations.embeddings.mock import MockEmbeddingProvider
from app.main import create_app
from app.models.feedback import Feedback
from app.models.feedback_embeddings import FeedbackEmbedding
from app.services.embedding_service import (
    EmbeddingService,
    compute_embedding_hash,
    prepare_embedding_input,
)


@pytest.fixture
def db_session():
    """Create isolated SQLite in-memory database and session for tests."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )

    @event.listens_for(engine, "connect")
    def do_connect(dbapi_connection, connection_record):
        dbapi_connection.isolation_level = None

    @event.listens_for(engine, "begin")
    def do_begin(conn):
        conn.exec_driver_sql("BEGIN")

    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def create_sample_feedback(
    session: Session,
    product: str = "Mobile App",
    cleaned_text: str = "Login button fails intermittently on iOS 17.",
    raw_text: str = "Login button fails intermittently on iOS 17 with user@test.com",
    quality_status: str = "clean",
    deleted: bool = False,
) -> Feedback:
    """Helper to persist a test feedback record."""
    fb = Feedback(
        feedback_id=uuid.uuid4(),
        source="csv",
        customer_id="cust-101",
        feedback_text=raw_text,
        cleaned_feedback_text=cleaned_text,
        product=product,
        feature="Authentication",
        quality_status=quality_status,
        timestamp=datetime.now(timezone.utc),
        deleted_at=datetime.now(timezone.utc) if deleted else None,
    )
    session.add(fb)
    session.commit()
    session.refresh(fb)
    return fb


# ---------------------------------------------------------------------------
# Unit Tests for Eligibility and Hashing
# ---------------------------------------------------------------------------


def test_prepare_embedding_input():
    """Verify input text formatting avoids PII and structures product context."""
    text = prepare_embedding_input(product="  Checkout API  ", cleaned_text="  Payment failed.  ")
    assert text == "Product: Checkout API\nFeedback: Payment failed."


def test_compute_embedding_hash_determinism():
    """Verify SHA-256 hash changes on any variation of text, product, model, or dimensions."""
    base_hash = compute_embedding_hash("Checkout", "Card expired", "gemini-embedding-2", 768)
    same_hash = compute_embedding_hash("Checkout", "Card expired", "gemini-embedding-2", 768)
    assert base_hash == same_hash

    # Different text
    assert base_hash != compute_embedding_hash("Checkout", "Card declined", "gemini-embedding-2", 768)
    # Different product
    assert base_hash != compute_embedding_hash("Billing", "Card expired", "gemini-embedding-2", 768)
    # Different model
    assert base_hash != compute_embedding_hash("Checkout", "Card expired", "other-model", 768)
    # Different dimension
    assert base_hash != compute_embedding_hash("Checkout", "Card expired", "gemini-embedding-2", 256)


# ---------------------------------------------------------------------------
# Single Feedback Embedding Tests
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_embed_single_feedback_success(db_session):
    """Verify successful generation and persistence of an individual feedback embedding."""
    fb = create_sample_feedback(db_session)
    mock_provider = MockEmbeddingProvider(default_dimensions=768)

    result = await EmbeddingService.embed_single_feedback(
        session=db_session,
        feedback_id=fb.feedback_id,
        provider=mock_provider,
    )

    assert result.feedback_id == fb.feedback_id
    assert result.status == "inserted"
    assert result.is_cache_hit is False
    assert result.embedding_model == "gemini-embedding-2"
    assert result.embedding_dimensions == 768
    assert mock_provider.call_count == 1

    # Verify database persistence
    stored = db_session.get(FeedbackEmbedding, result.embedding_id)
    assert stored is not None
    assert stored.feedback_id == fb.feedback_id
    assert len(stored.embedding_vector) == 768
    assert stored.input_hash == result.input_hash


@pytest.mark.anyio
async def test_embed_single_feedback_cache_hit(db_session):
    """Verify second call with identical text/product reuses existing embedding without provider calls."""
    fb = create_sample_feedback(db_session)
    mock_provider = MockEmbeddingProvider(default_dimensions=768)

    # First call: generates and persists
    res1 = await EmbeddingService.embed_single_feedback(
        session=db_session,
        feedback_id=fb.feedback_id,
        provider=mock_provider,
    )
    assert res1.status == "inserted"
    assert mock_provider.call_count == 1

    # Second call: cache hit
    res2 = await EmbeddingService.embed_single_feedback(
        session=db_session,
        feedback_id=fb.feedback_id,
        provider=mock_provider,
    )
    assert res2.status == "cached"
    assert res2.is_cache_hit is True
    assert res2.embedding_id == res1.embedding_id
    assert mock_provider.call_count == 1  # No additional provider call!


@pytest.mark.anyio
async def test_reembed_after_cleaned_text_change(db_session):
    """Verify changing cleaned_feedback_text invalidates hash and updates record in place."""
    fb = create_sample_feedback(db_session, cleaned_text="Original issue description.")
    mock_provider = MockEmbeddingProvider(default_dimensions=768)

    res1 = await EmbeddingService.embed_single_feedback(
        session=db_session,
        feedback_id=fb.feedback_id,
        provider=mock_provider,
    )
    assert res1.status == "inserted"
    old_hash = res1.input_hash

    # Modify cleaned text on feedback
    fb.cleaned_feedback_text = "Updated and re-cleaned issue description with more details."
    db_session.commit()

    # Re-embed
    res2 = await EmbeddingService.embed_single_feedback(
        session=db_session,
        feedback_id=fb.feedback_id,
        provider=mock_provider,
    )
    assert res2.status == "updated"
    assert res2.is_cache_hit is False
    assert res2.embedding_id == res1.embedding_id  # Same record updated in place
    assert res2.input_hash != old_hash
    assert mock_provider.call_count == 2

    # Verify only ONE record exists in DB for this feedback/model
    all_embeddings = db_session.scalars(
        select(FeedbackEmbedding).where(FeedbackEmbedding.feedback_id == fb.feedback_id)
    ).all()
    assert len(all_embeddings) == 1
    assert all_embeddings[0].input_hash == res2.input_hash


@pytest.mark.anyio
async def test_reembed_after_product_change(db_session):
    """Verify changing product context invalidates hash and triggers update."""
    fb = create_sample_feedback(db_session, product="Product A")
    mock_provider = MockEmbeddingProvider(default_dimensions=768)

    res1 = await EmbeddingService.embed_single_feedback(
        session=db_session,
        feedback_id=fb.feedback_id,
        provider=mock_provider,
    )
    assert res1.status == "inserted"

    # Modify product
    fb.product = "Product B"
    db_session.commit()

    res2 = await EmbeddingService.embed_single_feedback(
        session=db_session,
        feedback_id=fb.feedback_id,
        provider=mock_provider,
    )
    assert res2.status == "updated"
    assert res2.input_hash != res1.input_hash


@pytest.mark.anyio
async def test_ineligibility_rejections(db_session):
    """Verify soft-deleted, rejected, empty cleaned text, or missing product are rejected."""
    mock_provider = MockEmbeddingProvider()

    # 1. Soft-deleted feedback
    del_fb = create_sample_feedback(db_session, deleted=True)
    with pytest.raises(AppException) as exc_info:
        await EmbeddingService.embed_single_feedback(db_session, del_fb.feedback_id, provider=mock_provider)
    assert exc_info.value.code == "FEEDBACK_INELIGIBLE"
    assert "soft-deleted" in exc_info.value.message

    # 2. Rejected quality status
    rej_fb = create_sample_feedback(db_session, quality_status="rejected")
    with pytest.raises(AppException) as exc_info:
        await EmbeddingService.embed_single_feedback(db_session, rej_fb.feedback_id, provider=mock_provider)
    assert exc_info.value.code == "FEEDBACK_INELIGIBLE"
    assert "rejected" in exc_info.value.message

    # 3. Missing/empty cleaned text
    empty_fb = create_sample_feedback(db_session, cleaned_text="")
    with pytest.raises(AppException) as exc_info:
        await EmbeddingService.embed_single_feedback(db_session, empty_fb.feedback_id, provider=mock_provider)
    assert exc_info.value.code == "FEEDBACK_INELIGIBLE"
    assert "Cleaned feedback text is missing" in exc_info.value.message

    # 4. Non-existent feedback ID
    with pytest.raises(EntityNotFoundError):
        await EmbeddingService.embed_single_feedback(db_session, uuid.uuid4(), provider=mock_provider)


@pytest.mark.anyio
async def test_original_feedback_immutability(db_session):
    """Verify embedding operation does not mutate or overwrite original feedback fields."""
    fb = create_sample_feedback(
        db_session,
        raw_text="Original RAW feedback with sensitive info",
        cleaned_text="Cleaned feedback",
        product="StoreFront",
    )
    mock_provider = MockEmbeddingProvider()

    await EmbeddingService.embed_single_feedback(db_session, fb.feedback_id, provider=mock_provider)

    refreshed_fb = db_session.get(Feedback, fb.feedback_id)
    assert refreshed_fb.feedback_text == "Original RAW feedback with sensitive info"
    assert refreshed_fb.cleaned_feedback_text == "Cleaned feedback"
    assert refreshed_fb.product == "StoreFront"
    assert refreshed_fb.customer_id == "cust-101"


# ---------------------------------------------------------------------------
# Vector Validation and Provider Errors
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_invalid_vector_dimensions_rejection(db_session):
    """Verify provider returning incorrect dimensions is caught and rejected."""
    fb = create_sample_feedback(db_session)

    # Provider that forcibly returns 512 dimensions while service expects 768
    class MismatchedDimensionProvider(MockEmbeddingProvider):
        async def embed_text(self, text, dimensions=None):
            return await super().embed_text(text, dimensions=512)

    bad_provider = MismatchedDimensionProvider()

    with pytest.raises(EmbeddingValidationError, match="Expected embedding dimension 768, got 512"):
        await EmbeddingService.embed_single_feedback(
            session=db_session,
            feedback_id=fb.feedback_id,
            provider=bad_provider,
            dimensions=768,
        )

    # Verify nothing was persisted
    assert db_session.scalars(select(FeedbackEmbedding)).first() is None


@pytest.mark.anyio
async def test_provider_error_handling_and_rollback(db_session):
    """Verify provider timeout or failure raises AppException and rolls back cleanly."""
    fb = create_sample_feedback(db_session)
    timeout_provider = MockEmbeddingProvider(
        simulate_error=EmbeddingTimeoutError("Gemini timed out after 30s")
    )

    with pytest.raises(AppException) as exc_info:
        await EmbeddingService.embed_single_feedback(
            session=db_session,
            feedback_id=fb.feedback_id,
            provider=timeout_provider,
        )
    assert exc_info.value.code == "EMBEDDING_PROVIDER_ERROR"
    assert exc_info.value.status_code == 502

    # Verify no partial records remained
    assert db_session.scalars(select(FeedbackEmbedding)).first() is None


@pytest.mark.anyio
async def test_portable_vector_sqlite_application_dimension_validation():
    """Verify PortableVector rejects dimension mismatches on SQLite."""
    pv = PortableVector(dim=768)
    sqlite_dialect = create_engine("sqlite://").dialect

    # 512 floats passed to 768-dim type must raise ValueError
    with pytest.raises(ValueError, match="PortableVector expects 768 dimensions, got 512"):
        pv.process_bind_param([0.1] * 512, dialect=sqlite_dialect)

    # Non-finite values must raise ValueError
    nan_vec = [0.1] * 768
    nan_vec[5] = float("nan")
    with pytest.raises(ValueError, match="Vector contains non-finite value"):
        pv.process_bind_param(nan_vec, dialect=sqlite_dialect)


# ---------------------------------------------------------------------------
# Batch Processing Tests
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_embed_batch_success_and_cache_filtering(db_session):
    """Verify batch embedding: un-embedded items are requested, cached items are skipped, order is kept."""
    fb1 = create_sample_feedback(db_session, cleaned_text="Item 1")
    fb2 = create_sample_feedback(db_session, cleaned_text="Item 2")
    fb3 = create_sample_feedback(db_session, cleaned_text="Item 3")

    mock_provider = MockEmbeddingProvider(default_dimensions=768)

    # 1. First batch embeds all 3 items
    res1 = await EmbeddingService.embed_batch(
        session=db_session,
        feedback_ids=[fb1.feedback_id, fb2.feedback_id, fb3.feedback_id],
        provider=mock_provider,
    )
    assert res1.total == 3
    assert res1.processed == 3
    assert res1.inserted == 3
    assert res1.cached == 0
    assert res1.failed == 0
    assert mock_provider.call_count == 1  # 1 batch call for 3 items

    # 2. Modify only fb2
    fb2.cleaned_feedback_text = "Item 2 modified text"
    db_session.commit()

    # 3. Add fb4
    fb4 = create_sample_feedback(db_session, cleaned_text="Item 4")

    # 4. Second batch with [fb1 (cached), fb2 (updated), fb3 (cached), fb4 (new)]
    batch_ids = [fb1.feedback_id, fb2.feedback_id, fb3.feedback_id, fb4.feedback_id]
    res2 = await EmbeddingService.embed_batch(
        session=db_session,
        feedback_ids=batch_ids,
        provider=mock_provider,
    )
    assert res2.total == 4
    assert res2.processed == 4
    assert res2.cached == 2  # fb1 and fb3 were cached
    assert res2.updated == 1  # fb2 was updated
    assert res2.inserted == 1  # fb4 was inserted
    assert res2.failed == 0
    assert mock_provider.call_count == 2  # Only 1 additional provider call was made for the 2 items!


@pytest.mark.anyio
async def test_embed_batch_isolated_failures(db_session):
    """Verify ineligible or non-existent items are reported in errors without aborting valid items."""
    fb_valid = create_sample_feedback(db_session, cleaned_text="Valid item")
    fb_rejected = create_sample_feedback(db_session, quality_status="rejected", cleaned_text="Spam item")
    random_id = uuid.uuid4()

    mock_provider = MockEmbeddingProvider(default_dimensions=768)

    batch_ids = [fb_valid.feedback_id, fb_rejected.feedback_id, random_id]
    response = await EmbeddingService.embed_batch(
        session=db_session,
        feedback_ids=batch_ids,
        provider=mock_provider,
    )

    assert response.total == 3
    assert response.processed == 1  # Only fb_valid was processed
    assert response.inserted == 1
    assert response.failed == 2

    error_map = {err.feedback_id: err for err in response.errors}
    assert fb_rejected.feedback_id in error_map
    assert "rejected" in error_map[fb_rejected.feedback_id].error
    assert random_id in error_map
    assert "not found" in error_map[random_id].error


@pytest.mark.anyio
async def test_embed_batch_size_limit(db_session):
    """Verify batch exceeding max_batch_size raises 400 error."""
    mock_provider = MockEmbeddingProvider()
    too_many_ids = [uuid.uuid4() for _ in range(101)]

    with pytest.raises(AppException) as exc_info:
        await EmbeddingService.embed_batch(
            session=db_session,
            feedback_ids=too_many_ids,
            provider=mock_provider,
            max_batch_size=100,
        )
    assert exc_info.value.code == "BATCH_TOO_LARGE"
    assert exc_info.value.status_code == 400


# ---------------------------------------------------------------------------
# API Route Integration Tests
# ---------------------------------------------------------------------------


def test_api_embed_single_and_batch_endpoints(db_session, monkeypatch):
    """Verify FastAPI route endpoints /api/feedback/{id}/embed and /api/feedback/embed."""
    app = create_app()
    from app.db.session import get_db

    app.dependency_overrides[get_db] = lambda: db_session
    client = TestClient(app)

    # Mock provider to avoid network calls
    mock_provider = MockEmbeddingProvider(default_dimensions=768)
    monkeypatch.setattr(EmbeddingService, "get_default_provider", lambda: mock_provider)

    fb1 = create_sample_feedback(db_session, cleaned_text="Dashboard loading latency issue")
    fb2 = create_sample_feedback(db_session, cleaned_text="Export to CSV crashes browser")

    # 1. POST /api/feedback/{id}/embed
    resp1 = client.post(f"/api/feedback/{fb1.feedback_id}/embed")
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["feedback_id"] == str(fb1.feedback_id)
    assert data1["status"] == "inserted"
    assert data1["is_cache_hit"] is False
    assert len(data1["vector_preview"]) == 5

    # Repeat single call -> verify cache hit
    resp1_cached = client.post(f"/api/feedback/{fb1.feedback_id}/embed")
    assert resp1_cached.status_code == 200
    assert resp1_cached.json()["status"] == "cached"
    assert resp1_cached.json()["is_cache_hit"] is True

    # 2. POST /api/feedback/embed (Batch)
    batch_payload = {
        "feedback_ids": [str(fb1.feedback_id), str(fb2.feedback_id)],
    }
    resp_batch = client.post("/api/feedback/embed", json=batch_payload)
    assert resp_batch.status_code == 200
    batch_data = resp_batch.json()
    assert batch_data["total"] == 2
    assert batch_data["processed"] == 2
    assert batch_data["cached"] == 1  # fb1 was already cached
    assert batch_data["inserted"] == 1  # fb2 was inserted
    assert batch_data["failed"] == 0


@pytest.mark.anyio
async def test_embed_batch_commit_failure_consistency(db_session, monkeypatch):
    """Verify that when a batch commit fails:
    - No staged items are reported as inserted or updated.
    - Cached items remain accurately reported as cached.
    - Staged items are reported in errors with COMMIT_ERROR.
    - Transaction rollback prevents uncommitted items from remaining in DB.
    - Summary counts strictly agree with detailed items and errors.
    """
    # Create and pre-embed fb1 so it is a cached item
    fb1 = create_sample_feedback(db_session, cleaned_text="Cached item 1")
    mock_provider = MockEmbeddingProvider(default_dimensions=768)
    res_single = await EmbeddingService.embed_single_feedback(
        session=db_session,
        feedback_id=fb1.feedback_id,
        provider=mock_provider,
    )
    assert res_single.status == "inserted"

    # Create two un-embedded items
    fb2 = create_sample_feedback(db_session, cleaned_text="Uncached item 2")
    fb3 = create_sample_feedback(db_session, cleaned_text="Uncached item 3")

    # Monkeypatch db_session.commit to raise an exception on batch commit
    orig_commit = db_session.commit

    def failing_commit():
        raise RuntimeError("Simulated DB commit error")

    monkeypatch.setattr(db_session, "commit", failing_commit)

    res = await EmbeddingService.embed_batch(
        session=db_session,
        feedback_ids=[fb1.feedback_id, fb2.feedback_id, fb3.feedback_id],
        provider=mock_provider,
    )

    # 1. Summary counts must agree with detail lengths
    assert res.total == 3
    assert res.processed == 1  # Only fb1 was cached
    assert res.cached == 1
    assert res.inserted == 0  # NO false inserted!
    assert res.updated == 0
    assert res.failed == 2  # fb2 and fb3 failed commit
    assert len(res.items) == res.processed
    assert len(res.errors) == res.failed

    # 2. Detailed item verification
    assert res.items[0].feedback_id == fb1.feedback_id
    assert res.items[0].status == "cached"
    assert res.items[0].is_cache_hit is True

    # 3. Error items verification
    error_ids = {err.feedback_id for err in res.errors}
    assert error_ids == {fb2.feedback_id, fb3.feedback_id}
    for err in res.errors:
        assert err.error_code == "COMMIT_ERROR"
        assert "Simulated DB commit error" in err.error

    # Restore commit and check DB state
    monkeypatch.setattr(db_session, "commit", orig_commit)
    stmt = select(FeedbackEmbedding.feedback_id)
    persisted_ids = set(db_session.scalars(stmt).all())
    assert fb1.feedback_id in persisted_ids
    assert fb2.feedback_id not in persisted_ids
    assert fb3.feedback_id not in persisted_ids


@pytest.mark.anyio
async def test_embed_batch_one_item_validation_failure_isolation(db_session):
    """Verify one item failing vector validation does not corrupt unrelated successful items in the batch."""
    fb1 = create_sample_feedback(db_session, cleaned_text="Valid item 1")
    fb2 = create_sample_feedback(db_session, cleaned_text="Bad vector item 2")
    fb3 = create_sample_feedback(db_session, cleaned_text="Valid item 3")

    class MalformedVectorBatchProvider(MockEmbeddingProvider):
        async def embed_batch(self, texts, dimensions=None):
            resp = await super().embed_batch(texts, dimensions=dimensions)
            # Corrupt vector for second item with a NaN value
            resp.vectors[1] = [float("nan")] * 768
            return resp

    provider = MalformedVectorBatchProvider(default_dimensions=768)

    res = await EmbeddingService.embed_batch(
        session=db_session,
        feedback_ids=[fb1.feedback_id, fb2.feedback_id, fb3.feedback_id],
        provider=provider,
    )

    assert res.total == 3
    assert res.processed == 2
    assert res.inserted == 2
    assert res.failed == 1
    assert len(res.items) == 2
    assert len(res.errors) == 1

    succeeded_ids = {item.feedback_id for item in res.items}
    assert succeeded_ids == {fb1.feedback_id, fb3.feedback_id}

    assert res.errors[0].feedback_id == fb2.feedback_id
    assert res.errors[0].error_code == "VALIDATION_ERROR"

    # In DB: fb1 and fb3 are persisted, fb2 is not
    persisted = set(db_session.scalars(select(FeedbackEmbedding.feedback_id)).all())
    assert fb1.feedback_id in persisted
    assert fb3.feedback_id in persisted
    assert fb2.feedback_id not in persisted


@pytest.mark.anyio
async def test_embed_batch_concurrent_integrity_recovery(db_session):
    """Verify bounded recovery re-reads existing embedding on IntegrityError."""
    fb1 = create_sample_feedback(db_session, cleaned_text="Concurrent item 1")
    mock_provider = MockEmbeddingProvider(default_dimensions=768)

    # Pre-populate conflicting row
    input_hash = compute_embedding_hash(fb1.product, fb1.cleaned_feedback_text, "gemini-embedding-2", 768)
    vec = [0.1] * 768

    conflict_row = FeedbackEmbedding(
        embedding_id=uuid.uuid4(),
        feedback_id=fb1.feedback_id,
        embedding_model="gemini-embedding-2",
        embedding_dimensions=768,
        embedding_vector=vec,
        input_hash=input_hash,
    )
    db_session.add(conflict_row)
    db_session.commit()

    # Call embed_batch with force_refresh=True to force execution past the cache filter
    res = await EmbeddingService.embed_batch(
        session=db_session,
        feedback_ids=[fb1.feedback_id],
        provider=mock_provider,
        force_refresh=True,
    )

    assert res.total == 1
    assert res.processed == 1
    assert res.updated == 1
    assert res.failed == 0
    assert len(res.items) == 1
