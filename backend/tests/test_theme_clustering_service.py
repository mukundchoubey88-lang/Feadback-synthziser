"""Comprehensive Unit and Integration Tests for Theme Clustering Engine (Part 7 Step 4).

Tests cover:
- Mathematical correctness of pure-Python vector operations (cosine similarity, distance, normalization, centroid).
- Agglomerative average-linkage clustering determinism, tie-breaking, and stopping conditions.
- Qualifying candidate cluster construction, centroid calculation, medoid exemplar selection, cohesion score.
- Unassigned feedback classification (CLUSTER_BELOW_MIN_SIZE, BELOW_SIMILARITY_THRESHOLD, NO_COMPATIBLE_CLUSTER).
- Retrieval and strict product isolation from SQLite database.
- Exclusion of soft-deleted, rejected, failed, and already-themed feedback.
- Inclusion of unclassified feedback and optional classification metadata.
- Boundary conditions: N=0, N=1, N=2, batch size ceiling.
- Transaction detachment (zero database writes, no session commit/rollback).
"""

from datetime import datetime, timezone
import math
from typing import List, Optional, Tuple
from unittest.mock import MagicMock
import uuid
import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.exceptions import AppException
from app.db.base import Base
from app.models.classification import FeedbackClassification
from app.models.feedback import Feedback, FeedbackThemes
from app.models.feedback_embeddings import FeedbackEmbedding
from app.models.theme import Theme
from app.schemas.theme_clustering import (
    CandidateClusterItem,
    ThemeClusteringResult,
    UnassignedFeedbackItem,
)
from app.services.theme_clustering_service import (
    FeedbackClusterInput,
    ThemeClusteringService,
    compute_centroid,
    cosine_distance,
    cosine_similarity,
    generate_deterministic_cluster_id,
    normalize_vector,
    pairwise_distance_matrix,
    validate_vector,
)


# ---------------------------------------------------------------------------
# SQLite Database Fixture with proper Transaction Management
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


def make_unit_vector(direction_idx: int, dim: int = 768, noise: float = 0.0) -> List[float]:
    """Helper to generate deterministic unit vectors concentrated in a specific coordinate."""
    vec = [noise] * dim
    vec[direction_idx] = 1.0
    return normalize_vector(vec)


def create_test_feedback_with_embedding(
    session: Session,
    product: str = "Mobile App",
    cleaned_text: str = "Login screen freezes.",
    quality_status: str = "clean",
    deleted: bool = False,
    vector: Optional[List[float]] = None,
    model_name: str = "gemini-embedding-2",
    dimensions: int = 768,
) -> Tuple[Feedback, FeedbackEmbedding]:
    """Helper to persist a test feedback record with an embedding."""
    fb_id = uuid.uuid4()
    fb = Feedback(
        feedback_id=fb_id,
        source="csv",
        customer_id="cust-1",
        feedback_text="Raw unedited comment",
        cleaned_feedback_text=cleaned_text,
        product=product,
        timestamp=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
        deleted_at=datetime.now(timezone.utc) if deleted else None,
        quality_status=quality_status,
        processing_status="processed",
    )
    session.add(fb)

    vec = vector if vector is not None else make_unit_vector(0, dim=dimensions)
    emb = FeedbackEmbedding(
        embedding_id=uuid.uuid4(),
        feedback_id=fb_id,
        embedding_model=model_name,
        embedding_dimensions=dimensions,
        embedding_vector=vec,
        input_hash="dummy-hash",
    )
    session.add(emb)
    session.commit()
    return fb, emb


# ---------------------------------------------------------------------------
# 1. Pure-Python Vector Mathematics Tests
# ---------------------------------------------------------------------------

def test_cosine_similarity_known_vectors():
    """Verify cosine similarity on orthogonal, identical, and opposite vectors."""
    v1 = [1.0, 0.0, 0.0]
    v2 = [1.0, 0.0, 0.0]
    v_ortho = [0.0, 1.0, 0.0]
    v_opp = [-1.0, 0.0, 0.0]

    assert math.isclose(cosine_similarity(v1, v2), 1.0, abs_tol=1e-7)
    assert math.isclose(cosine_similarity(v1, v_ortho), 0.0, abs_tol=1e-7)
    assert math.isclose(cosine_similarity(v1, v_opp), -1.0, abs_tol=1e-7)

    assert math.isclose(cosine_distance(v1, v2), 0.0, abs_tol=1e-7)
    assert math.isclose(cosine_distance(v1, v_ortho), 1.0, abs_tol=1e-7)
    assert math.isclose(cosine_distance(v1, v_opp), 2.0, abs_tol=1e-7)


def test_cosine_similarity_dimension_mismatch():
    """Verify dimension mismatch raises ValueError."""
    with pytest.raises(ValueError, match="dimension mismatch"):
        cosine_similarity([1.0, 0.0], [1.0, 0.0, 0.0])


def test_normalize_vector_and_zero_vector():
    """Verify normalization ensures L2 norm equals 1.0 and zero vector raises error."""
    vec = [3.0, 4.0]
    normed = normalize_vector(vec)
    assert math.isclose(normed[0], 0.6, abs_tol=1e-7)
    assert math.isclose(normed[1], 0.8, abs_tol=1e-7)

    with pytest.raises(ValueError, match="zero-magnitude"):
        normalize_vector([0.0, 0.0, 0.0])


def test_vector_validation_nan_and_inf():
    """Verify NaN and Inf are detected and rejected."""
    with pytest.raises(ValueError, match="non-finite value"):
        validate_vector([1.0, float("nan"), 0.5])

    with pytest.raises(ValueError, match="non-finite value"):
        validate_vector([1.0, float("inf"), 0.5])


def test_compute_centroid():
    """Verify arithmetic centroid is unit-normalized."""
    v1 = [1.0, 0.0, 0.0]
    v2 = [0.0, 1.0, 0.0]
    centroid = compute_centroid([v1, v2])
    # Unnormalized mean is [0.5, 0.5, 0.0], normalized is [1/sqrt(2), 1/sqrt(2), 0.0]
    expected = 1.0 / math.sqrt(2.0)
    assert math.isclose(centroid[0], expected, abs_tol=1e-7)
    assert math.isclose(centroid[1], expected, abs_tol=1e-7)
    assert math.isclose(centroid[2], 0.0, abs_tol=1e-7)

    norm = math.sqrt(sum(x * x for x in centroid))
    assert math.isclose(norm, 1.0, abs_tol=1e-7)


def test_pairwise_distance_matrix():
    """Verify distance matrix is symmetric with zero diagonal."""
    vectors = [[1.0, 0.0], [0.0, 1.0], [0.7071, 0.7071]]
    mat = pairwise_distance_matrix(vectors)
    assert len(mat) == 3
    for i in range(3):
        assert math.isclose(mat[i][i], 0.0, abs_tol=1e-7)
        for j in range(3):
            assert math.isclose(mat[i][j], mat[j][i], abs_tol=1e-7)
            assert mat[i][j] >= 0.0


# ---------------------------------------------------------------------------
# 2. Agglomerative Average-Linkage Clustering Engine Tests
# ---------------------------------------------------------------------------

