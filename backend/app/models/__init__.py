"""SQLAlchemy 2.x database models.

All application models are exported here to ensure registration
with Base.metadata for Alembic discovery and table management.
"""

from app.models.feedback import Feedback, FeedbackThemes
from app.models.theme import Theme, ThemeSnapshot
from app.models.sentiment import SentimentHistory
from app.models.product_change import ProductChanges
from app.models.insight import Insight, InsightEvidence
from app.models.memory import MemoryMetadata
from app.models.upload_job import UploadJob
from app.models.classification import FeedbackClassification
from app.models.feedback_embeddings import FeedbackEmbedding

__all__ = [
    "Feedback",
    "FeedbackThemes",
    "Theme",
    "ThemeSnapshot",
    "SentimentHistory",
    "ProductChanges",
    "Insight",
    "InsightEvidence",
    "MemoryMetadata",
    "UploadJob",
    "FeedbackClassification",
    "FeedbackEmbedding",
]
