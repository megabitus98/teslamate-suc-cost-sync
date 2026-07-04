import httpx
import pytest
from suc_cost_sync.suc_client import SucClient


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_nearby_returns_sites_and_sends_key():
    def handler(req):
        assert req.url.path == "/api/v1/sites/nearby"
        assert req.headers.get("authorization") == "Bearer k"
        return httpx.Response(200, json={"sites": [{"location_guid": "g", "distance_miles": 0.1}]})

    suc = SucClient("https://suc", "k", _client(handler))
    sites = suc.nearby(44.4, 26.1, 0.5)
    assert sites[0]["location_guid"] == "g"


def test_pricing_cached_per_guid():
    calls = []

    def handler(req):
        calls.append(req.url.path)
        return httpx.Response(200, json={"location_guid": "g", "charging": {"rates": [2.22]}})

    suc = SucClient("https://suc", None, _client(handler))
    suc.pricing("g")
    suc.pricing("g")
    assert len(calls) == 1
    suc.clear_cache()
    suc.pricing("g")
    assert len(calls) == 2


def test_history_returns_snapshots():
    def handler(req):
        assert req.url.path == "/api/v1/history/pricing/g"
        return httpx.Response(200, json={"snapshots": [{"captured_at": "2026-05-20T21:00:00Z"}]})

    suc = SucClient("https://suc", None, _client(handler))
    assert suc.history("g")[0]["captured_at"] == "2026-05-20T21:00:00Z"


def test_no_key_sends_no_auth_header():
    def handler(req):
        assert "authorization" not in req.headers
        return httpx.Response(200, json={"sites": []})

    SucClient("https://suc", None, _client(handler)).nearby(1.0, 2.0, 0.5)


def test_retries_on_429_then_succeeds():
    seq = [429, 429, 200]
    slept = []

    def handler(req):
        code = seq.pop(0)
        if code == 429:
            return httpx.Response(429, headers={"retry-after": "1"}, json={})
        return httpx.Response(200, json={"sites": [{"location_guid": "g"}]})

    suc = SucClient("https://suc", None, _client(handler), backoff_s=0.0, sleep=slept.append)
    assert suc.nearby(1.0, 2.0, 0.5)[0]["location_guid"] == "g"
    assert slept == [1.0, 1.0]  # honoured Retry-After twice, no real sleep


def test_raises_when_429_persists():
    def handler(req):
        return httpx.Response(429, json={})

    suc = SucClient("https://suc", None, _client(handler), max_retries=2, sleep=lambda s: None)
    with pytest.raises(httpx.HTTPStatusError):
        suc.nearby(1.0, 2.0, 0.5)
