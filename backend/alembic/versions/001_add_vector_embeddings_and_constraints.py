"""Add vector embeddings, indexes, constraints, and error tracking

Revision ID: 001
Revises:
Create Date: 2025-10-06 10:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable pgvector extension
    op.execute('CREATE EXTENSION IF NOT EXISTS vector')

    # Create files table
    op.create_table(
        'files',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('google_drive_id', sa.String(255), unique=True, nullable=False),
        sa.Column('name', sa.String(500), nullable=False),
        sa.Column('mime_type', sa.String(100)),
        sa.Column('size_bytes', sa.BigInteger()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('modified_at', sa.DateTime(), server_default=sa.text('now()'), onupdate=sa.text('now()')),
        sa.Column('processing_status', sa.String(50), server_default='pending'),
        sa.Column('text_content', sa.Text()),
        sa.Column('embedding', Vector(384)),
    )

    # Create indexes on files table
    op.create_index('ix_files_google_drive_id', 'files', ['google_drive_id'], unique=True)
    op.create_index('ix_files_processing_status', 'files', ['processing_status'])
    op.execute(
        'CREATE INDEX ix_files_embedding ON files USING ivfflat (embedding vector_cosine_ops)'
    )

    # Create file_relationships table
    op.create_table(
        'file_relationships',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('source_file_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('target_file_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('similarity_score', sa.Float()),
        sa.Column('relationship_type', sa.String(50), server_default='semantic_similarity'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['source_file_id'], ['files.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['target_file_id'], ['files.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('source_file_id', 'target_file_id', name='uq_file_relationship_pair'),
        sa.CheckConstraint('source_file_id != target_file_id', name='ck_no_self_relationship'),
        sa.CheckConstraint('similarity_score >= 0.0 AND similarity_score <= 1.0', name='ck_similarity_score_range'),
    )

    # Create indexes on file_relationships table
    op.create_index('ix_file_relationships_source_target', 'file_relationships', ['source_file_id', 'target_file_id'])
    op.create_index('ix_file_relationships_similarity_score', 'file_relationships', ['similarity_score'])

    # Create clusters table
    op.create_table(
        'clusters',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('label', sa.String(255)),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
    )

    # Create file_clusters table
    op.create_table(
        'file_clusters',
        sa.Column('file_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('cluster_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.ForeignKeyConstraint(['file_id'], ['files.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['cluster_id'], ['clusters.id'], ondelete='CASCADE'),
    )

    # Create processing_jobs table
    op.create_table(
        'processing_jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('folder_id', sa.String(255)),
        sa.Column('status', sa.String(50), server_default='queued'),
        sa.Column('progress_percentage', sa.Integer(), server_default='0'),
        sa.Column('total_files', sa.Integer(), server_default='0'),
        sa.Column('processed_files', sa.Integer(), server_default='0'),
        sa.Column('error_message', sa.Text()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('completed_at', sa.DateTime()),
    )

    # Create index on processing_jobs table
    op.create_index('ix_processing_jobs_status', 'processing_jobs', ['status'])


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table('processing_jobs')
    op.drop_table('file_clusters')
    op.drop_table('clusters')
    op.drop_table('file_relationships')
    op.drop_table('files')

    # Drop pgvector extension
    op.execute('DROP EXTENSION IF EXISTS vector')
