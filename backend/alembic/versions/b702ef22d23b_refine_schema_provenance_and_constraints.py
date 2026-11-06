"""refine_schema_provenance_and_constraints

Revision ID: b702ef22d23b
Revises: ae66156cfb1a
Create Date: 2026-11-05 22:48:35.194256

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b702ef22d23b'
down_revision: Union[str, Sequence[str], None] = 'ae66156cfb1a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Apply schema refinements:

    1. Feedback: soft deletion timestamp (deleted_at).
    2. Themes: product-scoping with composite unique constraint (product, theme_name).
    3. InsightEvidence: restrictive foreign key on feedback deletion.
    4. ThemeSnapshots: period order and count consistency check constraints.
    5. MemoryMetadata: Hindsight bank_id, external memory_id, and typed foreign keys to source entities.
    """
    # 1. Feedback: Add deleted_at for soft deletion
    op.add_column(
        'feedback',
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True, comment='Soft deletion timestamp in UTC; null if active')
    )
    op.create_index(op.f('ix_feedback_deleted_at'), 'feedback', ['deleted_at'], unique=False)

    # 2. Themes: Product-scoped themes
    op.add_column(
        'themes',
        sa.Column('product', sa.String(length=100), server_default='default_product', nullable=False, comment='Product line or application owning this theme')
    )
    op.drop_constraint('uq_themes_theme_name', 'themes', type_='unique')
    op.create_unique_constraint('uq_themes_product_theme_name', 'themes', ['product', 'theme_name'])
    op.create_index(op.f('ix_themes_product'), 'themes', ['product'], unique=False)
    op.create_index('ix_themes_product_category', 'themes', ['product', 'category'], unique=False)
    op.create_index('ix_themes_product_status', 'themes', ['product', 'status'], unique=False)

    # 3. InsightEvidence: Change ON DELETE CASCADE to RESTRICT to protect evidence
    op.drop_constraint(op.f('fk_insight_evidence_feedback_id_feedback'), 'insight_evidence', type_='foreignkey')
    op.create_foreign_key(
        op.f('fk_insight_evidence_feedback_id_feedback'),
        'insight_evidence',
        'feedback',
        ['feedback_id'],
        ['feedback_id'],
        ondelete='RESTRICT'
    )

    # 4. ThemeSnapshots: Add period ordering and count consistency constraints
    op.create_check_constraint(
        'ck_theme_snapshots_period_order',
        'theme_snapshots',
        'period_start <= period_end'
    )
    op.create_check_constraint(
        'ck_theme_snapshots_count_consistency',
        'theme_snapshots',
        'positive_count + negative_count + neutral_count <= feedback_count'
    )

    # 5. MemoryMetadata: Provenance refinement with bank_id and typed source references
    op.add_column(
        'memory_metadata',
        sa.Column('bank_id', sa.String(length=128), server_default='default', nullable=False, comment='Hindsight memory bank identifier')
    )
    op.create_index('ix_memory_metadata_bank_id', 'memory_metadata', ['bank_id'], unique=False)

    op.add_column(
        'memory_metadata',
        sa.Column('hindsight_memory_id', sa.String(length=255), nullable=True, comment='External identifier returned by Hindsight platform upon memory retention')
    )
    op.create_index('ix_memory_metadata_hindsight_id', 'memory_metadata', ['hindsight_memory_id'], unique=False)

    op.add_column(
        'memory_metadata',
        sa.Column('source_entity_type', sa.String(length=50), server_default='feedback', nullable=False, comment='Categorical source entity type')
    )
    op.create_index('ix_memory_source_entity', 'memory_metadata', ['source_entity_type', 'created_at'], unique=False)

    op.add_column(
        'memory_metadata',
        sa.Column('feedback_id', sa.Uuid(), nullable=True, comment='Direct link to source Feedback record')
    )
    op.create_foreign_key(
        op.f('fk_memory_metadata_feedback_id_feedback'),
        'memory_metadata',
        'feedback',
        ['feedback_id'],
        ['feedback_id'],
        ondelete='SET NULL'
    )
    op.create_index('ix_memory_feedback_id', 'memory_metadata', ['feedback_id'], unique=False)

    op.add_column(
        'memory_metadata',
        sa.Column('snapshot_id', sa.Uuid(), nullable=True, comment='Direct link to source ThemeSnapshot record')
    )
    op.create_foreign_key(
        op.f('fk_memory_metadata_snapshot_id_theme_snapshots'),
        'memory_metadata',
        'theme_snapshots',
        ['snapshot_id'],
        ['snapshot_id'],
        ondelete='SET NULL'
    )
    op.create_index('ix_memory_snapshot_id', 'memory_metadata', ['snapshot_id'], unique=False)

    op.add_column(
        'memory_metadata',
        sa.Column('insight_id', sa.Uuid(), nullable=True, comment='Direct link to source Insight record')
    )
    op.create_foreign_key(
        op.f('fk_memory_metadata_insight_id_insights'),
        'memory_metadata',
        'insights',
        ['insight_id'],
        ['insight_id'],
        ondelete='SET NULL'
    )
    op.create_index('ix_memory_insight_id', 'memory_metadata', ['insight_id'], unique=False)

    op.alter_column(
        'memory_metadata',
        'source_reference',
        existing_type=sa.String(length=255),
        nullable=True
    )


