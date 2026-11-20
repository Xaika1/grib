import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


class Settings:
    def __init__(self) -> None:
        self.database_url = os.getenv("GRIB_DATABASE_URL", f"sqlite:///{ROOT / 'server' / 'grib.db'}")
        self.secret_key = os.getenv("GRIB_SECRET_KEY", "dev-secret-change-me-dev-secret-change-me")
        self.token_ttl_minutes = int(os.getenv("GRIB_TOKEN_TTL_MINUTES", "720"))

        self.admin_login = os.getenv("GRIB_ADMIN_LOGIN", "admin")
        self.admin_password = os.getenv("GRIB_ADMIN_PASSWORD", "admin")

        self.query_timeout_sec = float(os.getenv("GRIB_QUERY_TIMEOUT", "10"))
        self.query_max_rows = int(os.getenv("GRIB_QUERY_MAX_ROWS", "10000"))
        self.query_pool_size = int(os.getenv("GRIB_QUERY_POOL_SIZE", "8"))
        self.sqlite_dir = Path(os.getenv("GRIB_SQLITE_DIR", str(ROOT / "demo" / "data")))

        self.scheduler_enabled = _bool("GRIB_SCHEDULER", True)
        self.scheduler_tick_sec = float(os.getenv("GRIB_SCHEDULER_TICK", "1"))
        self.min_collector_interval_sec = int(os.getenv("GRIB_MIN_COLLECTOR_INTERVAL", "5"))
        self.sample_retention_days = int(os.getenv("GRIB_SAMPLE_RETENTION_DAYS", "30"))

        self.static_dir = Path(os.getenv("GRIB_STATIC_DIR", str(ROOT / "client" / "www")))
        self.cors_origins = [o.strip() for o in os.getenv("GRIB_CORS_ORIGINS", "*").split(",") if o.strip()]


settings = Settings()
