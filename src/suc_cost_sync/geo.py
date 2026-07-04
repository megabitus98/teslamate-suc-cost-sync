from tzfpy import get_tz

_MILES_TO_KM = 1.609344


def miles_to_km(miles: float) -> float:
    return miles * _MILES_TO_KM


def site_timezone(lat: float, lng: float) -> str | None:
    return get_tz(lng, lat)  # tzfpy takes (lng, lat); IANA name or None


def choose_site(sites: list[dict], max_km: float) -> dict | None:
    best = None
    for s in sites:
        km = miles_to_km(s["distance_miles"])
        if km <= max_km and (best is None or km < miles_to_km(best["distance_miles"])):
            best = s
    return best
