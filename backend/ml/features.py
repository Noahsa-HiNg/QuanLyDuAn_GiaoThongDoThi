import pandas as pd
import logging
from ml.constants import FEATURES
from ml.clean_data import clean_traffic_data , clean_roads
from ml.feature_engineering import engineer_features
from ml.prepare_dataset import load_roads_from_db, load_traffic_data, load_incidents

logger = logging.getLogger(__name__)

DEFAULT_MAX_SPEED = 40
DEFAULT_ROAD_LENGTH = 100.0

# predict sau 1 giờ nếu mỗi record cách nhau 5 phút
PREDICT_STEPS = 12

# __ create lable ------------------------------
def create_labels(df: pd.DataFrame,predict_steps: int = 12) -> pd.DataFrame:

    df["label"] = (
        df.groupby("street_id")["congestion_level"]
        .shift(-predict_steps)
    )

    return df
def merge_road_metadata(roads, traffic_df):

    roads_info = roads[
        [
            "id",
            "district_id",
            "max_speed",
            "road_length"
        ]
    ].rename(columns={"id": "street_id"})

    traffic_df = traffic_df.merge(
        roads_info,
        on="street_id",
        how="left"
    )

    traffic_df["max_speed"] = (
        traffic_df["max_speed"]
        .fillna(DEFAULT_MAX_SPEED)
    )

    traffic_df["road_length"] = (
        traffic_df["road_length"]
        .fillna(DEFAULT_ROAD_LENGTH)
    )

    traffic_df["district_id"] = (
        traffic_df["district_id"]
        .fillna(-1)
        .astype(int)
    )
    return traffic_df

def fill_free_flow_speed(df):

    df["free_flow_speed"] = (
        df["free_flow_speed"]
        .fillna(df["max_speed"])
        .fillna(DEFAULT_MAX_SPEED)
    )

    return df
# ── BUILD DATASET ─────────────────────────────────────────────────────────────
def build_dataset(n_days: int | None = None,roads_limit: int | None = None) -> pd.DataFrame | None:
    print("=" * 50 + " Building dataset " + "=" * 50)

    roads = load_roads_from_db(limit=roads_limit)
    print(f"[1] Roads loaded: {len(roads)}")

    if roads.empty:
        print("[ERROR] roads empty")
        return None

    roads = clean_roads(roads)
    print(f"[2] Roads after clean: {len(roads)}")

    street_ids = roads["id"].tolist()

    traffic_df = load_traffic_data(
        street_ids,
        n_days=n_days
    )

    print(f"[3] Traffic loaded: {len(traffic_df)}")

    traffic_df = clean_traffic_data(traffic_df)

    print(f"[4] Traffic after clean: {len(traffic_df)}")

    if traffic_df.empty:
        print("[ERROR] traffic_df empty")
        return None

    traffic_df = traffic_df.sort_values(
        ["street_id", "timestamp"]
    ).reset_index(drop=True)

    print(f"[5] After sort: {len(traffic_df)}")

    traffic_df = merge_road_metadata(
        roads,
        traffic_df
    )

    print(f"[6] After merge road metadata: {len(traffic_df)}")

    traffic_df = fill_free_flow_speed(
        traffic_df
    )

    print(f"[7] After fill free flow speed: {len(traffic_df)}")

    traffic_df = engineer_features(
        traffic_df
    )

    print(f"[8] After engineer_features: {len(traffic_df)}")

    traffic_df["has_incident"] = 0
    traffic_df["incident_severity"] = 0

    print("\n===== NULL COUNT AFTER FEATURES =====")
    print(
        traffic_df[
            FEATURES
        ].isna().sum().sort_values(
            ascending=False
        )
    )

    traffic_df = create_labels(
        traffic_df,
        predict_steps=PREDICT_STEPS
    )

    print(f"\n[9] After create_labels: {len(traffic_df)}")

    print(
        f"Label null count: "
        f"{traffic_df['label'].isna().sum()}"
    )

    print("\n===== LABEL DISTRIBUTION =====")
    print(
        traffic_df["label"]
        .value_counts(dropna=False)
        .sort_index()
    )

    result = traffic_df[
        ["timestamp"] + FEATURES + ["label"]
    ]

    print(
        f"\n[10] Before dropna: {len(result)}"
    )

    print("\n===== NULL COUNT BEFORE DROPNA =====")
    print(
        result.isna().sum()
        .sort_values(
            ascending=False
        )
    )

    result = result.dropna()

    print(
        f"\n[11] After dropna: {len(result)}"
    )

    print("\n===== FINAL LABEL DISTRIBUTION =====")
    print(
        result["label"]
        .value_counts(normalize=True)
        .sort_index()
    )
    return result.reset_index(drop=True)