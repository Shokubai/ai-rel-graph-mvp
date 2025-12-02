"""remove_similarity_check_constraint

Revision ID: 50b9e07440c8
Revises: 914f42b1b109
Create Date: 2025-12-02 05:20:49.854916

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '50b9e07440c8'
down_revision: Union[str, Sequence[str], None] = '914f42b1b109'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Drop the CHECK constraint that causes collation issues."""
    # Drop the problematic constraint
    op.drop_constraint('check_source_lt_target', 'document_similarities', type_='check')

    # Add a UNIQUE constraint instead to prevent duplicates
    # This allows (A,B) or (B,A) but not both
    op.create_unique_constraint(
        'uq_document_similarities_pair',
        'document_similarities',
        ['source_document_id', 'target_document_id']
    )


def downgrade() -> None:
    """Restore the original CHECK constraint."""
    # Remove unique constraint
    op.drop_constraint('uq_document_similarities_pair', 'document_similarities', type_='unique')

    # Restore CHECK constraint
    op.create_check_constraint(
        'check_source_lt_target',
        'document_similarities',
        'source_document_id < target_document_id'
    )
