# backend/services/prediction_service.py

import os
import json
import logging
import joblib
import numpy as np
import pandas as pd
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import List
from sqlalchemy.orm import Session
from sqlalchemy import text

from ml.constants import FEATURES
from ml.features import compute_features

logger = logging.getLogger(__name__)

MODEL_DIR    = os.path.join(os.path.dirname(__file__), "../ml/models")
MODEL_PATH   = os.path.join(MODEL_DIR, "best_model.pkl")   # ✅ SỬA: rf_model → best_model
METRICS_PATH = os.path.join(MODEL_DIR, "metrics.json")

# 🔥 TIMEZONE FIX
VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


class PredictionService:
    def __init__(self):
        self._model  = None

        # 🔥 CACHE
        self._cache_data = None
        self._cache_time = None
        self._cache_ttl = 30  # seconds

        self._load_model()

    # ──────────────────────────────────────────
    # Load model (safe)
    # ──────────────────────────────────────────

    def _load_model(self) -> bool:
        if not os.path.exists(MODEL_PATH):
            logger.warning(f"⚠️ Model chưa tồn tại tại: {MODEL_PATH}")
            return False

        try:
            self._model = joblib.load(MODEL_PATH)

            # ✅ check feature mismatch (nếu model hỗ trợ)
            if hasattr(self._model, "n_features_in_"):
                if self._model.n_features_in_ != len(FEATURES):
                    raise ValueError(
                        f"Feature mismatch: model expects {self._model.n_features_in_}, got {len(FEATURES)}"
                    )

            model_type = type(self._model).__name__
            logger.info(f"✅ Model load OK — type: {model_type}")
            return True

        except Exception as e:
            logger.error(f"❌ Load model lỗi: {e}")
            self._model = None
            return False

    def reload_model(self):
        logger.info("🔄 Reload model...")

        success = self._load_model()

        if success:
            # 🔥 clear cache
            self._cache_data = None
            self._cache_time = None
            logger.info("🧹 Cache cleared after model reload")

    @property
    def is_ready(self) -> bool:
        return self._model is not None

    # ──────────────────────────────────────────
    # Query roads
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

    # ──────────────────────────────────────────
    # 🔥 Query ALL history
    # ──────────────────────────────────────────

    def _get_all_history(self, db: Session, road_id: int | None = None) -> pd.DataFrame:
        """
        Query lịch sử traffic. Chỉ lấy dữ liệu trong vòng 3 giờ gần nhất để tránh OOM
        và nghẽn DB (timeout) khi cơ sở dữ liệu có hàng triệu bản ghi.
        """
        from data.manual_coords import MANUAL_COORDS
        allowed_names = list(MANUAL_COORDS.keys())

        if road_id is not None:
            road_filter = "WHERE t.street_id = :road_id AND t.timestamp >= NOW() - INTERVAL '3 hours'"
            params = {"road_id": road_id}
            limit_clause = "LIMIT 100"
        else:
            road_filter = "WHERE s.name = ANY(:names) AND t.timestamp >= NOW() - INTERVAL '3 hours'"
            params = {"names": allowed_names}
            limit_clause = ""

        rows = db.execute(text(f"""
            SELECT t.street_id as road_id, t.avg_speed as speed, t.congestion_level, t.timestamp as updated_at,
                   COALESCE(s.length_km, 1.0) as road_length,
                   COALESCE(d.name, '') as district,
                   COALESCE(w.temperature, 28.0) as weather_temp,
                   COALESCE(w.rain_1h_mm, 0.0) as weather_rain
            FROM traffic_data t
            JOIN streets s ON t.street_id = s.id
            LEFT JOIN districts d ON s.district_id = d.id
            LEFT JOIN weather_snapshots w ON w.id = (
                SELECT ws.id FROM weather_snapshots ws
                WHERE ws.timestamp >= NOW() - INTERVAL '3 hours'
                ORDER BY ABS(EXTRACT(EPOCH FROM (ws.timestamp - t.timestamp)))
                LIMIT 1
            )
            {road_filter}
            ORDER BY t.street_id, t.timestamp DESC
            {limit_clause}
        """), params).fetchall()

        df = pd.DataFrame(rows)
        if df.empty:
            return df

        # 🔥 FIX TIMEZONE
        df["updated_at"] = pd.to_datetime(df["updated_at"], utc=True)
        df["updated_at"] = df["updated_at"].dt.tz_convert(VN_TZ)

        return df

    # ──────────────────────────────────────────
    # Build feature
    # ──────────────────────────────────────────

    def _build_feature_from_df(self, road_df: pd.DataFrame) -> np.ndarray:
        row = road_df.iloc[-1]

        feature_dict = compute_features(row, road_df)

        X = pd.DataFrame([feature_dict])[FEATURES]

        return X.values

    # ──────────────────────────────────────────
    # ✅ Predict internal (không cần scaler)
    # ──────────────────────────────────────────

    def _predict_raw(self, X: np.ndarray) -> tuple[int, float]:
        """
        Predict và trả về (predicted_level, confidence).
        LightGBM/CatBoost/XGBoost không cần scale feature — dùng trực tiếp.
        """
        pred  = int(self._model.predict(X)[0])
        proba = self._model.predict_proba(X)[0]
        conf  = round(float(proba.max()), 3)
        return pred, conf

    # ──────────────────────────────────────────
    # Predict 1 road
    # ──────────────────────────────────────────

    def predict(self, road_id: int, db: Session) -> dict:
        if not self.is_ready:
            return {"error": "Model chưa sẵn sàng", "road_id": road_id}

        try:
            road_df = self._get_all_history(db, road_id=road_id)

            if road_df.empty:
                return {"error": "Không có dữ liệu", "road_id": road_id}

            X = self._build_feature_from_df(road_df)
            pred, conf = self._predict_raw(X)   # ✅ không dùng scaler

            return {
                "road_id": road_id,
                "predicted_level": pred,
                "confidence": conf,
                "predicted_at": datetime.now(VN_TZ).isoformat(),
            }

        except Exception as e:
            logger.error(f"Lỗi predict road_id={road_id}: {e}")
            return {"error": str(e), "road_id": road_id}

    # ──────────────────────────────────────────
    # Predict all roads
    # ──────────────────────────────────────────

    def predict_all(self, db: Session) -> List[dict]:
        if not self.is_ready:
            raise ValueError("Model chưa sẵn sàng")

        now = datetime.now(VN_TZ)

        # 🔥 CACHE
        if self._cache_data and self._cache_time:
            delta = (now - self._cache_time).total_seconds()
            if delta < self._cache_ttl:
                logger.info("⚡ Return cached predictions")
                return self._cache_data

        roads = self._get_all_roads(db)
        history_df = self._get_all_history(db)

        if history_df.empty:
            raise ValueError("Không có dữ liệu lịch sử")

        grouped = history_df.groupby("road_id")

        results = []

        for road in roads:
            try:
                road_id = road["road_id"]

                if road_id not in grouped.groups:
                    continue

                road_df = grouped.get_group(road_id)

                X = self._build_feature_from_df(road_df)
                pred, conf = self._predict_raw(X)   # ✅ không dùng scaler

                results.append({
                    "road_id": road_id,
                    "road_name": road.get("road_name", ""),
                    "lat": road.get("lat"),
                    "lng": road.get("lng"),
                    "predicted_level": pred,
                    "confidence": conf,
                    "predicted_at": now.isoformat(),
                })

            except Exception as e:
                logger.error(f"Lỗi road_id={road_id}: {e}")
                continue

        # 🔥 save cache
        self._cache_data = results
        self._cache_time = now

        return results

    # ──────────────────────────────────────────
    # Metrics
    # ──────────────────────────────────────────

    def get_model_metrics(self) -> dict:
        if not os.path.exists(METRICS_PATH):
            return {"error": "Chưa có metrics — hãy train model"}

        try:
            with open(METRICS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Đọc metrics lỗi: {e}")
            return {"error": str(e)}


# Singleton
prediction_service = PredictionService()