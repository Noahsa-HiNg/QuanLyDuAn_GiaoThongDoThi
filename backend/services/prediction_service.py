# backend/services/prediction_service.py

import os
import json
import logging
import joblib
import numpy as np
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import List, Literal
from sqlalchemy.orm import Session
from sqlalchemy import text

from ml.constants import FEATURES

logger = logging.getLogger(__name__)

MODEL_DIR = os.path.join(os.path.dirname(__file__), "../ml/models")

HORIZONS = {
    "10min": {
        "model_path":   os.path.join(MODEL_DIR, "best_model_10minute.pkl"),
        "metrics_path": os.path.join(MODEL_DIR, "metrics_10minute.json"),
        "label":        "10 phút tới",
    },
    "20min": {
        "model_path":   os.path.join(MODEL_DIR, "best_model_20minute.pkl"),
        "metrics_path": os.path.join(MODEL_DIR, "metrics_20minute.json"),
        "label":        "20 phút tới",
    },
    "30min": {
        "model_path":   os.path.join(MODEL_DIR, "best_model_30minute.pkl"),
        "metrics_path": os.path.join(MODEL_DIR, "metrics_30minute.json"),
        "label":        "30 phút tới",
    },
}

HorizonKey = Literal["10min", "20min", "30min"]
DEFAULT_MAX_SPEED = 40.0
VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


def _is_rush_hour(hour: int) -> int:
    return 1 if (7 <= hour <= 9) or (17 <= hour <= 19) else 0


