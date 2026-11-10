"""Theme Lifecycle Service (Part 7 - Hackathon Prototype).

Provides simplified, robust theme lifecycle operations:
1. Candidate theme discovery and idempotent staging using ThemeClusteringService.
2. Candidate duplicate prevention using deterministic cluster UUIDs.
3. Theme listing with feedback counts and representative feedback excerpts.
4. Candidate activation (optionally with custom operator name) and discard.
5. Theme merging with membership migration, relevance score resolution,
   sentiment copy-on-null, and centroid recomputation.
6. Theme sentiment and intent summary calculation based on latest valid classifications.
"""

from collections import Counter
from datetime import datetime, timezone
import logging
from typing import Dict, List, Optional, Set, Tuple
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import AppException, EntityNotFoundError
from app.models.classification import FeedbackClassification
from app.models.feedback import Feedback, FeedbackThemes
from app.models.feedback_embeddings import FeedbackEmbedding
from app.models.theme import Theme
from app.schemas.theme import (
    DiscoverThemesResponse,
    MergeThemesResponse,
    RepresentativeFeedbackItem,
    ThemeResponse,
    ThemeSentimentSummary,
)
from app.services.theme_clustering_service import ThemeClusteringService, compute_centroid

logger = logging.getLogger("theme_lifecycle_service")


