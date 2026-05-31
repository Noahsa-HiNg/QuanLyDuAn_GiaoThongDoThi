import numpy as np
# ── HELPERS ────────────────────────────────────────────────────────────────────
def is_rush_hour(hour: int) -> int:
    return 1 if (7 <= hour <= 9) or (17 <= hour <= 19) else 0
def engineer_features(traffic_df):
    # =====================================================
    # Historical Features
    # =====================================================

    traffic_df["avg_speed_1h_ago"] = (
        traffic_df.groupby("street_id")["avg_speed"]
        .shift(12)
    )

    traffic_df["avg_speed_yesterday"] = (
        traffic_df.groupby("street_id")["avg_speed"]
        .shift(288)
    )

    # =====================================================
    # Feature Engineering
    # =====================================================

    traffic_df["current_speed"] = traffic_df["avg_speed"]

    traffic_df["speed_ratio"] = (
        traffic_df["current_speed"]
        / traffic_df["free_flow_speed"]
    )

    traffic_df["speed_ratio"] = (
        traffic_df["speed_ratio"]
        .replace([np.inf, -np.inf], np.nan)
        .fillna(1.0)
    )

    traffic_df["speed_delta"] = (
        traffic_df["current_speed"]
        - traffic_df["avg_speed_1h_ago"]
    )

    traffic_df["rolling_speed_3"] = (
        traffic_df.groupby("street_id")["current_speed"]
        .transform(
            lambda x: x.rolling(
                window=3,
                min_periods=1
            ).mean()
        )
    )
    # =====================================================
    # Time Features
    # =====================================================

    traffic_df["hour"] = (
        traffic_df["hour"]
        .astype(int)
    )

    traffic_df["day_of_week"] = (
        traffic_df["day_of_week"]
        .astype(int)
    )

    traffic_df["is_weekend"] = (
        traffic_df["day_of_week"] >= 5
    ).astype(int)

    traffic_df["is_rush_hour"] = (
        traffic_df["hour"]
        .apply(is_rush_hour)
    )
    return traffic_df