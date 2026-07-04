# teslamate-suc-cost-sync

Standalone Docker service that corrects TeslaMate Supercharger charge costs using
**time-of-use (TOU) pricing** from the `suc.nitu.it` Tesla Supercharger API.

A TeslaMate geofence can only hold one flat per-kWh rate, so off-peak sessions get
over-charged at the peak rate. This service recomputes each Supercharger session's
cost from the TOU window containing its **start time** (in the site's local
timezone — Tesla locks the rate at charge start), converts it to a single display
currency, and writes the corrected value onto `charging_processes.cost`. No changes
to TeslaMate itself.

## How it works

A sequential poll loop, every `POLL_INTERVAL_SECONDS`:

1. Read completed Supercharger charges from TeslaMate Postgres.
2. Map each charge's start coordinates → a SUC `location_guid` (`/sites/nearby`).
3. Pick the TOU rate for the window containing the charge's **site-local** start
   time (current pricing for fresh charges; nearest historical snapshot ≤ start
   for backfill).
4. `cost = rate × energy`, convert to `TARGET_CURRENCY` (Frankfurter, charge-date
   rate), round to 2 decimals, write it — plus an audit/idempotency row in
   `suc_cost_sync_log`, both in one transaction.
5. Optionally refresh the matched geofence's flat rate to the site's current peak
   (converted) — a sane fallback for TeslaMate's own estimates.

Site timezone is derived offline from the site's lat/lng (`tzfpy`); the SUC API
carries no timezone. Energy comes from `charge_energy_used` (what the charger
metered) by default. Congestion fees are out of scope — when a site has them, a
log note warns the computed cost may be slightly under actual.

Charges that **predate the SUC pricing history** (the `/history/pricing` endpoint
only goes back so far) are left untouched — no rate from that era can be
substantiated, so the existing TeslaMate cost is preserved rather than overwritten
with a guess. Use `BACKFILL_SINCE` to additionally bound how far back to look.

The service creates two small tables in the TeslaMate DB: `suc_cost_sync_log`
(audit + idempotency, one row per corrected charge) and `suc_cost_sync_skip`
(charges with no Supercharger nearby, or predating SUC pricing history — recorded
once with a reason so they aren't re-queried against the SUC API on every poll).
A steady-state poll with no new charges makes zero SUC API calls.

## Quick start

```bash
# 1. First backfill in DRY_RUN — review intended changes, write nothing
docker compose up --build        # DRY_RUN=true is the compose default

# 2. Happy with the logged numbers? Set DRY_RUN=false and restart.
```

The service writes nothing on a guess: any SUC or FX lookup failure logs and skips
that charge, retried on the next poll.

## Configuration (env vars)

| Var | Default | Purpose |
|---|---|---|
| `TESLAMATE_DB_DSN` | — (required) | Postgres connection to TeslaMate. |
| `SUC_API_BASE_URL` | `https://suc.nitu.it` | SUC API base. |
| `SUC_API_KEY` | (none) | Optional; core path is public. |
| `CAR_ID` | (all) | Optional car filter. |
| `POLL_INTERVAL_SECONDS` | `300` | Poll cadence. |
| `SITE_MATCH_RADIUS_KM` | `0.5` | Max distance to treat a charge as a SUC site. |
| `ENERGY_SOURCE` | `used` | `used` (`charge_energy_used`) or `added` (`charge_energy_added`). |
| `TARGET_CURRENCY` | `RON` | Currency all costs are normalized to (match TeslaMate's display currency). |
| `FX_API_BASE_URL` | `https://api.frankfurter.dev` | Frankfurter v2 FX API base. |
| `REFRESH_GEOFENCE_RATE` | `true` | Refresh matched geofence's flat rate to current peak (converted). |
| `RESPECT_MANUAL_EDITS` | `true` | Skip charges whose cost was changed externally. |
| `BACKFILL_ON_START` | `true` | Backfill past charges on startup (else only new charges). |
| `BACKFILL_SINCE` | (none) | Optional earliest date for backfill (`YYYY-MM-DD`). |
| `DRY_RUN` | `false` | Log intended changes, write nothing. |
| `FORCE` | `false` | Overwrite even externally-changed costs. |
| `LOG_LEVEL` | `INFO` | |

## Schema check before first live run

The SQL assumes a standard TeslaMate schema. Confirm column names against your DB:

```bash
psql "$TESLAMATE_DB_DSN" -c "\d charging_processes" -c "\d geofences" -c "\d positions"
```

Expected: `charging_processes(id, start_date, end_date, charge_energy_added,
charge_energy_used, cost, car_id, position_id, geofence_id)`,
`positions(id, latitude, longitude)`, `geofences(id, cost_per_unit, billing_type)`.
Adjust `src/suc_cost_sync/db.py` if yours differs.

## Development

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt
PYTHONPATH=src .venv/bin/pytest -v        # DB integration test skips without TESLAMATE_TEST_DSN
```
