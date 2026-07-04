from datetime import datetime, timezone
from suc_cost_sync.pricing import parse_hhmm, select_rate, peak_rate, select_snapshot

# Real Mega Mall shape (verified 2026-06-25): off-peak 1.47, peak 2.22, end "24:00".
CHARGING = {
    "currency_code": "RON",
    "tou_enabled": True,
    "rates": [2.22],
    "tou_rates": [
        {"start_time": "00:00", "end_time": "04:00", "rates": [1.47]},
        {"start_time": "04:00", "end_time": "08:00", "rates": [1.47]},
        {"start_time": "08:00", "end_time": "24:00", "rates": [2.22]},
    ],
}
FLAT = {"currency_code": "RON", "tou_enabled": False, "rates": [2.22], "tou_rates": []}
WRAP = {  # synthetic: window crossing midnight
    "currency_code": "EUR", "tou_enabled": True, "rates": [0.5],
    "tou_rates": [
        {"start_time": "22:00", "end_time": "06:00", "rates": [0.2]},
        {"start_time": "06:00", "end_time": "22:00", "rates": [0.5]},
    ],
}


def test_parse_hhmm():
    assert parse_hhmm("00:00") == 0
    assert parse_hhmm("08:00") == 480
    assert parse_hhmm("24:00") == 1440


def test_offpeak():
    assert select_rate(parse_hhmm("02:00"), CHARGING) == 1.47


def test_peak():
    assert select_rate(parse_hhmm("12:00"), CHARGING) == 2.22


def test_boundary_0800_is_peak():           # [start, end): 08:00 belongs to peak
    assert select_rate(parse_hhmm("08:00"), CHARGING) == 2.22


def test_boundary_0000_is_offpeak():
    assert select_rate(0, CHARGING) == 1.47


def test_end_2400_covers_2359():
    assert select_rate(parse_hhmm("23:59"), CHARGING) == 2.22


def test_flat_fallback():
    assert select_rate(parse_hhmm("03:00"), FLAT) == 2.22


def test_wrap_before_midnight():
    assert select_rate(parse_hhmm("23:00"), WRAP) == 0.2


def test_wrap_after_midnight():
    assert select_rate(parse_hhmm("02:00"), WRAP) == 0.2


def test_peak_rate():
    assert peak_rate(CHARGING) == 2.22
    assert peak_rate(FLAT) == 2.22


def test_select_snapshot_picks_latest_le_start():
    snaps = [
        {"captured_at": "2026-04-01T17:00:00Z", "peak_rate": 2.15},
        {"captured_at": "2026-04-28T21:00:00Z", "peak_rate": 2.16},
        {"captured_at": "2026-05-20T21:00:00Z", "peak_rate": 2.22},
    ]
    start = datetime(2026, 5, 1, tzinfo=timezone.utc)
    assert select_snapshot(snaps, start)["peak_rate"] == 2.16


def test_select_snapshot_older_than_history_returns_none():
    # charge predates the earliest snapshot -> not substantiable -> None (skip)
    snaps = [{"captured_at": "2026-04-01T17:00:00Z", "peak_rate": 2.15}]
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert select_snapshot(snaps, start) is None


def test_select_snapshot_newer_than_all_uses_latest():
    snaps = [
        {"captured_at": "2026-04-01T17:00:00Z", "peak_rate": 2.15},
        {"captured_at": "2026-05-20T21:00:00Z", "peak_rate": 2.22},
    ]
    start = datetime(2026, 6, 1, tzinfo=timezone.utc)  # fresh charge, after all snapshots
    assert select_snapshot(snaps, start)["peak_rate"] == 2.22


def test_select_snapshot_empty():
    assert select_snapshot([], datetime(2026, 1, 1, tzinfo=timezone.utc)) is None
