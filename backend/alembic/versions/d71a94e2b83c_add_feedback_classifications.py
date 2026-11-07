"""add_feedback_classifications

Revision ID: d71a94e2b83c
Revises: f6b903e1a82d
Create Date: 2026-11-06 15:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd71a94e2b83c'
down_revision: Union[str, Sequence[str], None] = 'f6b903e1a82d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create feedback_classifications table with constraints and indexes."""
    op.create_table(
        'feedback_classifications',
        sa.Column('classification_id', sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            'feedback_id',
            sa.Uuid(as_uuid=True),
            sa.ForeignKey('feedback.feedback_id', ondelete='CASCADE'),
            nullable=False,
            comment='Foreign key to feedback record with cascade deletion',
        ),
        sa.Column(
            'classification_version',
            sa.String(50),
            nullable=False,
            server_default='1.0.0',
            comment='Pipeline/model version for deterministic reclassification',
        ),
        sa.Column(
            'status',
            sa.String(50),
            nullable=False,
            server_default='classified',
            comment='Lifecycle status: classified, failed, pending_review',
        ),
        sa.Column(
            'overall_sentiment',
            sa.String(50),
            nullable=False,
            comment='Categorical overall sentiment: positive, negative, neutral, mixed',
        ),
        sa.Column(
            'sentiment_score',
            sa.Float(),
            nullable=False,
            comment='Continuous overall sentiment score (-1.0 to +1.0)',
        ),
        sa.Column(
            'sentiment_intensity',
            sa.String(50),
            nullable=False,
            server_default='medium',
            comment='Sentiment intensity: low, medium, high',
        ),
        sa.Column(
            'customer_intent',
            sa.String(50),
            nullable=False,
            comment='Primary customer intent: complaint, suggestion, praise, question, feature_request, other',
        ),
        sa.Column(
            'identified_product',
            sa.String(100),
            nullable=True,
            comment='Identified product or null if uncertain',
        ),
        sa.Column(
            'identified_feature',
            sa.String(100),
            nullable=True,
            comment='Identified feature or null if uncertain',
        ),
        sa.Column(
            'topics',
            sa.JSON(),
            nullable=True,
            comment="List of classified topic labels with confidence: [{'label': str, 'confidence': float}]",
        ),
        sa.Column(
            'aspects',
            sa.JSON(),
            nullable=True,
            comment="List of aspect sentiments: [{'aspect': str, 'sentiment': str, 'sentiment_score': float, 'confidence': float, 'evidence': str}]",
        ),
        sa.Column(
            'pain_points',
            sa.JSON(),
            nullable=True,
            comment='List of extracted customer pain points',
        ),
        sa.Column(
            'keywords',
            sa.JSON(),
            nullable=True,
            comment='List of salient keywords extracted from feedback',
        ),
        sa.Column(
            'confidence_score',
            sa.Float(),
            nullable=False,
            comment='Model-estimated confidence score from 0.0 to 1.0',
        ),
        sa.Column(
            'needs_review',
            sa.Boolean(),
            nullable=False,
            server_default=sa.text('false'),
            comment='True if classification meets low-confidence or ambiguity review criteria',
        ),
        sa.Column(
            'review_reason',
            sa.String(255),
            nullable=True,
            comment='Reason human review was triggered',
        ),
        sa.Column(
            'provider',
            sa.String(50),
            nullable=True,
            comment='Responding AI provider name (e.g. gemini, openrouter, grok)',
        ),
        sa.Column(
            'model',
            sa.String(100),
            nullable=True,
            comment='Specific model ID that executed the classification completion',
        ),
        sa.Column(
            'latency_ms',
            sa.Float(),
            nullable=True,
            comment='Inference latency in milliseconds',
        ),
        sa.Column(
            'token_usage',
            sa.JSON(),
            nullable=True,
            comment='Token metrics: prompt_tokens, completion_tokens, total_tokens, cost_usd',
        ),
        sa.Column(
            'error_message',
            sa.Text(),
            nullable=True,
            comment='Safe error description if classification failed',
        ),
        sa.Column(
            'classified_at',
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            comment='Classification timestamp in UTC',
        ),
        sa.UniqueConstraint(
            'feedback_id',
            'classification_version',
            name='uq_feedback_classifications_feedback_version',
        ),
        sa.CheckConstraint(
            'sentiment_score >= -1.0 AND sentiment_score <= 1.0',
            name='ck_feedback_classifications_sentiment_score',
        ),
        sa.CheckConstraint(
            'confidence_score >= 0.0 AND confidence_score <= 1.0',
            name='ck_feedback_classifications_confidence_score',
        ),
        sa.CheckConstraint(
            "overall_sentiment IN ('positive', 'negative', 'neutral', 'mixed')",
            name='ck_feedback_classifications_overall_sentiment',
        ),
        sa.CheckConstraint(
            "sentiment_intensity IN ('low', 'medium', 'high')",
            name='ck_feedback_classifications_sentiment_intensity',
        ),
        sa.CheckConstraint(
            "customer_intent IN ('complaint', 'suggestion', 'praise', 'question', 'feature_request', 'other')",
            name='ck_feedback_classifications_customer_intent',
        ),
        sa.CheckConstraint(
            "status IN ('classified', 'failed', 'pending_review')",
            name='ck_feedback_classifications_status',
        ),
    )

    op.create_index(
        'ix_feedback_classifications_feedback_id',
        'feedback_classifications',
        ['feedback_id'],
    )
    op.create_index(
        'ix_feedback_classifications_overall_sentiment',
        'feedback_classifications',
        ['overall_sentiment'],
    )
    op.create_index(
        'ix_feedback_classifications_customer_intent',
        'feedback_classifications',
        ['customer_intent'],
    )
    op.create_index(
        'ix_feedback_classifications_status',
        'feedback_classifications',
        ['status'],
    )
    op.create_index(
        'ix_feedback_classifications_needs_review',
        'feedback_classifications',
        ['needs_review'],
    )
    op.create_index(
        'ix_feedback_classifications_classified_at',
        'feedback_classifications',
        ['classified_at'],
    )
    op.create_index(
        'ix_feedback_classifications_feedback_classified',
        'feedback_classifications',
        ['feedback_id', 'classified_at'],
    )
    op.create_index(
        'ix_feedback_classifications_sentiment_intent',
        'feedback_classifications',
        ['overall_sentiment', 'customer_intent'],
    )


def downgrade() -> None:
    """Drop feedback_classifications table and all associated indexes."""
    op.drop_index(
        'ix_feedback_classifications_sentiment_intent',
        table_name='feedback_classifications',
    )
    op.drop_index(
        'ix_feedback_classifications_feedback_classified',
        table_name='feedback_classifications',
    )
    op.drop_index(
        'ix_feedback_classifications_classified_at',
        table_name='feedback_classifications',
    )
    op.drop_index(
        'ix_feedback_classifications_needs_review',
        table_name='feedback_classifications',
    )
    op.drop_index(
        'ix_feedback_classifications_status',
        table_name='feedback_classifications',
    )
    op.drop_index(
        'ix_feedback_classifications_customer_intent',
        table_name='feedback_classifications',
    )
    op.drop_index(
        'ix_feedback_classifications_overall_sentiment',
        table_name='feedback_classifications',
    )
    op.drop_index(
        'ix_feedback_classifications_feedback_id',
        table_name='feedback_classifications',
    )
    op.drop_table('feedback_classifications')