class ThemeLifecycleService:
    """Service handling discovery, staging, activation, discard, merge, and summaries for themes."""

    @classmethod
    def discover_and_stage_candidates(
        cls,
        session: Session,
        product: str,
        similarity_threshold: Optional[float] = None,
        min_cluster_size: Optional[int] = None,
        max_batch_size: Optional[int] = None,
    ) -> DiscoverThemesResponse:
        """Discover candidate clusters from eligible feedback and stage them into the database."""
        clustering_result = ThemeClusteringService.cluster_product(
            session=session,
            product=product,
            similarity_threshold=similarity_threshold,
            min_cluster_size=min_cluster_size,
            max_batch_size=max_batch_size,
        )

        staged_candidates: List[ThemeResponse] = []
        new_candidates_count = 0
        skipped_candidates_count = 0

        for cand in clustering_result.clusters:
            cand_id = cand.cluster_id

            # 1. Idempotency: Check if theme already exists by deterministic UUID
            existing_theme = session.get(Theme, cand_id)
            if existing_theme is not None:
                skipped_candidates_count += 1
                if existing_theme.status == "candidate":
                    theme_resp = cls._build_theme_response(
                        session=session,
                        theme=existing_theme,
                        include_summary=False,
                    )
                    staged_candidates.append(theme_resp)
                continue

            # 2. Derive suggested title from dominant topic or intent
            if cand.dominant_topics:
                suggested_label = cand.dominant_topics[0].label.strip()
            elif cand.dominant_intent:
                suggested_label = cand.dominant_intent.replace("_", " ").capitalize()
            else:
                suggested_label = "Feedback Cluster"

            # Cap label to fit within theme_name 150-char constraint
            capped_label = suggested_label[:80].strip()
            cand_name = f"Candidate: {capped_label} ({str(cand_id)[:8]})"

            # Ensure unique theme_name for this product
            name_collision = session.execute(
                select(Theme.theme_id).where(
                    Theme.product == product, Theme.theme_name == cand_name
                )
            ).scalar_one_or_none()
            if name_collision is not None:
                cand_name = f"Candidate: {capped_label} ({cand_id.hex[:12]})"

            category_name = cand.dominant_intent or "discovered"

            # 3. Create candidate Theme record
            theme = Theme(
                theme_id=cand_id,
                product=product,
                theme_name=cand_name,
                description=f"Auto-discovered candidate theme containing {cand.size} feedback items.",
                category=category_name[:100],
                status="candidate",
                centroid_vector=cand.centroid_vector,
                lineage_metadata={
                    "representative_feedback_ids": [str(x) for x in cand.representative_feedback_ids],
                    "average_similarity": cand.average_similarity,
                    "cohesion_score": cand.cohesion_score,
                    "dominant_intent": cand.dominant_intent,
                    "dominant_topics": [t.model_dump() for t in cand.dominant_topics],
                },
            )
            session.add(theme)
            session.flush()

            # 4. Attach member feedback records to feedback_themes junction
            for fid in cand.member_feedback_ids:
                existing_junction = session.get(FeedbackThemes, (fid, cand_id))
                if existing_junction is None:
                    session.add(
                        FeedbackThemes(
                            feedback_id=fid,
                            theme_id=cand_id,
                            relevance_score=1.0,
                            aspect_sentiment=None,
                        )
                    )

            session.flush()
            new_candidates_count += 1

            theme_resp = cls._build_theme_response(
                session=session,
                theme=theme,
                include_summary=False,
            )
            staged_candidates.append(theme_resp)

        session.commit()

        logger.info(
            "Candidate discovery complete for '%s': discovered=%d, new_staged=%d, skipped=%d",
            product,
            len(clustering_result.clusters),
            new_candidates_count,
            skipped_candidates_count,
        )

        return DiscoverThemesResponse(
            product=product,
            discovered_count=len(clustering_result.clusters),
            new_candidates_staged=new_candidates_count,
            existing_candidates_skipped=skipped_candidates_count,
            candidates=staged_candidates,
        )

    @classmethod
    def list_themes(
        cls,
        session: Session,
        product: str,
        status: Optional[str] = None,
    ) -> List[ThemeResponse]:
        """List themes filtered by product and optional lifecycle status."""
        stmt = select(Theme).where(Theme.product == product)
        if status:
            stmt = stmt.where(Theme.status == status)
        stmt = stmt.order_by(Theme.created_at.desc(), Theme.theme_name.asc())

        themes = session.execute(stmt).scalars().all()
        return [
            cls._build_theme_response(session=session, theme=t, include_summary=True)
            for t in themes
        ]

    @classmethod
    def get_theme_detail(
        cls,
        session: Session,
        theme_id: uuid.UUID,
    ) -> ThemeResponse:
        """Retrieve full details, representative feedback, and sentiment summary for a theme."""
        theme = session.get(Theme, theme_id)
        if theme is None:
            raise EntityNotFoundError(f"Theme '{theme_id}' was not found.")

        return cls._build_theme_response(session=session, theme=theme, include_summary=True)

    @classmethod
    def activate_candidate(
        cls,
        session: Session,
        theme_id: uuid.UUID,
        custom_name: Optional[str] = None,
        category: Optional[str] = None,
        description: Optional[str] = None,
    ) -> ThemeResponse:
        """Promote a candidate theme to active status, optionally applying custom name/metadata."""
        theme = session.get(Theme, theme_id)
        if theme is None:
            raise EntityNotFoundError(f"Theme '{theme_id}' was not found.")

        if theme.status != "candidate":
            raise AppException(
                message=f"Only candidate themes can be activated (current status: '{theme.status}').",
                status_code=400,
                code="INVALID_THEME_STATUS",
            )

        if custom_name and custom_name.strip():
            # Check for name collision in active themes
            cleaned_name = custom_name.strip()
            existing_active = session.execute(
                select(Theme.theme_id).where(
                    Theme.product == theme.product,
                    Theme.theme_name == cleaned_name,
                    Theme.theme_id != theme_id,
                )
            ).scalar_one_or_none()
            if existing_active is not None:
                raise AppException(
                    message=f"A theme named '{cleaned_name}' already exists for product '{theme.product}'.",
                    status_code=409,
                    code="THEME_NAME_CONFLICT",
                )
            theme.theme_name = cleaned_name

        if category and category.strip():
            theme.category = category.strip()[:100]

        if description and description.strip():
            theme.description = description.strip()

        theme.status = "active"
        session.commit()

        logger.info("Candidate theme '%s' activated successfully as '%s'", theme_id, theme.theme_name)
        return cls._build_theme_response(session=session, theme=theme, include_summary=True)

    @classmethod
    def discard_candidate(
        cls,
        session: Session,
        theme_id: uuid.UUID,
    ) -> ThemeResponse:
        """Discard a candidate theme so it is no longer shown as an active or pending theme."""
        theme = session.get(Theme, theme_id)
        if theme is None:
            raise EntityNotFoundError(f"Theme '{theme_id}' was not found.")

        if theme.status != "candidate":
            raise AppException(
                message=f"Only candidate themes can be discarded (current status: '{theme.status}').",
                status_code=400,
                code="INVALID_THEME_STATUS",
            )

        theme.status = "discarded"
        session.commit()

        logger.info("Candidate theme '%s' discarded successfully", theme_id)
        return cls._build_theme_response(session=session, theme=theme, include_summary=False)

    @classmethod
    def merge_themes(
        cls,
        session: Session,
        source_theme_id: uuid.UUID,
        target_theme_id: uuid.UUID,
    ) -> MergeThemesResponse:
        """Merge an active source theme into an active target theme within the same product."""
        # 1. Reject self-merges
        if source_theme_id == target_theme_id:
            raise AppException(
                message="Cannot merge a theme into itself.",
                status_code=400,
                code="SELF_MERGE_REJECTED",
            )

        # 2. Load themes
        source = session.get(Theme, source_theme_id)
        target = session.get(Theme, target_theme_id)

        if source is None:
            raise EntityNotFoundError(f"Source theme '{source_theme_id}' not found.")
        if target is None:
            raise EntityNotFoundError(f"Target theme '{target_theme_id}' not found.")

        # 3. Reject cross-product merges
        if source.product != target.product:
            raise AppException(
                message=f"Cannot merge themes across different products ('{source.product}' vs '{target.product}').",
                status_code=400,
                code="CROSS_PRODUCT_MERGE_REJECTED",
            )

        # 4. State validation: require both themes to be active
        if source.status != "active":
            raise AppException(
                message=f"Source theme is not active (status='{source.status}'). Only active themes can be merged.",
                status_code=400,
                code="INVALID_THEME_STATUS",
            )
        if target.status != "active":
            raise AppException(
                message=f"Target theme is not active (status='{target.status}'). Only active themes can be merged.",
                status_code=400,
                code="INVALID_THEME_STATUS",
            )
        if source.merged_into_id is not None:
            raise AppException(
                message="Source theme has already been merged into another theme.",
                status_code=400,
                code="ALREADY_MERGED",
            )

        # 5. Migrate feedback_themes memberships with conflict resolution
        target_links: Dict[uuid.UUID, FeedbackThemes] = {
            link.feedback_id: link
            for link in session.execute(
                select(FeedbackThemes).where(FeedbackThemes.theme_id == target_theme_id)
            ).scalars().all()
        }

        source_links = session.execute(
            select(FeedbackThemes).where(FeedbackThemes.theme_id == source_theme_id)
        ).scalars().all()

        for s_link in source_links:
            fid = s_link.feedback_id
            if fid in target_links:
                # Duplicate association exists: retain highest relevance score
                t_link = target_links[fid]
                t_link.relevance_score = max(t_link.relevance_score, s_link.relevance_score)
                # Sentiment handling: preserve target sentiment if present; otherwise copy source
                if not t_link.aspect_sentiment and s_link.aspect_sentiment:
                    t_link.aspect_sentiment = s_link.aspect_sentiment
                # Remove redundant source junction
                session.delete(s_link)
            else:
                # Re-point source junction to target
                s_link.theme_id = target_theme_id
                target_links[fid] = s_link

        session.flush()

        # 6. Recompute target centroid using all member embeddings
        all_member_fids = list(target_links.keys())
        if all_member_fids:
            vector_rows = session.execute(
                select(FeedbackEmbedding.embedding_vector).where(
                    FeedbackEmbedding.feedback_id.in_(all_member_fids)
                )
            ).scalars().all()
            valid_vectors = [v for v in vector_rows if v and isinstance(v, list) and len(v) > 0]
            if valid_vectors:
                target.centroid_vector = compute_centroid(valid_vectors)

        # 7. Update source theme status and lineage metadata
        source.status = "merged"
        source.merged_into_id = target_theme_id
        now_utc = datetime.now(timezone.utc).isoformat()
        current_meta = dict(source.lineage_metadata or {})
        current_meta["merged_at"] = now_utc
        current_meta["merged_into_id"] = str(target_theme_id)
        source.lineage_metadata = current_meta

        session.commit()

        total_target_count = len(target_links)
        merged_source_count = len(source_links)

        logger.info(
            "Successfully merged theme '%s' into '%s' (transferred=%d, target_total=%d)",
            source_theme_id,
            target_theme_id,
            merged_source_count,
            total_target_count,
        )

        return MergeThemesResponse(
            target_theme_id=target_theme_id,
            source_theme_id=source_theme_id,
            status="merged",
            merged_feedback_count=merged_source_count,
            total_target_feedback_count=total_target_count,
            message="Successfully merged source theme into target theme.",
        )

    @classmethod
    def compute_theme_sentiment_summary(
        cls,
        session: Session,
        theme_id: uuid.UUID,
    ) -> ThemeSentimentSummary:
        """Compute aggregated sentiment and intent metrics using the latest valid classification per feedback."""
        member_fids = session.execute(
            select(FeedbackThemes.feedback_id).where(FeedbackThemes.theme_id == theme_id)
        ).scalars().all()

        total_count = len(member_fids)
        if total_count == 0:
            return ThemeSentimentSummary(
                total_feedbacks=0,
                classified_feedbacks=0,
                positive=0,
                negative=0,
                neutral=0,
                mixed=0,
                average_sentiment_score=None,
                dominant_intent=None,
            )

        # Window function selecting strictly the latest valid run per feedback item
        rn_subq = (
            select(
                FeedbackClassification.feedback_id,
                FeedbackClassification.overall_sentiment,
                FeedbackClassification.sentiment_score,
                FeedbackClassification.customer_intent,
                func.row_number()
                .over(
                    partition_by=FeedbackClassification.feedback_id,
                    order_by=(
                        FeedbackClassification.classified_at.desc(),
                        FeedbackClassification.run_number.desc(),
                        FeedbackClassification.classification_id.desc(),
                    ),
                )
                .label("rn"),
            )
            .where(
                FeedbackClassification.feedback_id.in_(member_fids),
                FeedbackClassification.status.in_(["classified", "pending_review"]),
            )
        ).subquery()

        latest_rows = session.execute(
            select(
                rn_subq.c.overall_sentiment,
                rn_subq.c.sentiment_score,
                rn_subq.c.customer_intent,
            ).where(rn_subq.c.rn == 1)
        ).all()

        classified_count = len(latest_rows)
        sentiment_counts = Counter(r[0] for r in latest_rows)
        intents = Counter(r[2] for r in latest_rows if r[2])

        avg_score: Optional[float] = None
        if classified_count > 0:
            avg_score = round(sum(r[1] for r in latest_rows) / classified_count, 4)

        dominant_intent = intents.most_common(1)[0][0] if intents else None

        return ThemeSentimentSummary(
            total_feedbacks=total_count,
            classified_feedbacks=classified_count,
            positive=sentiment_counts.get("positive", 0),
            negative=sentiment_counts.get("negative", 0),
            neutral=sentiment_counts.get("neutral", 0),
            mixed=sentiment_counts.get("mixed", 0),
            average_sentiment_score=avg_score,
            dominant_intent=dominant_intent,
        )

    @classmethod
    def _build_theme_response(
        cls,
        session: Session,
        theme: Theme,
        include_summary: bool = True,
    ) -> ThemeResponse:
        """Build ThemeResponse DTO including member counts, representative feedback, and summaries."""
        # 1. Total member feedback count
        fb_count = session.execute(
            select(func.count(FeedbackThemes.feedback_id)).where(
                FeedbackThemes.theme_id == theme.theme_id
            )
        ).scalar() or 0

        # 2. Representative feedback
        rep_items: List[RepresentativeFeedbackItem] = []
        meta = theme.lineage_metadata or {}
        rep_ids_raw = meta.get("representative_feedback_ids", [])
        rep_uuids: List[uuid.UUID] = []
        for rid in rep_ids_raw:
            try:
                rep_uuids.append(uuid.UUID(str(rid)))
            except (ValueError, TypeError):
                continue

        # If representative IDs were recorded in metadata, fetch them
        if rep_uuids:
            fb_rows = session.execute(
                select(
                    Feedback.feedback_id,
                    Feedback.feedback_text,
                    Feedback.cleaned_feedback_text,
                    FeedbackThemes.aspect_sentiment,
                )
                .join(
                    FeedbackThemes,
                    (Feedback.feedback_id == FeedbackThemes.feedback_id)
                    & (FeedbackThemes.theme_id == theme.theme_id),
                )
                .where(Feedback.feedback_id.in_(rep_uuids))
            ).all()
            for r in fb_rows:
                rep_items.append(
                    RepresentativeFeedbackItem(
                        feedback_id=r[0],
                        feedback_text=r[1],
                        cleaned_feedback_text=r[2],
                        aspect_sentiment=r[3],
                    )
                )

        # Fallback to first 3 member feedbacks if no representative IDs in metadata
        if not rep_items:
            fallback_rows = session.execute(
                select(
                    Feedback.feedback_id,
                    Feedback.feedback_text,
                    Feedback.cleaned_feedback_text,
                    FeedbackThemes.aspect_sentiment,
                )
                .join(
                    FeedbackThemes,
                    (Feedback.feedback_id == FeedbackThemes.feedback_id)
                    & (FeedbackThemes.theme_id == theme.theme_id),
                )
                .limit(3)
            ).all()
            for r in fallback_rows:
                rep_items.append(
                    RepresentativeFeedbackItem(
                        feedback_id=r[0],
                        feedback_text=r[1],
                        cleaned_feedback_text=r[2],
                        aspect_sentiment=r[3],
                    )
                )

        # 3. Optional summary
        summary: Optional[ThemeSentimentSummary] = None
        if include_summary:
            summary = cls.compute_theme_sentiment_summary(session=session, theme_id=theme.theme_id)

        return ThemeResponse(
            theme_id=theme.theme_id,
            product=theme.product,
            theme_name=theme.theme_name,
            description=theme.description,
            category=theme.category,
            status=theme.status,
            created_at=theme.created_at,
            feedback_count=fb_count,
            merged_into_id=theme.merged_into_id,
            representative_feedback=rep_items,
            sentiment_summary=summary,
        )
