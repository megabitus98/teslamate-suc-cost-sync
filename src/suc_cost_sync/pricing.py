from dataclasses import dataclass
from datetime import datetime


def parse_hhmm(s: str) -> int:
    h, m = s.split(":")
    return int(h) * 60 + int(m)  # "24:00" -> 1440


@dataclass(frozen=True)
class _Window:
    start: int
    end: int
    rate: float


def _windows(tou_rates: list[dict]) -> list[_Window]:
    return [
        _Window(parse_hhmm(w["start_time"]), parse_hhmm(w["end_time"]), float(w["rates"][0]))
        for w in tou_rates
    ]


def select_rate(local_minute: int, charging: dict) -> float:
    """Per-kWh rate for the half-open [start, end) window containing local_minute.
    Falls back to flat rates[0] when TOU disabled or no window matches."""
    if charging.get("tou_enabled") and charging.get("tou_rates"):
        for w in _windows(charging["tou_rates"]):
            if w.start <= w.end:  # normal window
                if w.start <= local_minute < w.end:
                    return w.rate
            else:  # wraps midnight, e.g. 22:00-06:00
                if local_minute >= w.start or local_minute < w.end:
                    return w.rate
    return float(charging["rates"][0])


def peak_rate(charging: dict) -> float:
    if charging.get("tou_enabled") and charging.get("tou_rates"):
        return max(float(w["rates"][0]) for w in charging["tou_rates"])
    return float(charging["rates"][0])


def _ts(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def select_snapshot(snapshots: list[dict], start_utc: datetime) -> dict | None:
    """Latest history snapshot captured at or before start_utc.
    Returns None when there are no snapshots OR the charge predates them all
    (caller distinguishes the two: empty history -> use current pricing;
    pre-history -> skip, since no rate of that era can be substantiated)."""
    eligible = [s for s in snapshots if _ts(s["captured_at"]) <= start_utc]
    if not eligible:
        return None
    return max(eligible, key=lambda s: _ts(s["captured_at"]))