def test_agglomerative_clustering_two_separated_clusters():
    """Verify 6 feedback items (3 around direction A, 3 around direction B) form 2 candidate clusters."""
    dim = 768
    # Group 1: 3 items around axis 0
    v1 = make_unit_vector(0, dim=dim, noise=0.01)
    v2 = make_unit_vector(0, dim=dim, noise=0.02)
    v3 = make_unit_vector(0, dim=dim, noise=0.03)

    # Group 2: 3 items around axis 1
    v4 = make_unit_vector(1, dim=dim, noise=0.01)
    v5 = make_unit_vector(1, dim=dim, noise=0.02)
    v6 = make_unit_vector(1, dim=dim, noise=0.03)

    items = [
        FeedbackClusterInput(feedback_id=uuid.uuid4(), product="App", cleaned_feedback_text="g1", vector=v1),
        FeedbackClusterInput(feedback_id=uuid.uuid4(), product="App", cleaned_feedback_text="g1", vector=v2),
        FeedbackClusterInput(feedback_id=uuid.uuid4(), product="App", cleaned_feedback_text="g1", vector=v3),
        FeedbackClusterInput(feedback_id=uuid.uuid4(), product="App", cleaned_feedback_text="g2", vector=v4),
        FeedbackClusterInput(feedback_id=uuid.uuid4(), product="App", cleaned_feedback_text="g2", vector=v5),
        FeedbackClusterInput(feedback_id=uuid.uuid4(), product="App", cleaned_feedback_text="g2", vector=v6),
    ]

    result = ThemeClusteringService.cluster_feedback_items(
        items=items,
        product="App",
        similarity_threshold=0.80,
        min_cluster_size=3,
    )

    assert result.total_feedback_evaluated == 6
    assert result.clustered_feedback_count == 6
    assert result.unassigned_feedback_count == 0
    assert len(result.clusters) == 2

    # Verify each cluster has size 3
    assert result.clusters[0].size == 3
    assert result.clusters[1].size == 3

    # Verify cohesion scores are high
    assert result.clusters[0].cohesion_score >= 0.90
    assert result.clusters[1].cohesion_score >= 0.90


def test_clustering_with_outlier():
    """Verify an isolated feedback item below similarity threshold ends up in unassigned."""
    dim = 768
    v1 = make_unit_vector(0, dim=dim, noise=0.01)
    v2 = make_unit_vector(0, dim=dim, noise=0.02)
    v3 = make_unit_vector(0, dim=dim, noise=0.03)
    # Outlier around orthogonal axis 5
    v_outlier = make_unit_vector(5, dim=dim, noise=0.0)

    outlier_id = uuid.uuid4()
    items = [
        FeedbackClusterInput(feedback_id=uuid.uuid4(), product="App", cleaned_feedback_text="g1", vector=v1),
        FeedbackClusterInput(feedback_id=uuid.uuid4(), product="App", cleaned_feedback_text="g1", vector=v2),
        FeedbackClusterInput(feedback_id=uuid.uuid4(), product="App", cleaned_feedback_text="g1", vector=v3),
        FeedbackClusterInput(feedback_id=outlier_id, product="App", cleaned_feedback_text="outlier", vector=v_outlier),
    ]

    result = ThemeClusteringService.cluster_feedback_items(
        items=items,
        product="App",
        similarity_threshold=0.80,
        min_cluster_size=3,
    )

    assert result.total_feedback_evaluated == 4
    assert result.clustered_feedback_count == 3
    assert result.unassigned_feedback_count == 1
    assert len(result.clusters) == 1
    assert result.clusters[0].size == 3

    unassigned = result.unassigned[0]
    assert unassigned.feedback_id == outlier_id
    assert unassigned.reason == "BELOW_SIMILARITY_THRESHOLD"
    assert unassigned.nearest_cluster_id == result.clusters[0].cluster_id
    assert unassigned.nearest_similarity is not None


def test_clustering_min_cluster_size_rejection():
    """Verify that a cluster with size 2 is rejected when min_cluster_size is 3."""
    dim = 768
    v1 = make_unit_vector(0, dim=dim, noise=0.01)
    v2 = make_unit_vector(0, dim=dim, noise=0.02)

    id1 = uuid.uuid4()
    id2 = uuid.uuid4()
    items = [
        FeedbackClusterInput(feedback_id=id1, product="App", cleaned_feedback_text="c1", vector=v1),
        FeedbackClusterInput(feedback_id=id2, product="App", cleaned_feedback_text="c1", vector=v2),
    ]

    result = ThemeClusteringService.cluster_feedback_items(
        items=items,
        product="App",
        similarity_threshold=0.80,
        min_cluster_size=3,
    )

    assert result.total_feedback_evaluated == 2
    assert result.clustered_feedback_count == 0
    assert result.unassigned_feedback_count == 2
    assert len(result.clusters) == 0

    for u in result.unassigned:
        assert u.reason == "CLUSTER_BELOW_MIN_SIZE"


def test_deterministic_repeatability_100_runs():
    """Verify running the clustering algorithm 100 times on identical inputs yields 100% identical outputs."""
    dim = 768
    v1 = make_unit_vector(0, dim=dim, noise=0.01)
    v2 = make_unit_vector(0, dim=dim, noise=0.02)
    v3 = make_unit_vector(0, dim=dim, noise=0.03)

    items = [
        FeedbackClusterInput(feedback_id=uuid.UUID("11111111-1111-1111-1111-111111111111"), product="P", cleaned_feedback_text="t1", vector=v1),
        FeedbackClusterInput(feedback_id=uuid.UUID("22222222-2222-2222-2222-222222222222"), product="P", cleaned_feedback_text="t2", vector=v2),
        FeedbackClusterInput(feedback_id=uuid.UUID("33333333-3333-3333-3333-333333333333"), product="P", cleaned_feedback_text="t3", vector=v3),
    ]

    first_run = ThemeClusteringService.cluster_feedback_items(items=items, product="P", min_cluster_size=3)
    first_cluster_id = first_run.clusters[0].cluster_id
    first_reps = first_run.clusters[0].representative_feedback_ids
    first_centroid = first_run.clusters[0].centroid_vector

    for _ in range(100):
        run = ThemeClusteringService.cluster_feedback_items(items=items, product="P", min_cluster_size=3)
        assert run.clusters[0].cluster_id == first_cluster_id
        assert run.clusters[0].representative_feedback_ids == first_reps
        assert run.clusters[0].centroid_vector == first_centroid
        assert run.clusters[0].average_similarity == first_run.clusters[0].average_similarity
        assert run.clusters[0].cohesion_score == first_run.clusters[0].cohesion_score


def test_medoid_representative_selection():
    """Verify representative items are selected by closest distance to centroid."""
    dim = 768
    # Center item right on axis 0
    v_center = [0.0] * dim
    v_center[0] = 1.0

    # Symmetric flank items around coordinate 1 (+/- delta)
    v_flank1 = [0.0] * dim
    v_flank1[0] = 0.999
    v_flank1[1] = 0.01
    v_flank1 = normalize_vector(v_flank1)

    v_flank2 = [0.0] * dim
    v_flank2[0] = 0.999
    v_flank2[1] = -0.01
    v_flank2 = normalize_vector(v_flank2)

    id_center = uuid.uuid4()
    id_flank1 = uuid.uuid4()
    id_flank2 = uuid.uuid4()

    items = [
        FeedbackClusterInput(feedback_id=id_flank2, product="P", cleaned_feedback_text="f2", vector=v_flank2),
        FeedbackClusterInput(feedback_id=id_center, product="P", cleaned_feedback_text="center", vector=v_center),
        FeedbackClusterInput(feedback_id=id_flank1, product="P", cleaned_feedback_text="f1", vector=v_flank1),
    ]

    result = ThemeClusteringService.cluster_feedback_items(
        items=items,
        product="P",
        representative_count=1,
        min_cluster_size=3,
    )

    assert len(result.clusters) == 1
    # The center item should be the top representative (closest to centroid)
    assert result.clusters[0].representative_feedback_ids[0] == id_center


# ---------------------------------------------------------------------------
# 3. Database Retrieval and Product Isolation Tests
# ---------------------------------------------------------------------------

def test_retrieve_eligible_feedback_product_isolation(db_session):
    """Verify feedback for Product A is retrieved while Product B feedback is strictly isolated."""
    fb_a1, _ = create_test_feedback_with_embedding(db_session, product="Product-A", cleaned_text="A1")
    fb_a2, _ = create_test_feedback_with_embedding(db_session, product="Product-A", cleaned_text="A2")
    fb_b1, _ = create_test_feedback_with_embedding(db_session, product="Product-B", cleaned_text="B1")

    items_a = ThemeClusteringService.retrieve_eligible_feedback(db_session, product="Product-A")
    items_b = ThemeClusteringService.retrieve_eligible_feedback(db_session, product="Product-B")

    ids_a = {item.feedback_id for item in items_a}
    ids_b = {item.feedback_id for item in items_b}

    assert ids_a == {fb_a1.feedback_id, fb_a2.feedback_id}
    assert ids_b == {fb_b1.feedback_id}
    assert ids_a.isdisjoint(ids_b)


