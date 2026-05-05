from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
from services.routing import get_route

router = APIRouter()


@router.get(
    "/routes",
    summary="[Task 38] Tìm đường ngắn/nhanh nhất (A*)",
    tags=["Route"],
)
def find_route_api(
    from_lat: float   = Query(..., description="Vĩ độ điểm xuất phát"),
    from_lng: float   = Query(..., description="Kinh độ điểm xuất phát"),
    to_lat  : float   = Query(..., description="Vĩ độ điểm đích"),
    to_lng  : float   = Query(..., description="Kinh độ điểm đích"),
    mode    : str     = Query("shortest", description="shortest | fastest"),
    db      : Session = Depends(get_db),
):
    result = get_route(from_lat, from_lng, to_lat, to_lng, mode=mode, db_session=db)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result