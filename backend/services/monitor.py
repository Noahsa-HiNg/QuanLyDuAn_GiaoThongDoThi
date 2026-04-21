import logging
from backend.config import settings  # Giả sử settings có redis_host, redis_port
import redis

logger = logging.getLogger(__name__)

TOMTOM_DAILY_LIMIT = 2500

class APIMonitor:
    def __init__(self):
        self.r = redis.Redis(host=settings.redis_host, port=settings.redis_port, decode_responses=True)

    def check_budget(self) -> dict:
        count = int(self.r.get("api:tomtom:count") or 0)
        pct = (count / TOMTOM_DAILY_LIMIT) * 100
        status = "critical" if pct >= 100 else "warning" if pct >= 80 else "ok"
        return {"count": count, "limit": TOMTOM_DAILY_LIMIT, "pct": pct, "status": status}

    def log_budget_status(self):
        status = self.check_budget()
        if status["status"] == "warning":
            logger.warning(f"TomTom API {status['pct']:.0f}% quota used ({status['count']}/{status['limit']})")
        elif status["status"] == "critical":
            logger.error(f"TomTom API quota exceeded ({status['count']}/{status['limit']}). Switching to mock data.")

# Instance global
monitor = APIMonitor()