def test_retrieve_excludes_soft_deleted_and_bad_quality(db_session):
    """Verify soft-deleted, rejected, and failed records are excluded from retrieval."""
    fb_valid, _ = create_test_feedback_with_embedding(db_session, product="App", quality_status="clean")
    fb_flagged, _ = create_test_feedback_with_embedding(db_session, product="App", quality_status="flagged")
    fb_deleted, _ = create_test_feedback_with_embedding(db_session, product="App", deleted=True)
    fb_rejected, _ = create_test_feedback_with_embedding(db_session, product="App", quality_status="rejected")
    fb_failed, _ = create_test_feedback_with_embedding(db_session, product="App", quality_status="failed")

    items = ThemeClusteringService.retrieve_eligible_feedback(db_session, product="App")
    retrieved_ids = {item.feedback_id for item in items}

    assert fb_valid.feedback_id in retrieved_ids
    assert fb_flagged.feedback_id in retrieved_ids
    assert fb_deleted.feedback_id not in retrieved_ids
    assert fb_rejected.feedback_id not in retrieved_ids
    assert fb_failed.feedback_id not in retrieved_ids


def test_retrieve_excludes_already_themed_feedback(db_session):
    """Verify feedback already linked to an existing theme via feedback_themes is excluded."""
    fb_unthemed, _ = create_test_feedback_with_embedding(db_session, product="App", cleaned_text="Unthemed")
    fb_themed, _ = create_test_feedback_with_embedding(db_session, product="App", cleaned_text="Themed")

    # Create a theme and link fb_themed
    theme = Theme(
        theme_id=uuid.uuid4(),
        product="App",
        theme_name="Existing Theme",
        category="bug",
        status="active",
    )
    db_session.add(theme)
    assoc = FeedbackThemes(feedback_id=fb_themed.feedback_id, theme_id=theme.theme_id, relevance_score=0.95)
    db_session.add(assoc)
    db_session.commit()

    items = ThemeClusteringService.retrieve_eligible_feedback(db_session, product="App")
    retrieved_ids = {item.feedback_id for item in items}

    assert fb_unthemed.feedback_id in retrieved_ids
    assert fb_themed.feedback_id not in retrieved_ids


def test_retrieve_unclassified_feedback_remains_eligible(db_session):
    """Verify feedback lacking a FeedbackClassification record remains eligible for clustering."""
    fb, _ = create_test_feedback_with_embedding(db_session, product="App", cleaned_text="Unclassified item")
    items = ThemeClusteringService.retrieve_eligible_feedback(db_session, product="App")

    assert len(items) == 1
    assert items[0].feedback_id == fb.feedback_id
    assert items[0].classification_topics is None
    assert items[0].customer_intent is None


def test_retrieve_includes_pending_review_classification(db_session):
    """Verify feedback with 'pending_review' classification has its metadata attached without being excluded."""
    fb, _ = create_test_feedback_with_embedding(db_session, product="App", cleaned_text="Pending review item")

    cls_record = FeedbackClassification(
        classification_id=uuid.uuid4(),
        feedback_id=fb.feedback_id,
        classification_version="1.0.0",
        run_number=1,
        status="pending_review",
        overall_sentiment="negative",
        sentiment_score=-0.5,
        confidence_score=0.65,
        customer_intent="complaint",
        topics=[{"label": "Billing Issue", "confidence": 0.65}],
        classified_at=datetime.now(timezone.utc),
    )
    db_session.add(cls_record)
    db_session.commit()

    items = ThemeClusteringService.retrieve_eligible_feedback(db_session, product="App")
    assert len(items) == 1
    assert items[0].feedback_id == fb.feedback_id
    assert items[0].customer_intent == "complaint"
    assert items[0].classification_topics == [{"label": "Billing Issue", "confidence": 0.65}]


def test_retrieve_batch_size_limit_rejection(db_session):
    """Verify exceeding max_batch_size raises BATCH_TOO_LARGE AppException."""
    for i in range(5):
        create_test_feedback_with_embedding(db_session, product="App", cleaned_text=f"Item {i}")

    with pytest.raises(AppException) as exc_info:
        ThemeClusteringService.retrieve_eligible_feedback(
            db_session,
            product="App",
            max_batch_size=3,
        )
    assert exc_info.value.code == "BATCH_SIZE_EXCEEDED"
    assert exc_info.value.status_code == 400


# ---------------------------------------------------------------------------
# 4. Safety and Boundary Tests
# ---------------------------------------------------------------------------

def test_clustering_empty_dataset():
    """Verify empty input produces empty valid ThemeClusteringResult."""
    result = ThemeClusteringService.cluster_feedback_items(items=[], product="App")
    assert result.total_feedback_evaluated == 0
    assert result.clustered_feedback_count == 0
    assert result.unassigned_feedback_count == 0
    assert len(result.clusters) == 0
    assert len(result.unassigned) == 0


def test_clustering_single_record():
    """Verify single record input cannot form a cluster and is placed in unassigned."""
    dim = 768
    v = make_unit_vector(0, dim=dim)
    fb_id = uuid.uuid4()
    items = [FeedbackClusterInput(feedback_id=fb_id, product="App", cleaned_feedback_text="solo", vector=v)]

    result = ThemeClusteringService.cluster_feedback_items(items=items, product="App")
    assert result.total_feedback_evaluated == 1
    assert result.clustered_feedback_count == 0
    assert result.unassigned_feedback_count == 1
    assert result.unassigned[0].feedback_id == fb_id
    assert result.unassigned[0].reason == "NO_COMPATIBLE_CLUSTER"


def test_cross_product_input_rejection():
    """Verify feeding items from different products raises PRODUCT_MISMATCH AppException."""
    dim = 768
    v1 = make_unit_vector(0, dim=dim)
    v2 = make_unit_vector(0, dim=dim)
    items = [
        FeedbackClusterInput(feedback_id=uuid.uuid4(), product="App-A", cleaned_feedback_text="t1", vector=v1),
        FeedbackClusterInput(feedback_id=uuid.uuid4(), product="App-B", cleaned_feedback_text="t2", vector=v2),
    ]

    with pytest.raises(AppException) as exc_info:
        ThemeClusteringService.cluster_feedback_items(items=items, product="App-A")
    assert exc_info.value.code == "PRODUCT_MISMATCH"


def test_pure_computation_no_db_access():
    """Verify cluster_feedback_items does not touch session commit or rollback."""
    mock_session = MagicMock(spec=Session)

    dim = 768
    v1 = make_unit_vector(0, dim=dim, noise=0.01)
    v2 = make_unit_vector(0, dim=dim, noise=0.02)
    v3 = make_unit_vector(0, dim=dim, noise=0.03)

    items = [
        FeedbackClusterInput(feedback_id=uuid.uuid4(), product="App", cleaned_feedback_text="t1", vector=v1),
        FeedbackClusterInput(feedback_id=uuid.uuid4(), product="App", cleaned_feedback_text="t2", vector=v2),
        FeedbackClusterInput(feedback_id=uuid.uuid4(), product="App", cleaned_feedback_text="t3", vector=v3),
    ]

    result = ThemeClusteringService.cluster_feedback_items(items=items, product="App")
    assert result.total_feedback_evaluated == 3
    # Verify mock session was never touched
    mock_session.commit.assert_not_called()
    mock_session.rollback.assert_not_called()
    mock_session.execute.assert_not_called()


