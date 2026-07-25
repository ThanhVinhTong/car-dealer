from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Config:
    database_url: str
    cars_table: str
    price_history_table: str
    price_history_price_column: str
    price_history_recorded_at_column: str
    scraper_source: str
    marketplace_location: str
    min_price: int
    export_dir: str
    log_level: str
    headless: bool
    request_delay_seconds: float
    max_results_per_search_url: int


def load_config(env_file: str | Path | None = ".env") -> Config:
    """Load runtime configuration from environment variables and optional .env."""
    if env_file is not None:
        _load_dotenv_if_available(Path(env_file))

    database_url = _required("DATABASE_URL")
    marketplace_location = _required("MARKETPLACE_LOCATION").strip().strip("/")

    if not marketplace_location:
        raise ValueError("MARKETPLACE_LOCATION must not be empty")

    return Config(
        database_url=database_url,
        cars_table=os.getenv("CARS_TABLE", "cars").strip() or "cars",
        price_history_table=(
            os.getenv("PRICE_HISTORY_TABLE", "car_price_history").strip()
            or "car_price_history"
        ),
        price_history_price_column=(
            os.getenv("PRICE_HISTORY_PRICE_COLUMN", "price_aud").strip()
            or "price_aud"
        ),
        price_history_recorded_at_column=(
            os.getenv("PRICE_HISTORY_RECORDED_AT_COLUMN", "recorded_at").strip()
            or "recorded_at"
        ),
        scraper_source=os.getenv("SCRAPER_SOURCE", "facebook_marketplace").strip()
        or "facebook_marketplace",
        marketplace_location=marketplace_location,
        min_price=_int_env("MIN_PRICE"),
        export_dir=os.getenv("EXPORT_DIR", "exports").strip() or "exports",
        log_level=os.getenv("LOG_LEVEL", "INFO").strip() or "INFO",
        headless=_bool_env("HEADLESS", default=True),
        request_delay_seconds=_float_env("REQUEST_DELAY_SECONDS", default=2.0),
        max_results_per_search_url=_int_env(
            "MAX_RESULTS_PER_SEARCH_URL", default=50
        ),
    )


def _load_dotenv_if_available(path: Path) -> None:
    if not path.exists():
        return

    try:
        from dotenv import load_dotenv
    except ImportError:
        _load_dotenv_fallback(path)
        return

    load_dotenv(path, override=False)


def _load_dotenv_fallback(path: Path) -> None:
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue

        os.environ[key] = value.strip().strip('"').strip("'")


def _required(name: str) -> str:
    value = os.getenv(name)
    if value is None or not value.strip():
        raise ValueError(f"{name} must be set")
    return value.strip()


def _int_env(name: str, default: int | None = None) -> int:
    value = os.getenv(name)
    if value is None or not value.strip():
        if default is None:
            raise ValueError(f"{name} must be set")
        return default

    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc


def _float_env(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default

    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number") from exc


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default

    return value.strip().lower() in {"1", "true", "yes", "y", "on"}
