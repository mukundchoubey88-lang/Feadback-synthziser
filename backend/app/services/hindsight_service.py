"""Service orchestration for Hindsight Persistent Memory (Part 9).

Orchestrates selective synchronization between PostgreSQL and Hindsight:
- Curates high-signal customer feedback, active themes, snapshots, product changes, and insights.
- Implements strict deduplication using local MemoryMetadata records.
- Enriches recalled memories and reflections with PostgreSQL provenance.
- Enforces clear separation between LLM cognitive reasoning and exact SQL analytics.
"""

from datetime import datetime, timezone
import hashlib
import logging
import re
from typing import Any, Dict, List, Optional
import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.integrations.hindsight.client import HindsightClient
from app.models.classification import FeedbackClassification
from app.models.feedback import Feedback
from app.models.insight import Insight
from app.models.memory import MemoryMetadata
from app.models.product_change import ProductChanges
from app.models.theme import Theme, ThemeSnapshot
from app.schemas.memory import (
    MemoryItemResponse,
    MemoryRecallResponse,
    MemoryReflectResponse,
    MemoryStatusResponse,
    MemorySyncResponse,
)

logger = logging.getLogger(__name__)


def get_bank_id_for_product(product: str) -> str:
    """Generate a deterministic, isolated, URL-safe memory bank ID for a product."""
    normalized = re.sub(r"[^a-zA-Z0-9]+", "-", product.strip().lower()).strip("-")
    short_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:8]
    prefix = normalized[:24] if normalized else "product"
    return f"bank-{prefix}-{short_hash}"


