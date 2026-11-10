"""Unified Historical Memory Intelligence Service (Part 10 - Hackathon Prototype).

Orchestrates natural-language question answering for product managers by synthesizing:
1. PostgreSQL structured ground truth (feedback counts, sentiment ratios, pre/post release shifts, themes).
2. Hindsight Persistent Memory (semantic recall of trajectories, recurring issues, historical reflection).
3. Grounded causal safeguards (no unsupported causal claims; correlation != causation).
4. Full evidence and provenance citation (feedback IDs, theme IDs, release versions).
"""

from datetime import datetime, timedelta, timezone
import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple
import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.integrations.ai.manager import AIProviderManager
from app.integrations.ai.schemas import AIRequest
from app.integrations.hindsight.client import HindsightClient
from app.models.classification import FeedbackClassification
from app.models.feedback import Feedback
from app.models.product_change import ProductChanges
from app.models.theme import Theme
from app.schemas.intelligence import (
    FeedbackEvidenceItem,
    HistoricalIntelligenceResponse,
    IntelligenceEvidence,
    ReleaseEvidenceItem,
    SQLMetrics,
    ThemeEvidenceItem,
)
from app.services import hindsight_service
from app.services.analytics_service import AnalyticsService, get_latest_classification_subquery

logger = logging.getLogger(__name__)


