"""Theme Clustering Service (Part 7 Step 4).

Coordinates deterministic, product-isolated agglomerative average-linkage theme clustering.
Separates read-only database retrieval from pure-Python vector computation.
Operates strictly in memory; does NOT create or modify Theme or FeedbackThemes records.
"""

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
import heapq
import logging
import math
import time
from typing import Any, Dict, List, Optional, Set, Tuple
import uuid
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.exceptions import AppException
from app.models.classification import FeedbackClassification
from app.models.feedback import Feedback, FeedbackThemes
from app.models.feedback_embeddings import FeedbackEmbedding
from app.schemas.theme_clustering import (
    CandidateClusterItem,
    ThemeClusteringResult,
    TopicAggregationItem,
    UnassignedFeedbackItem,
)

logger = logging.getLogger("theme_clustering_service")

ALGORITHM_NAME = "agglomerative_average_linkage"
ALGORITHM_VERSION = "1.0.0"
CLUSTER_NAMESPACE_UUID = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")  # UUID namespace for deterministic IDs


# ---------------------------------------------------------------------------
# In-Memory Intermediate Data Representation
# ---------------------------------------------------------------------------

@dataclass
class FeedbackClusterInput:
    """Detached in-memory representation of an eligible feedback record and its embedding."""

    feedback_id: uuid.UUID
    product: str
    cleaned_feedback_text: str
    vector: List[float]
    classification_topics: Optional[List[Dict[str, Any]]] = None
    customer_intent: Optional[str] = None
    classification_confidence: Optional[float] = None
    classification_status: Optional[str] = None


# ---------------------------------------------------------------------------
# Pure Standard-Library Vector Mathematics
# ---------------------------------------------------------------------------

def validate_vector(vector: List[float], expected_dim: Optional[int] = None) -> None:
    """Validate that vector is a non-empty list of finite floats matching expected dimensions."""
    if not isinstance(vector, (list, tuple)):
        raise ValueError(f"Vector must be a list or tuple, got {type(vector).__name__}")
    if len(vector) == 0:
        raise ValueError("Vector cannot be empty")
    if expected_dim is not None and len(vector) != expected_dim:
        raise ValueError(f"Expected vector dimension {expected_dim}, got {len(vector)}")
    for idx, val in enumerate(vector):
        if not math.isfinite(val):
            raise ValueError(f"Vector contains non-finite value ({val}) at index {idx}")


def normalize_vector(vector: List[float]) -> List[float]:
    """Compute unit-normalized L2 vector: v / ||v||_2."""
    validate_vector(vector)
    sq_sum = sum(x * x for x in vector)
    norm = math.sqrt(sq_sum)
    if norm == 0.0 or math.isclose(norm, 0.0, abs_tol=1e-12):
        raise ValueError("Cannot normalize a zero-magnitude vector")
    return [x / norm for x in vector]


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """Compute cosine similarity between two float vectors, clamped to [-1.0, 1.0]."""
    if len(v1) != len(v2):
        raise ValueError(f"Vector dimension mismatch: {len(v1)} vs {len(v2)}")
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    if norm1 == 0.0 or norm2 == 0.0 or math.isclose(norm1 * norm2, 0.0, abs_tol=1e-12):
        return 0.0
    sim = dot / (norm1 * norm2)
    return max(-1.0, min(1.0, sim))


def cosine_distance(v1: List[float], v2: List[float]) -> float:
    """Compute numerical cosine distance: max(0.0, 1.0 - cosine_similarity(v1, v2))."""
    return max(0.0, 1.0 - cosine_similarity(v1, v2))


def compute_centroid(vectors: List[List[float]], expected_dim: Optional[int] = None) -> List[float]:
    """Calculate the unit-normalized arithmetic centroid vector of a list of vectors."""
    if not vectors:
        raise ValueError("Cannot compute centroid of an empty vector list")
    dim = len(vectors[0])
    validate_vector(vectors[0], expected_dim)

    sum_vec = [0.0] * dim
    for v in vectors:
        validate_vector(v, dim)
        for i in range(dim):
            sum_vec[i] += v[i]

    count = float(len(vectors))
    mean_vec = [x / count for x in sum_vec]

    # Unit-normalize the centroid
    try:
        return normalize_vector(mean_vec)
    except ValueError:
        # Fallback if vectors perfectly cancelled out
        return vectors[0]