async def sync_product_memories(
    session: Session,
    product: str,
    client: HindsightClient,
    dry_run: bool = False,
) -> MemorySyncResponse:
    """Curate high-signal entities from PostgreSQL and retain them into Hindsight bank.

    Curates across 5 cognitive memory types:
    1. customer_feedback: high-intensity sentiment, complaints, feature requests, praise
    2. theme_trajectory: active themes discovered or managed
    3. temporal_shift: historical theme snapshots and metric shifts
    4. product_release: release notes and feature deployments
    5. synthesized_insight: active synthesized recommendations and intelligence
    """
    bank_id = get_bank_id_for_product(product)
    details: Dict[str, int] = {
        "customer_feedback": 0,
        "theme_trajectory": 0,
        "temporal_shift": 0,
        "product_release": 0,
        "synthesized_insight": 0,
    }
    skipped_count = 0
    failed_count = 0
    synced_count = 0
    error_msg: Optional[str] = None

    if not dry_run and client.is_configured:
        bank_ready = await client.ensure_bank(bank_id)
        if not bank_ready:
            logger.warning("Could not pre-verify bank %s on Hindsight; proceeding with retain attempts.", bank_id)

    # 1. High-Signal Customer Feedback
    feedback_stmt = (
        select(Feedback, FeedbackClassification)
        .join(FeedbackClassification, Feedback.feedback_id == FeedbackClassification.feedback_id)
        .where(
            Feedback.product == product,
            Feedback.deleted_at.is_(None),
            or_(
                func.abs(FeedbackClassification.sentiment_score) >= 0.7,
                FeedbackClassification.customer_intent.in_(["complaint", "feature_request", "praise"]),
                FeedbackClassification.sentiment_intensity == "high",
            ),
        )
        .order_by(Feedback.timestamp.desc())
        .limit(100)
    )
    feedback_rows = session.execute(feedback_stmt).all()
    seen_feedback_ids = set()

    for fb, classification in feedback_rows:
        if fb.feedback_id in seen_feedback_ids:
            continue
        seen_feedback_ids.add(fb.feedback_id)

        # Check deduplication
        existing = session.scalar(
            select(MemoryMetadata).where(
                MemoryMetadata.source_entity_type == "feedback",
                MemoryMetadata.feedback_id == fb.feedback_id,
            )
        )
        if existing:
            skipped_count += 1
            continue

        if dry_run:
            synced_count += 1
            details["customer_feedback"] += 1
            continue

        excerpt = fb.cleaned_feedback_text or fb.feedback_text
        if len(excerpt) > 500:
            excerpt = excerpt[:497] + "..."

        content = (
            f"[Customer Feedback] ({classification.customer_intent or 'general'}, "
            f"sentiment: {classification.overall_sentiment}, "
            f"score: {classification.sentiment_score:.2f}): \"{excerpt}\""
        )
        context = (
            f"timestamp={fb.timestamp.isoformat()}, "
            f"feature={fb.feature or 'None'}, "
            f"app_version={fb.app_version or 'None'}"
        )

        h_id = await client.retain(bank_id, content, context)
        if h_id:
            meta = MemoryMetadata(
                bank_id=bank_id,
                hindsight_memory_id=h_id,
                memory_type="customer_feedback",
                source_entity_type="feedback",
                feedback_id=fb.feedback_id,
                source_reference=f"feedback:{fb.feedback_id}",
                created_at=datetime.now(timezone.utc),
            )
            session.add(meta)
            synced_count += 1
            details["customer_feedback"] += 1
        else:
            failed_count += 1

    # 2. Theme Trajectory
    themes = session.scalars(
        select(Theme).where(
            Theme.product == product,
            Theme.status == "active",
        ).order_by(Theme.created_at.desc())
    ).all()

    for th in themes:
        ref = f"theme:{th.theme_id}"
        existing = session.scalar(
            select(MemoryMetadata).where(
                MemoryMetadata.bank_id == bank_id,
                MemoryMetadata.source_reference == ref,
            )
        )
        if existing:
            skipped_count += 1
            continue

        if dry_run:
            synced_count += 1
            details["theme_trajectory"] += 1
            continue

        content = (
            f"[Theme Trajectory] Theme: \"{th.theme_name}\" "
            f"(Category: {th.category}, Status: {th.status}). "
            f"Description: {th.description or 'N/A'}"
        )
        context = f"theme_id={th.theme_id}, created_at={th.created_at.isoformat()}"

        h_id = await client.retain(bank_id, content, context)
        if h_id:
            meta = MemoryMetadata(
                bank_id=bank_id,
                hindsight_memory_id=h_id,
                memory_type="theme_trajectory",
                source_entity_type="external",
                related_theme=th.theme_id,
                source_reference=ref,
                created_at=datetime.now(timezone.utc),
            )
            session.add(meta)
            synced_count += 1
            details["theme_trajectory"] += 1
        else:
            failed_count += 1

    # 3. Temporal Shifts (ThemeSnapshots)
    snapshots = session.scalars(
        select(ThemeSnapshot)
        .join(Theme, ThemeSnapshot.theme_id == Theme.theme_id)
        .where(Theme.product == product)
        .order_by(ThemeSnapshot.period_end.desc())
        .limit(100)
    ).all()

    for snap in snapshots:
        existing = session.scalar(
            select(MemoryMetadata).where(
                MemoryMetadata.source_entity_type.in_(["snapshot", "theme_snapshot"]),
                MemoryMetadata.snapshot_id == snap.snapshot_id,
            )
        )
        if existing:
            skipped_count += 1
            continue

        if dry_run:
            synced_count += 1
            details["temporal_shift"] += 1
            continue

        theme_name = snap.theme.theme_name if snap.theme else "Unknown"
        content = (
            f"[Temporal Shift] Theme: \"{theme_name}\" "
            f"Window: {snap.period_start.date()} to {snap.period_end.date()}. "
            f"Feedback volume: {snap.feedback_count}, "
            f"Positive: {snap.positive_count}, Negative: {snap.negative_count}, "
            f"Avg Sentiment: {snap.sentiment_average:.2f}"
        )
        context = f"snapshot_id={snap.snapshot_id}, theme_id={snap.theme_id}"

        h_id = await client.retain(bank_id, content, context)
        if h_id:
            meta = MemoryMetadata(
                bank_id=bank_id,
                hindsight_memory_id=h_id,
                memory_type="temporal_shift",
                source_entity_type="theme_snapshot",
                snapshot_id=snap.snapshot_id,
                related_theme=snap.theme_id,
                source_reference=f"snapshot:{snap.snapshot_id}",
                created_at=datetime.now(timezone.utc),
            )
            session.add(meta)
            synced_count += 1
            details["temporal_shift"] += 1
        else:
            failed_count += 1

    # 4. Product Releases
    releases = session.scalars(
        select(ProductChanges).where(
            ProductChanges.product == product
        ).order_by(ProductChanges.release_date.desc())
    ).all()

    for rel in releases:
        ref = f"release:{rel.release_id}"
        existing = session.scalar(
            select(MemoryMetadata).where(
                MemoryMetadata.bank_id == bank_id,
                MemoryMetadata.source_reference == ref,
            )
        )
        if existing:
            skipped_count += 1
            continue

        if dry_run:
            synced_count += 1
            details["product_release"] += 1
            continue

        content = (
            f"[Product Release] Version {rel.version} ({rel.change_category}) "
            f"deployed on {rel.release_date.date()}. "
            f"Feature: {rel.feature or 'General'}. "
            f"Description: {rel.release_description}"
        )
        context = f"release_id={rel.release_id}, version={rel.version}"

        h_id = await client.retain(bank_id, content, context)
        if h_id:
            meta = MemoryMetadata(
                bank_id=bank_id,
                hindsight_memory_id=h_id,
                memory_type="product_release",
                source_entity_type="external",
                source_reference=ref,
                created_at=datetime.now(timezone.utc),
            )
            session.add(meta)
            synced_count += 1
            details["product_release"] += 1
        else:
            failed_count += 1

    # 5. Synthesized Insights
    insights = session.scalars(
        select(Insight).where(
            Insight.status == "active"
        ).order_by(Insight.created_at.desc())
    ).all()

    for ins in insights:
        existing = session.scalar(
            select(MemoryMetadata).where(
                MemoryMetadata.source_entity_type == "insight",
                MemoryMetadata.insight_id == ins.insight_id,
            )
        )
        if existing:
            skipped_count += 1
            continue

        if dry_run:
            synced_count += 1
            details["synthesized_insight"] += 1
            continue

        content = (
            f"[Synthesized Insight] Title: \"{ins.title}\". "
            f"Summary: {ins.summary}. "
            f"Recommendation: {ins.recommendation}. "
            f"Confidence: {ins.confidence_score:.2f}"
        )
        context = f"insight_id={ins.insight_id}, confidence={ins.confidence_score}"

        h_id = await client.retain(bank_id, content, context)
        if h_id:
            meta = MemoryMetadata(
                bank_id=bank_id,
                hindsight_memory_id=h_id,
                memory_type="synthesized_insight",
                source_entity_type="insight",
                insight_id=ins.insight_id,
                source_reference=f"insight:{ins.insight_id}",
                created_at=datetime.now(timezone.utc),
            )
            session.add(meta)
            synced_count += 1
            details["synthesized_insight"] += 1
        else:
            failed_count += 1

    if not dry_run:
        session.commit()

    if failed_count > 0 and not client.is_configured:
        error_msg = "Hindsight persistent memory is unconfigured (HINDSIGHT_BASE_URL unset). Retention skipped."
    elif failed_count > 0:
        error_msg = f"{failed_count} memory items could not be retained due to Hindsight service degradation."

    return MemorySyncResponse(
        product=product,
        bank_id=bank_id,
        dry_run=dry_run,
        synced_count=synced_count,
        skipped_count=skipped_count,
        failed_count=failed_count,
        details=details,
        error=error_msg,
    )


