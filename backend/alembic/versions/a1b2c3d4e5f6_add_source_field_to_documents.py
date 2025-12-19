"""Add source field to documents table

Revision ID: a1b2c3d4e5f6
Revises: 6bbd67eacddd
Create Date: 2025-12-18 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '6bbd67eacddd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add source column with default 'google_drive' for existing records
    op.add_column('documents', sa.Column('source', sa.String(length=50), nullable=False, server_default='google_drive'))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('documents', 'source')