def pairwise_distance_matrix(vectors: List[List[float]]) -> List[List[float]]:
    """Compute symmetric pairwise cosine distance matrix for N vectors.

    Distance formula: d(u, v) = max(0.0, 1.0 - cosine_similarity(u, v)).
    Diagonal entries are identically 0.0.
    Precomputes vector L2 norms once in O(N * D) to eliminate redundant
    O(N^2 * D) norm recomputations while preserving exact bitwise numerical equivalence.
    """
    n = len(vectors)
    if n == 0:
        return []
    matrix = [[0.0] * n for _ in range(n)]
    norms = [math.sqrt(sum(x * x for x in v)) for v in vectors]
    for i in range(n):
        norm1 = norms[i]
        v1 = vectors[i]
        for j in range(i + 1, n):
            norm2 = norms[j]
            v2 = vectors[j]
            if norm1 == 0.0 or norm2 == 0.0 or math.isclose(norm1 * norm2, 0.0, abs_tol=1e-12):
                sim = 0.0
            else:
                dot = sum(a * b for a, b in zip(v1, v2))
                sim = max(-1.0, min(1.0, dot / (norm1 * norm2)))
            dist = max(0.0, 1.0 - sim)
            matrix[i][j] = dist
            matrix[j][i] = dist
    return matrix


def generate_deterministic_cluster_id(product: str, member_ids: List[uuid.UUID]) -> uuid.UUID:
    """Generate a deterministic UUID5 candidate cluster identifier."""
    sorted_uuids = sorted(str(u) for u in member_ids)
    composite_key = f"{product}:{ALGORITHM_VERSION}:{','.join(sorted_uuids)}"
    return uuid.uuid5(CLUSTER_NAMESPACE_UUID, composite_key)


# ---------------------------------------------------------------------------
# Theme Clustering Service
# ---------------------------------------------------------------------------