def _enrich_memory_item(
    session: Session,
    bank_id: str,
    raw_item: Any,
) -> MemoryItemResponse:
    """Map raw Hindsight memory object to unified schema enriched with local PostgreSQL provenance."""
    if isinstance(raw_item, str):
        content = raw_item
        h_id = None
        context = None
    elif isinstance(raw_item, dict):
        content = str(raw_item.get("content") or raw_item.get("text") or raw_item.get("memory") or "")
        h_id = str(raw_item.get("id") or raw_item.get("memory_id") or "") or None
        context = raw_item.get("context")
    else:
        content = str(raw_item)
        h_id = None
        context = None

    if h_id:
        meta = session.scalar(
            select(MemoryMetadata).where(
                MemoryMetadata.hindsight_memory_id == h_id
            )
        )
        if meta:
            return MemoryItemResponse(
                memory_id=meta.memory_id,
                bank_id=meta.bank_id,
                hindsight_memory_id=meta.hindsight_memory_id,
                memory_type=meta.memory_type,
                source_entity_type=meta.source_entity_type,
                source_reference=meta.source_reference,
                content=content,
                context=context,
                created_at=meta.created_at,
            )

    return MemoryItemResponse(
        memory_id=None,
        bank_id=bank_id,
        hindsight_memory_id=h_id,
        memory_type="historical_recall",
        source_entity_type="external",
        source_reference=None,
        content=content,
        context=context,
        created_at=None,
    )


