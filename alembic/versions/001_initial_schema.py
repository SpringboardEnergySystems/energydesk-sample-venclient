"""initial schema with users resources and events

Revision ID: 001
Revises:
Create Date: 2026-02-18 14:00:00.000000

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
    # Create users table
    op.create_table('users',
    sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.Column('first_name', sa.String(length=100), nullable=True),
    sa.Column('last_name', sa.String(length=100), nullable=True),
    sa.Column('role', sa.Enum('ADMIN', 'USER', 'DATA_PROVIDER', name='userrole'), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('is_admin', sa.Boolean(), nullable=False),
    sa.Column('oauth_provider', sa.String(length=50), nullable=True),
    sa.Column('oauth_sub', sa.String(length=255), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('last_login', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)

    # Create meter_connections table
    op.create_table('meter_connections',
    sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('owner_id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('meterpoint_id', sa.String(length=100), nullable=False),
    sa.Column('description', sa.String(length=500), nullable=True),
    sa.Column('location_latitude', sa.Float(), nullable=True),
    sa.Column('location_longitude', sa.Float(), nullable=True),
    sa.Column('address1', sa.String(length=200), nullable=True),
    sa.Column('address2', sa.String(length=200), nullable=True),
    sa.Column('city', sa.String(length=100), nullable=True),
    sa.Column('postal_code', sa.String(length=20), nullable=True),
    sa.Column('country', sa.String(length=2), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_meter_connections_meterpoint_id'), 'meter_connections', ['meterpoint_id'], unique=True)

    # Create flexible_resources table
    op.create_table('flexible_resources',
    sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('meter_connection_id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('resource_external_id', sa.String(length=100), nullable=False),
    sa.Column('description', sa.String(length=500), nullable=True),
    sa.Column('resource_type', sa.Enum('BATTERY', 'EV_CHARGER', 'HEAT_PUMP', 'HVAC', 'SOLAR', 'WIND', 'LOAD', 'GENERATOR', 'OTHER', name='resourcetype'), nullable=False),
    sa.Column('vtn_registration_status', sa.Enum('NOT_REGISTERED', 'PENDING', 'REGISTERED', 'FAILED', 'DEREGISTERED', name='vtnregistrationstatus'), nullable=False),
    sa.Column('vtn_resource_id', sa.String(length=255), nullable=True),
    sa.Column('vtn_program_id', sa.String(length=255), nullable=True),
    sa.Column('vtn_last_sync', sa.DateTime(), nullable=True),
    sa.Column('rated_power_kw', sa.Float(), nullable=True),
    sa.Column('energy_capacity_kwh', sa.Float(), nullable=True),
    sa.Column('min_power_kw', sa.Float(), nullable=True),
    sa.Column('max_power_kw', sa.Float(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['meter_connection_id'], ['meter_connections.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_flexible_resources_resource_external_id'), 'flexible_resources', ['resource_external_id'], unique=True)

    # Create resource_status table
    op.create_table('resource_status',
    sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('resource_id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('status_timestamp', sa.DateTime(), nullable=False),
    sa.Column('status_code', sa.Enum('ONLINE', 'OFFLINE', 'ERROR', 'MAINTENANCE', 'UNKNOWN', name='resourcestatuscode'), nullable=False),
    sa.Column('message', sa.Text(), nullable=True),
    sa.Column('error_details', sa.Text(), nullable=True),
    sa.Column('power_kw', sa.Float(), nullable=True),
    sa.Column('soc_percent', sa.Float(), nullable=True),
    sa.Column('temperature_c', sa.Float(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['resource_id'], ['flexible_resources.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_resource_status_resource_id'), 'resource_status', ['resource_id'], unique=False)
    op.create_index(op.f('ix_resource_status_status_timestamp'), 'resource_status', ['status_timestamp'], unique=False)

    # Create vtn_events table
    op.create_table('vtn_events',
    sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('resource_id', postgresql.UUID(as_uuid=True), nullable=False),
    sa.Column('vtn_event_id', sa.String(length=255), nullable=False),
    sa.Column('event_type', sa.String(length=100), nullable=True),
    sa.Column('event_start', sa.DateTime(), nullable=False),
    sa.Column('event_end', sa.DateTime(), nullable=False),
    sa.Column('notification_time', sa.DateTime(), nullable=False),
    sa.Column('signal_name', sa.String(length=100), nullable=True),
    sa.Column('signal_type', sa.String(length=100), nullable=True),
    sa.Column('target_value', sa.Float(), nullable=True),
    sa.Column('current_value', sa.Float(), nullable=True),
    sa.Column('opt_status', sa.String(length=50), nullable=True),
    sa.Column('execution_status', sa.String(length=50), nullable=True),
    sa.Column('response_sent', sa.Boolean(), nullable=True),
    sa.Column('response_time', sa.DateTime(), nullable=True),
    sa.Column('execution_started', sa.DateTime(), nullable=True),
    sa.Column('execution_completed', sa.DateTime(), nullable=True),
    sa.Column('raw_event_data', sa.Text(), nullable=True),
    sa.Column('notes', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['resource_id'], ['flexible_resources.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_vtn_events_resource_id'), 'vtn_events', ['resource_id'], unique=False)
    op.create_index(op.f('ix_vtn_events_vtn_event_id'), 'vtn_events', ['vtn_event_id'], unique=True)


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_index(op.f('ix_vtn_events_vtn_event_id'), table_name='vtn_events')
    op.drop_index(op.f('ix_vtn_events_resource_id'), table_name='vtn_events')
    op.drop_table('vtn_events')

    op.drop_index(op.f('ix_resource_status_status_timestamp'), table_name='resource_status')
    op.drop_index(op.f('ix_resource_status_resource_id'), table_name='resource_status')
    op.drop_table('resource_status')

    op.drop_index(op.f('ix_flexible_resources_resource_external_id'), table_name='flexible_resources')
    op.drop_table('flexible_resources')

    op.drop_index(op.f('ix_meter_connections_meterpoint_id'), table_name='meter_connections')
    op.drop_table('meter_connections')

    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')

    # Drop enums
    sa.Enum(name='resourcestatuscode').drop(op.get_bind())
    sa.Enum(name='vtnregistrationstatus').drop(op.get_bind())
    sa.Enum(name='resourcetype').drop(op.get_bind())
    sa.Enum(name='userrole').drop(op.get_bind())
