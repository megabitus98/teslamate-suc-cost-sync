from suc_cost_sync import main


class FakeConn:
    def __init__(self, closed=False, rollback_raises=False):
        self.closed = closed
        self._rollback_raises = rollback_raises
        self.closed_called = False

    def rollback(self):
        if self._rollback_raises:
            raise RuntimeError("connection is lost")

    def close(self):
        self.closed_called = True


def _patch_connect(monkeypatch):
    fresh = FakeConn()
    monkeypatch.setattr(main, "_connect", lambda dsn: fresh)
    return fresh


def test_reuses_live_connection(monkeypatch):
    fresh = _patch_connect(monkeypatch)
    live = FakeConn()
    assert main._healthy_conn(live, "dsn") is live   # rollback ok -> reused
    assert fresh is not live


def test_reconnects_when_none(monkeypatch):
    fresh = _patch_connect(monkeypatch)
    assert main._healthy_conn(None, "dsn") is fresh


def test_reconnects_when_closed(monkeypatch):
    fresh = _patch_connect(monkeypatch)
    dead = FakeConn(closed=True)
    assert main._healthy_conn(dead, "dsn") is fresh


def test_reconnects_when_rollback_fails(monkeypatch):
    # the old crash: connection dropped mid-pass, rollback() throws -> reconnect instead
    fresh = _patch_connect(monkeypatch)
    broken = FakeConn(rollback_raises=True)
    assert main._healthy_conn(broken, "dsn") is fresh
    assert broken.closed_called
