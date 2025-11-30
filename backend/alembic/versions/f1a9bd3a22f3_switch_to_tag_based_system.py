"""switch_to_tag_based_system

Revision ID: f1a9bd3a22f3
Revises: 001
Create Date: 2025-10-13 04:51:56.182628

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1a9bd3a22f3'
down_revision: Union[str, Sequence[str], None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema to tag-based system."""
    # Create tags table
    op.create_table(
        'tags',
        sa.Column('id', sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(100), unique=True, nullable=False, index=True),
        sa.Column('category', sa.String(50), index=True),
        sa.Column('usage_count', sa.Integer, default=0),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

    # Create file_tags association table
    op.create_table(
        'file_tags',
        sa.Column('file_id', sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tag_id', sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('relevance_score', sa.Float, default=1.0),
        sa.ForeignKeyConstraint(['file_id'], ['files.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tag_id'], ['tags.id'], ondelete='CASCADE'),
    )

    # Remove embedding column from files table
    op.drop_index('ix_files_embedding', table_name='files')
    op.drop_column('files', 'embedding')

    # Add shared_tag_count column to file_relationships
    op.add_column(
        'file_relationships',
        sa.Column('shared_tag_count', sa.Integer, nullable=False, server_default='0', index=True)
    )

    # Update relationship_type default
    op.alter_column(
        'file_relationships',
        'relationship_type',
        server_default='tag_similarity'
    )

    # Add check constraint for shared_tag_count
    op.create_check_constraint(
        'ck_shared_tag_count_positive',
        'file_relationships',
        'shared_tag_count >= 0'
    )


def downgrade() -> None:
    """Downgrade schema back to embedding-based system."""
    # Drop check constraint
    op.drop_constraint('ck_shared_tag_count_positive', 'file_relationships')

    # Remove shared_tag_count column
    op.drop_column('file_relationships', 'shared_tag_count')

    # Restore relationship_type default
    op.alter_column(
        'file_relationships',
        'relationship_type',
        server_default='semantic_similarity'
    )

    # Restore embedding column to files table
    from pgvector.sqlalchemy import Vector
    op.add_column('files', sa.Column('embedding', Vector(384)))
    op.create_index(
        'ix_files_embedding',
        'files',
        ['embedding'],
        postgresql_using='ivfflat',
        postgresql_ops={'embedding': 'vector_cosine_ops'}
    )

    # Drop file_tags table
    op.drop_table('file_tags')

    # Drop tags table
    op.drop_table('tags')
