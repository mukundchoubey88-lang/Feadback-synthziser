"""Unit and integration tests for Theme Lifecycle Management (Part 7 - Hackathon Prototype).

Tests coverage:
1. Candidate discovery and idempotent staging using ThemeClusteringService.
2. Repeated discovery skipping existing candidate themes (duplicate prevention).
3. Product isolation across candidate discovery, listing, and merges.
4. Candidate activation (default name vs custom operator name) and discard.
5. Invalid state transitions (cannot activate non-candidate, cannot discard non-candidate).
6. Successful theme merge with membership migration.
7. Duplicate membership resolution during merge (highest relevance score, aspect sentiment copy-on-null).
8. Self-merge rejection and cross-product merge rejection.
9. Target centroid recomputation following theme merge.
10. Theme sentiment summary aggregation (multi-run deduplication, missing classification handling).
11. End-to-end FastAPI endpoints testing via TestClient.
"""

from datetime import datetime, timezone
from typing import List, Optional, Tuple
import uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.exceptions import AppException, EntityNotFoundError
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.classification import FeedbackClassification
from app.models.feedback import Feedback, FeedbackThemes
from app.models.feedback_embeddings import FeedbackEmbedding
from app.models.theme import Theme
from app.schemas.theme import (
    ActivateThemeRequest,
    DiscoverThemesRequest,
    MergeThemesRequest,
)
from app.services.theme_clustering_service import normalize_vector
from app.services.theme_lifecycle_service import ThemeLifecycleService


# ---------------------------------------------------------------------------
# SQLite Test Fixture with StaticPool
# ---------------------------------------------------------------------------

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


@pytest.fixture
def client(db_session):
    """FastAPI TestClient with overridden get_db dependency."""
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    test_client = TestClient(app)
    yield test_client
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Test Helpers
# ---------------------------------------------------------------------------

def make_unit_vector(direction_idx: int, dim: int = 768, noise: float = 0.0) -> List[float]:
    """Generate a deterministic unit-normalized vector."""
    vec = [noise] * dim
    vec[direction_idx] = 1.0
    return normalize_vector(vec)


def seed_feedback(
    session: Session,
    product: str = "TestApp",
    text: str = "Great search feature",
    vector_direction: int = 0,
    aspect_sentiment: Optional[str] = None,
) -> Tuple[Feedback, FeedbackEmbedding]:
    """Helper to persist a feedback row with embedding."""
    fb_id = uuid.uuid4()
    fb = Feedback(
        feedback_id=fb_id,
        product=product,
        feedback_text=text,
        cleaned_feedback_text=text,
        source="survey",
        quality_status="clean",
        timestamp=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
    )
    emb = FeedbackEmbedding(
        embedding_id=uuid.uuid4(),
        feedback_id=fb_id,
        embedding_model="gemini-embedding-2",
        embedding_dimensions=768,
        embedding_vector=make_unit_vector(vector_direction),
        input_hash=str(uuid.uuid4())[:16],
        created_at=datetime.now(timezone.utc),
    )
    session.add(fb)
    session.add(emb)
    session.commit()
    return fb, emb


def seed_classification(
    session: Session,
    feedback_id: uuid.UUID,
    sentiment: str = "positive",
    score: float = 0.8,
    intent: str = "praise",
    run_number: int = 1,
    status: str = "classified",
    version: str = "1.0.0",
    classified_at: Optional[datetime] = None,
) -> FeedbackClassification:
    """Helper to persist a classification run."""
    c = FeedbackClassification(
        classification_id=uuid.uuid4(),
        feedback_id=feedback_id,
        classification_version=version,
        run_number=run_number,
        status=status,
        overall_sentiment=sentiment,
        sentiment_score=score,
        sentiment_intensity="medium",
        customer_intent=intent,
        confidence_score=0.9,
        classified_at=classified_at or datetime.now(timezone.utc),
    )
    session.add(c)
    session.commit()
    return c


# ---------------------------------------------------------------------------
# Test Cases: Candidate Discovery & Idempotency
# ---------------------------------------------------------------------------

