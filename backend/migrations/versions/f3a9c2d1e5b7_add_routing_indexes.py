"""add_routing_indexes

Revision ID: f3a9c2d1e5b7
Revises: 4b8b84e4b6b6
Create Date: 2026-05-28 12:36:00.000000

Mục đích:
  Thêm 2 index còn thiếu để tăng tốc query build graph cho A*:

  1. idx_traffic_street_time_desc
     Bảng  : traffic_data
     Cột   : (street_id, timestamp DESC)
     Query : SELECT DISTINCT ON (s.name) ... ORDER BY s.name, td.timestamp DESC
     → Cho phép PostgreSQL dùng Index Scan thay vì Sort (giảm từ O(N log N) → O(log N))

  2. idx_streets_name
     Bảng  : streets
     Cột   : (name)
     Query : JOIN streets s ON ... ORDER BY s.name
     → Tăng tốc JOIN + ORDER BY khi số lượng street lớn
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f3a9c2d1e5b7'
down_revision: Union[str, Sequence[str], None] = '4b8b84e4b6b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Index 1: (street_id, timestamp DESC) cho query DISTINCT ON trong routing.py
    # Giúp PostgreSQL tìm bản ghi mới nhất của mỗi street_id không cần sort toàn bảng
    op.create_index(
        'idx_traffic_street_time_desc',
        'traffic_data',
        ['street_id', sa.text('timestamp DESC')],
        unique=False,
    )

    # Index 2: (name) cho bảng streets — tăng tốc JOIN + ORDER BY s.name
    op.create_index(
        'idx_streets_name',
        'streets',
        ['name'],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index('idx_streets_name', table_name='streets')
    op.drop_index('idx_traffic_street_time_desc', table_name='traffic_data')
