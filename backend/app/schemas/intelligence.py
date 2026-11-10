"""Pydantic schemas for Historical Memory Intelligence (Part 10).

Defines request and response structures for natural language Q&A workflows
that combine PostgreSQL authoritative metrics, theme evidence, release changelogs,
and Hindsight persistent memory reflections.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field


class FeedbackEvidenceItem(BaseModel):
    """Customer quote citation supporting an analytical claim."""

    model_config = ConfigDict(from_attributes=True)

    feedback_id: uuid.UUID = Field(..., description="PostgreSQL feedback UUID")
    timestamp: datetime = Field(..., description="UTC timestamp of the feedback")
    sentiment: Optional[str] = Field(None, description="Sentiment label (positive, negative, neutral, mixed)")
    intent: Optional[str] = Field(None, description="Classified customer intent")
    quote: str = Field(..., description="Normalized or excerpted feedback text")


class ThemeEvidenceItem(BaseModel):
    """Categorical theme context relevant to the user query."""

    model_config = ConfigDict(from_attributes=True)

    theme_id: uuid.UUID = Field(..., description="Theme UUID in PostgreSQL")
    theme_name: str = Field(..., description="Human-readable theme title")
    category: str = Field(..., description="Theme category (bug, usability, billing, etc.)")
    status: str = Field(..., description="Theme lifecycle status (candidate, active, archived, merged)")


class ReleaseEvidenceItem(BaseModel):
    """Product release event correlated with customer feedback trajectories."""

    model_config = ConfigDict(from_attributes=True)

    release_id: uuid.UUID = Field(..., description="Release UUID in PostgreSQL")
    version: str = Field(..., description="Semantic release version tag")
    release_date: datetime = Field(..., description="UTC release timestamp")
    change_category: str = Field(..., description="Type of release (feature_launch, hotfix, redesign, etc.)")
    feature: Optional[str] = Field(None, description="Impacted product feature or component")
    description: str = Field(..., description="Changelog narrative or release notes")


class IntelligenceEvidence(BaseModel):
    """Structured evidence citations grounded in PostgreSQL and Hindsight."""

    feedback_quotes: List[FeedbackEvidenceItem] = Field(
        default_factory=list,
        description="Verifiable customer feedback quotes with IDs",
    )
    themes: List[ThemeEvidenceItem] = Field(
        default_factory=list,
        description="Associated active themes discovered in PostgreSQL",
    )
    releases: List[ReleaseEvidenceItem] = Field(
        default_factory=list,
        description="Product releases and feature changes relevant to question timeframe",
    )
    hindsight_memory_refs: List[str] = Field(
        default_factory=list,
        description="External Hindsight memory IDs cited in reflection",
    )


class SQLMetrics(BaseModel):
    """Authoritative structured measurements computed strictly from PostgreSQL."""

    total_feedback: int = Field(0, description="Total feedback records evaluated")
    classified_feedback: int = Field(0, description="Feedback items with valid classifications")
    positive_percentage: float = Field(0.0, description="Percentage of positive feedback")
    negative_percentage: float = Field(0.0, description="Percentage of negative feedback")
    neutral_percentage: float = Field(0.0, description="Percentage of neutral feedback")
    average_sentiment_score: Optional[float] = Field(
        None, description="Continuous mean sentiment score (-1.0 to +1.0)"
    )
    pre_post_comparison: Optional[Dict[str, Any]] = Field(
        None,
        description="Quantitative comparison of feedback volume and sentiment before vs after the latest release",
    )
    aspect_mentions: Optional[Dict[str, int]] = Field(
        None,
        description="Frequency of relevant aspect mentions (e.g., checkout, performance, billing)",
    )


class HistoricalIntelligenceRequest(BaseModel):
    """Natural-language question query scoped to a product."""

    product: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Target product line or application name",
    )
    question: str = Field(
        ...,
        min_length=3,
        max_length=1000,
        description="Product manager's natural language question",
    )


class HistoricalIntelligenceResponse(BaseModel):
    """Unified intelligence response combining SQL facts, Hindsight memory, and causal guardrails."""

    product: str = Field(..., description="Product scoped for this inquiry")
    question: str = Field(..., description="Original user question")
    answer: str = Field(
        ...,
        description="Executive answer synthesizing SQL ground truth and historical memories",
    )
    key_findings: List[str] = Field(
        default_factory=list,
        description="Bulleted factual conclusions verified by data",
    )
    sql_metrics: SQLMetrics = Field(
        ...,
        description="Authoritative numerical measurements strictly from PostgreSQL",
    )
    historical_context: Optional[str] = Field(
        None,
        description="Semantic narrative and trajectory analysis retrieved from Hindsight Persistent Memory",
    )
    evidence: IntelligenceEvidence = Field(
        default_factory=IntelligenceEvidence,
        description="Supporting feedback quotes, themes, and product release events",
    )
    hindsight_available: bool = Field(
        ...,
        description="True if Hindsight memory service was reachable and contributed reflection",
    )
    limitations: List[str] = Field(
        default_factory=list,
        description="Explicit data limitations, non-causality notices, and missing evidence warnings",
    )