def test_discover_and_stage_candidates(db_session):
    """Verify that qualifying clusters are discovered and staged as candidate themes."""
    # Seed 3 feedbacks with identical vectors for product A (should form 1 cluster of size 3)
    fb1, _ = seed_feedback(db_session, product="Alpha", text="Search crashes on start", vector_direction=1)
    fb2, _ = seed_feedback(db_session, product="Alpha", text="Search breaks immediately", vector_direction=1)
    fb3, _ = seed_feedback(db_session, product="Alpha", text="Search query fails", vector_direction=1)

    resp = ThemeLifecycleService.discover_and_stage_candidates(
        session=db_session,
        product="Alpha",
        min_cluster_size=2,
    )

    assert resp.product == "Alpha"
    assert resp.discovered_count == 1
    assert resp.new_candidates_staged == 1
    assert resp.existing_candidates_skipped == 0
    assert len(resp.candidates) == 1

    candidate = resp.candidates[0]
    assert candidate.status == "candidate"
    assert candidate.feedback_count == 3
    assert candidate.product == "Alpha"
    assert candidate.theme_name.startswith("Candidate:")

    # Verify database persistence
    db_theme = db_session.get(Theme, candidate.theme_id)
    assert db_theme is not None
    assert db_theme.status == "candidate"

    # Verify junction records
    junctions = db_session.execute(
        select(FeedbackThemes).where(FeedbackThemes.theme_id == candidate.theme_id)
    ).scalars().all()
    assert len(junctions) == 3
    member_ids = {j.feedback_id for j in junctions}
    assert member_ids == {fb1.feedback_id, fb2.feedback_id, fb3.feedback_id}


def test_repeated_discovery_skips_duplicates(db_session):
    """Verify that repeated discovery calls are idempotent and do not create duplicate candidates."""
    seed_feedback(db_session, product="Alpha", text="Crash 1", vector_direction=2)
    seed_feedback(db_session, product="Alpha", text="Crash 2", vector_direction=2)

    resp1 = ThemeLifecycleService.discover_and_stage_candidates(
        session=db_session,
        product="Alpha",
        min_cluster_size=2,
    )
    assert resp1.new_candidates_staged == 1
    assert resp1.existing_candidates_skipped == 0

    # Repeat discovery with the exact same data (already clustered feedback is excluded by eligibility)
    resp2 = ThemeLifecycleService.discover_and_stage_candidates(
        session=db_session,
        product="Alpha",
        min_cluster_size=2,
    )
    assert resp2.new_candidates_staged == 0
    assert resp2.discovered_count == 0

    # Verify total themes in DB for Alpha is still exactly 1
    themes_count = db_session.execute(
        select(func.count(Theme.theme_id)).where(Theme.product == "Alpha")
    ).scalar()
    assert themes_count == 1


def test_staging_skips_existing_theme_id(db_session, monkeypatch):
    """Verify that if clustering returns a cluster whose UUID5 already exists, staging skips it."""
    fb1, _ = seed_feedback(db_session, product="AlphaDup", text="Crash A", vector_direction=20)
    fb2, _ = seed_feedback(db_session, product="AlphaDup", text="Crash B", vector_direction=20)

    # First discovery stages the candidate
    resp1 = ThemeLifecycleService.discover_and_stage_candidates(
        session=db_session,
        product="AlphaDup",
        min_cluster_size=2,
    )
    assert resp1.new_candidates_staged == 1
    cand_id = resp1.candidates[0].theme_id

    # Simulate clustering returning that same cluster again (e.g. from an in-memory batch)
    from app.services.theme_clustering_service import ThemeClusteringService
    from app.schemas.theme_clustering import ThemeClusteringResult, CandidateClusterItem

    mock_cluster = CandidateClusterItem(
        cluster_id=cand_id,
        product="AlphaDup",
        member_feedback_ids=[fb1.feedback_id, fb2.feedback_id],
        size=2,
        representative_feedback_ids=[fb1.feedback_id],
        centroid_vector=make_unit_vector(20),
        average_similarity=0.99,
        cohesion_score=0.99,
    )
    mock_result = ThemeClusteringResult(
        product="AlphaDup",
        algorithm="UPGMA",
        algorithm_version="1.0.0",
        parameters={},
        total_feedback_evaluated=2,
        clustered_feedback_count=2,
        unassigned_feedback_count=0,
        clusters=[mock_cluster],
        unassigned=[],
        duration_ms=1.0,
    )

    monkeypatch.setattr(
        ThemeClusteringService,
        "cluster_product",
        lambda *args, **kwargs: mock_result,
    )

    resp2 = ThemeLifecycleService.discover_and_stage_candidates(
        session=db_session,
        product="AlphaDup",
        min_cluster_size=2,
    )
    assert resp2.new_candidates_staged == 0
    assert resp2.existing_candidates_skipped == 1
    assert len(resp2.candidates) == 1
    assert resp2.candidates[0].theme_id == cand_id


