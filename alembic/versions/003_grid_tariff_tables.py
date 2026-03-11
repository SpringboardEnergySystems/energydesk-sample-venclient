"""Add normalized grid tariff tables (grid_companies, grid_tariff_periods, terskler, unntak)

These tables were added to models.py after migration 002 was already applied,
so they need their own migration.

Revision ID: 003
Revises: 002
Create Date: 2026-02-20 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '003'
down_revision = '002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── grid_companies ────────────────────────────────────────────────
    # One row per DSO. source_slug = YAML filename without .yml (e.g. 'elvia')
    op.create_table('grid_companies',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('source_slug', sa.String(100), nullable=False),
        sa.Column('gln', sa.String(200), nullable=True),
        sa.Column('sist_oppdatert', sa.String(20), nullable=True),
        sa.Column('kilder', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('source_slug'),
    )
    op.create_index('ix_grid_companies_name', 'grid_companies', ['name'])
    op.create_index('ix_grid_companies_source_slug', 'grid_companies', ['source_slug'])

    # ── grid_tariff_periods ───────────────────────────────────────────
    # One row per tariffer[] entry per company in the fri-nettleie YAML.
    # kundegrupper is a JSON list, e.g. ["liten_næring", "husholdning"]
    # energiledd_grunnpris_ore_kwh is in øre/kWh (divide by 100 for NOK/kWh)
    op.create_table('grid_tariff_periods',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('company_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('kundegrupper', sa.Text(), nullable=False),
        sa.Column('gyldig_fra', sa.DateTime(), nullable=False),
        sa.Column('gyldig_til', sa.DateTime(), nullable=True),
        sa.Column('fastledd_metode', sa.String(100), nullable=True),
        sa.Column('fastledd_terskel_inkludert', sa.Boolean(), nullable=True),
        sa.Column('energiledd_grunnpris_ore_kwh', sa.Float(), nullable=True),
        sa.Column('energiledd_raw', sa.Text(), nullable=True),
        sa.Column('raw_yaml', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['company_id'], ['grid_companies.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_grid_tariff_periods_company_id', 'grid_tariff_periods', ['company_id'])
    op.create_index('ix_grid_tariff_periods_gyldig_fra', 'grid_tariff_periods', ['gyldig_fra'])

    # ── grid_fastledd_terskler ────────────────────────────────────────
    # Step-function for the capacity fee.
    # terskel_kw = lower kW bound for this price step.
    # pris_nok_year = annual fee in NOK for customers whose peak falls in this step.
    op.create_table('grid_fastledd_terskler',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('period_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('terskel_kw', sa.Float(), nullable=False),
        sa.Column('pris_nok_year', sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(['period_id'], ['grid_tariff_periods.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_grid_fastledd_terskler_period_id', 'grid_fastledd_terskler', ['period_id'])

    # ── grid_energiledd_unntak ────────────────────────────────────────
    # Peak-hour energy price exceptions.
    # pris_ore_kwh overrides the grunnpris for the specified hours/days.
    op.create_table('grid_energiledd_unntak',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('period_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('navn', sa.String(100), nullable=True),
        sa.Column('timer', sa.String(20), nullable=True),
        sa.Column('dager', sa.Text(), nullable=True),
        sa.Column('pris_ore_kwh', sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(['period_id'], ['grid_tariff_periods.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_grid_energiledd_unntak_period_id', 'grid_energiledd_unntak', ['period_id'])


def downgrade() -> None:
    op.drop_index('ix_grid_energiledd_unntak_period_id', table_name='grid_energiledd_unntak')
    op.drop_table('grid_energiledd_unntak')

    op.drop_index('ix_grid_fastledd_terskler_period_id', table_name='grid_fastledd_terskler')
    op.drop_table('grid_fastledd_terskler')

    op.drop_index('ix_grid_tariff_periods_gyldig_fra', table_name='grid_tariff_periods')
    op.drop_index('ix_grid_tariff_periods_company_id', table_name='grid_tariff_periods')
    op.drop_table('grid_tariff_periods')

    op.drop_index('ix_grid_companies_source_slug', table_name='grid_companies')
    op.drop_index('ix_grid_companies_name', table_name='grid_companies')
    op.drop_table('grid_companies')

