"""initial_schema

Revision ID: ae66156cfb1a
Revises:
Create Date: 2026-11-05 22:33:58.312466

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ae66156cfb1a'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create all core PRD entity tables, constraints, foreign keys, and indexes."""
    # 1. Feedback table
    op.create_table(
        'feedback',
        sa.Column('feedback_id', sa.Uuid(), nullable=False),
        sa.Column('source', sa.String(length=100), nullable=False, comment='Source of feedback, e.g., csv, json, zendesk, app_store'),
        sa.Column('customer_id', sa.String(length=255), nullable=True, comment='External customer or account identifier'),
        sa.Column('feedback_text', sa.Text(), nullable=False, comment='Original unedited feedback content'),
        sa.Column('product', sa.String(length=100), nullable=False, comment='Product line or application name'),
        sa.Column('feature', sa.String(length=100), nullable=True, comment='Specific feature or component identified'),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False, comment='Original timestamp when feedback was provided by user'),
        sa.Column('app_version', sa.String(length=50), nullable=True, comment='Application or client release version'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='Ingestion timestamp in UTC'),
        sa.PrimaryKeyConstraint('feedback_id', name=op.f('pk_feedback'))
    )
    op.create_index(op.f('ix_feedback_app_version'), 'feedback', ['app_version'], unique=False)
    op.create_index(op.f('ix_feedback_customer_id'), 'feedback', ['customer_id'], unique=False)
    op.create_index(op.f('ix_feedback_feature'), 'feedback', ['feature'], unique=False)
    op.create_index(op.f('ix_feedback_product'), 'feedback', ['product'], unique=False)
    op.create_index('ix_feedback_product_feature', 'feedback', ['product', 'feature'], unique=False)
    op.create_index('ix_feedback_product_timestamp', 'feedback', ['product', 'timestamp'], unique=False)
    op.create_index(op.f('ix_feedback_source'), 'feedback', ['source'], unique=False)
    op.create_index(op.f('ix_feedback_timestamp'), 'feedback', ['timestamp'], unique=False)

    # 2. Themes table
    op.create_table(
        'themes',
        sa.Column('theme_id', sa.Uuid(), nullable=False),
        sa.Column('theme_name', sa.String(length=150), nullable=False, comment='Human-readable theme or issue title'),
        sa.Column('description', sa.Text(), nullable=True, comment='Detailed definition and scope of this theme'),
        sa.Column('category', sa.String(length=100), nullable=False, comment='Broad classification, e.g., usability, bug, billing, performance'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='Creation timestamp in UTC'),
        sa.Column('status', sa.String(length=50), server_default='active', nullable=False, comment='Status: active, emerging, declining, recurring, archived'),
        sa.PrimaryKeyConstraint('theme_id', name=op.f('pk_themes')),
        sa.UniqueConstraint('theme_name', name=op.f('uq_themes_theme_name'))
    )
    op.create_index(op.f('ix_themes_category'), 'themes', ['category'], unique=False)
    op.create_index('ix_themes_category_status', 'themes', ['category', 'status'], unique=False)
    op.create_index(op.f('ix_themes_status'), 'themes', ['status'], unique=False)
    op.create_index(op.f('ix_themes_theme_name'), 'themes', ['theme_name'], unique=False)

    # 3. FeedbackThemes junction table
    op.create_table(
        'feedback_themes',
        sa.Column('feedback_id', sa.Uuid(), nullable=False),
        sa.Column('theme_id', sa.Uuid(), nullable=False),
        sa.Column('relevance_score', sa.Float(), nullable=False, comment='Theme relevance score from 0.0 to 1.0'),
        sa.Column('aspect_sentiment', sa.String(length=50), nullable=True, comment='Aspect sentiment label: positive, negative, neutral, mixed'),
        sa.CheckConstraint('relevance_score >= 0.0 AND relevance_score <= 1.0', name='ck_feedback_themes_relevance_score'),
        sa.ForeignKeyConstraint(['feedback_id'], ['feedback.feedback_id'], name=op.f('fk_feedback_themes_feedback_id_feedback'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['theme_id'], ['themes.theme_id'], name=op.f('fk_feedback_themes_theme_id_themes'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('feedback_id', 'theme_id', name=op.f('pk_feedback_themes'))
    )
    op.create_index('ix_feedback_themes_feedback_id', 'feedback_themes', ['feedback_id'], unique=False)
    op.create_index('ix_feedback_themes_theme_id', 'feedback_themes', ['theme_id'], unique=False)

    # 4. SentimentHistory table
    op.create_table(
        'sentiment_history',
        sa.Column('sentiment_id', sa.Uuid(), nullable=False),
        sa.Column('feedback_id', sa.Uuid(), nullable=False),
        sa.Column('theme_id', sa.Uuid(), nullable=True, comment='Specific theme or aspect analyzed; null if overall document sentiment'),
        sa.Column('sentiment_label', sa.String(length=50), nullable=False, comment='Categorical sentiment label: positive, negative, neutral, mixed'),
        sa.Column('sentiment_score', sa.Float(), nullable=False, comment='Continuous sentiment score between -1.0 and +1.0'),
        sa.Column('confidence_score', sa.Float(), nullable=False, comment='Model confidence in sentiment classification (0.0 to 1.0)'),
        sa.Column('analysed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='Analysis execution timestamp in UTC'),
        sa.CheckConstraint('confidence_score >= 0.0 AND confidence_score <= 1.0', name='ck_sentiment_history_confidence'),
        sa.CheckConstraint('sentiment_score >= -1.0 AND sentiment_score <= 1.0', name='ck_sentiment_history_score'),
        sa.ForeignKeyConstraint(['feedback_id'], ['feedback.feedback_id'], name=op.f('fk_sentiment_history_feedback_id_feedback'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['theme_id'], ['themes.theme_id'], name=op.f('fk_sentiment_history_theme_id_themes'), ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('sentiment_id', name=op.f('pk_sentiment_history'))
    )
    op.create_index(op.f('ix_sentiment_history_analysed_at'), 'sentiment_history', ['analysed_at'], unique=False)
    op.create_index(op.f('ix_sentiment_history_feedback_id'), 'sentiment_history', ['feedback_id'], unique=False)
    op.create_index(op.f('ix_sentiment_history_sentiment_label'), 'sentiment_history', ['sentiment_label'], unique=False)
    op.create_index(op.f('ix_sentiment_history_theme_id'), 'sentiment_history', ['theme_id'], unique=False)
    op.create_index('ix_sentiment_feedback_analysed', 'sentiment_history', ['feedback_id', 'analysed_at'], unique=False)
    op.create_index('ix_sentiment_theme_analysed', 'sentiment_history', ['theme_id', 'analysed_at'], unique=False)

    # 5. ProductChanges table
    op.create_table(
        'product_changes',
        sa.Column('release_id', sa.Uuid(), nullable=False),
        sa.Column('product', sa.String(length=100), nullable=False, comment='Impacted product name or application'),
        sa.Column('feature', sa.String(length=100), nullable=True, comment='Specific feature or component modified'),
        sa.Column('release_description', sa.Text(), nullable=False, comment='Changelog, release notes, or summary of functional changes'),
        sa.Column('release_date', sa.DateTime(timezone=True), nullable=False, comment='Release deployment timestamp in UTC'),
        sa.Column('version', sa.String(length=50), nullable=False, comment='Release semantic version or build tag'),
        sa.Column('change_category', sa.String(length=50), nullable=False, comment='Type of release: major, minor, patch, hotfix, redesign, feature_launch'),
        sa.PrimaryKeyConstraint('release_id', name=op.f('pk_product_changes'))
    )
    op.create_index(op.f('ix_product_changes_change_category'), 'product_changes', ['change_category'], unique=False)
    op.create_index(op.f('ix_product_changes_feature'), 'product_changes', ['feature'], unique=False)
    op.create_index(op.f('ix_product_changes_product'), 'product_changes', ['product'], unique=False)
    op.create_index('ix_product_changes_product_date', 'product_changes', ['product', 'release_date'], unique=False)
    op.create_index('ix_product_changes_product_version', 'product_changes', ['product', 'version'], unique=False)
    op.create_index(op.f('ix_product_changes_release_date'), 'product_changes', ['release_date'], unique=False)
    op.create_index(op.f('ix_product_changes_version'), 'product_changes', ['version'], unique=False)

    # 6. ThemeSnapshots table
    op.create_table(
        'theme_snapshots',
        sa.Column('snapshot_id', sa.Uuid(), nullable=False),
        sa.Column('theme_id', sa.Uuid(), nullable=False),
        sa.Column('period_start', sa.DateTime(timezone=True), nullable=False, comment='Start timestamp of aggregation window (inclusive)'),
        sa.Column('period_end', sa.DateTime(timezone=True), nullable=False, comment='End timestamp of aggregation window (inclusive)'),
        sa.Column('feedback_count', sa.Integer(), nullable=False, comment='Total feedbacks received in period for theme'),
        sa.Column('positive_count', sa.Integer(), nullable=False, comment='Count of positive sentiment feedbacks'),
        sa.Column('negative_count', sa.Integer(), nullable=False, comment='Count of negative sentiment feedbacks'),
        sa.Column('neutral_count', sa.Integer(), nullable=False, comment='Count of neutral sentiment feedbacks'),
        sa.Column('sentiment_average', sa.Float(), nullable=False, comment='Mean sentiment score for the window (-1.0 to 1.0)'),
        sa.CheckConstraint('feedback_count >= 0', name='ck_theme_snapshots_feedback_count'),
        sa.CheckConstraint('negative_count >= 0', name='ck_theme_snapshots_negative_count'),
        sa.CheckConstraint('neutral_count >= 0', name='ck_theme_snapshots_neutral_count'),
        sa.CheckConstraint('positive_count >= 0', name='ck_theme_snapshots_positive_count'),
        sa.CheckConstraint('sentiment_average >= -1.0 AND sentiment_average <= 1.0', name='ck_theme_snapshots_sentiment_avg'),
        sa.ForeignKeyConstraint(['theme_id'], ['themes.theme_id'], name=op.f('fk_theme_snapshots_theme_id_themes'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('snapshot_id', name=op.f('pk_theme_snapshots'))
    )
    op.create_index(op.f('ix_theme_snapshots_period_end'), 'theme_snapshots', ['period_end'], unique=False)
    op.create_index(op.f('ix_theme_snapshots_period_start'), 'theme_snapshots', ['period_start'], unique=False)
    op.create_index(op.f('ix_theme_snapshots_theme_id'), 'theme_snapshots', ['theme_id'], unique=False)
    op.create_index('ix_theme_snapshots_theme_period', 'theme_snapshots', ['theme_id', 'period_start', 'period_end'], unique=False)

    # 7. Insights table
    op.create_table(
        'insights',
        sa.Column('insight_id', sa.Uuid(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False, comment='Short executive title of the insight'),
        sa.Column('summary', sa.Text(), nullable=False, comment='Detailed narrative analysis synthesizing multiple customer feedback points'),
        sa.Column('recommendation', sa.Text(), nullable=False, comment='Actionable product or engineering recommendation'),
        sa.Column('confidence_score', sa.Float(), nullable=False, comment='Confidence score from 0.0 to 1.0 backing this insight'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='Synthesis timestamp in UTC'),
        sa.Column('status', sa.String(length=50), server_default='active', nullable=False, comment='Lifecycle status: active, acknowledged, resolved, dismissed'),
        sa.CheckConstraint('confidence_score >= 0.0 AND confidence_score <= 1.0', name='ck_insights_confidence_score'),
        sa.PrimaryKeyConstraint('insight_id', name=op.f('pk_insights'))
    )
    op.create_index(op.f('ix_insights_created_at'), 'insights', ['created_at'], unique=False)
    op.create_index(op.f('ix_insights_status'), 'insights', ['status'], unique=False)
    op.create_index('ix_insights_status_created', 'insights', ['status', 'created_at'], unique=False)
    op.create_index(op.f('ix_insights_title'), 'insights', ['title'], unique=False)

    # 8. InsightEvidence junction table
    op.create_table(
        'insight_evidence',
        sa.Column('insight_id', sa.Uuid(), nullable=False),
        sa.Column('feedback_id', sa.Uuid(), nullable=False),
        sa.Column('evidence_type', sa.String(length=50), server_default='direct_quote', nullable=False, comment='Type of evidence: direct_quote, supporting_metric, anomaly_example, recurring_pattern'),
        sa.ForeignKeyConstraint(['feedback_id'], ['feedback.feedback_id'], name=op.f('fk_insight_evidence_feedback_id_feedback'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['insight_id'], ['insights.insight_id'], name=op.f('fk_insight_evidence_insight_id_insights'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('insight_id', 'feedback_id', name=op.f('pk_insight_evidence'))
    )
    op.create_index('ix_insight_evidence_feedback_id', 'insight_evidence', ['feedback_id'], unique=False)
    op.create_index('ix_insight_evidence_insight_id', 'insight_evidence', ['insight_id'], unique=False)

    # 9. MemoryMetadata table
    op.create_table(
        'memory_metadata',
        sa.Column('memory_id', sa.Uuid(), nullable=False),
        sa.Column('memory_type', sa.String(length=100), nullable=False, comment='Type of cognitive memory, e.g., theme_reflection, historical_shift, customer_trajectory'),
        sa.Column('source_reference', sa.String(length=255), nullable=False, comment='External Hindsight memory ID, snapshot reference, or document reference'),
        sa.Column('related_theme', sa.Uuid(), nullable=True, comment='Optional foreign key link to associated Theme'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='Initial memory creation timestamp in UTC'),
        sa.Column('last_updated', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False, comment='Timestamp of latest reflection, update, or reconciliation in UTC'),
        sa.ForeignKeyConstraint(['related_theme'], ['themes.theme_id'], name=op.f('fk_memory_metadata_related_theme_themes'), ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('memory_id', name=op.f('pk_memory_metadata'))
    )
    op.create_index(op.f('ix_memory_metadata_created_at'), 'memory_metadata', ['created_at'], unique=False)
    op.create_index(op.f('ix_memory_metadata_last_updated'), 'memory_metadata', ['last_updated'], unique=False)
    op.create_index(op.f('ix_memory_metadata_memory_type'), 'memory_metadata', ['memory_type'], unique=False)
    op.create_index('ix_memory_related_theme', 'memory_metadata', ['related_theme'], unique=False)
    op.create_index(op.f('ix_memory_metadata_source_reference'), 'memory_metadata', ['source_reference'], unique=False)
    op.create_index('ix_memory_type_created', 'memory_metadata', ['memory_type', 'created_at'], unique=False)


def downgrade() -> None:
    """Drop all tables in reverse dependency order."""
    op.drop_table('memory_metadata')
    op.drop_table('insight_evidence')
    op.drop_table('insights')
    op.drop_table('theme_snapshots')
    op.drop_table('product_changes')
    op.drop_table('sentiment_history')
    op.drop_table('feedback_themes')
    op.drop_table('themes')
    op.drop_table('feedback')
