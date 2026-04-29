"""add_weather_snapshots

Revision ID: ac1b3ceb1a6b
Revises: 1682ed50ea97
Create Date: 2026-04-22

Tạo bảng weather_snapshots để lưu thời tiết Đà Nẵng mỗi chu kỳ cào traffic.
Dùng cho: feature engineering ML (JOIN với traffic_data theo timestamp).
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'ac1b3ceb1a6b'
down_revision = '1682ed50ea97'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'weather_snapshots',
        sa.Column('id',            sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('timestamp',     sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('source',        sa.String(length=30), nullable=True),
        sa.Column('temperature',   sa.Float(), nullable=True),
        sa.Column('humidity',      sa.Integer(), nullable=True),
        sa.Column('wind_speed',    sa.Float(), nullable=True),
        sa.Column('rain_1h_mm',    sa.Float(), nullable=True),
        sa.Column('is_raining',    sa.Integer(), nullable=True),
        sa.Column('visibility_km', sa.Float(), nullable=True),
        sa.Column('weather_group', sa.Integer(), nullable=True),
        sa.Column('weather_id',    sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'idx_weather_timestamp',
        'weather_snapshots',
        ['timestamp'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index('idx_weather_timestamp', table_name='weather_snapshots')
    op.drop_table('weather_snapshots')