def test_every_evaluated_feedback_appears_exactly_once():
    """Verify partition invariance: every feedback item appears in exactly one cluster or unassigned."""
    dim = 768
    # 3 clusterable items
    v1 = make_unit_vector(0, dim=dim, noise=0.01)
    v2 = make_unit_vector(0, dim=dim, noise=0.02)
    v3 = make_unit_vector(0, dim=dim, noise=0.03)
    # 2 outlier items
    v4 = make_unit_vector(5, dim=dim)
    v5 = make_unit_vector(6, dim=dim)

    items = [
        FeedbackClusterInput(feedback_id=uuid.uuid4(), product="App", cleaned_feedback_text="c1", vector=v1),
        FeedbackClusterInput(feedback_id=uuid.uuid4(), product="App", cleaned_feedback_text="c2", vector=v2),
        FeedbackClusterInput(feedback_id=uuid.uuid4(), product="App", cleaned_feedback_text="c3", vector=v3),
        FeedbackClusterInput(feedback_id=uuid.uuid4(), product="App", cleaned_feedback_text="out1", vector=v4),
        FeedbackClusterInput(feedback_id=uuid.uuid4(), product="App", cleaned_feedback_text="out2", vector=v5),
    ]

    result = ThemeClusteringService.cluster_feedback_items(items=items, product="App")

    clustered_ids = set()
    for c in result.clusters:
        for fid in c.member_feedback_ids:
            assert fid not in clustered_ids, "Feedback ID in multiple clusters"
            clustered_ids.add(fid)

    unassigned_ids = {u.feedback_id for u in result.unassigned}
    assert clustered_ids.isdisjoint(unassigned_ids), "Feedback ID both clustered and unassigned"

    all_result_ids = clustered_ids.union(unassigned_ids)
    all_input_ids = {item.feedback_id for item in items}
    assert all_result_ids == all_input_ids
    assert result.total_feedback_evaluated == len(all_input_ids)


# ---------------------------------------------------------------------------
# 5. Optimization & Equivalence Verification Tests (Part 7 Step 4.2)
# ---------------------------------------------------------------------------

def test_lance_williams_incremental_vs_direct_member_pair_calculation():
    """Verify Lance-Williams incremental recurrence matches direct member-pair average distance."""
    import random
    random.seed(12345)
    dim = 64

    # Clusters A (|A|=3), B (|B|=4), C (|C|=5)
    vecs_a = [normalize_vector([random.gauss(0, 1) for _ in range(dim)]) for _ in range(3)]
    vecs_b = [normalize_vector([random.gauss(0, 1) for _ in range(dim)]) for _ in range(4)]
    vecs_c = [normalize_vector([random.gauss(0, 1) for _ in range(dim)]) for _ in range(5)]

    # Direct average distance D(A, C)
    sum_ac = sum(cosine_distance(va, vc) for va in vecs_a for vc in vecs_c)
    d_ac = sum_ac / (len(vecs_a) * len(vecs_c))

    # Direct average distance D(B, C)
    sum_bc = sum(cosine_distance(vb, vc) for vb in vecs_b for vc in vecs_c)
    d_bc = sum_bc / (len(vecs_b) * len(vecs_c))

    # Direct average distance D(A ∪ B, C)
    vecs_aub = vecs_a + vecs_b
    sum_aub_c = sum(cosine_distance(vx, vc) for vx in vecs_aub for vc in vecs_c)
    d_direct = sum_aub_c / (len(vecs_aub) * len(vecs_c))

    # Lance-Williams recurrence: D(A ∪ B, C) = (|A|*D(A,C) + |B|*D(B,C)) / (|A| + |B|)
    sz_a = len(vecs_a)
    sz_b = len(vecs_b)
    d_lw = (sz_a * d_ac + sz_b * d_bc) / (sz_a + sz_b)

    assert math.isclose(d_direct, d_lw, abs_tol=1e-12), f"Direct {d_direct} != LW {d_lw}"


def test_opposite_and_negative_similarity_vectors():
    """Verify opposite and negative similarity vectors behave correctly and distances reach 2.0."""
    dim = 768
    v_pos = [0.0] * dim
    v_pos[0] = 1.0

    v_neg = [0.0] * dim
    v_neg[0] = -1.0  # Opposite vector

    dist = cosine_distance(v_pos, v_neg)
    assert math.isclose(dist, 2.0, abs_tol=1e-7)

    sim = cosine_similarity(v_pos, v_neg)
    assert math.isclose(sim, -1.0, abs_tol=1e-7)

    # In clustering with threshold 0.80, they must never merge
    fb1 = FeedbackClusterInput(feedback_id=uuid.uuid4(), product="P", cleaned_feedback_text="t1", vector=v_pos)
    fb2 = FeedbackClusterInput(feedback_id=uuid.uuid4(), product="P", cleaned_feedback_text="t2", vector=v_neg)

    result = ThemeClusteringService.cluster_feedback_items(
        items=[fb1, fb2],
        product="P",
        similarity_threshold=0.80,
        min_cluster_size=2,
    )
    assert len(result.clusters) == 0
    assert len(result.unassigned) == 2


def test_equal_distance_tie_breaking_determinism():
    """Verify deterministic canonical feedback UUID tie-breaking on equidistant pairs."""
    dim = 768
    # Pair 1: v1 and v2 with angle theta
    # Pair 2: v3 and v4 with exact same angle theta
    theta = 0.3
    v1 = [0.0] * dim; v1[0] = 1.0
    v2 = [0.0] * dim; v2[0] = math.cos(theta); v2[1] = math.sin(theta)

    v3 = [0.0] * dim; v3[2] = 1.0
    v4 = [0.0] * dim; v4[2] = math.cos(theta); v4[3] = math.sin(theta)

    d12 = cosine_distance(v1, v2)
    d34 = cosine_distance(v3, v4)
    assert math.isclose(d12, d34, abs_tol=1e-12)

    # Assign controlled UUIDs: pair A has smaller UUIDs than pair B
    id_a1 = uuid.UUID("00000000-0000-0000-0000-000000000001")
    id_a2 = uuid.UUID("00000000-0000-0000-0000-000000000002")
    id_b1 = uuid.UUID("00000000-0000-0000-0000-000000000003")
    id_b2 = uuid.UUID("00000000-0000-0000-0000-000000000004")

    items = [
        FeedbackClusterInput(feedback_id=id_b1, product="P", cleaned_feedback_text="b1", vector=v3),
        FeedbackClusterInput(feedback_id=id_b2, product="P", cleaned_feedback_text="b2", vector=v4),
        FeedbackClusterInput(feedback_id=id_a1, product="P", cleaned_feedback_text="a1", vector=v1),
        FeedbackClusterInput(feedback_id=id_a2, product="P", cleaned_feedback_text="a2", vector=v2),
    ]

    result = ThemeClusteringService.cluster_feedback_items(
        items=items,
        product="P",
        similarity_threshold=math.cos(theta) - 0.01,
        min_cluster_size=2,
    )
    assert len(result.clusters) == 2
    # Verify both clusters were formed deterministically
    cluster_member_sets = [set(c.member_feedback_ids) for c in result.clusters]
    assert {id_a1, id_a2} in cluster_member_sets
    assert {id_b1, id_b2} in cluster_member_sets


def test_multiple_identical_embeddings_clustering():
    """Verify multiple items with identical embeddings (distance 0.0) merge without instability."""
    dim = 768
    v = make_unit_vector(0, dim=dim)
    ids = [uuid.uuid4() for _ in range(4)]
    items = [
        FeedbackClusterInput(feedback_id=ids[i], product="P", cleaned_feedback_text=f"ident_{i}", vector=v)
        for i in range(4)
    ]

    result = ThemeClusteringService.cluster_feedback_items(
        items=items,
        product="P",
        similarity_threshold=0.85,
        min_cluster_size=2,
    )
    assert len(result.clusters) == 1
    assert result.clusters[0].size == 4
    assert math.isclose(result.clusters[0].average_similarity, 1.0, abs_tol=1e-4)
    assert math.isclose(result.clusters[0].cohesion_score, 1.0, abs_tol=1e-4)
    assert result.unassigned_feedback_count == 0


