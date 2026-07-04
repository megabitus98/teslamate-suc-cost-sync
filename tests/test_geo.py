from suc_cost_sync.geo import miles_to_km, site_timezone, choose_site


def test_miles_to_km():
    assert round(miles_to_km(1.0), 5) == 1.60934


def test_timezone_bucharest():
    # Mega Mall centroid (verified 2026-06-25)
    assert site_timezone(44.441037, 26.15441) == "Europe/Bucharest"


def test_choose_nearest_within_radius():
    sites = [
        {"location_guid": "far", "distance_miles": 0.40},   # ~0.64 km
        {"location_guid": "near", "distance_miles": 0.10},  # ~0.16 km
    ]
    assert choose_site(sites, 0.5)["location_guid"] == "near"


def test_choose_none_when_all_outside_radius():
    sites = [{"location_guid": "x", "distance_miles": 1.0}]  # ~1.6 km
    assert choose_site(sites, 0.5) is None


def test_choose_empty():
    assert choose_site([], 0.5) is None
