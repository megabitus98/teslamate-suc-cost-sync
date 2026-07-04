import os
from dataclasses import dataclass


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class Config:
    teslamate_dsn: str
    suc_base_url: str
    suc_api_key: str | None
    car_id: int | None
    poll_interval_s: int
    site_match_radius_km: float
    energy_source: str
    target_currency: str
    fx_base_url: str
    refresh_geofence_rate: bool
    respect_manual_edits: bool
    backfill_on_start: bool
    backfill_since: str | None
    dry_run: bool
    force: bool
    log_level: str


def load_config() -> Config:
    dsn = os.getenv("TESLAMATE_DB_DSN")
    if not dsn:
        raise SystemExit("TESLAMATE_DB_DSN is required")
    energy = os.getenv("ENERGY_SOURCE", "used").strip().lower()
    if energy not in ("used", "added"):
        raise SystemExit("ENERGY_SOURCE must be 'used' or 'added'")
    car = os.getenv("CAR_ID")
    return Config(
        teslamate_dsn=dsn,
        suc_base_url=os.getenv("SUC_API_BASE_URL", "https://suc.nitu.it").rstrip("/"),
        suc_api_key=os.getenv("SUC_API_KEY") or None,
        car_id=int(car) if car else None,
        poll_interval_s=int(os.getenv("POLL_INTERVAL_SECONDS", "300")),
        site_match_radius_km=float(os.getenv("SITE_MATCH_RADIUS_KM", "0.5")),
        energy_source=energy,
        target_currency=os.getenv("TARGET_CURRENCY", "RON").upper(),
        fx_base_url=os.getenv("FX_API_BASE_URL", "https://api.frankfurter.dev").rstrip("/"),
        refresh_geofence_rate=_bool("REFRESH_GEOFENCE_RATE", True),
        respect_manual_edits=_bool("RESPECT_MANUAL_EDITS", True),
        backfill_on_start=_bool("BACKFILL_ON_START", True),
        backfill_since=os.getenv("BACKFILL_SINCE") or None,
        dry_run=_bool("DRY_RUN", False),
        force=_bool("FORCE", False),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
    )