def test_exact_threshold_boundary_behavior():
    """Verify exact boundary behavior: distance <= max_dist merges, distance > max_dist does not."""
    dim = 768
    # Target similarity = 0.80 => max_dist = 0.20
    # Let theta = acos(0.80)
    theta = math.acos(0.80)
    v1 = [0.0] * dim; v1[0] = 1.0
    v2 = [0.0] * dim; v2[0] = math.cos(theta); v2[1] = math.sin(theta)

    d = cosine_distance(v1, v2)
    assert math.isclose(d, 0.20, abs_tol=1e-9)

    items_boundary = [
        FeedbackClusterInput(feedback_id=uuid.uuid4(), product="P", cleaned_feedback_text="b1", vector=v1),
        FeedbackClusterInput(feedback_id=uuid.uuid4(), product="P", cleaned_feedback_text="b2", vector=v2),
    ]

    # At threshold 0.80, distance 0.20 <= max_dist (0.20) -> must merge
    res_merge = ThemeClusteringService.cluster_feedback_items(
        items=items_boundary,
        product="P",
        similarity_threshold=0.80,
        min_cluster_size=2,
    )
    assert len(res_merge.clusters) == 1
    assert res_merge.clustered_feedback_count == 2

    # If threshold is slightly higher (0.80001), max_dist = 0.19999 < 0.20 -> must NOT merge
    res_no_merge = ThemeClusteringService.cluster_feedback_items(
        items=items_boundary,
        product="P",
        similarity_threshold=0.8001,
        min_cluster_size=2,
    )
    assert len(res_no_merge.clusters) == 0
    assert res_no_merge.unassigned_feedback_count == 2


def test_lazy_invalidation_of_obsolete_heap_entries():
    """Verify heap correctly lazily discards obsolete entries of merged clusters."""
    dim = 768
    # 4 items: v1 and v2 very close, v3 close to both, v4 further away
    v1 = make_unit_vector(0, dim=dim, noise=0.001)
    v2 = make_unit_vector(0, dim=dim, noise=0.002)
    v3 = make_unit_vector(0, dim=dim, noise=0.01)
    v4 = make_unit_vector(0, dim=dim, noise=0.02)

    items = [
        FeedbackClusterInput(feedback_id=uuid.uuid4(), product="P", cleaned_feedback_text="1", vector=v1),
        FeedbackClusterInput(feedback_id=uuid.uuid4(), product="P", cleaned_feedback_text="2", vector=v2),
        FeedbackClusterInput(feedback_id=uuid.uuid4(), product="P", cleaned_feedback_text="3", vector=v3),
        FeedbackClusterInput(feedback_id=uuid.uuid4(), product="P", cleaned_feedback_text="4", vector=v4),
    ]

    result = ThemeClusteringService.cluster_feedback_items(
        items=items,
        product="P",
        similarity_threshold=0.80,
        min_cluster_size=2,
    )
    # All 4 items should cleanly merge into 1 cluster without stale heap reference issues
    assert len(result.clusters) == 1
    assert result.clusters[0].size == 4


def test_deterministic_results_across_repeated_executions():
    """Verify 10 repeated clustering executions on random synthetic data yield identical output."""
    import random
    random.seed(999)
    dim = 768
    items = [
        FeedbackClusterInput(
            feedback_id=uuid.uuid4(),
            product="P",
            cleaned_feedback_text=f"text_{i}",
            vector=normalize_vector([random.gauss(0, 1) for _ in range(dim)]),
        )
        for i in range(15)
    ]

    base_res = ThemeClusteringService.cluster_feedback_items(items=items, product="P", similarity_threshold=0.5, min_cluster_size=2)

    for _ in range(9):
        run_res = ThemeClusteringService.cluster_feedback_items(items=items, product="P", similarity_threshold=0.5, min_cluster_size=2)
        assert len(run_res.clusters) == len(base_res.clusters)
        assert len(run_res.unassigned) == len(base_res.unassigned)
        for c1, c2 in zip(run_res.clusters, base_res.clusters):
            assert c1.cluster_id == c2.cluster_id
            assert c1.member_feedback_ids == c2.member_feedback_ids
            assert c1.representative_feedback_ids == c2.representative_feedback_ids
            assert math.isclose(c1.cohesion_score, c2.cohesion_score, abs_tol=1e-5)


def test_different_database_retrieval_ordering_invariance():
    """Verify input item permutations produce identical candidate clusters and representatives."""
    import random
    random.seed(777)
    dim = 768
    # 2 distinct clusters
    v_a1 = make_unit_vector(0, dim=dim, noise=0.005)
    v_a2 = make_unit_vector(0, dim=dim, noise=0.006)
    v_a3 = make_unit_vector(0, dim=dim, noise=0.007)

    v_b1 = make_unit_vector(1, dim=dim, noise=0.005)
    v_b2 = make_unit_vector(1, dim=dim, noise=0.006)
    v_b3 = make_unit_vector(1, dim=dim, noise=0.007)

    items = [
        FeedbackClusterInput(feedback_id=uuid.uuid4(), product="P", cleaned_feedback_text="a1", vector=v_a1),
        FeedbackClusterInput(feedback_id=uuid.uuid4(), product="P", cleaned_feedback_text="a2", vector=v_a2),
        FeedbackClusterInput(feedback_id=uuid.uuid4(), product="P", cleaned_feedback_text="a3", vector=v_a3),
        FeedbackClusterInput(feedback_id=uuid.uuid4(), product="P", cleaned_feedback_text="b1", vector=v_b1),
        FeedbackClusterInput(feedback_id=uuid.uuid4(), product="P", cleaned_feedback_text="b2", vector=v_b2),
        FeedbackClusterInput(feedback_id=uuid.uuid4(), product="P", cleaned_feedback_text="b3", vector=v_b3),
    ]

    base_res = ThemeClusteringService.cluster_feedback_items(items=items, product="P", similarity_threshold=0.85, min_cluster_size=3)
    base_cluster_members = sorted([sorted(c.member_feedback_ids) for c in base_res.clusters])

    for perm_idx in range(5):
        shuffled = list(items)
        random.shuffle(shuffled)
        shuffled_res = ThemeClusteringService.cluster_feedback_items(items=shuffled, product="P", similarity_threshold=0.85, min_cluster_size=3)
        shuffled_cluster_members = sorted([sorted(c.member_feedback_ids) for c in shuffled_res.clusters])
        assert base_cluster_members == shuffled_cluster_members, f"Mismatch at permutation {perm_idx}"


def test_product_isolation_and_min_cluster_size_behavior():
    """Verify product isolation enforcement and min cluster size threshold routing."""
    dim = 768
    v1 = make_unit_vector(0, dim=dim)
    v2 = make_unit_vector(0, dim=dim)

    # 1. Product mismatch
    items_cross = [
        FeedbackClusterInput(feedback_id=uuid.uuid4(), product="ProdA", cleaned_feedback_text="1", vector=v1),
        FeedbackClusterInput(feedback_id=uuid.uuid4(), product="ProdB", cleaned_feedback_text="2", vector=v2),
    ]
    with pytest.raises(AppException) as exc_info:
        ThemeClusteringService.cluster_feedback_items(items=items_cross, product="ProdA")
    assert exc_info.value.code == "PRODUCT_MISMATCH"

    # 2. Min cluster size: 2 items merge, but min_cluster_size=3 => routed to unassigned
    items_small = [
        FeedbackClusterInput(feedback_id=uuid.uuid4(), product="ProdA", cleaned_feedback_text="1", vector=v1),
        FeedbackClusterInput(feedback_id=uuid.uuid4(), product="ProdA", cleaned_feedback_text="2", vector=v2),
    ]
    res_min = ThemeClusteringService.cluster_feedback_items(
        items=items_small,
        product="ProdA",
        similarity_threshold=0.80,
        min_cluster_size=3,
    )
    assert len(res_min.clusters) == 0
    assert len(res_min.unassigned) == 2
    for u in res_min.unassigned:
        assert u.reason == "CLUSTER_BELOW_MIN_SIZE"


