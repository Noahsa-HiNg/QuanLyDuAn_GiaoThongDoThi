import pandas as pd
import os
from sqlalchemy import create_engine
from datetime import datetime, timedelta
# ── CONFIG ─────────────────────────────────────────────────────────────────────
DB_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://myadmin:123456@localhost:5432/qlda_dothithongminh"
)
engine = create_engine(DB_URL)
# ── LOAD DATA ─────────────────────────────────────────────────────────────────
def load_roads_from_db(limit: int | None = None) -> pd.DataFrame:

    query = """
        SELECT
            id,
            name,
            district_id,
            max_speed,
            length_km * 1000 AS road_length
        FROM streets
    """

    if limit is not None:
        query += f" LIMIT {int(limit)}"

    return pd.read_sql(query, engine)


def load_traffic_data(street_ids: list,n_days: int | None = None):
    query = """
        SELECT
            street_id,
            "timestamp",
            avg_speed,
            congestion_level,
            free_flow_speed,
            EXTRACT(HOUR FROM "timestamp") AS hour,
            EXTRACT(DOW FROM "timestamp") AS day_of_week
        FROM traffic_data
        WHERE street_id = ANY(%s)
    """

    params = [street_ids]

    if n_days is not None:
        query += ' AND "timestamp" >= %s'
        params.append(
            datetime.utcnow() - timedelta(days=n_days)
        )

    query += """
        ORDER BY street_id, "timestamp"
    """

    return pd.read_sql(query, engine, params=tuple(params))


def load_incidents(street_ids: list, n_days: int = 14) -> pd.DataFrame:
    since = datetime.utcnow() - timedelta(days=n_days)

    query = """
        SELECT
            street_id,
            start_time,
            end_time,
            severity
        FROM incidents
        WHERE street_id = ANY(%s)
          AND start_time >= %s
    """

    return pd.read_sql(query, engine, params=(street_ids, since))