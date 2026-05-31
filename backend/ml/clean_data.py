import pandas as pd
# ======================= clean data =======================
def clean_traffic_data(df: pd.DataFrame) -> pd.DataFrame:

    if df.empty:
        return df

    df["timestamp"] = pd.to_datetime(
        df["timestamp"],
        utc=True,
        errors="coerce"
    )

    numeric_cols = [
        "avg_speed",
        "congestion_level",
        "free_flow_speed",
        "street_id",
    ]

    for c in numeric_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    # free flow mặc định
    df.loc[
        (df["free_flow_speed"].isna()) |
        (df["free_flow_speed"] <= 0),
        "free_flow_speed"
    ] = 60.0

    ratio = df["avg_speed"] / df["free_flow_speed"]

    df["congestion_level"] = 2
    df.loc[ratio >= 0.3, "congestion_level"] = 1
    df.loc[ratio >= 0.9, "congestion_level"] = 0

    df = df.dropna(
        subset=[
            "timestamp",
            "street_id",
            "avg_speed",
            "congestion_level",
        ]
    )

    df["street_id"] = df["street_id"].astype(int)

    valid_congestion = {0, 1, 2}

    df = df[df["congestion_level"].isin(valid_congestion)]

    df = df[
        (df["avg_speed"] > 0)
        & (df["avg_speed"] <= 150)
    ]

    df = df.drop_duplicates(
        subset=["street_id", "timestamp"],
        keep="last"
    )

    return df.reset_index(drop=True)

def clean_roads(df: pd.DataFrame) -> pd.DataFrame:

    if df.empty:
        return df

    df["max_speed"] = pd.to_numeric(
        df["max_speed"],
        errors="coerce"
    )

    df["road_length"] = pd.to_numeric(
        df["road_length"],
        errors="coerce"
    )

    df["district_id"] = pd.to_numeric(
        df["district_id"],
        errors="coerce"
    )

    return df.reset_index(drop=True)