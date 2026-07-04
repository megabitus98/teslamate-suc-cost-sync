import pytest
from suc_cost_sync.config import load_config


def test_defaults(monkeypatch):
    monkeypatch.setenv("TESLAMATE_DB_DSN", "postgresql://u@h/teslamate")
    for k in ("CAR_ID", "BACKFILL_SINCE", "SUC_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    cfg = load_config()
    assert cfg.suc_base_url == "https://suc.nitu.it"
    assert cfg.poll_interval_s == 300
    assert cfg.site_match_radius_km == 0.5
    assert cfg.energy_source == "used"
    assert cfg.target_currency == "RON"
    assert cfg.refresh_geofence_rate is True
    assert cfg.respect_manual_edits is True
    assert cfg.backfill_on_start is True
    assert cfg.dry_run is False and cfg.force is False
    assert cfg.car_id is None and cfg.suc_api_key is None


def test_overrides(monkeypatch):
    monkeypatch.setenv("TESLAMATE_DB_DSN", "dsn")
    monkeypatch.setenv("CAR_ID", "2")
    monkeypatch.setenv("ENERGY_SOURCE", "ADDED")
    monkeypatch.setenv("TARGET_CURRENCY", "eur")
    monkeypatch.setenv("DRY_RUN", "true")
    monkeypatch.setenv("REFRESH_GEOFENCE_RATE", "false")
    cfg = load_config()
    assert cfg.car_id == 2
    assert cfg.energy_source == "added"
    assert cfg.target_currency == "EUR"
    assert cfg.dry_run is True
    assert cfg.refresh_geofence_rate is False


def test_missing_dsn_exits(monkeypatch):
    monkeypatch.delenv("TESLAMATE_DB_DSN", raising=False)
    with pytest.raises(SystemExit):
        load_config()


def test_bad_energy_source_exits(monkeypatch):
    monkeypatch.setenv("TESLAMATE_DB_DSN", "dsn")
    monkeypatch.setenv("ENERGY_SOURCE", "wat")
    with pytest.raises(SystemExit):
        load_config()