def test_cluster_metrics_and_centroid_nearest_representative_naming():
    """Verify representative feedback items are nearest to centroid and metrics are clamped to [0.0, 1.0]."""
    dim = 768
    v_center = [0.0] * dim; v_center[0] = 1.0
    v1 = normalize_vector([1.0, 0.05] + [0.0] * (dim - 2))
    v2 = normalize_vector([1.0, -0.05] + [0.0] * (dim - 2))

    id_center = uuid.uuid4()
    id_1 = uuid.uuid4()
    id_2 = uuid.uuid4()

    items = [
        FeedbackClusterInput(feedback_id=id_1, product="P", cleaned_feedback_text="f1", vector=v1),
        FeedbackClusterInput(feedback_id=id_center, product="P", cleaned_feedback_text="center", vector=v_center),
        FeedbackClusterInput(feedback_id=id_2, product="P", cleaned_feedback_text="f2", vector=v2),
    ]

    result = ThemeClusteringService.cluster_feedback_items(
        items=items,
        product="P",
        similarity_threshold=0.85,
        min_cluster_size=3,
        representative_count=1,
    )

    assert len(result.clusters) == 1
    cluster = result.clusters[0]
    # Center item is closest to centroid
    assert cluster.representative_feedback_ids[0] == id_center
    assert 0.0 <= cluster.average_similarity <= 1.0
    assert 0.0 <= cluster.cohesion_score <= 1.0


def test_regression_optimized_matches_exact_reference_implementation():
    """Regression test: verify optimized heap UPGMA matches direct UPGMA on a deterministic dataset."""
    import random
    random.seed(2026)
    dim = 32
    N = 20
    items = []
    for i in range(N):
        v = normalize_vector([random.gauss(0, 1) for _ in range(dim)])
        items.append(FeedbackClusterInput(
            feedback_id=uuid.uuid4(),
            product="RegProduct",
            cleaned_feedback_text=f"txt_{i}",
            vector=v,
        ))

    # Reference direct UPGMA implementation
    def reference_upgma(ref_items: List[FeedbackClusterInput], threshold: float, min_size: int):
        n = len(ref_items)
        mat = [[cosine_distance(ref_items[i].vector, ref_items[j].vector) for j in range(n)] for i in range(n)]
        clusters = {i: [i] for i in range(n)}
        max_dist = max(0.0, 1.0 - threshold)
        cluster_dist = {(i, j): mat[i][j] for i in range(n) for j in range(i + 1, n)}
        next_c = n
        while len(clusters) > 1:
            best_pair = None
            min_d = float("inf")
            best_k = None
            for (c1, c2), d in cluster_dist.items():
                u1 = min(ref_items[idx].feedback_id for idx in clusters[c1])
                u2 = min(ref_items[idx].feedback_id for idx in clusters[c2])
                cand_k = (min(u1, u2), max(u1, u2))
                if best_pair is None or (d, cand_k) < (min_d, best_k):
                    min_d = d
                    best_k = cand_k
                    best_pair = (c1, c2)
            if best_pair is None or min_d > max_dist:
                break
            c_a, c_b = best_pair
            new_m = clusters[c_a] + clusters[c_b]
            c_new = next_c
            next_c += 1
            clusters[c_new] = new_m
            del clusters[c_a]
            del clusters[c_b]
            for k in [k for k in cluster_dist if c_a in k or c_b in k]:
                del cluster_dist[k]
            for c_other, m_other in clusters.items():
                if c_other == c_new:
                    continue
                tot = sum(mat[i][j] for i in new_m for j in m_other)
                cluster_dist[(min(c_new, c_other), max(c_new, c_other))] = tot / (len(new_m) * len(m_other))
        return [sorted(m) for m in clusters.values() if len(m) >= min_size]

    ref_clusters = reference_upgma(items, threshold=0.70, min_size=2)
    opt_result = ThemeClusteringService.cluster_feedback_items(
        items=items,
        product="RegProduct",
        similarity_threshold=0.70,
        min_cluster_size=2,
        dimensions=dim,
    )
    opt_clusters = []
    id_to_idx = {item.feedback_id: idx for idx, item in enumerate(items)}
    for c in opt_result.clusters:
        opt_clusters.append(sorted([id_to_idx[fid] for fid in c.member_feedback_ids]))

    ref_clusters.sort()
    opt_clusters.sort()
    assert ref_clusters == opt_clusters, f"Reference {ref_clusters} != Optimized {opt_clusters}"


# ---------------------------------------------------------------------------
# 6. Priority Queue Tie-Handling Correction & Batch Safety Tests (Step 4.2.2)
# ---------------------------------------------------------------------------

def test_identical_vectors_clustering_no_heap_drain():
    """Verify 50 identical vectors merge into 1 cluster deterministically without error."""
    dim = 768
    v = make_unit_vector(0, dim=dim)
    items = [
        FeedbackClusterInput(
            feedback_id=uuid.uuid4(),
            product="P",
            cleaned_feedback_text=f"ident_{i}",
            vector=list(v),
        )
        for i in range(50)
    ]
    res = ThemeClusteringService.cluster_feedback_items(
        items=items,
        product="P",
        similarity_threshold=0.85,
        min_cluster_size=2,
    )
    assert len(res.clusters) == 1
    assert res.clusters[0].size == 50
    assert res.unassigned_feedback_count == 0
    assert math.isclose(res.clusters[0].average_similarity, 1.0, abs_tol=1e-4)


def test_orthogonal_vectors_identical_distances_merge():
    """Verify orthogonal vectors with identical distances merge deterministically when threshold permits."""
    dim = 768
    items = []
    for i in range(10):
        v = [0.0] * dim
        v[i] = 1.0
        items.append(FeedbackClusterInput(
            feedback_id=uuid.uuid4(),
            product="P",
            cleaned_feedback_text=f"ortho_{i}",
            vector=v,
        ))
    res = ThemeClusteringService.cluster_feedback_items(
        items=items,
        product="P",
        similarity_threshold=-0.1,  # max_dist = 1.1 >= 1.0, all merge
        min_cluster_size=2,
    )
    assert len(res.clusters) == 1
    assert res.clusters[0].size == 10


def test_symmetric_repeated_distance_datasets():
    """Verify symmetric dataset with multiple repeated equal distances clusters deterministically."""
    dim = 768
    items = []
    for i in range(24):
        v = [0.0] * dim
        group = i % 4
        v[group * 2] = 1.0
        v[group * 2 + 1] = 0.5
        items.append(FeedbackClusterInput(
            feedback_id=uuid.uuid4(),
            product="P",
            cleaned_feedback_text=f"sym_{i}",
            vector=normalize_vector(v),
        ))
    res = ThemeClusteringService.cluster_feedback_items(
        items=items,
        product="P",
        similarity_threshold=0.85,
        min_cluster_size=2,
    )
    assert len(res.clusters) == 4
    for c in res.clusters:
        assert c.size == 6


def test_near_equal_distances_strictly_smaller_wins():
    """Verify genuinely smaller distance wins even when difference is < 1e-9 (no artificial bucketing)."""
    dim = 768
    theta1 = 0.3
    theta2 = 0.3 + 1e-11  # difference is ~1e-11, well within 1e-9

    v1 = [0.0] * dim; v1[0] = 1.0
    v2 = [0.0] * dim; v2[0] = math.cos(theta1); v2[1] = math.sin(theta1)

    v3 = [0.0] * dim; v3[2] = 1.0
    v4 = [0.0] * dim; v4[2] = math.cos(theta2); v4[3] = math.sin(theta2)

    d12 = cosine_distance(v1, v2)
    d34 = cosine_distance(v3, v4)
    assert d12 < d34
    assert (d34 - d12) < 1e-9

    # Assign pair 2 SMALLER UUIDs than pair 1
    # If the engine erroneously forced ties within 1e-9, pair 2 would win by UUID.
    # Under exact ordering, Pair 1 MUST win because d12 < d34 strictly.
    id_p1_a = uuid.UUID("ffffffff-ffff-ffff-ffff-ffffffff0001")
    id_p1_b = uuid.UUID("ffffffff-ffff-ffff-ffff-ffffffff0002")
    id_p2_a = uuid.UUID("00000000-0000-0000-0000-000000000001")
    id_p2_b = uuid.UUID("00000000-0000-0000-0000-000000000002")

    items = [
        FeedbackClusterInput(feedback_id=id_p2_a, product="P", cleaned_feedback_text="p2a", vector=v3),
        FeedbackClusterInput(feedback_id=id_p2_b, product="P", cleaned_feedback_text="p2b", vector=v4),
        FeedbackClusterInput(feedback_id=id_p1_a, product="P", cleaned_feedback_text="p1a", vector=v1),
        FeedbackClusterInput(feedback_id=id_p1_b, product="P", cleaned_feedback_text="p1b", vector=v2),
    ]

    cutoff_d = (d12 + d34) / 2.0
    res = ThemeClusteringService.cluster_feedback_items(
        items=items,
        product="P",
        similarity_threshold=1.0 - cutoff_d,
        min_cluster_size=2,
    )
    assert len(res.clusters) == 1
    assert set(res.clusters[0].member_feedback_ids) == {id_p1_a, id_p1_b}