class ThemeClusteringService:
    """Pure, detached theme clustering engine using Agglomerative Average Linkage."""

    @classmethod
    def retrieve_eligible_feedback(
        cls,
        session: Session,
        product: str,
        model_name: Optional[str] = None,
        dimensions: Optional[int] = None,
        max_batch_size: Optional[int] = None,
    ) -> List[FeedbackClusterInput]:
        """Phase A: Query eligible, unclustered feedback and embeddings for a single product.

        Pure read-only query. Releases database connection before computation.
        """
        configured_ceiling = settings.THEME_CLUSTERING_MAX_BATCH_SIZE
        if max_batch_size is not None:
            if max_batch_size <= 0:
                raise AppException(
                    message="max_batch_size must be positive",
                    status_code=400,
                    code="INVALID_BATCH_SIZE",
                )
            effective_limit = min(max_batch_size, configured_ceiling)
        else:
            effective_limit = configured_ceiling

        target_model = model_name or settings.AI_EMBEDDING_MODEL
        target_dims = dimensions or settings.AI_EMBEDDING_DIMENSIONS

        # Subquery to exclude feedback already associated with an active theme in feedback_themes
        associated_subquery = select(FeedbackThemes.feedback_id).subquery()

        stmt = (
            select(
                Feedback.feedback_id,
                Feedback.product,
                Feedback.cleaned_feedback_text,
                FeedbackEmbedding.embedding_vector,
                FeedbackEmbedding.embedding_model,
                FeedbackEmbedding.embedding_dimensions,
            )
            .join(FeedbackEmbedding, Feedback.feedback_id == FeedbackEmbedding.feedback_id)
            .where(
                Feedback.product == product,
                Feedback.deleted_at.is_(None),
                Feedback.quality_status.in_(["clean", "flagged"]),
                Feedback.cleaned_feedback_text.is_not(None),
                Feedback.feedback_id.not_in(select(associated_subquery)),
                FeedbackEmbedding.embedding_model == target_model,
                FeedbackEmbedding.embedding_dimensions == target_dims,
            )
            .order_by(Feedback.created_at.asc(), Feedback.feedback_id.asc())
        )

        rows = session.execute(stmt).all()

        if len(rows) > effective_limit:
            raise AppException(
                message=(
                    f"Eligible feedback count ({len(rows)}) exceeds maximum allowed "
                    f"batch limit of {effective_limit} for product '{product}'."
                ),
                status_code=400,
                code="BATCH_SIZE_EXCEEDED",
            )

        if not rows:
            return []

        # Retrieve optional latest classification metadata
        fb_ids = [r[0] for r in rows]
        cls_stmt = (
            select(FeedbackClassification)
            .where(
                FeedbackClassification.feedback_id.in_(fb_ids),
                FeedbackClassification.status.in_(["classified", "pending_review"]),
            )
            .order_by(
                FeedbackClassification.feedback_id,
                FeedbackClassification.classified_at.desc(),
                FeedbackClassification.classification_id.desc(),
            )
        )
        cls_records = session.execute(cls_stmt).scalars().all()

        # Map latest classification per feedback
        cls_map: Dict[uuid.UUID, FeedbackClassification] = {}
        for cr in cls_records:
            if cr.feedback_id not in cls_map:
                cls_map[cr.feedback_id] = cr

        # Materialize in-memory inputs
        inputs: List[FeedbackClusterInput] = []
        for fb_id, prod, clean_text, vec, emb_model, emb_dims in rows:
            validate_vector(vec, target_dims)
            cls_meta = cls_map.get(fb_id)
            inputs.append(
                FeedbackClusterInput(
                    feedback_id=fb_id,
                    product=prod,
                    cleaned_feedback_text=clean_text or "",
                    vector=vec,
                    classification_topics=cls_meta.topics if cls_meta else None,
                    customer_intent=cls_meta.customer_intent if cls_meta else None,
                    classification_confidence=cls_meta.confidence_score if cls_meta else None,
                    classification_status=cls_meta.status if cls_meta else None,
                )
            )

        return inputs

    @classmethod
    def cluster_feedback_items(
        cls,
        items: List[FeedbackClusterInput],
        product: str,
        similarity_threshold: Optional[float] = None,
        min_cluster_size: Optional[int] = None,
        representative_count: Optional[int] = None,
        dimensions: Optional[int] = None,
        max_batch_size: Optional[int] = None,
    ) -> ThemeClusteringResult:
        """Phase B: Pure in-memory Agglomerative Average-Linkage clustering.

        Completely detached from database transactions and sessions.
        """
        start_time = time.perf_counter()

        # Enforce maximum batch size ceiling before expensive pairwise computations
        configured_ceiling = settings.THEME_CLUSTERING_MAX_BATCH_SIZE
        if max_batch_size is not None:
            if max_batch_size <= 0:
                raise AppException(
                    message="max_batch_size must be positive",
                    status_code=400,
                    code="INVALID_BATCH_SIZE",
                )
            effective_limit = min(max_batch_size, configured_ceiling)
        else:
            effective_limit = configured_ceiling

        if len(items) > effective_limit:
            raise AppException(
                message=(
                    f"Feedback items count ({len(items)}) exceeds maximum allowed "
                    f"batch limit of {effective_limit} for product '{product}'."
                ),
                status_code=400,
                code="BATCH_SIZE_EXCEEDED",
            )

        target_sim = similarity_threshold or settings.THEME_CLUSTERING_SIMILARITY_THRESHOLD
        target_min_size = min_cluster_size or settings.THEME_CLUSTERING_MIN_CLUSTER_SIZE
        target_reps = representative_count or settings.THEME_CLUSTERING_REPRESENTATIVE_COUNT
        expected_dim = dimensions or settings.AI_EMBEDDING_DIMENSIONS
        max_dist = max(0.0, 1.0 - target_sim)

        parameters = {
            "similarity_threshold": target_sim,
            "min_cluster_size": target_min_size,
            "representative_count": target_reps,
            "max_distance": max_dist,
            "dimensions": expected_dim,
        }

        # 0. Empty dataset
        if not items:
            duration_ms = (time.perf_counter() - start_time) * 1000.0
            return ThemeClusteringResult(
                product=product,
                algorithm=ALGORITHM_NAME,
                algorithm_version=ALGORITHM_VERSION,
                parameters=parameters,
                total_feedback_evaluated=0,
                clustered_feedback_count=0,
                unassigned_feedback_count=0,
                clusters=[],
                unassigned=[],
                duration_ms=duration_ms,
            )

        # Validate all items belong to requested product and have correct vector dimension
        for item in items:
            if item.product != product:
                raise AppException(
                    message=f"Cross-product item detected: expected '{product}', got '{item.product}'",
                    status_code=400,
                    code="PRODUCT_MISMATCH",
                )
            validate_vector(item.vector, expected_dim)

        n = len(items)

        # 1. Compute pairwise distance matrix
        vectors = [item.vector for item in items]
        dist_matrix = pairwise_distance_matrix(vectors)

        # 2. Initialize N singleton clusters and priority queue
        active_clusters: Set[int] = set(range(n))
        cluster_sizes: Dict[int, int] = {i: 1 for i in range(n)}
        cluster_members: Dict[int, List[int]] = {i: [i] for i in range(n)}
        min_fids: Dict[int, uuid.UUID] = {i: items[i].feedback_id for i in range(n)}

        # Active cluster distances: dist_table[c1][c2] = distance
        dist_table: Dict[int, Dict[int, float]] = {i: {} for i in range(2 * n)}
        heap: List[Tuple[float, Tuple[uuid.UUID, uuid.UUID], int, int]] = []

        for i in range(n):
            for j in range(i + 1, n):
                d = dist_matrix[i][j]
                dist_table[i][j] = d
                dist_table[j][i] = d
                cand_key = (min(min_fids[i], min_fids[j]), max(min_fids[i], min_fids[j]))
                heap.append((d, cand_key, i, j))

        heapq.heapify(heap)

        # 3. Agglomerative Average-Linkage Merge Loop
        # Uses incremental Lance-Williams weighted recurrence:
        #   D(A ∪ B, C) = (|A| * D(A, C) + |B| * D(B, C)) / (|A| + |B|)
        # with min-heap priority queue, lazy invalidation of obsolete pairs,
        # and deterministic tie-breaking on canonical feedback UUID tuples.
        #
        # Mathematical Tie-Handling Policy: Python heap tuple comparison orders
        # entries primarily by exact floating-point distance `d`, and secondarily
        # by the canonical feedback UUID pair `cand_key` for exactly equal distances.
        # Distances are not quantized, rounded, or bucketed into synthetic bins;
        # a genuinely smaller distance (even by < 1e-9) strictly takes precedence
        # over a larger distance. No entries are drained or repushed for tie resolution.
        next_cluster_id = n

        while len(active_clusters) > 1 and heap:
            d, cand_key, c1, c2 = heapq.heappop(heap)

            # Lazy invalidation: ignore pairs involving clusters that were already merged
            if c1 not in active_clusters or c2 not in active_clusters:
                continue

            # Stopping threshold check (distance > max_dist corresponds to similarity < threshold;
            # equality d == max_dist is allowed to merge)
            if d > max_dist:
                break

            c_a, c_b = c1, c2
            sz_a = cluster_sizes[c_a]
            sz_b = cluster_sizes[c_b]
            sz_new = sz_a + sz_b

            c_new = next_cluster_id
            next_cluster_id += 1

            active_clusters.remove(c_a)
            active_clusters.remove(c_b)
            active_clusters.add(c_new)

            cluster_sizes[c_new] = sz_new
            cluster_members[c_new] = cluster_members[c_a] + cluster_members[c_b]
            min_fids[c_new] = min(min_fids[c_a], min_fids[c_b])

            # Lance-Williams incremental update: O(M) operations
            for c_other in list(active_clusters):
                if c_other == c_new:
                    continue
                d_a = dist_table[c_a][c_other]
                d_b = dist_table[c_b][c_other]
                d_new = (sz_a * d_a + sz_b * d_b) / sz_new

                dist_table[c_new][c_other] = d_new
                dist_table[c_other][c_new] = d_new
                del dist_table[c_other][c_a]
                del dist_table[c_other][c_b]

                cand_k = (min(min_fids[c_new], min_fids[c_other]), max(min_fids[c_new], min_fids[c_other]))
                pair_k = (min(c_new, c_other), max(c_new, c_other))
                heapq.heappush(heap, (d_new, cand_k, pair_k[0], pair_k[1]))

            del dist_table[c_a]
            del dist_table[c_b]

        # Reconstruct final active clusters dictionary sorted by cluster ID
        clusters: Dict[int, List[int]] = {c_id: cluster_members[c_id] for c_id in sorted(active_clusters)}

        # 4. Partition qualifying candidate clusters vs unassigned feedback
        qualifying_clusters: List[CandidateClusterItem] = []
        unassigned_items: List[UnassignedFeedbackItem] = []

        # Temporary store for candidate cluster centroids to calculate nearest similarities
        candidate_centroids: Dict[uuid.UUID, List[float]] = {}

        # Iterate active clusters sorted by cluster_id for strict determinism
        for c_id, member_indices in clusters.items():
            member_inputs = [items[idx] for idx in member_indices]
            cluster_size = len(member_inputs)
            member_uuids = [m.feedback_id for m in member_inputs]

            if cluster_size >= target_min_size:
                # Qualifying cluster
                cluster_vecs = [m.vector for m in member_inputs]
                centroid = compute_centroid(cluster_vecs, expected_dim)
                cand_id = generate_deterministic_cluster_id(product, member_uuids)
                candidate_centroids[cand_id] = centroid

                # Representative feedback items: closest to centroid (centroid_nearest_representative)
                centroid_nearest_representative_scores = []
                for m in member_inputs:
                    dist_to_cent = cosine_distance(m.vector, centroid)
                    centroid_nearest_representative_scores.append((dist_to_cent, m.feedback_id))
                centroid_nearest_representative_scores.sort(key=lambda x: (x[0], x[1]))
                rep_count = min(cluster_size, target_reps)
                representative_ids = [item[1] for item in centroid_nearest_representative_scores[:rep_count]]

                # Average pairwise similarity
                if cluster_size > 1:
                    pair_sim_sum = 0.0
                    pair_count = 0
                    for i_idx in range(cluster_size):
                        for j_idx in range(i_idx + 1, cluster_size):
                            orig_i = member_indices[i_idx]
                            orig_j = member_indices[j_idx]
                            pair_sim_sum += 1.0 - dist_matrix[orig_i][orig_j]
                            pair_count += 1
                    avg_sim = max(0.0, min(1.0, pair_sim_sum / pair_count))
                else:
                    avg_sim = 1.0

                # Cohesion score: mean similarity to centroid
                cohesion_sum = sum(cosine_similarity(v, centroid) for v in cluster_vecs)
                cohesion_score = max(0.0, min(1.0, cohesion_sum / cluster_size))

                # Aggregate topics from member classifications
                topic_counter: Dict[str, List[float]] = {}
                intent_counter: Counter[str] = Counter()

                for m in member_inputs:
                    if m.customer_intent:
                        intent_counter[m.customer_intent] += 1
                    if m.classification_topics:
                        for top in m.classification_topics:
                            if isinstance(top, dict) and "label" in top:
                                lbl = str(top["label"]).strip()
                                conf = float(top.get("confidence", 1.0))
                                topic_counter.setdefault(lbl, []).append(conf)

                dominant_topics: List[TopicAggregationItem] = []
                for lbl, confs in topic_counter.items():
                    dominant_topics.append(
                        TopicAggregationItem(
                            label=lbl,
                            count=len(confs),
                            average_confidence=sum(confs) / len(confs),
                        )
                    )
                # Sort dominant topics by count descending, then confidence descending
                dominant_topics.sort(key=lambda t: (t.count, t.average_confidence), reverse=True)

                dominant_intent = intent_counter.most_common(1)[0][0] if intent_counter else None

                qualifying_clusters.append(
                    CandidateClusterItem(
                        cluster_id=cand_id,
                        product=product,
                        member_feedback_ids=member_uuids,
                        size=cluster_size,
                        representative_feedback_ids=representative_ids,
                        centroid_vector=centroid,
                        average_similarity=round(avg_sim, 4),
                        cohesion_score=round(cohesion_score, 4),
                        dominant_topics=dominant_topics[:5],
                        dominant_intent=dominant_intent,
                    )
                )

        # Sort qualifying clusters deterministically by size descending, cluster_id ascending
        qualifying_clusters.sort(key=lambda c: (-c.size, c.cluster_id))

        # 5. Process unassigned items
        for c_id, member_indices in clusters.items():
            member_inputs = [items[idx] for idx in member_indices]
            cluster_size = len(member_inputs)

            if cluster_size < target_min_size:
                for m in member_inputs:
                    # Determine precise reason
                    if cluster_size > 1:
                        reason = "CLUSTER_BELOW_MIN_SIZE"
                    else:
                        # Check if isolated singleton or below similarity threshold
                        reason = "BELOW_SIMILARITY_THRESHOLD" if len(items) > 1 else "NO_COMPATIBLE_CLUSTER"

                    # Calculate nearest candidate cluster similarity if qualifying clusters exist
                    nearest_id: Optional[uuid.UUID] = None
                    nearest_sim: Optional[float] = None

                    if candidate_centroids:
                        best_sim = -2.0
                        for c_uuid, c_cent in candidate_centroids.items():
                            s = cosine_similarity(m.vector, c_cent)
                            if s > best_sim:
                                best_sim = s
                                nearest_id = c_uuid
                                nearest_sim = max(0.0, min(1.0, round(best_sim, 4)))

                    unassigned_items.append(
                        UnassignedFeedbackItem(
                            feedback_id=m.feedback_id,
                            reason=reason,
                            nearest_cluster_id=nearest_id,
                            nearest_similarity=nearest_sim,
                        )
                    )

        # Sort unassigned items deterministically by feedback_id
        unassigned_items.sort(key=lambda u: u.feedback_id)

        clustered_count = sum(c.size for c in qualifying_clusters)
        unassigned_count = len(unassigned_items)
        duration_ms = (time.perf_counter() - start_time) * 1000.0

        logger.info(
            "Theme clustering complete for '%s': evaluated=%d, clusters=%d (clustered=%d), unassigned=%d, duration=%.2fms",
            product,
            n,
            len(qualifying_clusters),
            clustered_count,
            unassigned_count,
            duration_ms,
        )

        return ThemeClusteringResult(
            product=product,
            algorithm=ALGORITHM_NAME,
            algorithm_version=ALGORITHM_VERSION,
            parameters=parameters,
            total_feedback_evaluated=n,
            clustered_feedback_count=clustered_count,
            unassigned_feedback_count=unassigned_count,
            clusters=qualifying_clusters,
            unassigned=unassigned_items,
            duration_ms=round(duration_ms, 2),
        )

    @classmethod
    def cluster_product(
        cls,
        session: Session,
        product: str,
        similarity_threshold: Optional[float] = None,
        min_cluster_size: Optional[int] = None,
        representative_count: Optional[int] = None,
        max_batch_size: Optional[int] = None,
        dimensions: Optional[int] = None,
    ) -> ThemeClusteringResult:
        """Execute end-to-end theme clustering for a product.

        Phase A: Read-only query.
        Phase B: Pure in-memory computation.
        Zero database writes; no commit/rollback executed.
        """
        inputs = cls.retrieve_eligible_feedback(
            session=session,
            product=product,
            dimensions=dimensions,
            max_batch_size=max_batch_size,
        )

        return cls.cluster_feedback_items(
            items=inputs,
            product=product,
            similarity_threshold=similarity_threshold,
            min_cluster_size=min_cluster_size,
            representative_count=representative_count,
            dimensions=dimensions,
            max_batch_size=max_batch_size,
        )
