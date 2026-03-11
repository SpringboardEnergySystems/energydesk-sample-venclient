"""Add heartbeat tracking columns to flexible_resources

Revision ID: 004_heartbeat_tracking
Revises: 003_grid_tariff_tables
Create Date: 2026-03-05

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '004'
down_revision = '003'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('flexible_resources',
        sa.Column('last_heartbeat_at', sa.DateTime(), nullable=True))
    op.add_column('flexible_resources',
        sa.Column('last_heartbeat_worker', sa.String(100), nullable=True))


def downgrade():
    op.drop_column('flexible_resources', 'last_heartbeat_worker')
    op.drop_column('flexible_resources', 'last_heartbeat_at')