class PredictionService:
    def __init__(self):
        self._models: dict[str, object]           = {k: None for k in HORIZONS}
        self._cache_data: dict[str, list | None]  = {k: None for k in HORIZONS}
        self._cache_time: dict[str, datetime | None] = {k: None for k in HORIZONS}
        self._cache_ttl = 30  # seconds

        self._load_all_models()

    # ──────────────────────────────────────────
    # Load models
    # ──────────────────────────────────────────

    def _load_model(self, horizon: HorizonKey) -> bool:
        path = HORIZONS[horizon]["model_path"]

        if not os.path.exists(path):
            logger.warning(f"⚠️ Model [{horizon}] chưa tồn tại: {path}")
            return False

        try:
            model = joblib.load(path)

            if hasattr(model, "n_features_in_"):
                if model.n_features_in_ != len(FEATURES):
                    raise ValueError(
                        f"Feature mismatch [{horizon}]: "
                        f"model expects {model.n_features_in_}, got {len(FEATURES)}"
                    )

            self._models[horizon] = model
            logger.info(f"✅ Model [{horizon}] load OK — {type(model).__name__}")
            return True

        except Exception as e:
            logger.error(f"❌ Load model [{horizon}] lỗi: {e}")
            self._models[horizon] = None
            return False

    def _load_all_models(self):
        for horizon in HORIZONS:
            self._load_model(horizon)

    def reload_model(self, horizon: HorizonKey | None = None):
        targets = [horizon] if horizon else list(HORIZONS.keys())
        for h in targets:
            logger.info(f"🔄 Reload model [{h}]...")
            if self._load_model(h):
                self._cache_data[h] = None
                self._cache_time[h] = None
                logger.info(f"🧹 Cache [{h}] cleared")

    def is_ready(self, horizon: HorizonKey = "10min") -> bool:
        return self._models.get(horizon) is not None

    def ready_horizons(self) -> list[str]:
        return [h for h, m in self._models.items() if m is not None]

    # ──────────────────────────────────────────
    # Query DB
    # ──────────────────────────────────────────

    def _get_all_roads(self, db: Session) -> list:
        from data.manual_coords import MANUAL_COORDS
        allowed_names = list(MANUAL_COORDS.keys())

        rows = db.execute(text("""
            SELECT s.id as road_id, s.name as road_name,
                   COALESCE(ST_Y(ST_Centroid(s.geometry)), 16.0) as lat,
                   COALESCE(ST_X(ST_Centroid(s.geometry)), 108.0) as lng
            FROM streets s
            WHERE s.name = ANY(:names)
        """), {"names": allowed_names}).fetchall()

        return [dict(row._mapping) for row in rows]

    def _get_all_history(self, db: Session, road_id: int | None = None) -> pd.DataFrame:
        from data.manual_coords import MANUAL_COORDS
        allowed_names = list(MANUAL_COORDS.keys())

        if road_id is not None:
            road_filter  = "WHERE t.street_id = :road_id AND t.timestamp >= NOW() - INTERVAL '3 hours'"
            params       = {"road_id": road_id}
            limit_clause = "LIMIT 100"
        else:
            road_filter  = "WHERE s.name = ANY(:names) AND t.timestamp >= NOW() - INTERVAL '3 hours'"
            params       = {"names": allowed_names}
            limit_clause = ""

        rows = db.execute(text(f"""
            SELECT
                t.street_id   AS road_id,
                t.avg_speed,
                t.congestion_level,
                t.free_flow_speed,
                t.timestamp,
                COALESCE(s.length_km, 1.0)   AS road_length,
                COALESCE(s.max_speed, {DEFAULT_MAX_SPEED}) AS max_speed,
                COALESCE(d.id, -1)            AS district_id,
                EXTRACT(HOUR FROM t.timestamp AT TIME ZONE 'Asia/Ho_Chi_Minh') AS hour,
                EXTRACT(DOW  FROM t.timestamp AT TIME ZONE 'Asia/Ho_Chi_Minh') AS day_of_week
            FROM traffic_data t
            JOIN streets s ON t.street_id = s.id
            LEFT JOIN districts d ON s.district_id = d.id
            {road_filter}
            ORDER BY t.street_id, t.timestamp ASC
            {limit_clause}
        """), params).fetchall()

        df = pd.DataFrame(rows)
        if df.empty:
            return df

        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
        return df

    def _get_active_incidents(self, db: Session, road_id: int | None = None) -> pd.DataFrame:
        """Lấy incidents đang active tại thời điểm hiện tại."""
        now_utc = datetime.now(VN_TZ).astimezone()

        if road_id is not None:
            where = "WHERE street_id = :road_id AND start_time <= :now AND end_time >= :now"
            params = {"road_id": road_id, "now": now_utc}
        else:
            where = "WHERE start_time <= :now AND end_time >= :now"
            params = {"now": now_utc}

        rows = db.execute(text(f"""
            SELECT street_id, severity
            FROM incidents
            {where}
        """), params).fetchall()

        return pd.DataFrame(rows)

    # ──────────────────────────────────────────
    # Build features từ DataFrame (thay compute_features)
    # ──────────────────────────────────────────

    def _build_features(self, road_df: pd.DataFrame, incidents_df: pd.DataFrame) -> np.ndarray:
        """
        Tính toàn bộ FEATURES từ lịch sử traffic của 1 đường.
        road_df đã được sort theo timestamp ASC.
        Lấy record cuối cùng (mới nhất) làm hiện tại.
        """
        df  = road_df.sort_values("timestamp").reset_index(drop=True)
        now = df.iloc[-1]  # record mới nhất = thời điểm hiện tại

        current_speed   = float(now["avg_speed"])
        free_flow_speed = float(now.get("free_flow_speed") or now.get("max_speed") or DEFAULT_MAX_SPEED)
        max_speed       = float(now.get("max_speed") or DEFAULT_MAX_SPEED)
        road_length     = float(now.get("road_length") or 1.0)
        district_id     = int(now.get("district_id") or -1)
        hour            = int(now["hour"])
        day_of_week     = int(now["day_of_week"])

        # ── speed_ratio ──────────────────────────────────
        speed_ratio = current_speed / free_flow_speed if free_flow_speed > 0 else 1.0

        # ── avg_speed_1h_ago — tìm record gần nhất cách 60 phút ─────────────
        ts_now      = now["timestamp"]
        target_1h   = ts_now - pd.Timedelta(hours=1)
        target_24h  = ts_now - pd.Timedelta(hours=24)
        tol         = pd.Timedelta(minutes=10)

        def nearest_speed(target_ts):
            candidates = df[abs(df["timestamp"] - target_ts) <= tol]
            if candidates.empty:
                return np.nan
            idx = (candidates["timestamp"] - target_ts).abs().idxmin()
            return float(candidates.loc[idx, "avg_speed"])

        avg_speed_1h_ago    = nearest_speed(target_1h)
        avg_speed_yesterday = nearest_speed(target_24h)

        # fallback: nếu không có 24h trước (query chỉ 3h), dùng 1h trước
        if np.isnan(avg_speed_yesterday):
            avg_speed_yesterday = avg_speed_1h_ago

        # fallback cuối: dùng current_speed
        if np.isnan(avg_speed_1h_ago):
            avg_speed_1h_ago    = current_speed
        if np.isnan(avg_speed_yesterday):
            avg_speed_yesterday = current_speed

        # ── speed_delta ──────────────────────────────────
        speed_delta = current_speed - avg_speed_1h_ago

        # ── rolling_speed_3 — mean 3 records gần nhất ───
        rolling_speed_3 = float(df["avg_speed"].iloc[-3:].mean())

        # ── time features ────────────────────────────────
        is_weekend   = 1 if day_of_week >= 5 else 0
        is_rush_hour = _is_rush_hour(hour)

        # ── incidents ────────────────────────────────────
        road_id = int(now["road_id"])
        if not incidents_df.empty and road_id in incidents_df["street_id"].values:
            active = incidents_df[incidents_df["street_id"] == road_id]
            has_incident      = 1
            incident_severity = int(active["severity"].max())
        else:
            has_incident      = 0
            incident_severity = 0

        # ── Assemble theo thứ tự FEATURES ────────────────
        feature_dict = {
            "hour":                hour,
            "day_of_week":         day_of_week,
            "is_weekend":          is_weekend,
            "is_rush_hour":        is_rush_hour,
            "current_speed":       current_speed,
            "free_flow_speed":     free_flow_speed,
            "speed_ratio":         speed_ratio,
            "speed_delta":         speed_delta,
            "rolling_speed_3":     rolling_speed_3,
            "road_length":         road_length,
            "max_speed":           max_speed,
            "district_id":         district_id,
            "avg_speed_1h_ago":    avg_speed_1h_ago,
            "avg_speed_yesterday": avg_speed_yesterday,
            "has_incident":        has_incident,
            "incident_severity":   incident_severity,
        }

        X = pd.DataFrame([feature_dict])[FEATURES]
        return X.values

    # ──────────────────────────────────────────
    # Predict internal
    # ──────────────────────────────────────────

    def _predict_raw(self, X: np.ndarray, horizon: HorizonKey) -> tuple[int, float]:
        model = self._models[horizon]
        pred  = int(model.predict(X)[0])
        proba = model.predict_proba(X)[0]
        conf  = round(float(proba.max()), 3)
        return pred, conf

    # ──────────────────────────────────────────
    # Predict 1 road
    # ──────────────────────────────────────────

    def predict(self, road_id: int, db: Session, horizon: HorizonKey = "10min") -> dict:
        if not self.is_ready(horizon):
            return {"error": f"Model [{horizon}] chưa sẵn sàng", "road_id": road_id}

        try:
            road_df      = self._get_all_history(db, road_id=road_id)
            incidents_df = self._get_active_incidents(db, road_id=road_id)

            if road_df.empty:
                return {"error": "Không có dữ liệu", "road_id": road_id}

            X          = self._build_features(road_df, incidents_df)
            pred, conf = self._predict_raw(X, horizon)

            return {
                "road_id":         road_id,
                "horizon":         horizon,
                "horizon_label":   HORIZONS[horizon]["label"],
                "predicted_level": pred,
                "confidence":      conf,
                "predicted_at":    datetime.now(VN_TZ).isoformat(),
            }

        except Exception as e:
            logger.error(f"Lỗi predict road_id={road_id} horizon={horizon}: {e}")
            return {"error": str(e), "road_id": road_id}

    # ──────────────────────────────────────────
    # Predict all roads
    # ──────────────────────────────────────────

    def predict_all(self, db: Session, horizon: HorizonKey = "10min") -> List[dict]:
        if not self.is_ready(horizon):
            raise ValueError(f"Model [{horizon}] chưa sẵn sàng")

        now = datetime.now(VN_TZ)

        if self._cache_data[horizon] and self._cache_time[horizon]:
            delta = (now - self._cache_time[horizon]).total_seconds()
            if delta < self._cache_ttl:
                logger.info(f"⚡ Return cached predictions [{horizon}]")
                return self._cache_data[horizon]

        roads        = self._get_all_roads(db)
        history_df   = self._get_all_history(db)
        incidents_df = self._get_active_incidents(db)

        if history_df.empty:
            raise ValueError("Không có dữ liệu lịch sử")

        grouped = history_df.groupby("road_id")
        results = []

        for road in roads:
            try:
                road_id = road["road_id"]

                if road_id not in grouped.groups:
                    continue

                road_df    = grouped.get_group(road_id)
                X          = self._build_features(road_df, incidents_df)
                pred, conf = self._predict_raw(X, horizon)

                results.append({
                    "road_id":         road_id,
                    "road_name":       road.get("road_name", ""),
                    "lat":             road.get("lat"),
                    "lng":             road.get("lng"),
                    "horizon":         horizon,
                    "horizon_label":   HORIZONS[horizon]["label"],
                    "predicted_level": pred,
                    "confidence":      conf,
                    "predicted_at":    now.isoformat(),
                })

            except Exception as e:
                logger.error(f"Lỗi road_id={road_id} horizon={horizon}: {e}")
                continue

        self._cache_data[horizon] = results
        self._cache_time[horizon] = now

        return results

    def predict_all_horizons(self, db: Session) -> dict[str, List[dict]]:
        return {h: self.predict_all(db, horizon=h) for h in self.ready_horizons()}

    # ──────────────────────────────────────────
    # Metrics
    # ──────────────────────────────────────────

    def get_model_metrics(self, horizon: HorizonKey | None = None) -> dict:
        if horizon:
            path = HORIZONS[horizon]["metrics_path"]
            if not os.path.exists(path):
                return {"error": f"Chưa có metrics cho [{horizon}] — hãy train model"}
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                return {"error": str(e)}

        all_metrics = {}
        for h, cfg in HORIZONS.items():
            p = cfg["metrics_path"]
            if not os.path.exists(p):
                all_metrics[h] = {"error": "Chưa train"}
                continue
            try:
                with open(p, "r", encoding="utf-8") as f:
                    all_metrics[h] = json.load(f)
            except Exception as e:
                all_metrics[h] = {"error": str(e)}

        return all_metrics


# Singleton
prediction_service = PredictionService()