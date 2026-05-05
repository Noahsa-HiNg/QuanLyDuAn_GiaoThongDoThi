# backend/routers/predict.py  ← A viết file này
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from database import get_db
from services.prediction_service import prediction_service
import schemas

router = APIRouter(prefix="/api", tags=["predict"])

@router.get("/predict/30min", response_model=List[schemas.PredictedRecord])
async def predict_30min(db: Session = Depends(get_db)):
    if not prediction_service.is_ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Model chưa sẵn sàng. Vui lòng chạy train trước."
        )
    return prediction_service.predict_all(db)

@router.get("/predict/30min/{road_id}")
async def predict_one(road_id: int, db: Session = Depends(get_db)):
    if not prediction_service.is_ready:
        raise HTTPException(status_code=503, detail="Model chưa sẵn sàng.")
    try:
        return prediction_service.predict(road_id, db)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.get("/predict/metrics")
async def get_metrics():
    return prediction_service.get_model_metrics()