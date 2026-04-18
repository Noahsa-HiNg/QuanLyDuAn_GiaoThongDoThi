"""create all tables

Revision ID: 1682ed50ea97
Revises:
Create Date: 2026-04-18 16:46:41.871957

GHI CHÚ:
  geoalchemy2 tự động tạo GIST spatial index khi tạo cột Geometry.
  Vì vậy KHÔNG cần gọi create_index thủ công cho các cột geometry.
  Nếu tạo thủ công sẽ bị lỗi "relation already exists".
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import geoalchemy2

# revision identifiers, used by Alembic.
revision: str = '1682ed50ea97'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Tạo tất cả bảng của dự án."""

    # ── Bảng gốc (không có foreign key) ──────────────────────
    op.create_table('districts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('geometry', geoalchemy2.types.Geometry(
            geometry_type='POLYGON', srid=4326, dimension=2,
            from_text='ST_GeomFromEWKT', name='geometry'), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    # GeoAlchemy2 tự tạo GIST index cho cột geometry — không cần gọi thủ công
    op.create_index(op.f('ix_districts_id'), 'districts', ['id'],
                    unique=False, if_not_exists=True)

    op.create_table('users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False),
        sa.Column('full_name', sa.String(length=200), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('failed_attempts', sa.Integer(), nullable=False),
        sa.Column('is_locked', sa.Boolean(), nullable=False),
        sa.Column('locked_until', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('last_login', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'],
                    unique=True, if_not_exists=True)
    op.create_index(op.f('ix_users_id'), 'users', ['id'],
                    unique=False, if_not_exists=True)

    # ── audit_log và system_config phụ thuộc users ────────────
    op.create_table('audit_log',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('action', sa.String(length=100), nullable=False),
        sa.Column('target_table', sa.String(length=50), nullable=True),
        sa.Column('target_id', sa.Integer(), nullable=True),
        sa.Column('detail', sa.JSON(), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # ── streets phụ thuộc districts ───────────────────────────
    op.create_table('streets',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('district_id', sa.Integer(), nullable=True),
        sa.Column('geometry', geoalchemy2.types.Geometry(
            geometry_type='LINESTRING', srid=4326, dimension=2,
            from_text='ST_GeomFromEWKT', name='geometry'), nullable=True),
        sa.Column('length_km', sa.Float(), nullable=True),
        sa.Column('max_speed', sa.Integer(), nullable=True),
        sa.Column('is_one_way', sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(['district_id'], ['districts.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    # GeoAlchemy2 tự tạo GIST index cho cột geometry
    op.create_index(op.f('ix_streets_id'), 'streets', ['id'],
                    unique=False, if_not_exists=True)

    op.create_table('system_config',
        sa.Column('key', sa.String(length=100), nullable=False),
        sa.Column('value', sa.String(length=500), nullable=False),
        sa.Column('updated_by', sa.Integer(), nullable=True),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['updated_by'], ['users.id'], ),
        sa.PrimaryKeyConstraint('key')
    )

    # ── Bảng phụ thuộc streets ────────────────────────────────
    op.create_table('feedback',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('street_id', sa.Integer(), nullable=True),
        sa.Column('lat', sa.Float(), nullable=False),
        sa.Column('lon', sa.Float(), nullable=False),
        sa.Column('report_type', sa.String(length=30), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['street_id'], ['streets.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_feedback_street_time', 'feedback',
                    ['street_id', 'created_at'], unique=False, if_not_exists=True)
    op.create_index(op.f('ix_feedback_id'), 'feedback', ['id'],
                    unique=False, if_not_exists=True)

    op.create_table('incidents',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('street_id', sa.Integer(), nullable=False),
        sa.Column('type', sa.String(length=50), nullable=True),
        sa.Column('start_time', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('end_time', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('severity', sa.Integer(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint("status IN ('active', 'dispatched', 'resolved')",
                           name='check_status_valid'),
        sa.CheckConstraint('severity IN (1, 2, 3)', name='check_severity_valid'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
        sa.ForeignKeyConstraint(['street_id'], ['streets.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_incidents_active_street', 'incidents', ['street_id'],
                    unique=False, postgresql_where='is_active = TRUE',
                    if_not_exists=True)
    op.create_index(op.f('ix_incidents_id'), 'incidents', ['id'],
                    unique=False, if_not_exists=True)

    op.create_table('predictions',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('street_id', sa.Integer(), nullable=False),
        sa.Column('predicted_at', sa.TIMESTAMP(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.Column('target_time', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('horizon_minutes', sa.Integer(), nullable=False),
        sa.Column('pred_speed', sa.Float(), nullable=True),
        sa.Column('pred_level', sa.Integer(), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.CheckConstraint('confidence >= 0.0 AND confidence <= 1.0',
                           name='check_confidence_range'),
        sa.CheckConstraint('pred_level IN (0, 1, 2)', name='check_pred_level_valid'),
        sa.ForeignKeyConstraint(['street_id'], ['streets.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_predictions_street_time', 'predictions',
                    ['street_id', 'predicted_at'], unique=False, if_not_exists=True)

    op.create_table('traffic_data',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('street_id', sa.Integer(), nullable=False),
        sa.Column('timestamp', sa.TIMESTAMP(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.Column('avg_speed', sa.Float(), nullable=True),
        sa.Column('congestion_level', sa.Integer(), nullable=True),
        sa.Column('source', sa.String(length=20), nullable=True),
        sa.CheckConstraint('avg_speed >= 0', name='check_avg_speed_positive'),
        sa.CheckConstraint('congestion_level IN (0, 1, 2)',
                           name='check_congestion_level_valid'),
        sa.ForeignKeyConstraint(['street_id'], ['streets.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_traffic_street_time', 'traffic_data',
                    ['street_id', 'timestamp'], unique=False, if_not_exists=True)


def downgrade() -> None:
    """Xóa tất cả bảng (theo thứ tự ngược — con trước, cha sau)."""
    op.drop_index('idx_traffic_street_time', table_name='traffic_data')
    op.drop_table('traffic_data')
    op.drop_index('idx_predictions_street_time', table_name='predictions')
    op.drop_table('predictions')
    op.drop_index(op.f('ix_incidents_id'), table_name='incidents')
    op.drop_index('idx_incidents_active_street', table_name='incidents')
    op.drop_table('incidents')
    op.drop_index(op.f('ix_feedback_id'), table_name='feedback')
    op.drop_index('idx_feedback_street_time', table_name='feedback')
    op.drop_table('feedback')
    op.drop_table('system_config')
    op.drop_table('audit_log')
    op.drop_index(op.f('ix_streets_id'), table_name='streets')
    op.drop_table('streets')
    op.drop_index(op.f('ix_users_id'), table_name='users')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')
    op.drop_index(op.f('ix_districts_id'), table_name='districts')
    op.drop_table('districts')
