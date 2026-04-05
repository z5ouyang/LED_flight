from __future__ import annotations

from typing import Any


def vertical_indicator(finfo: dict[str, Any]) -> str:
    """Return ^/v prefix based on vertical speed, or empty for level."""
    try:
        vs = int(finfo.get("vertical_speed", 0))
    except (ValueError, TypeError):
        return ""
    if vs > 100:
        return "^"
    if vs < -100:
        return "v"
    return ""


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
