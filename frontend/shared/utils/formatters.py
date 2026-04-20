"""
shared/utils/formatters.py — Format helpers

Dùng để hiển thị số, thời gian, % cho UI.
"""


def format_speed(speed: float | None) -> str:
    """'45 km/h' hoặc '—' nếu None."""
    return f"{speed:.0f} km/h" if speed else "—"


def format_pct(value: float) -> str:
    """'73.5%'"""
    return f"{value:.1f}%"


def congestion_label(level: int | None) -> str:
    """Trả về emoji + text theo mức ùn tắc."""
    return {
        0: "🟢 Thông thoáng",
        1: "🟡 Chậm",
        2: "🔴 Kẹt xe",
    }.get(level, "⚪ Chưa có dữ liệu")
