"""add_here_incident_id_and_source

Revision ID: a2c5e8f1b3d9
Revises: f3a9c2d1e5b7
Create Date: 2026-05-30 20:34:00.000000

Mục đích:
  Bổ sung 2 cột mới vào bảng `incidents` để hỗ trợ cào tai nạn
  tự động từ HERE Traffic Incidents API:

  1. here_incident_id (VARCHAR 150, UNIQUE, NULLABLE)
     - Lưu ID gốc của tai nạn từ HERE API
     - NULL   → sự cố do CSGT nhập tay (không ảnh hưởng dữ liệu cũ)
     - có giá trị → cào tự động (dùng để dedup: không insert trùng)

  2. source (VARCHAR 20, NOT NULL, DEFAULT 'manual')
     - 'manual'   → CSGT / Admin nhập tay
     - 'here_api' → Cào tự động từ HERE Traffic Incidents API
     - DEFAULT 'manual' đảm bảo tất cả bản ghi cũ vẫn hợp lệ

  Các index đi kèm:
     - ix_incidents_here_incident_id  (UNIQUE) — dedup nhanh
     - idx_incidents_source           — filter theo nguồn
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a2c5e8f1b3d9'
down_revision: Union[str, Sequence[str], None] = 'f3a9c2d1e5b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. Thêm cột here_incident_id ─────────────────────────────────────────
    # nullable=True: bản ghi cũ (CSGT nhập tay) giữ nguyên NULL
    op.add_column(
        'incidents',
        sa.Column('here_incident_id', sa.String(150), nullable=True),
    )

    # Unique index để dedup: nếu cùng here_incident_id → bỏ qua insert mới
    op.create_index(
        'ix_incidents_here_incident_id',
        'incidents',
        ['here_incident_id'],
        unique=True,
        # Partial index: chỉ index bản ghi NON-NULL (tiết kiệm space với nhiều NULL)
        postgresql_where=sa.text("here_incident_id IS NOT NULL"),
    )

    # ── 2. Thêm cột source ────────────────────────────────────────────────────
    # server_default='manual': bản ghi cũ tự động nhận giá trị 'manual'
    op.add_column(
        'incidents',
        sa.Column(
            'source',
            sa.String(20),
            nullable=False,
            server_default='manual',
        ),
    )

    # Index để query nhanh theo nguồn (VD: WHERE source = 'here_api')
    op.create_index(
        'idx_incidents_source',
        'incidents',
        ['source'],
        unique=False,
    )

    # ── 3. Check constraint cho source ───────────────────────────────────────
    op.create_check_constraint(
        'check_source_valid',
        'incidents',
        "source IN ('manual', 'here_api')",
    )


def downgrade() -> None:
    # Xóa theo thứ tự ngược
    op.drop_constraint('check_source_valid', 'incidents', type_='check')
    op.drop_index('idx_incidents_source', table_name='incidents')
    op.drop_column('incidents', 'source')

    op.drop_index('ix_incidents_here_incident_id', table_name='incidents')
    op.drop_column('incidents', 'here_incident_id')