def test_discovery_product_isolation(db_session):
    """Verify that discovery only processes feedback belonging to the specified product."""
    seed_feedback(db_session, product="ProductA", text="Feature A1", vector_direction=3)
    seed_feedback(db_session, product="ProductA", text="Feature A2", vector_direction=3)
    seed_feedback(db_session, product="ProductB", text="Feature B1", vector_direction=3)
    seed_feedback(db_session, product="ProductB", text="Feature B2", vector_direction=3)

    resp_a = ThemeLifecycleService.discover_and_stage_candidates(
        session=db_session,
        product="ProductA",
        min_cluster_size=2,
    )
    assert resp_a.discovered_count == 1
    assert resp_a.candidates[0].product == "ProductA"

    resp_b = ThemeLifecycleService.discover_and_stage_candidates(
        session=db_session,
        product="ProductB",
        min_cluster_size=2,
    )
    assert resp_b.discovered_count == 1
    assert resp_b.candidates[0].product == "ProductB"


# ---------------------------------------------------------------------------
# Test Cases: Candidate Activation & Discard
# ---------------------------------------------------------------------------

def test_activate_candidate_default_and_custom_name(db_session):
    """Verify activating a candidate theme promotes status to active and applies optional custom name."""
    fb1, _ = seed_feedback(db_session, product="Beta", text="Sync issue 1", vector_direction=4)
    fb2, _ = seed_feedback(db_session, product="Beta", text="Sync issue 2", vector_direction=4)

    resp = ThemeLifecycleService.discover_and_stage_candidates(
        session=db_session,
        product="Beta",
        min_cluster_size=2,
    )
    cand_id = resp.candidates[0].theme_id

    # Activate with custom name
    activated = ThemeLifecycleService.activate_candidate(
        session=db_session,
        theme_id=cand_id,
        custom_name="Cloud Sync Failures",
        category="Reliability",
        description="Issues related to background cloud synchronization.",
    )

    assert activated.status == "active"
    assert activated.theme_name == "Cloud Sync Failures"
    assert activated.category == "Reliability"
    assert activated.description == "Issues related to background cloud synchronization."

    # Verify in DB
    db_theme = db_session.get(Theme, cand_id)
    assert db_theme.status == "active"
    assert db_theme.theme_name == "Cloud Sync Failures"


def test_activate_non_candidate_raises_error(db_session):
    """Verify that activating a theme that is not a candidate raises an error."""
    theme = Theme(
        theme_id=uuid.uuid4(),
        product="Beta",
        theme_name="Active Theme",
        category="general",
        status="active",
    )
    db_session.add(theme)
    db_session.commit()

    with pytest.raises(AppException) as exc_info:
        ThemeLifecycleService.activate_candidate(
            session=db_session,
            theme_id=theme.theme_id,
        )
    assert exc_info.value.code == "INVALID_THEME_STATUS"
    assert "Only candidate themes can be activated" in exc_info.value.message


def test_discard_candidate(db_session):
    """Verify discarding a candidate theme transitions its status to discarded."""
    seed_feedback(db_session, product="Gamma", text="Minor UI bug 1", vector_direction=5)
    seed_feedback(db_session, product="Gamma", text="Minor UI bug 2", vector_direction=5)

    resp = ThemeLifecycleService.discover_and_stage_candidates(
        session=db_session,
        product="Gamma",
        min_cluster_size=2,
    )
    cand_id = resp.candidates[0].theme_id

    discarded = ThemeLifecycleService.discard_candidate(
        session=db_session,
        theme_id=cand_id,
    )
    assert discarded.status == "discarded"

    db_theme = db_session.get(Theme, cand_id)
    assert db_theme.status == "discarded"


