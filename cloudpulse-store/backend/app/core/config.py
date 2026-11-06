import os
from dataclasses import dataclass, field


def _split_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    app_name: str = os.getenv("APP_NAME", "CloudPulse Store API")
    service_name: str = os.getenv("SERVICE_NAME", "cloudpulse-store-backend")
    app_version: str = os.getenv("APP_VERSION", "1.0.0")
    environment: str = os.getenv("ENVIRONMENT", "development")
    log_level: str = os.getenv("LOG_LEVEL", "INFO").upper()

    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./data/cloudpulse.db")

    seed_on_startup: bool = os.getenv("SEED_ON_STARTUP", "true").lower() == "true"

    # Only needed when the frontend is served from a different origin
    # (e.g. `npm run dev` on port 5173). Behind Nginx everything is same-origin.
    cors_origins: list[str] = field(
        default_factory=lambda: _split_csv(
            os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
        )
    )


settings = Settings()