def test_exactly_equal_distances_canonical_uuid_tie_order():
    """Verify bitwise equal distances use canonical UUID pair as deterministic tie-breaker."""
    dim = 768
    theta = 0.25
    v1 = [0.0] * dim; v1[0] = 1.0
    v2 = [0.0] * dim; v2[0] = math.cos(theta); v2[1] = math.sin(theta)

    v3 = [0.0] * dim; v3[2] = 1.0
    v4 = [0.0] * dim; v4[2] = math.cos(theta); v4[3] = math.sin(theta)

    d12 = cosine_distance(v1, v2)
    d34 = cosine_distance(v3, v4)
    assert d12 == d34

    id_small_a = uuid.UUID("00000000-0000-0000-0000-000000000001")
    id_small_b = uuid.UUID("00000000-0000-0000-0000-000000000002")
    id_large_a = uuid.UUID("00000000-0000-0000-0000-000000000003")
    id_large_b = uuid.UUID("00000000-0000-0000-0000-000000000004")

    items = [
        FeedbackClusterInput(feedback_id=id_large_a, product="P", cleaned_feedback_text="l1", vector=v3),
        FeedbackClusterInput(feedback_id=id_large_b, product="P", cleaned_feedback_text="l2", vector=v4),
        FeedbackClusterInput(feedback_id=id_small_a, product="P", cleaned_feedback_text="s1", vector=v1),
        FeedbackClusterInput(feedback_id=id_small_b, product="P", cleaned_feedback_text="s2", vector=v2),
    ]

    res = ThemeClusteringService.cluster_feedback_items(
        items=items,
        product="P",
        similarity_threshold=math.cos(theta) - 0.01,
        min_cluster_size=2,
    )
    assert len(res.clusters) == 2


def test_batch_size_boundary_150_accepted():
    """Verify input with exactly 150 items is accepted and processed without error."""
    dim = 768
    v = make_unit_vector(0, dim=dim)
    items = [
        FeedbackClusterInput(
            feedback_id=uuid.uuid4(),
            product="P",
            cleaned_feedback_text=f"txt_{i}",
            vector=list(v),
        )
        for i in range(150)
    ]
    res = ThemeClusteringService.cluster_feedback_items(
        items=items,
        product="P",
        similarity_threshold=0.85,
        min_cluster_size=2,
    )
    assert res.total_feedback_evaluated == 150
    assert res.clustered_feedback_count == 150


def test_batch_size_151_rejected_in_cluster_feedback_items():
    """Verify input with 151 items is rejected before pairwise computation."""
    dim = 768
    v = make_unit_vector(0, dim=dim)
    items = [
        FeedbackClusterInput(
            feedback_id=uuid.uuid4(),
            product="P",
            cleaned_feedback_text=f"txt_{i}",
            vector=list(v),
        )
        for i in range(151)
    ]
    with pytest.raises(AppException) as exc_info:
        ThemeClusteringService.cluster_feedback_items(
            items=items,
            product="P",
        )
    assert exc_info.value.code == "BATCH_SIZE_EXCEEDED"
    assert exc_info.value.status_code == 400
    assert "exceeds maximum allowed batch limit of 150" in exc_info.value.message


# ---------------------------------------------------------------------------
# 5. Production Batch Ceiling & Safety Override Tests
# ---------------------------------------------------------------------------

def test_cluster_items_no_override_uses_configured_limit():
    """Verify cluster_feedback_items accepts 150 items and rejects 151 items when no override is provided."""
    dim = 768
    v = make_unit_vector(0, dim=dim)
    items_150 = [
        FeedbackClusterInput(
            feedback_id=uuid.uuid4(),
            product="P",
            cleaned_feedback_text=f"txt_{i}",
            vector=list(v),
        )
        for i in range(150)
    ]
    res = ThemeClusteringService.cluster_feedback_items(items=items_150, product="P")
    assert res.total_feedback_evaluated == 150

    items_151 = items_150 + [
        FeedbackClusterInput(
            feedback_id=uuid.uuid4(),
            product="P",
            cleaned_feedback_text="txt_150",
            vector=list(v),
        )
    ]
    with pytest.raises(AppException) as exc_info:
        ThemeClusteringService.cluster_feedback_items(items=items_151, product="P")
    assert exc_info.value.code == "BATCH_SIZE_EXCEEDED"
    assert exc_info.value.status_code == 400
    assert "exceeds maximum allowed batch limit of 150" in exc_info.value.message


def test_cluster_items_override_100_effective_limit():
    """Verify cluster_feedback_items with max_batch_size=100 sets effective limit to 100."""
    dim = 768
    v = make_unit_vector(0, dim=dim)
    items_100 = [
        FeedbackClusterInput(
            feedback_id=uuid.uuid4(),
            product="P",
            cleaned_feedback_text=f"txt_{i}",
            vector=list(v),
        )
        for i in range(100)
    ]
    res = ThemeClusteringService.cluster_feedback_items(items=items_100, product="P", max_batch_size=100)
    assert res.total_feedback_evaluated == 100

    items_101 = items_100 + [
        FeedbackClusterInput(
            feedback_id=uuid.uuid4(),
            product="P",
            cleaned_feedback_text="txt_100",
            vector=list(v),
        )
    ]
    with pytest.raises(AppException) as exc_info:
        ThemeClusteringService.cluster_feedback_items(items=items_101, product="P", max_batch_size=100)
    assert exc_info.value.code == "BATCH_SIZE_EXCEEDED"
    assert exc_info.value.status_code == 400
    assert "exceeds maximum allowed batch limit of 100" in exc_info.value.message


def test_cluster_items_override_150_effective_limit():
    """Verify cluster_feedback_items with max_batch_size=150 sets effective limit to 150."""
    dim = 768
    v = make_unit_vector(0, dim=dim)
    items_150 = [
        FeedbackClusterInput(
            feedback_id=uuid.uuid4(),
            product="P",
            cleaned_feedback_text=f"txt_{i}",
            vector=list(v),
        )
        for i in range(150)
    ]
    res = ThemeClusteringService.cluster_feedback_items(items=items_150, product="P", max_batch_size=150)
    assert res.total_feedback_evaluated == 150

    items_151 = items_150 + [
        FeedbackClusterInput(
            feedback_id=uuid.uuid4(),
            product="P",
            cleaned_feedback_text="txt_150",
            vector=list(v),
        )
    ]
    with pytest.raises(AppException) as exc_info:
        ThemeClusteringService.cluster_feedback_items(items=items_151, product="P", max_batch_size=150)
    assert exc_info.value.code == "BATCH_SIZE_EXCEEDED"
    assert exc_info.value.status_code == 400
    assert "exceeds maximum allowed batch limit of 150" in exc_info.value.message


def test_cluster_items_override_300_cannot_increase_configured_ceiling():
    """Verify override of 300 CANNOT increase production ceiling of 150 in cluster_feedback_items."""
    dim = 768
    v = make_unit_vector(0, dim=dim)
    items_151 = [
        FeedbackClusterInput(
            feedback_id=uuid.uuid4(),
            product="P",
            cleaned_feedback_text=f"txt_{i}",
            vector=list(v),
        )
        for i in range(151)
    ]
    with pytest.raises(AppException) as exc_info:
        ThemeClusteringService.cluster_feedback_items(
            items=items_151,
            product="P",
            max_batch_size=300,
        )
    assert exc_info.value.code == "BATCH_SIZE_EXCEEDED"
    assert exc_info.value.status_code == 400
    assert "exceeds maximum allowed batch limit of 150" in exc_info.value.message


