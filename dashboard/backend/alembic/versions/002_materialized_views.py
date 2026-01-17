"""Create materialized views for analytics

Revision ID: 002
Revises: 001
Create Date: 2026-01-10 00:00:01.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create mv_daily_compliance materialized view
    op.execute("""
        CREATE MATERIALIZED VIEW mv_daily_compliance AS
        SELECT
            DATE(s.timestamp) AS date,
            s.device_id,
            d.unit_id,
            COUNT(*) AS total_sessions,
            COUNT(*) FILTER (WHERE s.compliant = TRUE) AS compliant_sessions,
            ROUND(100.0 * COUNT(*) FILTER (WHERE s.compliant = TRUE) / COUNT(*), 2) AS compliance_rate,
            ROUND(AVG(s.duration_ms), 2) AS avg_duration_ms
        FROM sessions s
        JOIN devices d ON s.device_id = d.id
        WHERE s.low_quality = FALSE
        GROUP BY DATE(s.timestamp), s.device_id, d.unit_id
    """)
    op.create_index(
        'idx_mv_daily_compliance',
        'mv_daily_compliance',
        ['date', 'device_id'],
        unique=True
    )
    op.create_index(
        'idx_mv_daily_compliance_unit',
        'mv_daily_compliance',
        ['unit_id', 'date']
    )
    
    # Create mv_step_statistics materialized view
    op.execute("""
        CREATE MATERIALIZED VIEW mv_step_statistics AS
        SELECT
            st.step_id,
            COUNT(*) AS total_attempts,
            COUNT(*) FILTER (WHERE st.completed = FALSE) AS missed_count,
            ROUND(100.0 * COUNT(*) FILTER (WHERE st.completed = FALSE) / COUNT(*), 2) AS miss_rate,
            ROUND(AVG(st.duration_ms), 2) AS avg_duration_ms
        FROM steps st
        JOIN sessions s ON st.session_id = s.id
        WHERE s.low_quality = FALSE
        GROUP BY st.step_id
    """)
    op.create_index(
        'idx_mv_step_statistics',
        'mv_step_statistics',
        ['step_id'],
        unique=True
    )
    
    # Create mv_device_status materialized view
    op.execute("""
        CREATE MATERIALIZED VIEW mv_device_status AS
        SELECT
            d.id AS device_id,
            d.unit_id,
            d.device_name,
            d.firmware_version,
            MAX(h.timestamp) AS last_seen,
            COUNT(h.id) FILTER (WHERE h.timestamp > NOW() - INTERVAL '24 hours') AS heartbeats_24h,
            CASE WHEN MAX(h.timestamp) < NOW() - INTERVAL '1 hour' THEN TRUE ELSE FALSE END AS is_offline
        FROM devices d
        LEFT JOIN heartbeats h ON d.id = h.device_id
        GROUP BY d.id, d.unit_id, d.device_name, d.firmware_version
    """)
    op.create_index(
        'idx_mv_device_status',
        'mv_device_status',
        ['device_id'],
        unique=True
    )
    op.create_index(
        'idx_mv_device_status_unit',
        'mv_device_status',
        ['unit_id']
    )


def downgrade() -> None:
    # Drop materialized views in reverse order
    op.drop_index('idx_mv_device_status_unit', table_name='mv_device_status')
    op.drop_index('idx_mv_device_status', table_name='mv_device_status')
    op.execute('DROP MATERIALIZED VIEW IF EXISTS mv_device_status')
    
    op.drop_index('idx_mv_step_statistics', table_name='mv_step_statistics')
    op.execute('DROP MATERIALIZED VIEW IF EXISTS mv_step_statistics')
    
    op.drop_index('idx_mv_daily_compliance_unit', table_name='mv_daily_compliance')
    op.drop_index('idx_mv_daily_compliance', table_name='mv_daily_compliance')
    op.execute('DROP MATERIALIZED VIEW IF EXISTS mv_daily_compliance')
