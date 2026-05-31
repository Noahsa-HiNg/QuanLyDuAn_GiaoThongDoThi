# backend/routers/predict.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from database import get_db
from services.prediction_service import prediction_service, HorizonKey
import schemas

# prefix="/predict" + main.py prefix="/api" → /api/predict/...
router = APIRouter(prefix="/predict", tags=["Predict"])


# ── HELPER ────────────────────────────────────────────────────────────────────
def _check_ready(horizon: HorizonKey):
    if not prediction_service.is_ready(horizon):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Model [{horizon}] chưa sẵn sàng. Vui lòng chạy train trước.",
        )


# ── PREDICT ALL ROADS ─────────────────────────────────────────────────────────

@router.get("/10min", response_model=List[schemas.PredictedRecord], summary="Dự đoán tất cả đường — 10 phút tới")
async def predict_all_10min(db: Session = Depends(get_db)):
    _check_ready("10min")
    try:
        return prediction_service.predict_all(db, horizon="10min")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))


@router.get("/20min", response_model=List[schemas.PredictedRecord], summary="Dự đoán tất cả đường — 20 phút tới")
async def predict_all_20min(db: Session = Depends(get_db)):
    _check_ready("20min")
    try:
        return prediction_service.predict_all(db, horizon="20min")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))


@router.get("/30min", response_model=List[schemas.PredictedRecord], summary="Dự đoán tất cả đường — 30 phút tới")
async def predict_all_30min(db: Session = Depends(get_db)):
    _check_ready("30min")
    try:
        return prediction_service.predict_all(db, horizon="30min")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))


@router.get("/all-horizons", summary="Dự đoán tất cả đường × cả 3 khung giờ")
async def predict_all_horizons(db: Session = Depends(get_db)):
    ready = prediction_service.ready_horizons()
    if not ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Chưa có model nào sẵn sàng. Vui lòng chạy train trước.",
        )

@router.get("/30min/{road_id}")
async def predict_one(road_id: int, db: Session = Depends(get_db)):
    if not prediction_service.is_ready:
        raise HTTPException(status_code=503, detail="Model chưa sẵn sàng.")
    try:
        return prediction_service.predict_all_horizons(db)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(e))


# ── PREDICT 1 ROAD ────────────────────────────────────────────────────────────

@router.get("/10min/{road_id}", summary="Dự đoán 1 đường — 10 phút tới")
async def predict_one_10min(road_id: int, db: Session = Depends(get_db)):
    _check_ready("10min")
    result = prediction_service.predict(road_id, db, horizon="10min")
    if "error" in result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=result["error"])
    return result


@router.get("/20min/{road_id}", summary="Dự đoán 1 đường — 20 phút tới")
async def predict_one_20min(road_id: int, db: Session = Depends(get_db)):
    _check_ready("20min")
    result = prediction_service.predict(road_id, db, horizon="20min")
    if "error" in result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=result["error"])
    return result


@router.get("/30min/{road_id}", summary="Dự đoán 1 đường — 30 phút tới")
async def predict_one_30min(road_id: int, db: Session = Depends(get_db)):
    _check_ready("30min")
    result = prediction_service.predict(road_id, db, horizon="30min")
    if "error" in result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=result["error"])
    return result


# ── METRICS ───────────────────────────────────────────────────────────────────

@router.get("/metrics", summary="Metrics tất cả models")
async def get_all_metrics():
    return prediction_service.get_model_metrics()


@router.get("/metrics/{horizon}", summary="Metrics của 1 horizon cụ thể (10min | 20min | 30min)")
async def get_metrics_by_horizon(horizon: HorizonKey):
    result = prediction_service.get_model_metrics(horizon=horizon)
    if "error" in result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=result["error"])
    return result


# ── STATUS ────────────────────────────────────────────────────────────────────

@router.get("/status", summary="Trạng thái các models")
async def get_model_status():
    return {
        horizon: {
            "ready":  prediction_service.is_ready(horizon),
            "label":  cfg["label"],
        }
        for horizon, cfg in __import__("services.prediction_service", fromlist=["HORIZONS"]).HORIZONS.items()
    }