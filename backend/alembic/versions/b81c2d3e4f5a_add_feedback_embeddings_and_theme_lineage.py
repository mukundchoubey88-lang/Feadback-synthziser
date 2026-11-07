"""add_feedback_embeddings_and_theme_lineage

Revision ID: b81c2d3e4f5a
Revises: e82b95f3c94d
Create Date: 2026-11-06 23:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

try:
    from pgvector.sqlalchemy import Vector
except ImportError:
    Vector = None


# revision identifiers, used by Alembic.
revision: str = 'b81c2d3e4f5a'
down_revision: Union[str, Sequence[str], None] = 'e82b95f3c94d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create feedback_embeddings table and add theme centroid and lineage tracking."""
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    # 1. Conditionally enable pgvector extension on PostgreSQL
    if is_postgres:
        op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    # 2. Select appropriate vector column type (pgvector on PG, JSON on SQLite)
    if is_postgres and Vector is not None:
        vector_type = Vector(768)
    else:
        vector_type = sa.JSON()

    # 3. Create feedback_embeddings table
    op.create_table(
        'feedback_embeddings',
        sa.Column('embedding_id', sa.Uuid(as_uuid=True), primary_key=True),
        sa.Column(
            'feedback_id',
            sa.Uuid(as_uuid=True),
            sa.ForeignKey('feedback.feedback_id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('embedding_model', sa.String(length=64), nullable=False, comment='Embedding model handle'),
        sa.Column('embedding_dimensions', sa.Integer(), nullable=False, comment='Vector dimension count'),
        sa.Column('embedding_vector', vector_type, nullable=False, comment='Vector embedding data'),
        sa.Column('input_hash', sa.String(length=64), nullable=False, comment='Hash for idempotent caching'),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('CURRENT_TIMESTAMP'),
            nullable=False,
            comment='Generation timestamp in UTC',
        ),
        sa.UniqueConstraint('feedback_id', 'embedding_model', name='uq_feedback_embeddings_feedback_model'),
    )
    op.create_index('ix_feedback_embeddings_feedback_id', 'feedback_embeddings', ['feedback_id'], unique=False)
    op.create_index('ix_feedback_embeddings_input_hash', 'feedback_embeddings', ['input_hash'], unique=False)
    op.create_index('ix_feedback_embeddings_model', 'feedback_embeddings', ['embedding_model'], unique=False)

    # 4. Optional HNSW cosine similarity index on PostgreSQL
    if is_postgres:
        op.execute(
            "CREATE INDEX IF NOT EXISTS ix_feedback_embeddings_vector_hnsw "
            "ON feedback_embeddings USING hnsw (embedding_vector vector_cosine_ops);"
        )

    # 5. Extend themes table with centroid vector and lineage tracking
    with op.batch_alter_table('themes') as batch_op:
        batch_op.add_column(
            sa.Column(
                'centroid_vector',
                vector_type,
                nullable=True,
                comment='Normalized centroid embedding vector of member feedbacks',
            )
        )
        batch_op.add_column(
            sa.Column(
                'merged_into_id',
                sa.Uuid(as_uuid=True),
                sa.ForeignKey('themes.theme_id', ondelete='SET NULL', name='fk_themes_merged_into_id'),
                nullable=True,
                comment='Target theme if this theme was merged into another',
            )
        )
        batch_op.add_column(
            sa.Column(
                'split_from_id',
                sa.Uuid(as_uuid=True),
                sa.ForeignKey('themes.theme_id', ondelete='SET NULL', name='fk_themes_split_from_id'),
                nullable=True,
                comment='Parent theme if this theme was split from another',
            )
        )
        batch_op.add_column(
            sa.Column(
                'lineage_metadata',
                sa.JSON(),
                nullable=True,
                comment='Audit trail and lineage history for merges, splits, and reactivations',
            )
        )
        batch_op.create_index('ix_themes_merged_into_id', ['merged_into_id'], unique=False)
        batch_op.create_index('ix_themes_split_from_id', ['split_from_id'], unique=False)


def downgrade() -> None:
    """Revert theme extensions and feedback_embeddings table."""
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    # 1. Revert themes table modifications
    with op.batch_alter_table('themes') as batch_op:
        batch_op.drop_index('ix_themes_split_from_id')
        batch_op.drop_index('ix_themes_merged_into_id')
        batch_op.drop_column('lineage_metadata')
        batch_op.drop_column('split_from_id')
        batch_op.drop_column('merged_into_id')
        batch_op.drop_column('centroid_vector')

    # 2. Drop PostgreSQL HNSW index if present
    if is_postgres:
        op.execute("DROP INDEX IF EXISTS ix_feedback_embeddings_vector_hnsw;")

    # 3. Drop feedback_embeddings table
    op.drop_index('ix_feedback_embeddings_model', table_name='feedback_embeddings')
    op.drop_index('ix_feedback_embeddings_input_hash', table_name='feedback_embeddings')
    op.drop_index('ix_feedback_embeddings_feedback_id', table_name='feedback_embeddings')
    op.drop_table('feedback_embeddings')
