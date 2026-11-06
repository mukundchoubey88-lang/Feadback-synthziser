"""add_content_and_metadata_quality_scores

Revision ID: f6b903e1a82d
Revises: e5a8f23c91d4
Create Date: 2026-11-06 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f6b903e1a82d'
down_revision: Union[str, Sequence[str], None] = 'e5a8f23c91d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add separate content quality and metadata completeness score columns to feedback table."""
    with op.batch_alter_table('feedback') as batch_op:
        batch_op.add_column(
            sa.Column(
                'content_quality_score',
                sa.Float(),
                nullable=True,
                comment='Content usefulness score from 0.0 to 100.0 without metadata penalties',
            )
        )
        batch_op.add_column(
            sa.Column(
                'metadata_completeness_score',
                sa.Float(),
                nullable=True,
                comment='Completeness of optional metadata fields from 0.0 to 100.0',
            )
        )


def downgrade() -> None:
    """Drop content quality and metadata completeness score columns from feedback table."""
    with op.batch_alter_table('feedback') as batch_op:
        batch_op.drop_column('metadata_completeness_score')
        batch_op.drop_column('content_quality_score')
