from datetime import datetime, timezone
from decimal import Decimal

import httpx

from suc_cost_sync.config import Config
from suc_cost_sync.fx import FxCache
from suc_cost_sync.suc_client import SucClient
from suc_cost_sync.sync import compute_correction, process_charge, should_process

CHARGING = {
    "currency_code": "RON", "tou_enabled": True, "rates": [2.22],
    "tou_rates": [
        {"start_time": "00:00", "end_time": "08:00", "rates": [1.47]},
        {"start_time": "08:00", "end_time": "24:00", "rates": [2.22]},
    ],
}


def _compute(start_utc, energy=10.0, factor=1.0, congestion=False):
    return compute_correction(
        charge_id=1, charging=CHARGING, site_currency="RON",
        tz_name="Europe/Bucharest", start_utc=start_utc, energy_kwh=energy,
        fx_factor=factor, fx_date="2026-05-20", location_guid="g",
        congestion_flagged=congestion,
    )


def test_offpeak_local_time():
    # 05:30 UTC = 08:30 Bucharest (DST +3) -> peak 2.22
    c = _compute(datetime(2026, 5, 20, 5, 30, tzinfo=timezone.utc))
    assert c.tou_rate == 2.22
    assert c.cost_target == Decimal("22.20")


def test_offpeak_before_local_0800():
    # 04:30 UTC = 07:30 Bucharest -> off-peak 1.47
    c = _compute(datetime(2026, 5, 20, 4, 30, tzinfo=timezone.utc))
    assert c.tou_rate == 1.47
    assert c.cost_target == Decimal("14.70")


def test_fx_applied_and_rounded():
    c = _compute(datetime(2026, 5, 20, 4, 30, tzinfo=timezone.utc), energy=10.0, factor=5.2325)
    # 1.47 * 10 * 5.2325 = 76.91775 -> 76.92
    assert c.cost_target == Decimal("76.92")


def test_congestion_flag_passthrough():
    assert _compute(datetime(2026, 5, 20, 4, 30, tzinfo=timezone.utc), congestion=True).congestion_flagged is True


def test_should_process_unseen():
    assert should_process(False, None, None, True, False) is True


def test_should_process_unchanged_skips():
    assert should_process(True, Decimal("22.20"), Decimal("22.20"), True, False) is False


def test_should_process_external_edit_respected():
    assert should_process(True, Decimal("9.99"), Decimal("22.20"), True, False) is False


def test_should_process_external_edit_forced():
    assert should_process(True, Decimal("9.99"), Decimal("22.20"), True, True) is True


def test_should_process_external_edit_not_respected():
    assert should_process(True, Decimal("9.99"), Decimal("22.20"), False, False) is True


# --- process_charge pre-history boundary (dry-run so no DB needed) ---

GUID = "g"
SNAP_2026_04 = {"captured_at": "2026-04-01T17:00:00Z",
                "pricing": {"charging": CHARGING}}


def _suc(history_snapshots):
    def handler(req):
        p = req.url.path
        if p == "/api/v1/sites/nearby":
            return httpx.Response(200, json={"sites": [{
                "location_guid": GUID, "distance_miles": 0.05,
                "centroid": {"latitude": 44.441037, "longitude": 26.15441}}]})
        if p == f"/api/v1/pricing/{GUID}":
            return httpx.Response(200, json={"charging": dict(CHARGING, currency_code="RON"),
                                             "congestion": {}})
        if p == f"/api/v1/history/pricing/{GUID}":
            return httpx.Response(200, json={"snapshots": history_snapshots})
        raise AssertionError(p)
    return SucClient("https://suc", None, httpx.Client(transport=httpx.MockTransport(handler)))


def _cfg():
    return Config(
        teslamate_dsn="x", suc_base_url="https://suc", suc_api_key=None, car_id=None,
        poll_interval_s=300, site_match_radius_km=0.5, energy_source="used",
        target_currency="RON", fx_base_url="https://fx", refresh_geofence_rate=True,
        respect_manual_edits=True, backfill_on_start=True, backfill_since=None,
        dry_run=True, force=False, log_level="INFO")


def _row(start_utc):
    return {"id": 1, "start_date": start_utc, "charge_energy_used": 10.0,
            "charge_energy_added": 9.0, "cost": None, "car_id": 1, "geofence_id": None,
            "latitude": 44.441, "longitude": 26.154, "logged": False, "logged_cost": None}


def _fx():
    return FxCache("https://fx", httpx.Client(transport=httpx.MockTransport(
        lambda r: httpx.Response(200, json=[]))))


def test_pre_history_charge_is_skipped():
    # charge in 2024, only a 2026-04 snapshot exists -> predates history -> skip
    suc = _suc([SNAP_2026_04])
    result = process_charge(_cfg(), None, suc, _fx(), _row(datetime(2024, 6, 1, tzinfo=timezone.utc)))
    assert result == "skip:pre-history"


def test_charge_after_snapshot_is_priced():
    # charge after the snapshot -> priced (dry-run path)
    suc = _suc([SNAP_2026_04])
    result = process_charge(_cfg(), None, suc, _fx(), _row(datetime(2026, 5, 1, 12, tzinfo=timezone.utc)))
    assert result == "dry-run"
