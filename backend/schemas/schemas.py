class TrafficRecord(BaseModel):
    road_id: int
    road_name: str
    lat: float
    lng: float
    speed: float          # km/h
    congestion_level: int # 1=xanh, 2=vàng, 3=đỏ
    updated_at: datetime