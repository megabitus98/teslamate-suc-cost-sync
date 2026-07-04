import time

import httpx


class SucClient:
    def __init__(self, base_url: str, api_key: str | None, client: httpx.Client,
                 *, max_retries: int = 3, backoff_s: float = 5.0, sleep=time.sleep):
        self._base = base_url.rstrip("/")
        self._client = client
        self._headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._pricing: dict[str, dict] = {}
        self._history: dict[str, list] = {}
        self._max_retries = max_retries
        self._backoff_s = backoff_s
        self._sleep = sleep

    def clear_cache(self) -> None:
        self._pricing.clear()
        self._history.clear()

    def _get(self, path: str, params: dict | None = None):
        """GET with linear backoff on 429 (honours Retry-After). Raises on
        non-2xx after retries are exhausted."""
        r = None
        for attempt in range(self._max_retries + 1):
            r = self._client.get(f"{self._base}{path}", params=params,
                                 headers=self._headers, timeout=20)
            if r.status_code == 429 and attempt < self._max_retries:
                ra = r.headers.get("retry-after")
                wait = float(ra) if ra and ra.isdigit() else self._backoff_s * (attempt + 1)
                self._sleep(wait)
                continue
            r.raise_for_status()
            return r.json()
        r.raise_for_status()  # exhausted retries on a persistent 429
        return r.json()

    def nearby(self, lat: float, lng: float, radius_km: float) -> list[dict]:
        return self._get("/api/v1/sites/nearby",
                         {"lat": lat, "lng": lng, "radius_km": radius_km}).get("sites", [])

    def pricing(self, guid: str) -> dict:
        if guid not in self._pricing:
            self._pricing[guid] = self._get(f"/api/v1/pricing/{guid}")
        return self._pricing[guid]

    def history(self, guid: str) -> list[dict]:
        if guid not in self._history:
            self._history[guid] = self._get(f"/api/v1/history/pricing/{guid}").get("snapshots", [])
        return self._history[guid]
