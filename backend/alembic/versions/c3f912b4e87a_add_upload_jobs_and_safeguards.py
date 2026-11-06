"""add_upload_jobs_and_safeguards

Revision ID: c3f912b4e87a
Revises: b702ef22d23b
Create Date: 2026-11-05 23:50:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3f912b4e87a'
down_revision: Union[str, Sequence[str], None] = 'b702ef22d23b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Apply Part 3 schema updates and safeguards:

    1. Safeguard A: Remove temporary server_default on themes.product.
    2. Safeguard B: Add check constraint to memory_metadata ensuring source_entity_type
       agrees with typed foreign keys.
    3. Part 3: Create upload_jobs table for tracking ingestion jobs.
    """
    # 1. Safeguard A: Remove server_default on themes.product
    with op.batch_alter_table('themes') as batch_op:
        batch_op.alter_column('product', server_default=None)

    # 2. Safeguard B: Memory provenance consistency constraint
    with op.batch_alter_table('memory_metadata') as batch_op:
        batch_op.create_check_constraint(
            'ck_memory_metadata_provenance',
            "(feedback_id IS NULL OR source_entity_type = 'feedback') AND "
            "(snapshot_id IS NULL OR source_entity_type IN ('snapshot', 'theme_snapshot')) AND "
            "(insight_id IS NULL OR source_entity_type = 'insight')"
        )

    # 3. Create upload_jobs table
    op.create_table(
        'upload_jobs',
        sa.Column('job_id', sa.Uuid(), nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('format', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('total_records', sa.Integer(), server_default='0', nullable=False),
        sa.Column('inserted_records', sa.Integer(), server_default='0', nullable=False),
        sa.Column('rejected_records', sa.Integer(), server_default='0', nullable=False),
        sa.Column('duplicate_records', sa.Integer(), server_default='0', nullable=False),
        sa.Column('error_summary', sa.Text(), nullable=True),
        sa.Column('errors', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('job_id'),
        sa.CheckConstraint(
            "status IN ('pending', 'processing', 'completed', 'completed_with_errors', 'failed')",
            name='ck_upload_jobs_status'
        ),
    )
    op.create_index(op.f('ix_upload_jobs_status'), 'upload_jobs', ['status'], unique=False)
    op.create_index(op.f('ix_upload_jobs_created_at'), 'upload_jobs', ['created_at'], unique=False)


def downgrade() -> None:
    """Reverse Part 3 schema updates and safeguards."""
    # 3. Drop upload_jobs
    op.drop_index(op.f('ix_upload_jobs_created_at'), table_name='upload_jobs')
    op.drop_index(op.f('ix_upload_jobs_status'), table_name='upload_jobs')
    op.drop_table('upload_jobs')

    # 2. Drop memory provenance constraint
    with op.batch_alter_table('memory_metadata') as batch_op:
        batch_op.drop_constraint('ck_memory_metadata_provenance', type_='check')

    # 1. Restore server_default on themes.product
    with op.batch_alter_table('themes') as batch_op:
        batch_op.alter_column('product', server_default='default_product')
