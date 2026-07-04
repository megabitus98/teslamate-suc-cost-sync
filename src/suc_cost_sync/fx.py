import httpx


class FxCache:
    def __init__(self, base_url: str, client: httpx.Client):
        self._base = base_url.rstrip("/")
        self._client = client
        self._cache: dict[tuple[str, str, str], tuple[float, str]] = {}

    def factor(self, date: str, base_ccy: str, target_ccy: str) -> tuple[float, str]:
        """(factor, effective_date) where target = local * factor.
        Same currency -> (1.0, date), no HTTP. Raises on lookup failure."""
        if base_ccy == target_ccy:
            return 1.0, date
        key = (date, base_ccy, target_ccy)
        if key in self._cache:
            return self._cache[key]
        r = self._client.get(
            f"{self._base}/v2/rates",
            params={"date": date, "base": base_ccy, "quotes": target_ccy},
            timeout=20,
        )
        r.raise_for_status()
        rows = r.json()
        if not rows or "rate" not in rows[0]:
            raise ValueError(f"no FX rate {base_ccy}->{target_ccy} on {date}")
        result = (float(rows[0]["rate"]), rows[0].get("date", date))
        self._cache[key] = result
        return result