class HistoricalIntelligenceService:
    """Unified engine for historical intelligence queries combining PostgreSQL and Hindsight."""

    @classmethod
    async def ask(
        cls,
        session: Session,
        product: str,
        question: str,
        hindsight_client: HindsightClient,
        ai_manager: Optional[AIProviderManager] = None,
    ) -> HistoricalIntelligenceResponse:
        """Process a natural language intelligence question scoped to a product."""
        # 1. Check data availability for product
        total_fb_count = session.scalar(
            select(func.count(Feedback.feedback_id)).where(
                Feedback.product == product,
                Feedback.deleted_at.is_(None),
            )
        ) or 0

        if total_fb_count == 0:
            return HistoricalIntelligenceResponse(
                product=product,
                question=question,
                answer=(
                    f"Insufficient historical feedback data recorded for product '{product}'. "
                    "Cannot evaluate customer sentiment or historical trajectories."
                ),
                key_findings=[f"Zero customer feedback records exist in PostgreSQL for product '{product}'."],
                sql_metrics=SQLMetrics(total_feedback=0),
                historical_context=None,
                evidence=IntelligenceEvidence(),
                hindsight_available=False,
                limitations=[
                    "Insufficient data: zero feedback records found in PostgreSQL.",
                    "No product releases or themes could be evaluated.",
                ],
            )

        # 2. Retrieve PostgreSQL Ground Truth Analytics
        overview = AnalyticsService.get_overview(
            session=session,
            product=product,
            days=90,
        )

        aspect_res = AnalyticsService.get_aspect_sentiment(
            session=session,
            product=product,
            days=90,
            limit=5,
        )
        aspect_dict = {
            a.aspect_name: a.negative_mentions for a in aspect_res.aspects
        } if aspect_res.aspects else None

        # 3. Retrieve Product Releases and Compute Pre/Post Release Comparison
        releases = session.scalars(
            select(ProductChanges)
            .where(ProductChanges.product == product)
            .order_by(ProductChanges.release_date.desc())
            .limit(5)
        ).all()

        pre_post_data: Optional[Dict[str, Any]] = None
        release_evidence: List[ReleaseEvidenceItem] = []

        for rel in releases:
            release_evidence.append(
                ReleaseEvidenceItem(
                    release_id=rel.release_id,
                    version=rel.version,
                    release_date=rel.release_date,
                    change_category=rel.change_category,
                    feature=rel.feature,
                    description=rel.release_description,
                )
            )

        if releases:
            latest_rel = releases[0]
            rel_dt = latest_rel.release_date
            if rel_dt.tzinfo is None:
                rel_dt = rel_dt.replace(tzinfo=timezone.utc)

            pre_post_data = cls._compute_pre_post_metrics(session, product, rel_dt, latest_rel.version)

        # 4. Identify Relevant Themes
        active_themes = session.scalars(
            select(Theme)
            .where(
                Theme.product == product,
                Theme.status == "active",
            )
            .order_by(Theme.created_at.desc())
        ).all()

        # Prioritize themes mentioned in question
        q_lower = question.lower()
        matched_themes: List[Theme] = []
        other_themes: List[Theme] = []

        for th in active_themes:
            if th.theme_name.lower() in q_lower or th.category.lower() in q_lower:
                matched_themes.append(th)
            else:
                other_themes.append(th)

        selected_themes = (matched_themes + other_themes)[:3]
        theme_evidence = [
            ThemeEvidenceItem(
                theme_id=th.theme_id,
                theme_name=th.theme_name,
                category=th.category,
                status=th.status,
            )
            for th in selected_themes
        ]

        # 5. Extract Representative Customer Quotes
        feedback_evidence = cls._extract_feedback_evidence(session, product, question)

        # 6. Retrieve Historical Memories from Hindsight
        hindsight_available = False
        historical_context: Optional[str] = None
        memory_refs: List[str] = []

        if hindsight_client.is_configured:
            recall_res = await hindsight_service.recall_memories(
                session=session,
                product=product,
                query=question,
                limit=5,
                client=hindsight_client,
            )
            hindsight_available = recall_res.available
            if recall_res.available and recall_res.memories:
                memory_refs = [
                    m.hindsight_memory_id for m in recall_res.memories if m.hindsight_memory_id
                ]
                reflect_res = await hindsight_service.reflect_on_memories(
                    session=session,
                    product=product,
                    query=question,
                    client=hindsight_client,
                )
                if reflect_res.available and reflect_res.reasoning:
                    historical_context = reflect_res.reasoning

        # Build SQL metrics payload
        sql_metrics = SQLMetrics(
            total_feedback=overview.total_feedback_count,
            classified_feedback=overview.classified_feedback_count,
            positive_percentage=overview.sentiment_breakdown.positive_percentage,
            negative_percentage=overview.sentiment_breakdown.negative_percentage,
            neutral_percentage=overview.sentiment_breakdown.neutral_percentage,
            average_sentiment_score=overview.average_sentiment_score,
            pre_post_comparison=pre_post_data,
            aspect_mentions=aspect_dict,
        )

        evidence = IntelligenceEvidence(
            feedback_quotes=feedback_evidence,
            themes=theme_evidence,
            releases=release_evidence,
            hindsight_memory_refs=memory_refs,
        )

        # 7. Synthesize Response (LLM with deterministic fallback)
        answer, key_findings, limitations = await cls._synthesize_answer(
            question=question,
            product=product,
            sql_metrics=sql_metrics,
            historical_context=historical_context,
            hindsight_available=hindsight_available,
            evidence=evidence,
            ai_manager=ai_manager,
        )

        return HistoricalIntelligenceResponse(
            product=product,
            question=question,
            answer=answer,
            key_findings=key_findings,
            sql_metrics=sql_metrics,
            historical_context=historical_context,
            evidence=evidence,
            hindsight_available=hindsight_available,
            limitations=limitations,
        )

    @classmethod
    def _compute_pre_post_metrics(
        cls,
        session: Session,
        product: str,
        rel_dt: datetime,
        version: str,
    ) -> Dict[str, Any]:
        """Compute structured sentiment volume and metrics before vs after release."""
        pre_start = rel_dt - timedelta(days=30)
        post_end = datetime.now(timezone.utc)
        latest_cls = get_latest_classification_subquery()

        # Pre-release query
        pre_rows = session.execute(
            select(latest_cls.c.overall_sentiment, latest_cls.c.sentiment_score)
            .select_from(Feedback)
            .join(latest_cls, Feedback.feedback_id == latest_cls.c.feedback_id)
            .where(
                Feedback.product == product,
                Feedback.deleted_at.is_(None),
                Feedback.timestamp >= pre_start,
                Feedback.timestamp < rel_dt,
            )
        ).all()

        # Post-release query
        post_rows = session.execute(
            select(latest_cls.c.overall_sentiment, latest_cls.c.sentiment_score)
            .select_from(Feedback)
            .join(latest_cls, Feedback.feedback_id == latest_cls.c.feedback_id)
            .where(
                Feedback.product == product,
                Feedback.deleted_at.is_(None),
                Feedback.timestamp >= rel_dt,
                Feedback.timestamp <= post_end,
            )
        ).all()

        pre_total = len(pre_rows)
        pre_neg = sum(1 for r in pre_rows if r[0] == "negative")
        pre_pos = sum(1 for r in pre_rows if r[0] == "positive")
        pre_scores = [r[1] for r in pre_rows if r[1] is not None]
        pre_neg_pct = round((pre_neg / pre_total) * 100, 1) if pre_total else 0.0
        pre_avg = round(sum(pre_scores) / len(pre_scores), 4) if pre_scores else None

        post_total = len(post_rows)
        post_neg = sum(1 for r in post_rows if r[0] == "negative")
        post_pos = sum(1 for r in post_rows if r[0] == "positive")
        post_scores = [r[1] for r in post_rows if r[1] is not None]
        post_neg_pct = round((post_neg / post_total) * 100, 1) if post_total else 0.0
        post_avg = round(sum(post_scores) / len(post_scores), 4) if post_scores else None

        delta_neg = round(post_neg_pct - pre_neg_pct, 1) if (pre_total and post_total) else None

        return {
            "release_version": version,
            "release_date": rel_dt.isoformat(),
            "pre_release": {
                "window_days": 30,
                "count": pre_total,
                "negative_count": pre_neg,
                "positive_count": pre_pos,
                "negative_percentage": pre_neg_pct,
                "average_sentiment_score": pre_avg,
            },
            "post_release": {
                "count": post_total,
                "negative_count": post_neg,
                "positive_count": post_pos,
                "negative_percentage": post_neg_pct,
                "average_sentiment_score": post_avg,
            },
            "delta_negative_percentage": delta_neg,
        }

    @classmethod
    def _extract_feedback_evidence(
        cls,
        session: Session,
        product: str,
        question: str,
    ) -> List[FeedbackEvidenceItem]:
        """Extract verifiable customer feedback quotes relevant to user inquiry."""
        latest_cls = get_latest_classification_subquery()
        base_stmt = (
            select(
                Feedback.feedback_id,
                Feedback.timestamp,
                Feedback.cleaned_feedback_text,
                Feedback.feedback_text,
                latest_cls.c.overall_sentiment,
                latest_cls.c.customer_intent,
            )
            .select_from(Feedback)
            .outerjoin(latest_cls, Feedback.feedback_id == latest_cls.c.feedback_id)
            .where(
                Feedback.product == product,
                Feedback.deleted_at.is_(None),
            )
        )

        # Keyword heuristics from question
        keywords = [
            w for w in re.findall(r"\b[a-zA-Z]{4,}\b", question.lower())
            if w not in {"what", "when", "where", "which", "about", "after", "latest", "release", "problem", "customer", "customers", "still", "have", "with"}
        ]

        matched_rows = []
        if keywords:
            keyword_conditions = [
                or_(
                    Feedback.feedback_text.ilike(f"%{kw}%"),
                    Feedback.cleaned_feedback_text.ilike(f"%{kw}%"),
                )
                for kw in keywords[:3]
            ]
            kw_stmt = base_stmt.where(or_(*keyword_conditions)).order_by(Feedback.timestamp.desc()).limit(4)
            matched_rows = session.execute(kw_stmt).all()

        if not matched_rows:
            fallback_stmt = base_stmt.order_by(Feedback.timestamp.desc()).limit(3)
            matched_rows = session.execute(fallback_stmt).all()

        quotes: List[FeedbackEvidenceItem] = []
        for row in matched_rows:
            fb_id, ts, cleaned, raw, sentiment, intent = row
            text = cleaned or raw or ""
            if len(text) > 280:
                text = text[:277] + "..."
            quotes.append(
                FeedbackEvidenceItem(
                    feedback_id=fb_id,
                    timestamp=ts,
                    sentiment=sentiment,
                    intent=intent,
                    quote=text,
                )
            )
        return quotes

    @classmethod
    async def _synthesize_answer(
        cls,
        question: str,
        product: str,
        sql_metrics: SQLMetrics,
        historical_context: Optional[str],
        hindsight_available: bool,
        evidence: IntelligenceEvidence,
        ai_manager: Optional[AIProviderManager],
    ) -> Tuple[str, List[str], List[str]]:
        """Synthesize answer using AIProviderManager if available, falling back to deterministic synthesis."""
        if ai_manager is not None:
            try:
                system_instruction = (
                    "You are the Feedback Intelligence Agent. Answer the product manager's question using the provided "
                    "authoritative PostgreSQL metrics and Hindsight historical memories.\n"
                    "RULES:\n"
                    "1. Never invent or contradict numerical values. All counts, percentages, and scores MUST strictly match the provided SQL metrics.\n"
                    "2. Do NOT claim that a release or product change caused an improvement or regression. Explicitly describe timing correlations as observational.\n"
                    "3. If Hindsight is unavailable, explicitly note that historical memory synthesis was unavailable and conclusions rely solely on PostgreSQL records.\n"
                    "4. Return clean JSON with keys: 'answer' (str), 'key_findings' (list of str), 'limitations' (list of str)."
                )

                prompt_data = {
                    "question": question,
                    "product": product,
                    "sql_metrics": sql_metrics.model_dump(),
                    "historical_context": historical_context,
                    "hindsight_available": hindsight_available,
                    "evidence_quotes_count": len(evidence.feedback_quotes),
                    "releases_count": len(evidence.releases),
                }

                req = AIRequest(
                    prompt=json.dumps(prompt_data),
                    system_instruction=system_instruction,
                    temperature=0.1,
                )
                ai_resp = await ai_manager.generate(req)
                if ai_resp.raw_json and isinstance(ai_resp.raw_json, dict):
                    ans = str(ai_resp.raw_json.get("answer") or "")
                    findings = ai_resp.raw_json.get("key_findings") or []
                    limits = ai_resp.raw_json.get("limitations") or []
                    if ans:
                        return ans, findings, limits
            except Exception as exc:
                logger.debug("AIProviderManager generation skipped or failed (%s); using deterministic synthesizer.", exc)

        # Deterministic Grounded Synthesizer
        return cls._deterministic_synthesizer(
            question=question,
            product=product,
            sql_metrics=sql_metrics,
            historical_context=historical_context,
            hindsight_available=hindsight_available,
            evidence=evidence,
        )

    @classmethod
    def _deterministic_synthesizer(
        cls,
        question: str,
        product: str,
        sql_metrics: SQLMetrics,
        historical_context: Optional[str],
        hindsight_available: bool,
        evidence: IntelligenceEvidence,
    ) -> Tuple[str, List[str], List[str]]:
        """Reliable, testable, fully grounded answer synthesis without hallucinations."""
        key_findings: List[str] = []
        limitations: List[str] = [
            "Causality guardrail: Temporal correlation between product releases and sentiment changes does not confirm causation; unmeasured factors may contribute."
        ]

        if not hindsight_available:
            limitations.append(
                "Historical memory reasoning (Hindsight) was unavailable; findings rely exclusively on structured PostgreSQL records."
            )

        pre_post = sql_metrics.pre_post_comparison
        rel_str = ""
        pre_post_str = ""

        if pre_post and pre_post.get("release_version"):
            v = pre_post["release_version"]
            pre_neg = pre_post["pre_release"]["negative_percentage"]
            post_neg = pre_post["post_release"]["negative_percentage"]
            delta = pre_post.get("delta_negative_percentage")
            rel_str = f"Following release {v}, "
            if delta is not None:
                if delta < 0:
                    pre_post_str = (
                        f"negative feedback shifted from {pre_neg}% pre-release down to {post_neg}% post-release "
                        f"({abs(delta):.1f}% decrease in negative share). "
                    )
                    key_findings.append(f"Negative feedback decreased by {abs(delta):.1f}% following release {v}.")
                elif delta > 0:
                    pre_post_str = (
                        f"negative feedback increased from {pre_neg}% pre-release to {post_neg}% post-release "
                        f"(+{delta:.1f}% increase in negative share). "
                    )
                    key_findings.append(f"Negative feedback increased by {delta:.1f}% following release {v}.")
                else:
                    pre_post_str = f"negative feedback remained flat at {pre_neg}%. "
                    key_findings.append(f"Negative feedback volume remained unchanged following release {v}.")
        else:
            limitations.append("No product release changelog events were recorded for pre/post temporal comparison.")

        # Overall sentiment summary
        key_findings.append(
            f"Overall sentiment stands at {sql_metrics.positive_percentage}% positive and {sql_metrics.negative_percentage}% negative "
            f"across {sql_metrics.total_feedback} feedback items."
        )

        if evidence.themes:
            top_theme = evidence.themes[0]
            key_findings.append(f"Primary active theme identified: '{top_theme.theme_name}' ({top_theme.category}).")

        # Build answer narrative
        answer_parts = [
            f"Based on {sql_metrics.total_feedback} customer feedback records for '{product}', "
            f"overall sentiment is {sql_metrics.positive_percentage}% positive, "
            f"{sql_metrics.negative_percentage}% negative, and {sql_metrics.neutral_percentage}% neutral."
        ]

        if pre_post_str:
            answer_parts.append(
                f"{rel_str}{pre_post_str}However, this shift represents an observational temporal correlation rather than direct causation."
            )

        if historical_context:
            answer_parts.append(f"Historical memory reflection: {historical_context}")
        elif not hindsight_available:
            answer_parts.append(
                "Historical memory context could not be retrieved from Hindsight; conclusions are grounded solely on PostgreSQL data."
            )
        else:
            answer_parts.append("No recurring historical memory patterns were cited for this specific inquiry.")

        answer = " ".join(answer_parts)
        return answer, key_findings, limitations
