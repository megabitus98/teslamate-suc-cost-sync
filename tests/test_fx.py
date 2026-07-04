import httpx
import pytest
from suc_cost_sync.fx import FxCache


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_same_currency_is_noop():
    calls = []

    def handler(req):
        calls.append(req)
        return httpx.Response(200, json=[])

    fx = FxCache("https://fx", _client(handler))
    assert fx.factor("2026-05-20", "RON", "RON") == (1.0, "2026-05-20")
    assert calls == []  # no HTTP for same currency


def test_factor_parsed_from_v2_array():
    def handler(req):
        assert req.url.path == "/v2/rates"
        return httpx.Response(200, json=[{"date": "2026-05-20", "base": "EUR", "quote": "RON", "rate": 5.2325}])

    fx = FxCache("https://fx", _client(handler))
    factor, eff = fx.factor("2026-05-20", "EUR", "RON")
    assert factor == 5.2325 and eff == "2026-05-20"


def test_cached_second_call_hits_no_http():
    calls = []

    def handler(req):
        calls.append(req)
        return httpx.Response(200, json=[{"date": "2026-05-20", "base": "EUR", "quote": "RON", "rate": 5.2325}])

    fx = FxCache("https://fx", _client(handler))
    fx.factor("2026-05-20", "EUR", "RON")
    fx.factor("2026-05-20", "EUR", "RON")
    assert len(calls) == 1


def test_empty_array_raises():
    fx = FxCache("https://fx", _client(lambda req: httpx.Response(200, json=[])))
    with pytest.raises(ValueError):
        fx.factor("2026-05-20", "USD", "RON")
