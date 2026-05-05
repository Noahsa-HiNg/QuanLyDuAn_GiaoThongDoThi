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

MODEL_DIR    = os.path.join(os.path.dirname(__file__), "../../ml/models")
MODEL_PATH   = os.path.join(MODEL_DIR, "rf_model.pkl")
SCALER_PATH  = os.path.join(MODEL_DIR, "scaler.pkl")
METRICS_PATH = os.path.join(MODEL_DIR, "metrics.json")

# 🔥 TIMEZONE FIX
VN_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


class PredictionService:
    def __init__(self):
        self._model  = None
        self._scaler = None

        # 🔥 CACHE
        self._cache_data = None
        self._cache_time = None
        self._cache_ttl = 30  # seconds

        self._load_model()

    # ──────────────────────────────────────────
    # Load model (safe)
    # ──────────────────────────────────────────

    def _load_model(self) -> bool:
        if not os.path.exists(MODEL_PATH) or not os.path.exists(SCALER_PATH):
            logger.warning("⚠️ Model hoặc scaler chưa tồn tại")
            return False

        try:
            self._model  = joblib.load(MODEL_PATH)
            self._scaler = joblib.load(SCALER_PATH)

            # 🔥 check feature mismatch
            if hasattr(self._model, "n_features_in_"):
                if self._model.n_features_in_ != len(FEATURES):
                    raise ValueError(
                        f"Feature mismatch: model expects {self._model.n_features_in_}, got {len(FEATURES)}"
                    )

            logger.info("✅ Model + scaler load OK")
            return True

        except Exception as e:
            logger.error(f"❌ Load model lỗi: {e}")
            self._model = self._scaler = None
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
        return self._model is not None and self._scaler is not None

    # ──────────────────────────────────────────
    # Query roads
    # ──────────────────────────────────────────

    def _get_all_roads(self, db: Session) -> list:
        rows = db.execute(text("""
            SELECT r.id as road_id, r.road_name, r.lat, r.lng
            FROM roads r
        """)).fetchall()

        return [dict(row._mapping) for row in rows]

    # ──────────────────────────────────────────
    # 🔥 Query ALL history
    # ──────────────────────────────────────────

    def _get_all_history(self, db: Session) -> pd.DataFrame:
        rows = db.execute(text("""
            SELECT t.road_id, t.speed, t.congestion_level, t.updated_at,
                   COALESCE(r.length, 1.0) as road_length,
                   COALESCE(r.district, '') as district,
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
            ORDER BY t.road_id, t.updated_at
        """)).fetchall()

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
    # Predict 1 road
    # ──────────────────────────────────────────

    def predict(self, road_id: int, db: Session) -> dict:
        if not self.is_ready:
            return {"error": "Model chưa sẵn sàng", "road_id": road_id}

        try:
            history_df = self._get_all_history(db)
            road_df = history_df[history_df["road_id"] == road_id]

            if road_df.empty:
                return {"error": "Không có dữ liệu", "road_id": road_id}

            X = self._build_feature_from_df(road_df)
            X_scaled = self._scaler.transform(X)

            pred  = int(self._model.predict(X_scaled)[0])
            proba = self._model.predict_proba(X_scaled)[0]
            conf  = round(float(proba.max()), 3)

            return {
                "road_id": road_id,
                "predicted_level": pred,
                "confidence": conf,
                "predicted_at": datetime.now(VN_TZ).isoformat(),  # 🔥 FIX
            }

        except Exception as e:
            logger.error(f"Lỗi predict road_id={road_id}: {e}")
            return {"error": str(e), "road_id": road_id}

    # ──────────────────────────────────────────
    # Predict all roads
    # ──────────────────────────────────────────

    def predict_all(self, db: Session) -> List[dict]:
        if not self.is_ready:
            return [{"error": "Model chưa sẵn sàng"}]

        now = datetime.now(VN_TZ)  # 🔥 FIX

        # 🔥 CACHE
        if self._cache_data and self._cache_time:
            delta = (now - self._cache_time).total_seconds()
            if delta < self._cache_ttl:
                logger.info("⚡ Return cached predictions")
                return self._cache_data

        roads = self._get_all_roads(db)
        history_df = self._get_all_history(db)

        if history_df.empty:
            return [{"error": "Không có dữ liệu lịch sử"}]

        grouped = history_df.groupby("road_id")

        results = []

        for road in roads:
            try:
                road_id = road["road_id"]

                if road_id not in grouped.groups:
                    continue

                road_df = grouped.get_group(road_id)

                X = self._build_feature_from_df(road_df)
                X_scaled = self._scaler.transform(X)

                pred  = int(self._model.predict(X_scaled)[0])
                proba = self._model.predict_proba(X_scaled)[0]
                conf  = round(float(proba.max()), 3)

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