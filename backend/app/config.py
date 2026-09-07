from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "ERP Manufaktur API"
    api_prefix: str = "/api/v1"
    database_url: str = "postgresql+asyncpg://erp:erp_dev_password@localhost:5432/erp_manufaktur"
    jwt_secret: str = "development-only-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 480
    business_timezone: str = "Asia/Jakarta"
    purchasing_department_code: str = "PURCHASING"
    sales_department_code: str = "SALES"
    warehouse_department_code: str = "WAREHOUSE"
    production_department_code: str = "PRODUCTION"
    quality_department_code: str = "QUALITY"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000", "http://localhost:8080"])
    first_admin_email: str = "admin@example.com"
    first_admin_password: str = "Admin123!"
    first_admin_first_name: str = "System"
    first_admin_last_name: str = "Administrator"

    @field_validator("database_url", mode="before")
    @classmethod
    def async_database_url(cls, value: str) -> str:
        """Accept managed-Postgres URLs while keeping SQLAlchemy async."""
        value = str(value)
        if value.startswith("postgres://"):
            return "postgresql+asyncpg://" + value.removeprefix("postgres://")
        if value.startswith("postgresql://"):
            return "postgresql+asyncpg://" + value.removeprefix("postgresql://")
        return value

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
