from pydantic_settings import BaseSettings


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
    tomtom_api_key: str = ""     # Đăng ký tại developer.tomtom.com (2500 req/ngày free)
    goong_api_key: str = ""      # Đăng ký tại docs.goong.io      (1000 req/ngày free)

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()