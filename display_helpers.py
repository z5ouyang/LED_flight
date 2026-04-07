from __future__ import annotations

from typing import Any

_prev_altitude: int | None = None
_prev_direction: int = 0


def reset_vertical(initial_dir: int = 0) -> None:
    """Reset vertical tracking for a new flight, optionally seeding the direction.

    Called when a new flight is detected so the first `vertical_direction()`
    call returns the seeded value rather than a stale delta from the previous
    flight.  The seed should come from trail data in the FR24 detail response.
    """
    global _prev_altitude, _prev_direction
    _prev_altitude = None
    _prev_direction = initial_dir


def vertical_direction(altitude: int | str) -> int:
    """Return climb/descent direction: 1=climbing, -1=descending, 0=level.

    Sticky — when the altitude delta is below the threshold, keeps the
    previous direction instead of flipping to 0.  This prevents flicker
    during brief level segments and preserves the trail-seeded initial
    direction until real altitude change occurs.
    """
    global _prev_altitude, _prev_direction
    try:
        alt = int(altitude)
    except (ValueError, TypeError):
        return _prev_direction
    if _prev_altitude is None:
        _prev_altitude = alt
        return _prev_direction
    diff = alt - _prev_altitude
    _prev_altitude = alt
    if diff < -20:
        _prev_direction = -1
    elif diff > 20:
        _prev_direction = 1
    return _prev_direction


def altitude_color(altitude: int | str) -> str:
    """Color by altitude: green (low), yellow (mid), red (high)."""
    try:
        alt = int(altitude)
    except (ValueError, TypeError):
        return "FF0"
    if alt < 3000:
        return "0F0"
    if alt < 15000:
        return "FF0"
    return "F00"


def flight_exit_message(
    flight: dict[str, Any],
    local_airport: str,
    landing_altitude: int,
) -> str:
    """Build context-aware exit message based on local airport."""
    ori = flight.get("ori", "NA")
    dest = flight.get("dest", "NA")
    landed = flight["altitude"] < landing_altitude
    speed_str = str(flight["speed"]) + " kts"

    if local_airport and dest == local_airport:
        return _arriving_message(ori, speed_str, landed, local_airport)
    if local_airport and ori == local_airport:
        return _departing_message(dest, local_airport)
    if landed:
        return f"Landed\t{speed_str}"
    if ori != "NA" and dest != "NA":
        return f"{ori} -> {dest}"
    return "Out of Monitor Boundary"


def _arriving_message(ori: str, speed_str: str, landed: bool, local_airport: str) -> str:
    if landed:
        return f"Arriving {local_airport}\t{speed_str}"
    if ori != "NA":
        return f"Arriving {local_airport} from {ori}"
    return f"Arriving {local_airport}"


def _departing_message(dest: str, local_airport: str) -> str:
    if dest != "NA":
        return f"Departing {local_airport} -> {dest}"
    return f"Departing {local_airport}"