async def recall_memories(
    session: Session,
    product: str,
    query: str,
    limit: int,
    client: HindsightClient,
) -> MemoryRecallResponse:
    """Recall relevant historical memories from Hindsight with local PostgreSQL provenance."""
    bank_id = get_bank_id_for_product(product)
    raw_res = await client.recall(bank_id=bank_id, query=query, limit=limit)

    if not raw_res.get("success"):
        return MemoryRecallResponse(
            product=product,
            bank_id=bank_id,
            query=query,
            available=False,
            memories=[],
            error=raw_res.get("error") or "Hindsight memory recall failed.",
        )

    memories_raw = raw_res.get("memories", [])
    enriched_memories = [
        _enrich_memory_item(session, bank_id, item) for item in memories_raw
    ]

    return MemoryRecallResponse(
        product=product,
        bank_id=bank_id,
        query=query,
        available=True,
        memories=enriched_memories,
        error=None,
    )


async def reflect_on_memories(
    session: Session,
    product: str,
    query: str,
    client: HindsightClient,
) -> MemoryReflectResponse:
    """Request synthesized reasoning from Hindsight memory bank over historical trends."""
    bank_id = get_bank_id_for_product(product)
    raw_res = await client.reflect(bank_id=bank_id, query=query)

    if not raw_res.get("success"):
        return MemoryReflectResponse(
            product=product,
            bank_id=bank_id,
            query=query,
            available=False,
            reasoning=None,
            supporting_memories=[],
            error=raw_res.get("error") or "Hindsight reflection service is unavailable.",
        )

    supporting_raw = raw_res.get("memories", [])
    supporting_memories = [
        _enrich_memory_item(session, bank_id, item) for item in supporting_raw
    ]

    return MemoryReflectResponse(
        product=product,
        bank_id=bank_id,
        query=query,
        available=True,
        reasoning=raw_res.get("reasoning"),
        supporting_memories=supporting_memories,
        error=None,
    )


async def get_memory_status(
    session: Session,
    client: HindsightClient,
) -> MemoryStatusResponse:
    """Retrieve integration health status and local sync metrics."""
    configured = client.is_configured
    available = await client.health_check() if configured else False

    total_synced = session.scalar(
        select(func.count(MemoryMetadata.memory_id))
    ) or 0

    bank_count = session.scalar(
        select(func.count(func.distinct(MemoryMetadata.bank_id)))
    ) or 0

    # Redact credentials if base_url contains inline auth
    safe_base_url = None
    if client.base_url:
        safe_base_url = re.sub(r"://([^:@]+):([^@]+)@", r"://***:***@", client.base_url)

    return MemoryStatusResponse(
        configured=configured,
        available=available,
        base_url=safe_base_url,
        total_synced_memories=int(total_synced),
        bank_count=int(bank_count),
    )
