from pydantic_settings import BaseSettings
from pydantic import ConfigDict


class Settings(BaseSettings):
    # --- Cấu hình PostgreSQL ---
    postgres_user: str
    postgres_password: str
    postgres_db: str
    postgres_host: str = "postgres"  # Tên service trong docker-compose
    postgres_port: int = 5432

    # --- Cấu hình Redis ---
    redis_host: str = "redis"        # Tên service trong docker-compose
    redis_port: int = 6379

    # --- Cấu hình JWT (bảo mật đăng nhập) ---
    jwt_secret_key: str = "change-this-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_hours: int = 8

    # --- API Keys traffic ---
    # Single key (backward-compat)
    tomtom_api_key: str = ""     # Key chính
    goong_api_key: str = ""      # Đăng ký tại docs.goong.io (1000 req/ngày free)

    # Multi-key TomTom: điền nhiều key cách nhau bằng dấu phẩy
    # Ví dụ: TOMTOM_API_KEYS=key1,key2,key3
    # Hệ thống tự động luân phiên key khi 1 key hết quota
    tomtom_api_keys: str = ""    # Danh sách key, ngăn cách bằng dấu phẩy

    @property
    def tomtom_keys_list(self) -> list[str]:
        """
        Trả về list tất cả TomTom key hợp lệ.
        Ưu tiên TOMTOM_API_KEYS (multi), fallback về TOMTOM_API_KEY (single).
        """
        # Từ TOMTOM_API_KEYS (multi-key)
        if self.tomtom_api_keys:
            keys = [k.strip() for k in self.tomtom_api_keys.split(",") if k.strip()]
            if keys:
                return keys
        # Fallback: TOMTOM_API_KEY (single)
        if self.tomtom_api_key:
            return [self.tomtom_api_key]
        return []

    model_config = ConfigDict(env_file=".env", case_sensitive=False, extra='ignore')


settings = Settings()