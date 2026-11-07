"""Pydantic Schemas for Feedback Classification & Sentiment Analysis.

Defines strict Pydantic v2 schemas for multi-topic classification, aspect-based
sentiment analysis, customer intent, model-estimated confidence, and persistence models.

NOTE ON CONFIDENCE SCORES:
Model-reported confidence scores (0.0 to 1.0) represent heuristic model estimates
of classification certainty and are NOT statistically calibrated probabilities.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, ConfigDict, Field, field_validator


class OverallSentiment(str, Enum):
    """Overall categorical sentiment classification."""

    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    MIXED = "mixed"


class AspectSentiment(str, Enum):
    """Dedicated aspect-level sentiment classification supporting positive, negative, neutral, and mixed."""

    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    MIXED = "mixed"


class SentimentIntensity(str, Enum):
    """Intensity level of expressed sentiment."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class CustomerIntent(str, Enum):
    """Primary intent detected in customer feedback."""

    COMPLAINT = "complaint"
    SUGGESTION = "suggestion"
    PRAISE = "praise"
    QUESTION = "question"
    FEATURE_REQUEST = "feature_request"
    OTHER = "other"


class ReviewReason(str, Enum):
    """Standard reasons for triggering human review."""

    LOW_CONFIDENCE = "low_confidence"
    AMBIGUOUS_SENTIMENT = "ambiguous_sentiment"
    SARCASM_DETECTED = "sarcasm_detected"
    MIXED_SIGNALS = "mixed_signals"
    UNKNOWN_PRODUCT = "unknown_product"
    UNGROUNDED_EVIDENCE = "ungrounded_evidence"
    MANUAL_AUDIT = "manual_audit"


class TopicItem(BaseModel):
    """Categorical topic with heuristic model confidence."""

    label: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Standardized topic or issue label (e.g. performance, usability, billing)",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Heuristic model confidence score (0.0 to 1.0)",
    )

    model_config = ConfigDict(extra="forbid")

    @field_validator("label")
    @classmethod
    def clean_label(cls, v: str) -> str:
        cleaned = v.strip().lower()
        if not cleaned:
            raise ValueError("Topic label cannot be blank")
        return cleaned


