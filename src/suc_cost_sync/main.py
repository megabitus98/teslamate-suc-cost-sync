import logging
import threading
import time
from collections import Counter
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer

import httpx
import psycopg

from . import db, sync
from .config import load_config
from .fx import FxCache
from .suc_client import SucClient

log = logging.getLogger(__name__)


def _start_health_server(port: int = 8080) -> None:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")

        def log_message(self, *args):
            pass

    threading.Thread(target=HTTPServer(("0.0.0.0", port), Handler).serve_forever,
                     daemon=True).start()


def run_pass(cfg, conn, suc, fx, floor) -> dict:
    suc.clear_cache()
    tally = Counter()
    for row in db.fetch_candidates(conn, cfg.car_id, floor):
        tally[sync.process_charge(cfg, conn, suc, fx, row)] += 1
    if tally:
        log.info("pass complete: %s", dict(tally))
    return dict(tally)


def main() -> None:
    cfg = load_config()
    logging.basicConfig(level=cfg.log_level, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    _start_health_server()

    startup = datetime.now(timezone.utc).replace(microsecond=0)
    floor = cfg.backfill_since if cfg.backfill_on_start else startup.isoformat(sep=" ")
    log.info("starting; target=%s energy=%s dry_run=%s floor=%s",
             cfg.target_currency, cfg.energy_source, cfg.dry_run, floor)

    with httpx.Client() as http, psycopg.connect(cfg.teslamate_dsn) as conn:
        db.ensure_table(conn)
        suc = SucClient(cfg.suc_base_url, cfg.suc_api_key, http)
        fx = FxCache(cfg.fx_base_url, http)
        while True:
            try:
                run_pass(cfg, conn, suc, fx, floor)
            except Exception:
                log.exception("poll pass failed; retrying next interval")
                conn.rollback()
            time.sleep(cfg.poll_interval_s)


if __name__ == "__main__":
    main()
