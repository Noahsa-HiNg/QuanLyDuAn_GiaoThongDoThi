"""add_timestamp_index

Revision ID: 4b8b84e4b6b6
Revises: ac1b3ceb1a6b
Create Date: 2026-05-27 10:05:18.783498

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4b8b84e4b6b6'
down_revision: Union[str, Sequence[str], None] = 'ac1b3ceb1a6b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Chỉ tạo index trên cột timestamp của bảng traffic_data để tăng tốc truy vấn thống kê
    op.create_index('idx_traffic_data_timestamp', 'traffic_data', ['timestamp'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_traffic_data_timestamp', table_name='traffic_data')
