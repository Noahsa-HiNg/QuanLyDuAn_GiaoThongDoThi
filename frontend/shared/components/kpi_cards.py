"""
shared/components/kpi_cards.py — 3 KPI Metric Cards
v1.0
"""

import streamlit as st


def render_kpi_cards(traffic_data: dict) -> None:
    """
    Render 3 KPI cards glassmorphism ở đầu trang.
    SCRUM 11

    Cards:
      🔴 Số đường kẹt xe
      🟢 % Tuyến thông thoáng
      🔵 Tốc độ TB toàn thành phố
    """
    total   = traffic_data.get("total_streets", 0) or 1
    red     = traffic_data.get("red_count", 0)
    green   = traffic_data.get("green_count", 0)
    avg_spd = traffic_data.get("avg_speed_city", 0)
    green_pct = round(green / total * 100, 1) if total else 0

    st.markdown(f"""
    <div class="kpi-grid">

      <div class="kpi-card red">
        <div class="kpi-icon">🔴</div>
        <div class="kpi-body">
          <div class="kpi-value">{red}</div>
          <div class="kpi-label">Đường đang kẹt xe</div>
        </div>
      </div>

      <div class="kpi-card green">
        <div class="kpi-icon">🟢</div>
        <div class="kpi-body">
          <div class="kpi-value">{green_pct}%</div>
          <div class="kpi-label">Tuyến thông thoáng</div>
        </div>
      </div>

      <div class="kpi-card blue">
        <div class="kpi-icon">🚗</div>
        <div class="kpi-body">
          <div class="kpi-value">{avg_spd:.0f}</div>
          <div class="kpi-label">Tốc độ TB (km/h)</div>
        </div>
      </div>

    </div>
    """, unsafe_allow_html=True)
