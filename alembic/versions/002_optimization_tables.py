"""Add asset groups, spot prices, optimization runs and schedules

Revision ID: 002
Revises: 001
Create Date: 2026-02-20 10:00:00.000000

NOTE: Grid tariff tables (grid_companies, grid_tariff_periods,
      grid_fastledd_terskler, grid_energiledd_unntak) live in migration 003.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── asset_groups ──────────────────────────────────────────────────
    op.create_table(
        'asset_groups',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'asset_group_members',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('group_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('resource_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['group_id'], ['asset_groups.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['resource_id'], ['flexible_resources.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_asset_group_members_group_id', 'asset_group_members', ['group_id'])
    op.create_index('ix_asset_group_members_resource_id', 'asset_group_members', ['resource_id'])

    # ── spot_prices ───────────────────────────────────────────────────
    op.create_table(
        'spot_prices',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('price_area', sa.String(20), nullable=False),
        sa.Column('period_start', sa.DateTime(), nullable=False),
        sa.Column('period_end', sa.DateTime(), nullable=False),
        sa.Column('price_nok_mwh', sa.Float(), nullable=False),
        sa.Column('price_eur_mwh', sa.Float(), nullable=True),
        sa.Column('currency', sa.String(10), nullable=True),
        sa.Column('resolution_minutes', sa.Float(), nullable=True),
        sa.Column('source', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_spot_prices_price_area', 'spot_prices', ['price_area'])
    op.create_index('ix_spot_prices_period_start', 'spot_prices', ['period_start'])
    op.create_index('uq_spot_prices_area_start', 'spot_prices',
                    ['price_area', 'period_start'], unique=True)

    # ── optimization_runs ─────────────────────────────────────────────
    op.create_table(
        'optimization_runs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('asset_group_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('resource_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('run_type', sa.String(50), nullable=False),
        sa.Column('price_area', sa.String(20), nullable=True),
        sa.Column('grid_company', sa.String(200), nullable=True),
        sa.Column('period_start', sa.DateTime(), nullable=False),
        sa.Column('period_end', sa.DateTime(), nullable=False),
        sa.Column('battery_capacity_kwh', sa.Float(), nullable=True),
        sa.Column('battery_max_charge_kw', sa.Float(), nullable=True),
        sa.Column('battery_max_discharge_kw', sa.Float(), nullable=True),
        sa.Column('battery_efficiency', sa.Float(), nullable=True),
        sa.Column('initial_soc', sa.Float(), nullable=True),
        sa.Column('status', sa.String(50), nullable=True),
        sa.Column('objective_value', sa.Float(), nullable=True),
        sa.Column('total_cycles', sa.Float(), nullable=True),
        sa.Column('solver_used', sa.String(50), nullable=True),
        sa.Column('solve_time_s', sa.Float(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('result_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['asset_group_id'], ['asset_groups.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['resource_id'], ['flexible_resources.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_optimization_runs_asset_group_id', 'optimization_runs', ['asset_group_id'])
    op.create_index('ix_optimization_runs_resource_id', 'optimization_runs', ['resource_id'])

    # ── optimization_schedules ────────────────────────────────────────
    op.create_table(
        'optimization_schedules',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('run_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('period_start', sa.DateTime(), nullable=False),
        sa.Column('period_end', sa.DateTime(), nullable=False),
        sa.Column('charge_kw', sa.Float(), nullable=True),
        sa.Column('discharge_kw', sa.Float(), nullable=True),
        sa.Column('net_power_kw', sa.Float(), nullable=True),
        sa.Column('soc_kwh', sa.Float(), nullable=True),
        sa.Column('spot_price_nok_mwh', sa.Float(), nullable=True),
        sa.Column('grid_tariff_nok_kwh', sa.Float(), nullable=True),
        sa.Column('total_cost_nok', sa.Float(), nullable=True),
        sa.Column('total_revenue_nok', sa.Float(), nullable=True),
        sa.Column('net_earnings_nok', sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(['run_id'], ['optimization_runs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_optimization_schedules_run_id', 'optimization_schedules', ['run_id'])
    op.create_index('ix_optimization_schedules_period_start', 'optimization_schedules', ['period_start'])


def downgrade() -> None:
    # NOTE: downgrade 003 first before downgrading 002
    op.drop_index('ix_optimization_schedules_period_start', table_name='optimization_schedules')
    op.drop_index('ix_optimization_schedules_run_id', table_name='optimization_schedules')
    op.drop_table('optimization_schedules')

    op.drop_index('ix_optimization_runs_resource_id', table_name='optimization_runs')
    op.drop_index('ix_optimization_runs_asset_group_id', table_name='optimization_runs')
    op.drop_table('optimization_runs')

    op.drop_index('uq_spot_prices_area_start', table_name='spot_prices')
    op.drop_index('ix_spot_prices_period_start', table_name='spot_prices')
    op.drop_index('ix_spot_prices_price_area', table_name='spot_prices')
    op.drop_table('spot_prices')

    op.drop_index('ix_asset_group_members_resource_id', table_name='asset_group_members')
    op.drop_index('ix_asset_group_members_group_id', table_name='asset_group_members')
    op.drop_table('asset_group_members')
    op.drop_table('asset_groups')

