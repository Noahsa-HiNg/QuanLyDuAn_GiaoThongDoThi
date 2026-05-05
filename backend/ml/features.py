# ml/features.py
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

DANANG_DISTRICTS = {
    "Hải Châu": 0, "Thanh Khê": 1, "Sơn Trà": 2,
    "Ngũ Hành Sơn": 3, "Liên Chiểu": 4, "Cẩm Lệ": 5,
    "Hòa Vang": 6
}

def is_rush_hour(hour: int) -> int:
    return 1 if (7 <= hour <= 9) or (17 <= hour <= 19) else 0

def encode_district(district_name: str) -> int:
    return DANANG_DISTRICTS.get(district_name, 0)

def compute_features(row: pd.Series, history_df: pd.DataFrame) -> dict:
    ts: datetime = row["updated_at"]
    hour = ts.hour
    dow = ts.weekday()

    # 🔥 history_df đã là 1 road rồi
    road_df = history_df

    # ===== 1h trước =====
    one_hour_ago = ts - timedelta(hours=1)
    past_1h = road_df[
        (road_df["updated_at"] >= one_hour_ago) &
        (road_df["updated_at"] < ts)
    ]

    avg_1h = past_1h["speed"].mean()
    if np.isnan(avg_1h):
        avg_1h = row["speed"]

    # ===== hôm qua =====
    yesterday_time = ts - timedelta(days=1)

    past_yd = road_df[
        (road_df["updated_at"] >= yesterday_time - timedelta(minutes=30)) &
        (road_df["updated_at"] <= yesterday_time + timedelta(minutes=30))
    ]

    avg_yd = past_yd["speed"].mean()
    if np.isnan(avg_yd):
        avg_yd = row["speed"]

    return {
        "hour": hour,
        "day_of_week": dow,
        "is_weekend": int(dow >= 5),
        "is_rush_hour": is_rush_hour(hour),
        "current_congestion": row["congestion_level"],
        "current_speed": row["speed"],
        "road_length": row.get("road_length", 1.0),
        "district_encoded": encode_district(row.get("district", "")),
        "weather_temp": row.get("weather_temp", 30.0),
        "weather_rain": row.get("weather_rain", 0),
        "avg_speed_1h_ago": avg_1h,
        "avg_speed_yesterday": avg_yd,
    }

def build_training_data(db_session: Session = None) -> pd.DataFrame:
    """
    Build dataset cho training.
    Nếu không có db_session → generate mock data (dùng khi dev/test).
    Label = congestion_level của record 30 phút sau.
    """
    if db_session is not None:
        return _build_from_db(db_session)
    else:
        return _generate_mock_dataset()

def _build_from_db(db: Session) -> pd.DataFrame:
    from sqlalchemy import text
    # ✅ JOIN with weather_snapshots to get real historical weather data
    rows = db.execute(text("""
        SELECT r.id as road_id, r.road_name, r.lat, r.lng,
               r.length as road_length, r.district,
               t.speed, t.congestion_level, t.updated_at,
               -- ✅ Get nearest weather snapshot for each traffic record
               COALESCE(w.temperature, 28.0) as weather_temp,
               COALESCE(w.rain_1h_mm, 0.0) as weather_rain
        FROM traffic_records t
        JOIN roads r ON t.road_id = r.id
        LEFT JOIN LATERAL (
            SELECT temperature, rain_1h_mm
            FROM weather_snapshots
            ORDER BY ABS(EXTRACT(EPOCH FROM (timestamp - t.updated_at)))
            LIMIT 1
        ) w ON true
        ORDER BY t.updated_at ASC
    """)).fetchall()

    df = pd.DataFrame(rows)
    df["updated_at"] = pd.to_datetime(df["updated_at"])
    # ✅ Weather data now comes from database, not hardcoded
    return _attach_labels_and_features(df)

def _generate_mock_dataset(n_roads: int = 50, days: int = 14) -> pd.DataFrame:
    """Tạo mock dataset đủ dùng để train (50 đường × 14 ngày × 24h = ~16,800 records)."""
    np.random.seed(42)
    records = []
    base_time = datetime.now() - timedelta(days=days)

    district_list = list(DANANG_DISTRICTS.keys())

    for road_id in range(1, n_roads + 1):
        district = district_list[road_id % len(district_list)]
        road_length = np.random.uniform(0.5, 5.0)

        for day_offset in range(days):
            for hour in range(24):
                ts = base_time + timedelta(days=day_offset, hours=hour)
                dow = ts.weekday()

                # Simulate realistic traffic pattern
                rush = is_rush_hour(hour)
                base_speed = 50 - 20 * rush - 5 * (dow >= 5)
                speed = max(5.0, base_speed + np.random.normal(0, 8))

                if speed > 40:
                    congestion = 1
                elif speed > 20:
                    congestion = 2
                else:
                    congestion = 3

                records.append({
                    "road_id":         road_id,
                    "road_name":       f"Đường số {road_id}",
                    "district":        district,
                    "road_length":     round(road_length, 2),
                    "speed":           round(speed, 1),
                    "congestion_level": congestion,
                    "updated_at":      ts,
                    "weather_temp":    round(np.random.uniform(25, 38), 1),
                    "weather_rain":    int(np.random.random() < 0.2),
                })

    df = pd.DataFrame(records)
    return _attach_labels_and_features(df)

def _attach_labels_and_features(df: pd.DataFrame) -> pd.DataFrame:
    """Gắn label (congestion 30p sau) và tính features cho từng record."""
    
    df = df.sort_values(["road_id", "updated_at"]).reset_index(drop=True)

    # ===== LABEL =====
    df["label"] = (
        df.groupby("road_id")["congestion_level"]
          .shift(-1)
          .fillna(df["congestion_level"])
          .astype(int)
    )

    feature_rows = []

    # 🔥 FIX PERFORMANCE: group theo road_id
    for road_id, group in df.groupby("road_id"):
        group = group.sort_values("updated_at")

        for _, row in group.iterrows():
            feature_rows.append(compute_features(row, group))  # ⚠️ truyền group

    features_df = pd.DataFrame(feature_rows)

    # ⚠️ đảm bảo label khớp
    features_df["label"] = df["label"].values

    return features_df.dropna()