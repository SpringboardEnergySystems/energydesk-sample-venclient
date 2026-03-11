"""Add vtn_programs and vtn_program_enrollments tables

Revision ID: 005_vtn_programs
Revises: 004
Create Date: 2026-03-10

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '005'
down_revision = '004'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'vtn_programs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('vtn_id', sa.String(255), nullable=False, unique=True),
        sa.Column('program_id', sa.String(255), nullable=True),
        sa.Column('program_name', sa.String(500), nullable=False),
        sa.Column('program_long_name', sa.String(500), nullable=True),
        sa.Column('program_type', sa.String(100), nullable=True),
        sa.Column('program_priority', sa.Float(), nullable=True, default=0),
        sa.Column('state', sa.String(50), nullable=True, default='PENDING'),
        sa.Column('program_issuer', sa.String(255), nullable=True),
        sa.Column('retailer_name', sa.String(255), nullable=True),
        sa.Column('retailer_long_name', sa.String(500), nullable=True),
        sa.Column('effective_start_date', sa.DateTime(), nullable=True),
        sa.Column('effective_end_date', sa.DateTime(), nullable=True),
        sa.Column('program_period_start', sa.DateTime(), nullable=True),
        sa.Column('program_period_end', sa.DateTime(), nullable=True),
        sa.Column('enrollment_period_start', sa.DateTime(), nullable=True),
        sa.Column('enrollment_period_end', sa.DateTime(), nullable=True),
        sa.Column('created_date', sa.DateTime(), nullable=True),
        sa.Column('modification_date_time', sa.DateTime(), nullable=True),
        sa.Column('country', sa.String(10), nullable=True),
        sa.Column('principal_subdivision', sa.String(100), nullable=True),
        sa.Column('timezone', sa.String(100), nullable=True, default='UTC'),
        sa.Column('market_context', sa.String(255), nullable=True),
        sa.Column('participation_type', sa.String(100), nullable=True),
        sa.Column('notification_time', sa.String(100), nullable=True),
        sa.Column('call_heads_up_time', sa.String(100), nullable=True),
        sa.Column('interval_period', sa.String(50), nullable=True, default='PT1H'),
        sa.Column('interval_period_duration', sa.String(50), nullable=True),
        sa.Column('interruptible', sa.Boolean(), nullable=True, default=False),
        sa.Column('raw_json', sa.Text(), nullable=True),
        sa.Column('last_synced_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_vtn_programs_vtn_id', 'vtn_programs', ['vtn_id'])
    op.create_index('ix_vtn_programs_program_id', 'vtn_programs', ['program_id'])

    op.create_table(
        'vtn_program_enrollments',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('program_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('vtn_programs.id'), nullable=False),
        sa.Column('resource_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('flexible_resources.id'), nullable=False),
        sa.Column('status', sa.String(50), nullable=False, default='not_enrolled'),
        sa.Column('requested_at', sa.DateTime(), nullable=True),
        sa.Column('enrolled_at', sa.DateTime(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_vtn_program_enrollments_program_id', 'vtn_program_enrollments', ['program_id'])
    op.create_index('ix_vtn_program_enrollments_resource_id', 'vtn_program_enrollments', ['resource_id'])


def downgrade():
    op.drop_table('vtn_program_enrollments')
    op.drop_table('vtn_programs')

