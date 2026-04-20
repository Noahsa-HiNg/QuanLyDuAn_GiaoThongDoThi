"""
shared/utils/colors.py — Màu sắc theo mức ùn tắc

Format: [R, G, B, A] — Pydeck dùng RGBA 0-255
"""

# congestion_level: 0=Xanh, 1=Vàng, 2=Đỏ, None=Xám
CONGESTION_COLORS: dict = {
    0:    [34,  197,  94, 220],   # Xanh lá  — thông thoáng
    1:    [234, 179,   8, 220],   # Vàng     — chậm
    2:    [239,  68,  68, 220],   # Đỏ       — kẹt xe
    None: [156, 163, 175, 150],   # Xám      — chưa có dữ liệu
}

# Hex colors cho CSS / Plotly
CONGESTION_HEX: dict = {
    0: "#22c55e",
    1: "#eab308",
    2: "#ef4444",
    None: "#9ca3af",
}


def get_color(congestion_level: int | None) -> list[int]:
    """Trả về [R, G, B, A] theo mức ùn tắc."""
    return CONGESTION_COLORS.get(congestion_level, CONGESTION_COLORS[None])