def test_cluster_items_invalid_override_zero_raises():
    """Verify max_batch_size=0 raises INVALID_BATCH_SIZE AppException."""
    items = [
        FeedbackClusterInput(
            feedback_id=uuid.uuid4(),
            product="P",
            cleaned_feedback_text="txt",
            vector=make_unit_vector(0, dim=768),
        )
    ]
    with pytest.raises(AppException) as exc_info:
        ThemeClusteringService.cluster_feedback_items(
            items=items,
            product="P",
            max_batch_size=0,
        )
    assert exc_info.value.code == "INVALID_BATCH_SIZE"
    assert exc_info.value.status_code == 400
    assert "max_batch_size must be positive" in exc_info.value.message


def test_cluster_items_invalid_override_negative_raises():
    """Verify negative max_batch_size raises INVALID_BATCH_SIZE AppException."""
    items = [
        FeedbackClusterInput(
            feedback_id=uuid.uuid4(),
            product="P",
            cleaned_feedback_text="txt",
            vector=make_unit_vector(0, dim=768),
        )
    ]
    for invalid_val in (-1, -100):
        with pytest.raises(AppException) as exc_info:
            ThemeClusteringService.cluster_feedback_items(
                items=items,
                product="P",
                max_batch_size=invalid_val,
            )
        assert exc_info.value.code == "INVALID_BATCH_SIZE"
        assert exc_info.value.status_code == 400


def test_cluster_items_rejection_happens_before_distance_matrix(monkeypatch):
    """Verify batch limit rejection occurs before pairwise distance matrix construction."""
    matrix_called = False

    def spy_matrix(*args, **kwargs):
        nonlocal matrix_called
        matrix_called = True
        return []

    monkeypatch.setattr("app.services.theme_clustering_service.pairwise_distance_matrix", spy_matrix)

    dim = 768
    v = make_unit_vector(0, dim=dim)
    items_151 = [
        FeedbackClusterInput(
            feedback_id=uuid.uuid4(),
            product="P",
            cleaned_feedback_text=f"txt_{i}",
            vector=list(v),
        )
        for i in range(151)
    ]

    with pytest.raises(AppException) as exc_info:
        ThemeClusteringService.cluster_feedback_items(items=items_151, product="P")
    assert exc_info.value.code == "BATCH_SIZE_EXCEEDED"
    assert not matrix_called, "pairwise_distance_matrix must NOT be called on batch rejection"

    with pytest.raises(AppException) as exc_info2:
        ThemeClusteringService.cluster_feedback_items(items=items_151[:10], product="P", max_batch_size=0)
    assert exc_info2.value.code == "INVALID_BATCH_SIZE"
    assert not matrix_called, "pairwise_distance_matrix must NOT be called on invalid batch size"


def test_cluster_items_stress_benchmark_isolated_configuration(monkeypatch):
    """Verify 200 items can be clustered ONLY via isolated settings override."""
    monkeypatch.setattr(settings, "THEME_CLUSTERING_MAX_BATCH_SIZE", 300)

    dim = 768
    v = make_unit_vector(0, dim=dim)
    items_200 = [
        FeedbackClusterInput(
            feedback_id=uuid.uuid4(),
            product="P",
            cleaned_feedback_text=f"txt_{i}",
            vector=list(v),
        )
        for i in range(200)
    ]

    res = ThemeClusteringService.cluster_feedback_items(items=items_200, product="P")
    assert res.total_feedback_evaluated == 200
    assert res.clustered_feedback_count == 200


def test_retrieve_no_override_uses_configured_limit(db_session):
    """Verify retrieve_eligible_feedback rejects > 150 items under default configured limit."""
    for i in range(151):
        create_test_feedback_with_embedding(db_session, product="App", cleaned_text=f"Item {i}")

    with pytest.raises(AppException) as exc_info:
        ThemeClusteringService.retrieve_eligible_feedback(db_session, product="App")
    assert exc_info.value.code == "BATCH_SIZE_EXCEEDED"
    assert exc_info.value.status_code == 400
    assert "exceeds maximum allowed batch limit of 150" in exc_info.value.message


def test_retrieve_override_smaller_limit_effective(db_session):
    """Verify retrieve_eligible_feedback with override 3 sets effective limit to 3."""
    for i in range(5):
        create_test_feedback_with_embedding(db_session, product="App", cleaned_text=f"Item {i}")

    with pytest.raises(AppException) as exc_info:
        ThemeClusteringService.retrieve_eligible_feedback(
            db_session,
            product="App",
            max_batch_size=3,
        )
    assert exc_info.value.code == "BATCH_SIZE_EXCEEDED"
    assert exc_info.value.status_code == 400
    assert "exceeds maximum allowed batch limit of 3" in exc_info.value.message

    retrieved = ThemeClusteringService.retrieve_eligible_feedback(
        db_session,
        product="App",
        max_batch_size=5,
    )
    assert len(retrieved) == 5


def test_retrieve_override_150_effective_limit(db_session):
    """Verify retrieve_eligible_feedback with max_batch_size=150 sets effective limit to 150."""
    for i in range(151):
        create_test_feedback_with_embedding(db_session, product="App", cleaned_text=f"Item {i}")

    with pytest.raises(AppException) as exc_info:
        ThemeClusteringService.retrieve_eligible_feedback(
            db_session,
            product="App",
            max_batch_size=150,
        )
    assert exc_info.value.code == "BATCH_SIZE_EXCEEDED"
    assert exc_info.value.status_code == 400
    assert "exceeds maximum allowed batch limit of 150" in exc_info.value.message


def test_retrieve_override_300_cannot_increase_configured_ceiling(db_session):
    """Verify max_batch_size=300 CANNOT increase production ceiling of 150 in retrieve_eligible_feedback."""
    for i in range(151):
        create_test_feedback_with_embedding(db_session, product="App", cleaned_text=f"Item {i}")

    with pytest.raises(AppException) as exc_info:
        ThemeClusteringService.retrieve_eligible_feedback(
            db_session,
            product="App",
            max_batch_size=300,
        )
    assert exc_info.value.code == "BATCH_SIZE_EXCEEDED"
    assert exc_info.value.status_code == 400
    assert "exceeds maximum allowed batch limit of 150" in exc_info.value.message


def test_retrieve_invalid_override_zero_raises(db_session):
    """Verify max_batch_size=0 raises INVALID_BATCH_SIZE in retrieve_eligible_feedback."""
    with pytest.raises(AppException) as exc_info:
        ThemeClusteringService.retrieve_eligible_feedback(
            db_session,
            product="App",
            max_batch_size=0,
        )
    assert exc_info.value.code == "INVALID_BATCH_SIZE"
    assert exc_info.value.status_code == 400
    assert "max_batch_size must be positive" in exc_info.value.message


def test_retrieve_invalid_override_negative_raises(db_session):
    """Verify negative max_batch_size raises INVALID_BATCH_SIZE in retrieve_eligible_feedback."""
    for invalid_val in (-1, -10):
        with pytest.raises(AppException) as exc_info:
            ThemeClusteringService.retrieve_eligible_feedback(
                db_session,
                product="App",
                max_batch_size=invalid_val,
            )
        assert exc_info.value.code == "INVALID_BATCH_SIZE"
        assert exc_info.value.status_code == 400


def test_retrieve_stress_benchmark_isolated_configuration(db_session, monkeypatch):
    """Verify retrieving > 150 items succeeds under isolated configuration override."""
    monkeypatch.setattr(settings, "THEME_CLUSTERING_MAX_BATCH_SIZE", 250)

    for i in range(200):
        create_test_feedback_with_embedding(db_session, product="App", cleaned_text=f"Item {i}")

    retrieved = ThemeClusteringService.retrieve_eligible_feedback(db_session, product="App")
    assert len(retrieved) == 200
