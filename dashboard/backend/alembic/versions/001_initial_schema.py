"""Initial schema: create all tables with indexes and foreign keys

Revision ID: 001
Revises: 
Create Date: 2026-01-10 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create units table
    op.create_table(
        'units',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('unit_name', sa.String(length=100), nullable=False),
        sa.Column('unit_code', sa.String(length=20), nullable=False),
        sa.Column('hospital_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('unit_code')
    )
    op.create_index('idx_units_hospital_id', 'units', ['hospital_id'])
    
    # Create devices table
    op.create_table(
        'devices',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('unit_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('device_name', sa.String(length=100), nullable=False),
        sa.Column('firmware_version', sa.String(length=20), nullable=True),
        sa.Column('installation_date', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['unit_id'], ['units.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('unit_id', 'device_name', name='uq_device_name_per_unit')
    )
    op.create_index('idx_devices_unit_id', 'devices', ['unit_id'])
    
    # Create sessions table
    op.create_table(
        'sessions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('device_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('timestamp', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('duration_ms', sa.Integer(), nullable=False),
        sa.Column('compliant', sa.Boolean(), nullable=False),
        sa.Column('low_quality', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('missed_steps', postgresql.ARRAY(sa.Integer()), nullable=True, server_default=sa.text("'{}'::integer[]")),
        sa.Column('config_version', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.CheckConstraint('duration_ms >= 5000 AND duration_ms <= 120000', name='check_duration_range'),
        sa.ForeignKeyConstraint(['device_id'], ['devices.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_sessions_device_timestamp', 'sessions', ['device_id', sa.text('timestamp DESC')])
    op.create_index('idx_sessions_timestamp', 'sessions', [sa.text('timestamp DESC')])
    op.create_index('idx_sessions_compliant', 'sessions', ['compliant'])
    op.create_index('idx_sessions_low_quality', 'sessions', ['low_quality'])
    
    # Create steps table
    op.create_table(
        'steps',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('session_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('step_id', sa.Integer(), nullable=False),
        sa.Column('duration_ms', sa.Integer(), nullable=False),
        sa.Column('completed', sa.Boolean(), nullable=False),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.CheckConstraint('step_id >= 2 AND step_id <= 7', name='check_step_id_range'),
        sa.CheckConstraint('duration_ms >= 0', name='check_duration_non_negative'),
        sa.CheckConstraint('confidence_score IS NULL OR (confidence_score >= 0.0 AND confidence_score <= 1.0)', name='check_confidence_range'),
        sa.ForeignKeyConstraint(['session_id'], ['sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_steps_session_id', 'steps', ['session_id'])
    op.create_index('idx_steps_step_id', 'steps', ['step_id'])
    
    # Create heartbeats table
    op.create_table(
        'heartbeats',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('device_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('timestamp', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('firmware_version', sa.String(length=20), nullable=True),
        sa.Column('online_status', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['device_id'], ['devices.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_heartbeats_device_timestamp', 'heartbeats', ['device_id', sa.text('timestamp DESC')])
    
    # Create users table
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('unit_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('last_login_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.CheckConstraint("role IN ('org_admin', 'analyst', 'unit_manager', 'technician')", name='check_valid_role'),
        sa.CheckConstraint("(role = 'unit_manager' AND unit_id IS NOT NULL) OR (role != 'unit_manager' AND unit_id IS NULL)", name='check_unit_manager_has_unit'),
        sa.ForeignKeyConstraint(['unit_id'], ['units.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email')
    )
    op.create_index('idx_users_email', 'users', ['email'])
    op.create_index('idx_users_role', 'users', ['role'])


def downgrade() -> None:
    # Drop tables in reverse order (respecting foreign key dependencies)
    op.drop_index('idx_users_role', table_name='users')
    op.drop_index('idx_users_email', table_name='users')
    op.drop_table('users')
    
    op.drop_index('idx_heartbeats_device_timestamp', table_name='heartbeats')
    op.drop_table('heartbeats')
    
    op.drop_index('idx_steps_step_id', table_name='steps')
    op.drop_index('idx_steps_session_id', table_name='steps')
    op.drop_table('steps')
    
    op.drop_index('idx_sessions_low_quality', table_name='sessions')
    op.drop_index('idx_sessions_compliant', table_name='sessions')
    op.drop_index('idx_sessions_timestamp', table_name='sessions')
    op.drop_index('idx_sessions_device_timestamp', table_name='sessions')
    op.drop_table('sessions')
    
    op.drop_index('idx_devices_unit_id', table_name='devices')
    op.drop_table('devices')
    
    op.drop_index('idx_units_hospital_id', table_name='units')
    op.drop_table('units')
