from decimal import Decimal

import psycopg
from psycopg.rows import dict_row

_DDL = """
CREATE TABLE IF NOT EXISTS suc_cost_sync_log (
    charging_process_id bigint PRIMARY KEY
        REFERENCES charging_processes(id) ON DELETE CASCADE,
    location_guid      text NOT NULL,
    tou_rate           double precision NOT NULL,
    energy_kwh         double precision NOT NULL,
    site_currency      text NOT NULL,
    cost_local         double precision NOT NULL,
    fx_factor          double precision NOT NULL,
    fx_date            text NOT NULL,
    cost_target        numeric NOT NULL,
    energy_source      text NOT NULL,
    congestion_flagged boolean NOT NULL DEFAULT false,
    updated_at         timestamptz NOT NULL DEFAULT now()
);
-- Charges determined to be not near any Supercharger (position is immutable, so
-- this is permanent). Lets us skip them without re-querying the SUC API forever.
CREATE TABLE IF NOT EXISTS suc_cost_sync_skip (
    charging_process_id bigint PRIMARY KEY
        REFERENCES charging_processes(id) ON DELETE CASCADE,
    reason     text NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now()
);
"""

_CANDIDATES = """
SELECT cp.id,
       cp.start_date,
       cp.charge_energy_used,
       cp.charge_energy_added,
       cp.cost,
       cp.car_id,
       cp.geofence_id,
       p.latitude,
       p.longitude,
       (l.charging_process_id IS NOT NULL) AS logged,
       l.cost_target AS logged_cost
FROM charging_processes cp
JOIN positions p ON p.id = cp.position_id
LEFT JOIN suc_cost_sync_log l ON l.charging_process_id = cp.id
LEFT JOIN suc_cost_sync_skip s ON s.charging_process_id = cp.id
WHERE cp.end_date IS NOT NULL
  AND s.charging_process_id IS NULL
  AND (%(car_id)s::int IS NULL OR cp.car_id = %(car_id)s)
  AND (%(floor)s::timestamp IS NULL OR cp.end_date >= %(floor)s::timestamp)
ORDER BY cp.start_date
"""

_UPSERT_LOG = """
INSERT INTO suc_cost_sync_log
    (charging_process_id, location_guid, tou_rate, energy_kwh, site_currency,
     cost_local, fx_factor, fx_date, cost_target, energy_source, congestion_flagged, updated_at)
VALUES
    (%(id)s, %(guid)s, %(rate)s, %(energy)s, %(ccy)s,
     %(cost_local)s, %(factor)s, %(fx_date)s, %(cost_target)s, %(energy_source)s, %(congestion)s, now())
ON CONFLICT (charging_process_id) DO UPDATE SET
    location_guid = EXCLUDED.location_guid,
    tou_rate = EXCLUDED.tou_rate,
    energy_kwh = EXCLUDED.energy_kwh,
    site_currency = EXCLUDED.site_currency,
    cost_local = EXCLUDED.cost_local,
    fx_factor = EXCLUDED.fx_factor,
    fx_date = EXCLUDED.fx_date,
    cost_target = EXCLUDED.cost_target,
    energy_source = EXCLUDED.energy_source,
    congestion_flagged = EXCLUDED.congestion_flagged,
    updated_at = now()
"""


def ensure_table(conn: psycopg.Connection) -> None:
    with conn.cursor() as cur:
        cur.execute(_DDL)
    conn.commit()


def fetch_candidates(conn: psycopg.Connection, car_id, floor_iso) -> list[dict]:
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(_CANDIDATES, {"car_id": car_id, "floor": floor_iso})
        return cur.fetchall()


def write_correction(conn: psycopg.Connection, corr, energy_source: str) -> None:
    """Cost write + log upsert in one transaction."""
    with conn.transaction(), conn.cursor() as cur:
        cur.execute(
            "UPDATE charging_processes SET cost = %(cost)s WHERE id = %(id)s",
            {"cost": corr.cost_target, "id": corr.charge_id},
        )
        cur.execute(_UPSERT_LOG, {
            "id": corr.charge_id, "guid": corr.location_guid, "rate": corr.tou_rate,
            "energy": corr.energy_kwh, "ccy": corr.site_currency, "cost_local": corr.cost_local,
            "factor": corr.fx_factor, "fx_date": corr.fx_date,
            "cost_target": Decimal(str(corr.cost_target)), "energy_source": energy_source,
            "congestion": corr.congestion_flagged,
        })


def mark_skip(conn: psycopg.Connection, charge_id: int, reason: str) -> None:
    """Permanently mark a charge as not-applicable (not near a Supercharger),
    so future passes don't re-query the SUC API for it."""
    with conn.transaction(), conn.cursor() as cur:
        cur.execute(
            "INSERT INTO suc_cost_sync_skip (charging_process_id, reason) VALUES (%(id)s, %(reason)s) "
            "ON CONFLICT (charging_process_id) DO NOTHING",
            {"id": charge_id, "reason": reason},
        )


def refresh_geofence(conn: psycopg.Connection, geofence_id: int, rate_target: float) -> None:
    with conn.transaction(), conn.cursor() as cur:
        cur.execute(
            "UPDATE geofences SET cost_per_unit = %(rate)s WHERE id = %(gid)s",
            {"rate": Decimal(str(rate_target)), "gid": geofence_id},
        )