class AspectItem(BaseModel):
    """Aspect-based sentiment analysis with verbatim grounded evidence."""

    aspect: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Specific feature, component, or service aspect analyzed",
    )
    sentiment: AspectSentiment = Field(
        ...,
        description="Aspect-level sentiment: positive, negative, neutral, mixed",
    )
    sentiment_score: float = Field(
        ...,
        ge=-1.0,
        le=1.0,
        description="Aspect continuous sentiment score (-1.0 very negative to +1.0 very positive)",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Heuristic model confidence score for this aspect (0.0 to 1.0)",
    )
    evidence: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Verbatim excerpt from feedback supporting this aspect analysis",
    )

    model_config = ConfigDict(extra="forbid")

    @field_validator("aspect")
    @classmethod
    def clean_aspect(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Aspect name cannot be blank")
        return cleaned

    @field_validator("evidence")
    @classmethod
    def clean_evidence(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Aspect evidence cannot be blank")
        return cleaned


class FeedbackClassificationLLMOutput(BaseModel):
    """Strict schema for AI-generated classification payload.

    Validated directly by AIProviderManager against model completion output.
    Does not contain database persistence metadata (e.g. classification_id).
    """

    overall_sentiment: OverallSentiment = Field(
        ...,
        description="Overall feedback sentiment classification",
    )
    sentiment_score: float = Field(
        ...,
        ge=-1.0,
        le=1.0,
        description="Continuous overall sentiment score (-1.0 to +1.0)",
    )
    sentiment_intensity: SentimentIntensity = Field(
        default=SentimentIntensity.MEDIUM,
        description="Sentiment intensity: low, medium, high",
    )
    customer_intent: CustomerIntent = Field(
        ...,
        description="Primary customer intent (complaint, suggestion, praise, etc.)",
    )
    topics: List[TopicItem] = Field(
        default_factory=list,
        max_length=10,
        description="List of detected topics with confidence scores",
    )
    product: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Identified product name, or null if uncertain",
    )
    feature: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Identified feature or component, or null if uncertain",
    )
    pain_points: List[str] = Field(
        default_factory=list,
        max_length=10,
        description="Customer pain points extracted directly from feedback",
    )
    aspects: List[AspectItem] = Field(
        default_factory=list,
        max_length=10,
        description="Aspect-based sentiment analysis with verbatim evidence",
    )
    keywords: List[str] = Field(
        default_factory=list,
        max_length=20,
        description="Salient keywords extracted from feedback",
    )
    confidence_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Overall classification confidence score (0.0 to 1.0)",
    )
    needs_review: bool = Field(
        default=False,
        description="True if classification meets low-confidence or ambiguity criteria",
    )
    review_reason: Optional[str] = Field(
        default=None,
        max_length=255,
        description="Reason human review was flagged (e.g. low_confidence, ambiguous_sentiment)",
    )

    model_config = ConfigDict(extra="forbid")

    @field_validator("product", "feature", mode="before")
    @classmethod
    def sanitize_optional_str(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        cleaned = str(v).strip()
        return cleaned if cleaned else None

    @field_validator("pain_points", "keywords", mode="before")
    @classmethod
    def clean_str_list(cls, v: Any) -> List[str]:
        if not isinstance(v, list):
            return []
        cleaned_list: List[str] = []
        for item in v:
            if isinstance(item, str):
                s = item.strip()
                if s and len(s) <= 255 and s not in cleaned_list:
                    cleaned_list.append(s)
        return cleaned_list


class FeedbackClassificationRecord(BaseModel):
    """Database persistence schema matching stored FeedbackClassification entity."""

    model_config = ConfigDict(from_attributes=True)

    classification_id: uuid.UUID
    feedback_id: uuid.UUID
    classification_version: str
    run_number: int = Field(1, description="Sequential execution index for this feedback and classification version")
    status: str
    overall_sentiment: str
    sentiment_score: float
    sentiment_intensity: str
    customer_intent: str
    identified_product: Optional[str] = None
    identified_feature: Optional[str] = None
    topics: Optional[List[Dict[str, Any]]] = None
    aspects: Optional[List[Dict[str, Any]]] = None
    pain_points: Optional[List[str]] = None
    keywords: Optional[List[str]] = None
    confidence_score: float
    needs_review: bool
    review_reason: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    latency_ms: Optional[float] = None
    token_usage: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    classified_at: datetime



class ClassificationItemError(BaseModel):
    """Failure details for an individual record in a batch classification run."""

    feedback_id: uuid.UUID
    error: str
    status: str = "failed"


class BatchClassificationRequest(BaseModel):
    """Request payload for bounded batch feedback classification."""

    feedback_ids: List[uuid.UUID] = Field(
        default_factory=list,
        description="Bounded list of feedback UUIDs to classify (max 50)",
    )
    reprocess: bool = Field(
        default=False,
        description="If True, forces reclassification of items already processed under current version",
    )


class BatchClassificationResponse(BaseModel):
    """Aggregate result summary of a batch feedback classification execution."""

    total_requested: int
    successful_count: int
    failed_count: int
    skipped_count: int
    results: List[FeedbackClassificationRecord] = Field(default_factory=list)
    errors: List[ClassificationItemError] = Field(default_factory=list)


class ClassificationSummaryResponse(BaseModel):
    """Aggregate analytics and sentiment distribution across classifications."""

    total_classifications: int = Field(
        ...,
        description="Total historical classification records matching criteria",
    )
    latest_classified_count: int = Field(
        ...,
        description="Count of unique feedback records with at least one active classification",
    )
    sentiment_distribution: Dict[str, int] = Field(
        default_factory=lambda: {"positive": 0, "negative": 0, "neutral": 0, "mixed": 0},
        description="Overall sentiment distribution for latest valid classifications",
    )
    intent_distribution: Dict[str, int] = Field(
        default_factory=lambda: {
            "complaint": 0,
            "suggestion": 0,
            "praise": 0,
            "question": 0,
            "feature_request": 0,
            "other": 0,
        },
        description="Customer intent distribution for latest valid classifications",
    )
    aspect_sentiment_distribution: Dict[str, int] = Field(
        default_factory=lambda: {"positive": 0, "negative": 0, "neutral": 0, "mixed": 0},
        description="Aspect-level sentiment distribution extracted from latest valid classifications",
    )
    needs_review_count: int = Field(
        0,
        description="Number of latest valid classifications flagged as requiring human review",
    )
    status_distribution: Dict[str, int] = Field(
        default_factory=lambda: {"classified": 0, "failed": 0, "pending_review": 0},
        description="Status breakdown across latest classification attempts per feedback item (reflects operational health including failed attempts)",
    )
    feedback_quality_status_distribution: Dict[str, int] = Field(
        default_factory=lambda: {"clean": 0, "flagged": 0, "pending": 0, "rejected": 0, "failed": 0},
        description="Quality status distribution of feedback records matching filter",
    )