def downgrade() -> None:
    """Reverse schema refinements."""
    # 5. MemoryMetadata
    op.alter_column(
        'memory_metadata',
        'source_reference',
        existing_type=sa.String(length=255),
        nullable=False
    )
    op.drop_index('ix_memory_insight_id', table_name='memory_metadata')
    op.drop_constraint(op.f('fk_memory_metadata_insight_id_insights'), 'memory_metadata', type_='foreignkey')
    op.drop_column('memory_metadata', 'insight_id')

    op.drop_index('ix_memory_snapshot_id', table_name='memory_metadata')
    op.drop_constraint(op.f('fk_memory_metadata_snapshot_id_theme_snapshots'), 'memory_metadata', type_='foreignkey')
    op.drop_column('memory_metadata', 'snapshot_id')

    op.drop_index('ix_memory_feedback_id', table_name='memory_metadata')
    op.drop_constraint(op.f('fk_memory_metadata_feedback_id_feedback'), 'memory_metadata', type_='foreignkey')
    op.drop_column('memory_metadata', 'feedback_id')

    op.drop_index('ix_memory_source_entity', table_name='memory_metadata')
    op.drop_column('memory_metadata', 'source_entity_type')

    op.drop_index('ix_memory_metadata_hindsight_id', table_name='memory_metadata')
    op.drop_column('memory_metadata', 'hindsight_memory_id')

    op.drop_index('ix_memory_metadata_bank_id', table_name='memory_metadata')
    op.drop_column('memory_metadata', 'bank_id')

    # 4. ThemeSnapshots
    op.drop_constraint('ck_theme_snapshots_count_consistency', 'theme_snapshots', type_='check')
    op.drop_constraint('ck_theme_snapshots_period_order', 'theme_snapshots', type_='check')

    # 3. InsightEvidence
    op.drop_constraint(op.f('fk_insight_evidence_feedback_id_feedback'), 'insight_evidence', type_='foreignkey')
    op.create_foreign_key(
        op.f('fk_insight_evidence_feedback_id_feedback'),
        'insight_evidence',
        'feedback',
        ['feedback_id'],
        ['feedback_id'],
        ondelete='CASCADE'
    )

    # 2. Themes
    op.drop_index('ix_themes_product_status', table_name='themes')
    op.drop_index('ix_themes_product_category', table_name='themes')
    op.drop_index(op.f('ix_themes_product'), table_name='themes')
    op.drop_constraint('uq_themes_product_theme_name', 'themes', type_='unique')
    op.create_unique_constraint('uq_themes_theme_name', 'themes', ['theme_name'])
    op.drop_column('themes', 'product')

    # 1. Feedback
    op.drop_index(op.f('ix_feedback_deleted_at'), table_name='feedback')
    op.drop_column('feedback', 'deleted_at')
