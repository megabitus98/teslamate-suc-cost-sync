import os
import pytest

psycopg = pytest.importorskip("psycopg")
DSN = os.getenv("TESLAMATE_TEST_DSN")
pytestmark = pytest.mark.skipif(not DSN, reason="set TESLAMATE_TEST_DSN to run DB tests")


def test_ensure_table_idempotent():
    from suc_cost_sync import db
    with psycopg.connect(DSN) as conn:
        db.ensure_table(conn)
        db.ensure_table(conn)  # second call must not raise
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass('suc_cost_sync_log')")
            assert cur.fetchone()[0] is not None