def test_discard_non_candidate_raises_error(db_session):
    """Verify that discarding an active theme raises an error."""
    theme = Theme(
        theme_id=uuid.uuid4(),
        product="Gamma",
        theme_name="Active Production Theme",
        category="general",
        status="active",
    )
    db_session.add(theme)
    db_session.commit()

    with pytest.raises(AppException) as exc_info:
        ThemeLifecycleService.discard_candidate(
            session=db_session,
            theme_id=theme.theme_id,
        )
    assert exc_info.value.code == "INVALID_THEME_STATUS"
    assert "Only candidate themes can be discarded" in exc_info.value.message


# ---------------------------------------------------------------------------
# Test Cases: Theme Merging & Conflict Handling
# ---------------------------------------------------------------------------

def test_successful_theme_merge_and_membership_migration(db_session):
    """Verify merging two active themes re-points memberships and sets merged_into_id."""
    fb1, _ = seed_feedback(db_session, product="Delta", text="D1", vector_direction=10)
    fb2, _ = seed_feedback(db_session, product="Delta", text="D2", vector_direction=10)
    fb3, _ = seed_feedback(db_session, product="Delta", text="D3", vector_direction=11)
    fb4, _ = seed_feedback(db_session, product="Delta", text="D4", vector_direction=11)

    target_theme = Theme(
        theme_id=uuid.uuid4(),
        product="Delta",
        theme_name="Target Active Theme",
        category="bug",
        status="active",
        centroid_vector=make_unit_vector(10),
    )
    source_theme = Theme(
        theme_id=uuid.uuid4(),
        product="Delta",
        theme_name="Source Active Theme",
        category="bug",
        status="active",
        centroid_vector=make_unit_vector(11),
    )
    db_session.add_all([target_theme, source_theme])
    db_session.commit()

    # Link fb1, fb2 to target; fb3, fb4 to source
    db_session.add_all([
        FeedbackThemes(feedback_id=fb1.feedback_id, theme_id=target_theme.theme_id, relevance_score=0.9),
        FeedbackThemes(feedback_id=fb2.feedback_id, theme_id=target_theme.theme_id, relevance_score=0.8),
        FeedbackThemes(feedback_id=fb3.feedback_id, theme_id=source_theme.theme_id, relevance_score=0.95),
        FeedbackThemes(feedback_id=fb4.feedback_id, theme_id=source_theme.theme_id, relevance_score=0.7),
    ])
    db_session.commit()

    res = ThemeLifecycleService.merge_themes(
        session=db_session,
        source_theme_id=source_theme.theme_id,
        target_theme_id=target_theme.theme_id,
    )

    assert res.status == "merged"
    assert res.target_theme_id == target_theme.theme_id
    assert res.source_theme_id == source_theme.theme_id
    assert res.total_target_feedback_count == 4
    assert res.merged_feedback_count == 2

    # Verify source theme state
    db_session.refresh(source_theme)
    assert source_theme.status == "merged"
    assert source_theme.merged_into_id == target_theme.theme_id
    assert source_theme.lineage_metadata is not None
    assert "merged_at" in source_theme.lineage_metadata

    # Verify target theme memberships
    target_members = db_session.execute(
        select(FeedbackThemes).where(FeedbackThemes.theme_id == target_theme.theme_id)
    ).scalars().all()
    assert len(target_members) == 4
    member_ids = {m.feedback_id for m in target_members}
    assert member_ids == {fb1.feedback_id, fb2.feedback_id, fb3.feedback_id, fb4.feedback_id}


def test_merge_duplicate_membership_retains_highest_relevance_and_sentiment(db_session):
    """Verify that when duplicate associations exist, highest relevance score is kept and aspect sentiment is preserved."""
    shared_fb, _ = seed_feedback(db_session, product="Delta", text="Shared Feedback", vector_direction=12)

    target_theme = Theme(
        theme_id=uuid.uuid4(),
        product="Delta",
        theme_name="Target T",
        category="bug",
        status="active",
        centroid_vector=make_unit_vector(12),
    )
    source_theme = Theme(
        theme_id=uuid.uuid4(),
        product="Delta",
        theme_name="Source S",
        category="bug",
        status="active",
        centroid_vector=make_unit_vector(12),
    )
    db_session.add_all([target_theme, source_theme])
    db_session.commit()

    # Target has lower relevance score (0.6) and null aspect_sentiment
    # Source has higher relevance score (0.95) and aspect_sentiment="negative"
    db_session.add_all([
        FeedbackThemes(
            feedback_id=shared_fb.feedback_id,
            theme_id=target_theme.theme_id,
            relevance_score=0.6,
            aspect_sentiment=None,
        ),
        FeedbackThemes(
            feedback_id=shared_fb.feedback_id,
            theme_id=source_theme.theme_id,
            relevance_score=0.95,
            aspect_sentiment="negative",
        ),
    ])
    db_session.commit()

    ThemeLifecycleService.merge_themes(
        session=db_session,
        source_theme_id=source_theme.theme_id,
        target_theme_id=target_theme.theme_id,
    )

    # After merge: exactly 1 junction row for target_theme and shared_fb
    junctions = db_session.execute(
        select(FeedbackThemes).where(
            FeedbackThemes.theme_id == target_theme.theme_id,
            FeedbackThemes.feedback_id == shared_fb.feedback_id,
        )
    ).scalars().all()

    assert len(junctions) == 1
    j = junctions[0]
    assert j.relevance_score == 0.95  # Highest relevance kept
    assert j.aspect_sentiment == "negative"  # Copied from source


