"""ml_based_tags_with_embeddings

Revision ID: 002
Revises: f1a9bd3a22f3
Create Date: 2025-10-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, REAL


# revision identifiers, used by Alembic.
revision: str = '002'
down_revision: Union[str, Sequence[str], None] = 'f1a9bd3a22f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema for ML-based tag extraction with embeddings."""
    # Increase tag name length to support multi-word phrases
    op.alter_column(
        'tags',
        'name',
        type_=sa.String(255),
        existing_type=sa.String(100),
        existing_nullable=False,
    )

    # Make category nullable (will be auto-discovered from clusters)
    op.alter_column(
        'tags',
        'category',
        nullable=True,
        existing_type=sa.String(50),
    )

    # Add embedding column to store semantic vectors
    op.add_column(
        'tags',
        sa.Column('embedding', ARRAY(REAL), nullable=True)
    )


def downgrade() -> None:
    """Downgrade schema back to frequency-based tags."""
    # Remove embedding column
    op.drop_column('tags', 'embedding')

    # Restore category to non-nullable
    op.alter_column(
        'tags',
        'category',
        nullable=False,
        existing_type=sa.String(50),
    )

    # Restore tag name length
    op.alter_column(
        'tags',
        'name',
        type_=sa.String(100),
        existing_type=sa.String(255),
        existing_nullable=False,
    )
