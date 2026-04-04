from __future__ import annotations

import math
from typing import Any

import kdnode as kd

LANDING_ALTITUDE_MAX = 4000


def get_distance(
    center: list[float] | None, loc: list[float],
) -> float:
    if center is None:
        return 1
    return math.sqrt(
        (center[0] - loc[0]) ** 2 + (center[1] - loc[1]) ** 2
    )


def is_between(v: float, r: list[float] | tuple[float, float]) -> bool:
    s, l = r
    if s > l:
        s, l = l, s
    return s <= v <= l


def _heading_progress(
    fInfo: list[Any], geoloc: tuple[float, ...],
) -> float:
    h = fInfo[3]
    tl_lat, br_lat, tl_lon, br_lon = geoloc
    span_lat = abs(tl_lat - br_lat)
    span_lon = abs(tl_lon - br_lon)
    if 45 <= h < 135:
        return float((fInfo[2] - tl_lon) / span_lon)
    if 135 <= h < 225:
        return float(abs(tl_lat - fInfo[1]) / span_lat)
    if 225 <= h < 315:
        return float((br_lon - fInfo[2]) / span_lon)
    return float((fInfo[1] - br_lat) / span_lat)


def is_in_dynamic_altitude(
    fInfo: list[Any],
    geoloc: tuple[float, ...],
    altitude: list[float],
    threshold_rate: float = 0.2,
) -> bool:
    progress = _heading_progress(fInfo, geoloc)
    expected_altitude = (
        altitude[0] + progress * (altitude[1] - altitude[0])
    )
    return bool(
        abs(fInfo[4] - expected_altitude)
        <= expected_altitude * threshold_rate
    )


def is_in_altitude(
    fInfo: list[Any],
    geoloc: tuple[float, ...],
    altitude: list[float] | None,
    altitude_rev: list[float] | None,
    threshold_rate: float = 0.2,
) -> bool:
    if altitude is None and altitude_rev is None:
        return True
    for one in [altitude, altitude_rev]:
        if one is not None and is_in_dynamic_altitude(
            fInfo, geoloc, one, threshold_rate
        ):
            return True
    return False


def is_in_heading(
    fheading: float,
    heading: list[float] | None,
    heading_rev: list[float] | None,
) -> tuple[bool, list[float] | None]:
    if heading is None and heading_rev is None:
        return True, None
    for one in [heading, heading_rev]:
        if one is not None and is_between(fheading, one):
            return True, one
    return False, None


def is_in_region(
    fInfo: list[Any],
    geoloc: tuple[float, ...],
    altitude: list[float] | None,
    heading: list[float] | None,
    speed: list[float] | None,
    altitude_rev: list[float] | None,
    heading_rev: list[float] | None,
) -> bool:
    if speed is not None and not is_between(fInfo[5], speed):
        return False
    b_heading, h = is_in_heading(
        fInfo[3], heading, heading_rev
    )
    if not b_heading:
        return False
    if h is None:
        return is_in_altitude(
            fInfo, geoloc, altitude, altitude_rev
        )
    if h == heading and altitude is not None:
        return is_in_dynamic_altitude(
            fInfo, geoloc, altitude
        )
    if h == heading_rev and altitude_rev is not None:
        return is_in_dynamic_altitude(
            fInfo, geoloc, altitude_rev
        )
    return False


def closest_heading(angle: int) -> int:
    compass_points = [0, 45, 90, 135, 180, 225, 270, 315]
    return min(
        compass_points,
        key=lambda x: abs((angle - x + 180) % 360 - 180),
    )


def get_iata_loc(
    trail: dict[str, float],
    iata: str,
    city: str,
    raidus: float = 5,
) -> tuple[str, str]:
    airport_info = kd.nearest(
        kd.IATA_INFO, (trail["lat"], trail["lng"])
    )
    if airport_info is not None and airport_info[-1] < raidus:
        lat, lng, iata, city, distance = airport_info
    return iata, city


def is_ori_trail(
    trails: list[dict[str, Any]], tolerance: float = 0.85,
) -> bool:
    if trails[-1]["alt"] < 100:
        return True
    takeoff_index = min(len(trails), 200)
    takeoff_alt = sum(
        1
        for i in range(
            len(trails) - takeoff_index, len(trails)
        )
        if trails[i - 1]["alt"] >= trails[i]["alt"]
    )
    return takeoff_alt / takeoff_index > tolerance


def is_dest_trails(
    trails: list[dict[str, Any]], tolerance: float = 0.85,
) -> bool:
    if trails[0]["alt"] > LANDING_ALTITUDE_MAX:
        return False
    landing_index = min(int(len(trails) / 2), 200)
    landing_alt = sum(
        1
        for i in range(landing_index)
        if trails[i]["alt"] <= trails[i + 1]["alt"]
    )
    return landing_alt / landing_index > tolerance


def estimate_dest_trails(
    trail: dict[str, Any], dist: float = 5,
) -> dict[str, Any]:
    pred_trail = trail.copy()
    if pred_trail["alt"] > LANDING_ALTITUDE_MAX:
        return pred_trail
    R = 3958.8
    phi1 = math.radians(pred_trail["lat"])
    lambda1 = math.radians(pred_trail["lng"])
    theta = math.radians(pred_trail["hd"])
    d_over_R = dist / R
    phi2 = math.asin(
        math.sin(phi1) * math.cos(d_over_R)
        + math.cos(phi1)
        * math.sin(d_over_R)
        * math.cos(theta)
    )
    lambda2 = lambda1 + math.atan2(
        math.sin(theta)
        * math.sin(d_over_R)
        * math.cos(phi1),
        math.cos(d_over_R)
        - math.sin(phi1) * math.sin(phi2),
    )
    pred_trail.update(
        {
            "lat": math.degrees(phi2),
            "lng": math.degrees(lambda2),
        }
    )
    return pred_trail