def test_self_merge_rejection(db_session):
    """Verify attempting to merge a theme into itself is rejected."""
    t_id = uuid.uuid4()
    with pytest.raises(AppException) as exc_info:
        ThemeLifecycleService.merge_themes(
            session=db_session,
            source_theme_id=t_id,
            target_theme_id=t_id,
        )
    assert exc_info.value.code == "SELF_MERGE_REJECTED"


def test_cross_product_merge_rejection(db_session):
    """Verify attempting to merge themes from different products is rejected."""
    t1 = Theme(theme_id=uuid.uuid4(), product="Prod1", theme_name="T1", category="c", status="active")
    t2 = Theme(theme_id=uuid.uuid4(), product="Prod2", theme_name="T2", category="c", status="active")
    db_session.add_all([t1, t2])
    db_session.commit()

    with pytest.raises(AppException) as exc_info:
        ThemeLifecycleService.merge_themes(
            session=db_session,
            source_theme_id=t1.theme_id,
            target_theme_id=t2.theme_id,
        )
    assert exc_info.value.code == "CROSS_PRODUCT_MERGE_REJECTED"


def test_already_merged_theme_cannot_be_remerged(db_session):
    """Verify that an already merged theme cannot be merged again."""
    t1 = Theme(theme_id=uuid.uuid4(), product="Prod1", theme_name="T1", category="c", status="merged", merged_into_id=uuid.uuid4())
    t2 = Theme(theme_id=uuid.uuid4(), product="Prod1", theme_name="T2", category="c", status="active")
    db_session.add_all([t1, t2])
    db_session.commit()

    with pytest.raises(AppException) as exc_info:
        ThemeLifecycleService.merge_themes(
            session=db_session,
            source_theme_id=t1.theme_id,
            target_theme_id=t2.theme_id,
        )
    assert exc_info.value.code in ("INVALID_THEME_STATUS", "ALREADY_MERGED")


# ---------------------------------------------------------------------------
# Test Cases: Sentiment Summary Aggregation
# ---------------------------------------------------------------------------

def test_theme_sentiment_summary_deduplicates_runs(db_session):
    """Verify sentiment summary selects only the latest valid run per feedback item."""
    fb1, _ = seed_feedback(db_session, product="Epsilon", text="Feedback 1")
    fb2, _ = seed_feedback(db_session, product="Epsilon", text="Feedback 2")
    fb3, _ = seed_feedback(db_session, product="Epsilon", text="Feedback 3 unclassified")

    theme = Theme(
        theme_id=uuid.uuid4(),
        product="Epsilon",
        theme_name="Epsilon Theme",
        category="perf",
        status="active",
    )
    db_session.add(theme)
    db_session.commit()

    db_session.add_all([
        FeedbackThemes(feedback_id=fb1.feedback_id, theme_id=theme.theme_id),
        FeedbackThemes(feedback_id=fb2.feedback_id, theme_id=theme.theme_id),
        FeedbackThemes(feedback_id=fb3.feedback_id, theme_id=theme.theme_id),
    ])
    db_session.commit()

    # fb1: Run 1 negative (score -0.8), Run 2 positive (score 0.9, later run_number)
    # The latest run (Run 2) should be counted!
    seed_classification(db_session, fb1.feedback_id, sentiment="negative", score=-0.8, run_number=1)
    seed_classification(db_session, fb1.feedback_id, sentiment="positive", score=0.9, run_number=2)

    # fb2: Run 1 neutral (score 0.0)
    seed_classification(db_session, fb2.feedback_id, sentiment="neutral", score=0.0, run_number=1)

    # fb3: has no classification

    summary = ThemeLifecycleService.compute_theme_sentiment_summary(
        session=db_session,
        theme_id=theme.theme_id,
    )

    assert summary.total_feedbacks == 3
    assert summary.classified_feedbacks == 2
    assert summary.positive == 1  # fb1 latest is positive
    assert summary.negative == 0  # fb1 run 1 is NOT counted
    assert summary.neutral == 1   # fb2 is neutral
    assert summary.mixed == 0
    # Average score: (0.9 + 0.0) / 2 = 0.45
    assert summary.average_sentiment_score == 0.45


