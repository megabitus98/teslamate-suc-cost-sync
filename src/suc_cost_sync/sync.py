import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from . import db, geo
from . import pricing as P

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Correction:
    charge_id: int
    location_guid: str
    tou_rate: float
    energy_kwh: float
    site_currency: str
    cost_local: float
    fx_factor: float
    fx_date: str
    cost_target: Decimal
    congestion_flagged: bool


def compute_correction(*, charge_id, charging, site_currency, tz_name, start_utc,
                       energy_kwh, fx_factor, fx_date, location_guid,
                       congestion_flagged) -> Correction:
    local = start_utc.astimezone(ZoneInfo(tz_name))
    rate = P.select_rate(local.hour * 60 + local.minute, charging)
    cost_local = rate * energy_kwh
    cost_target = Decimal(f"{cost_local * fx_factor:.2f}")
    return Correction(charge_id, location_guid, rate, energy_kwh, site_currency,
                      round(cost_local, 4), fx_factor, fx_date, cost_target,
                      congestion_flagged)


def should_process(logged, db_cost, logged_cost, respect_manual_edits, force) -> bool:
    if not logged:
        return True
    changed = db_cost is None or logged_cost is None or \
        abs(Decimal(str(db_cost)) - Decimal(str(logged_cost))) > Decimal("0.005")
    if not changed:
        return False          # we wrote it, untouched -> skip
    if force:
        return True
    return not respect_manual_edits   # changed externally


def _congestion_flagged(pricing_obj: dict) -> bool:
    c = pricing_obj.get("congestion") or {}
    return bool(c.get("rate_per_minute"))


def _mark(cfg, conn, charge_id, reason) -> None:
    """Persist a permanent not-applicable marker, unless in dry-run."""
    if not cfg.dry_run:
        db.mark_skip(conn, charge_id, reason)


def process_charge(cfg, conn, suc, fx, row) -> str:
    try:
        if not should_process(row["logged"], row["cost"], row["logged_cost"],
                              cfg.respect_manual_edits, cfg.force):
            return "skip:idempotent"

        lat, lng = row["latitude"], row["longitude"]
        if lat is None or lng is None:
            _mark(cfg, conn, row["id"], "no-position")
            return "skip:no-position"

        site = geo.choose_site(suc.nearby(lat, lng, cfg.site_match_radius_km),
                              cfg.site_match_radius_km)
        if site is None:
            _mark(cfg, conn, row["id"], "not-suc")
            return "skip:not-suc"
        guid = site["location_guid"]

        energy = row["charge_energy_used"] if cfg.energy_source == "used" else row["charge_energy_added"]
        if energy is None:
            return "skip:no-energy"

        current = suc.pricing(guid)
        charging_now = current["charging"]
        site_ccy = charging_now["currency_code"]

        start_utc = row["start_date"]
        if start_utc.tzinfo is None:           # TeslaMate stores naive UTC
            start_utc = start_utc.replace(tzinfo=timezone.utc)

        snapshots = suc.history(guid)
        snap = P.select_snapshot(snapshots, start_utc)
        if snap is None and snapshots:
            # charge predates the earliest SUC pricing snapshot -> the rate of
            # that era cannot be substantiated; leave TeslaMate's cost untouched.
            _mark(cfg, conn, row["id"], "pre-history")
            return "skip:pre-history"
        charging_for_rate = snap["pricing"]["charging"] if snap else charging_now

        tz_name = geo.site_timezone(site["centroid"]["latitude"], site["centroid"]["longitude"])
        if tz_name is None:
            return "skip:no-timezone"

        try:
            factor, fx_date = fx.factor(start_utc.date().isoformat(), site_ccy, cfg.target_currency)
        except Exception as e:                 # never write a guessed number
            log.warning("charge %s: FX lookup failed (%s) -> skip", row["id"], e)
            return "skip:fx-fail"

        if _congestion_flagged(current):
            log.info("charge %s: site %s has congestion pricing; computed cost may be under actual",
                     row["id"], guid)

        corr = compute_correction(
            charge_id=row["id"], charging=charging_for_rate, site_currency=site_ccy,
            tz_name=tz_name, start_utc=start_utc, energy_kwh=float(energy),
            fx_factor=factor, fx_date=fx_date, location_guid=guid,
            congestion_flagged=_congestion_flagged(current),
        )

        if cfg.dry_run:
            log.info("DRY_RUN charge %s: %.2f %s -> %s %s (rate %.4f, factor %.4f)",
                     row["id"], corr.cost_local, site_ccy, corr.cost_target,
                     cfg.target_currency, corr.tou_rate, factor)
            return "dry-run"

        with conn.transaction():
            db.write_correction(conn, corr, cfg.energy_source)
            if cfg.refresh_geofence_rate and row["geofence_id"] is not None:
                peak_target = round(P.peak_rate(charging_now) * factor, 4)
                db.refresh_geofence(conn, row["geofence_id"], peak_target)
        log.info("charge %s: wrote %s %s", row["id"], corr.cost_target, cfg.target_currency)
        return "written"
    except Exception:
        log.exception("charge %s: unexpected error -> skip", row.get("id"))
        return "skip:error"
