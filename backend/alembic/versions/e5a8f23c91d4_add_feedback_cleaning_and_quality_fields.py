"""add_feedback_cleaning_and_quality_fields

Revision ID: e5a8f23c91d4
Revises: c3f912b4e87a
Create Date: 2026-11-06 08:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5a8f23c91d4'
down_revision: Union[str, Sequence[str], None] = 'c3f912b4e87a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Apply Part 4 schema updates: add data cleaning, PII tracking, and quality scoring fields."""
    with op.batch_alter_table('feedback') as batch_op:
        batch_op.add_column(
            sa.Column('cleaned_feedback_text', sa.Text(), nullable=True, comment='Normalized and PII-redacted feedback copy')
        )
        batch_op.add_column(
            sa.Column('quality_status', sa.String(length=50), nullable=False, server_default='pending', comment='Quality classification: pending, clean, flagged, rejected, failed')
        )
        batch_op.add_column(
            sa.Column('quality_score', sa.Float(), nullable=True, comment='Deterministic quality score from 0.0 to 100.0')
        )
        batch_op.add_column(
            sa.Column('quality_flags', sa.JSON(), nullable=True, comment='List of diagnostic quality and anomaly flags')
        )
        batch_op.add_column(
            sa.Column('pii_detected', sa.Boolean(), nullable=False, server_default=sa.false(), comment='Flag indicating presence of sensitive PII in original text')
        )
        batch_op.add_column(
            sa.Column('pii_types', sa.JSON(), nullable=True, comment='Categories of PII discovered (e.g., email, phone, url)')
        )
        batch_op.add_column(
            sa.Column('cleaning_version', sa.String(length=50), nullable=True, comment='Algorithm version used for cleaning and redaction')
        )
        batch_op.add_column(
            sa.Column('cleaned_at', sa.DateTime(timezone=True), nullable=True, comment='Timestamp when cleaning pipeline executed in UTC')
        )
        batch_op.add_column(
            sa.Column('processing_status', sa.String(length=50), nullable=False, server_default='unprocessed', comment='Pipeline execution state: unprocessed, processing, processed, failed')
        )
        batch_op.add_column(
            sa.Column('processing_error', sa.Text(), nullable=True, comment='Error details if cleaning pipeline failed')
        )
        batch_op.create_index('ix_feedback_quality_status', ['quality_status'], unique=False)
        batch_op.create_index('ix_feedback_processing_status', ['processing_status'], unique=False)
        batch_op.create_check_constraint(
            'ck_feedback_quality_status',
            "quality_status IN ('pending', 'clean', 'flagged', 'rejected', 'failed')"
        )
        batch_op.create_check_constraint(
            'ck_feedback_processing_status',
            "processing_status IN ('unprocessed', 'processing', 'processed', 'failed')"
        )


def downgrade() -> None:
    """Reverse Part 4 schema updates."""
    with op.batch_alter_table('feedback') as batch_op:
        batch_op.drop_constraint('ck_feedback_processing_status', type_='check')
        batch_op.drop_constraint('ck_feedback_quality_status', type_='check')
        batch_op.drop_index('ix_feedback_processing_status')
        batch_op.drop_index('ix_feedback_quality_status')
        batch_op.drop_column('processing_error')
        batch_op.drop_column('processing_status')
        batch_op.drop_column('cleaned_at')
        batch_op.drop_column('cleaning_version')
        batch_op.drop_column('pii_types')
        batch_op.drop_column('pii_detected')
        batch_op.drop_column('quality_flags')
        batch_op.drop_column('quality_score')
        batch_op.drop_column('quality_status')
        batch_op.drop_column('cleaned_feedback_text')