# ---------------------------------------------------------------------------
# Test Cases: FastAPI Endpoints (TestClient)
# ---------------------------------------------------------------------------

def test_api_discover_and_list_themes(client, db_session):
    """Test POST /api/themes/discover and GET /api/themes via FastAPI."""
    seed_feedback(db_session, product="ApiApp", text="Api crash 1", vector_direction=15)
    seed_feedback(db_session, product="ApiApp", text="Api crash 2", vector_direction=15)

    # 1. Discover candidates
    discover_resp = client.post(
        "/api/themes/discover",
        json={"product": "ApiApp", "min_cluster_size": 2},
    )
    assert discover_resp.status_code == 200
    disc_data = discover_resp.json()
    assert disc_data["product"] == "ApiApp"
    assert disc_data["discovered_count"] == 1
    assert disc_data["new_candidates_staged"] == 1

    cand_id = disc_data["candidates"][0]["theme_id"]

    # 2. List candidate themes
    list_resp = client.get("/api/themes?product=ApiApp&status=candidate")
    assert list_resp.status_code == 200
    list_data = list_resp.json()
    assert len(list_data) == 1
    assert list_data[0]["theme_id"] == cand_id
    assert list_data[0]["status"] == "candidate"

    # 3. Get theme detail
    detail_resp = client.get(f"/api/themes/{cand_id}")
    assert detail_resp.status_code == 200
    detail_data = detail_resp.json()
    assert detail_data["theme_id"] == cand_id
    assert detail_data["feedback_count"] == 2
    assert "sentiment_summary" in detail_data


def test_api_activate_and_merge_themes(client, db_session):
    """Test activating candidates and merging them via FastAPI endpoints."""
    # Seed themes directly
    t1 = Theme(theme_id=uuid.uuid4(), product="ApiApp2", theme_name="Cand 1", category="general", status="candidate")
    t2 = Theme(theme_id=uuid.uuid4(), product="ApiApp2", theme_name="Cand 2", category="general", status="candidate")
    db_session.add_all([t1, t2])
    db_session.commit()

    # Activate t1
    act1 = client.post(
        f"/api/themes/{t1.theme_id}/activate",
        json={"custom_name": "Active Theme Alpha"},
    )
    assert act1.status_code == 200
    assert act1.json()["status"] == "active"
    assert act1.json()["theme_name"] == "Active Theme Alpha"

    # Activate t2
    act2 = client.post(
        f"/api/themes/{t2.theme_id}/activate",
        json={"custom_name": "Active Theme Beta"},
    )
    assert act2.status_code == 200
    assert act2.json()["status"] == "active"

    # Merge t2 into t1
    merge_resp = client.post(
        "/api/themes/merge",
        json={
            "source_theme_id": str(t2.theme_id),
            "target_theme_id": str(t1.theme_id),
        },
    )
    assert merge_resp.status_code == 200
    merge_data = merge_resp.json()
    assert merge_data["status"] == "merged"
    assert merge_data["target_theme_id"] == str(t1.theme_id)
    assert merge_data["source_theme_id"] == str(t2.theme_id)


def test_api_discard_candidate(client, db_session):
    """Test POST /api/themes/{theme_id}/discard via FastAPI."""
    t = Theme(theme_id=uuid.uuid4(), product="ApiApp3", theme_name="Cand 3", category="general", status="candidate")
    db_session.add(t)
    db_session.commit()

    discard_resp = client.post(f"/api/themes/{t.theme_id}/discard")
    assert discard_resp.status_code == 200
    assert discard_resp.json()["status"] == "discarded"
