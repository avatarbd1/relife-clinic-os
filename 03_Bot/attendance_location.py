"""Pure helpers for attendance geofence validation."""

from math import asin, cos, radians, sin, sqrt


def distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return great-circle distance between two WGS84 coordinates."""
    earth_radius_m = 6_371_000
    d_lat = radians(lat2 - lat1)
    d_lon = radians(lon2 - lon1)
    a = (
        sin(d_lat / 2) ** 2
        + cos(radians(lat1)) * cos(radians(lat2)) * sin(d_lon / 2) ** 2
    )
    return 2 * earth_radius_m * asin(sqrt(a))


def validate_location(
    latitude: float,
    longitude: float,
    accuracy_m: float | None,
    *,
    clinic_latitude: float,
    clinic_longitude: float,
    radius_m: float,
    max_accuracy_m: float,
) -> dict:
    if not clinic_latitude or not clinic_longitude:
        return {"allowed": False, "reason": "not_configured", "distance_m": None}
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        return {"allowed": False, "reason": "invalid_location", "distance_m": None}
    if accuracy_m is not None and accuracy_m > max_accuracy_m:
        return {"allowed": False, "reason": "low_accuracy", "distance_m": None}

    distance = distance_meters(latitude, longitude, clinic_latitude, clinic_longitude)
    # If the reported accuracy circle overlaps the clinic radius, accept it.
    effective_distance = max(0.0, distance - max(0.0, accuracy_m or 0.0))
    return {
        "allowed": effective_distance <= radius_m,
        "reason": "inside" if effective_distance <= radius_m else "outside",
        "distance_m": round(distance, 1),
    }
