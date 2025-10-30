"""Initial tables

Revision ID: 001
Revises: 
Create Date: 2025-10-29 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create file_uploads table
    op.create_table(
        'file_uploads',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('uploaded_at', sa.DateTime(), nullable=False),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('total_rows', sa.Integer(), nullable=True),
        sa.Column('valid_rows', sa.Integer(), nullable=True),
        sa.Column('invalid_rows', sa.Integer(), nullable=True),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('webhook_url', sa.String(length=500), nullable=True),
        sa.Column('errors', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_file_uploads_status'), 'file_uploads', ['status'])
    op.create_index(op.f('ix_file_uploads_uploaded_at'), 'file_uploads', ['uploaded_at'])

    # Create users table
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('phone', sa.String(length=20), nullable=False),
        sa.Column('age', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('upload_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'])
    op.create_index(op.f('ix_users_upload_id'), 'users', ['upload_id'])

    # Create processing_metrics table
    op.create_table(
        'processing_metrics',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('job_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('metric_name', sa.String(length=100), nullable=False),
        sa.Column('metric_value', sa.Float(), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_processing_metrics_job_id'), 'processing_metrics', ['job_id'])
    op.create_index(op.f('ix_processing_metrics_timestamp'), 'processing_metrics', ['timestamp'])


def downgrade() -> None:
    op.drop_index(op.f('ix_processing_metrics_timestamp'), table_name='processing_metrics')
    op.drop_index(op.f('ix_processing_metrics_job_id'), table_name='processing_metrics')
    op.drop_table('processing_metrics')
    
    op.drop_index(op.f('ix_users_upload_id'), table_name='users')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')
    
    op.drop_index(op.f('ix_file_uploads_uploaded_at'), table_name='file_uploads')
    op.drop_index(op.f('ix_file_uploads_status'), table_name='file_uploads')
    op.drop_table('file_uploads')