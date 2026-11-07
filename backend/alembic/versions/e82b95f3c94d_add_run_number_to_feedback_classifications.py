"""add_run_number_to_feedback_classifications

Revision ID: e82b95f3c94d
Revises: d71a94e2b83c
Create Date: 2026-11-06 17:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e82b95f3c94d'
down_revision: Union[str, Sequence[str], None] = 'd71a94e2b83c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add run_number to feedback_classifications and update unique constraint to support execution history."""
    with op.batch_alter_table('feedback_classifications') as batch_op:
        batch_op.add_column(
            sa.Column(
                'run_number',
                sa.Integer(),
                nullable=False,
                server_default='1',
                comment='Sequential execution run index per feedback item and algorithm version',
            )
        )
        batch_op.drop_constraint(
            'uq_feedback_classifications_feedback_version',
            type_='unique',
        )
        batch_op.create_unique_constraint(
            'uq_feedback_classifications_feedback_version_run',
            ['feedback_id', 'classification_version', 'run_number'],
        )


def downgrade() -> None:
    """Revert unique constraint and remove run_number from feedback_classifications.

    Safety Check:
    Inspects existing feedback_classifications for duplicate (feedback_id, classification_version)
    groups before altering constraints. If multiple historical runs exist, aborts with a clear,
    actionable RuntimeError to prevent automatic deletion or violation of uniqueness.
    """
    bind = op.get_bind()
    if bind is not None:
        dup_query = sa.text("""
            SELECT feedback_id, classification_version, COUNT(*) AS run_count
            FROM feedback_classifications
            GROUP BY feedback_id, classification_version
            HAVING COUNT(*) > 1
        """)
        duplicates = bind.execute(dup_query).fetchall()
        if duplicates:
            sample_info = ", ".join(
                f"(feedback_id={row[0]}, version='{row[1]}', runs={row[2]})"
                for row in duplicates[:3]
            )
            raise RuntimeError(
                f"Downgrade aborted for migration 'e82b95f3c94d': Found {len(duplicates)} "
                f"(feedback_id, classification_version) group(s) with multiple historical execution runs "
                f"(e.g. {sample_info}). "
                f"Restoring unique constraint 'uq_feedback_classifications_feedback_version' would "
                f"fail or require deleting/overwriting historical execution data. "
                f"In accordance with strict historical data preservation policies, classification records "
                f"are never automatically deleted or overwritten. Please manually resolve or archive "
                f"duplicate execution runs before attempting to downgrade."
            )

    with op.batch_alter_table('feedback_classifications') as batch_op:
        batch_op.drop_constraint(
            'uq_feedback_classifications_feedback_version_run',
            type_='unique',
        )
        batch_op.create_unique_constraint(
            'uq_feedback_classifications_feedback_version',
            ['feedback_id', 'classification_version'],
        )
        batch_op.drop_column('run_number')
