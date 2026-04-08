"""Daily flight statistics tracker.

Maintains per-day counters and extremes (most-frequent origin, biggest
plane, furthest airport, etc.) derived from each flight shown on the
LED display.  Resets at midnight.  Persisted to ``daily_stats.json``
so a restart doesn't lose the day's progress.

The display-side code calls :func:`record_flight` once per new flight
and :func:`format_stat` to render a rotating stat on the idle screen.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from datetime import datetime, tzinfo
from typing import Any

import aircraft_size
from kdnode import distance_haversine

STATS_FILE = "daily_stats.json"
NUM_STATS = 13
EMPTY = "-"

_STATE: dict[str, Any] = {}
_STAT_INDEX: int = 0
_HOME_COORD: tuple[float, float] | None = None
_AIRPORT_COORDS: dict[str, tuple[float, float]] = {}
_TZ: tzinfo | None = None


def init(
    home_coord: tuple[float, float] | None,
    airport_coords: dict[str, tuple[float, float]],
    tz: tzinfo,
) -> None:
    """Initialize module state with home location, airport lookup, and timezone."""
    global _HOME_COORD, _AIRPORT_COORDS, _TZ, _STAT_INDEX
    _HOME_COORD = home_coord
    _AIRPORT_COORDS = airport_coords
    _TZ = tz
    _load()
    _STAT_INDEX = int(_STATE.get("stat_index", 0))


def _now() -> datetime:
    """Return current local datetime in the configured timezone.

    The Pi may be running in UTC but the daily rollover must happen at
    local midnight — all stats calculations go through this helper.
    """
    return datetime.now(_TZ)


def _today_str() -> str:
    return _now().strftime("%Y-%m-%d")


def _empty_state() -> dict[str, Any]:
    return {
        "date": _today_str(),
        "origins": {},
        "aircraft_types": {},
        "airlines": {},
        "max_altitude": None,
        "fastest": None,
        "first_flight": None,
        "hourly": {},
        "furthest": None,
        "biggest": None,
        "smallest": None,
        "longest_route": None,
        "shortest_route": None,
        "stat_index": 0,
    }


def _load() -> None:
    global _STATE
    _STATE = _empty_state()
    if not os.path.exists(STATS_FILE):
        return
    with open(STATS_FILE) as f:
        data = json.load(f)
    if data.get("date") == _today_str():
        _STATE = data


def _save() -> None:
    _STATE["stat_index"] = _STAT_INDEX
    with open(STATS_FILE, "w") as f:
        json.dump(_STATE, f)


def _reset_if_new_day() -> None:
    global _STATE
    if _STATE.get("date") != _today_str():
        _STATE = _empty_state()
        _save()


def _safe_int(val: Any) -> int | None:
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


def _shorten_airline(name: str) -> str:
    for suffix in (" Airlines", " Air Lines", " Airways", " Aviation"):
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return name[:12]


def _record_counters(flight_info: dict[str, Any]) -> None:
    ori = flight_info.get("ori", "")
    ac_code = flight_info.get("aircraft_code", "")
    airline = flight_info.get("airline_name", "")
    if ori and ori != "NA":
        _STATE["origins"][ori] = _STATE["origins"].get(ori, 0) + 1
    if ac_code and ac_code != "NA":
        _STATE["aircraft_types"][ac_code] = _STATE["aircraft_types"].get(ac_code, 0) + 1
    if airline and airline != "NA":
        short = _shorten_airline(airline)
        _STATE["airlines"][short] = _STATE["airlines"].get(short, 0) + 1


def _record_extremes(flight_info: dict[str, Any]) -> None:
    flight_num = flight_info.get("flight_number", "")
    alt = _safe_int(flight_info.get("altitude"))
    if alt is not None:
        cur = _STATE.get("max_altitude")
        if cur is None or alt > cur["value"]:
            _STATE["max_altitude"] = {"value": alt, "flight": flight_num}
    spd = _safe_int(flight_info.get("speed"))
    if spd is not None:
        cur = _STATE.get("fastest")
        if cur is None or spd > cur["value"]:
            _STATE["fastest"] = {"value": spd, "flight": flight_num}


def _record_time(flight_info: dict[str, Any]) -> None:
    now = _now()
    if _STATE.get("first_flight") is None:
        _STATE["first_flight"] = {
            "time": now.strftime("%H:%M"),
            "flight": flight_info.get("flight_number", ""),
        }
    hour = str(now.hour)
    _STATE["hourly"][hour] = _STATE["hourly"].get(hour, 0) + 1


def _record_size(flight_info: dict[str, Any]) -> None:
    ac_code = flight_info.get("aircraft_code", "")
    wingspan = aircraft_size.get_wingspan(ac_code)
    if wingspan is None:
        return
    cur_big = _STATE.get("biggest")
    if cur_big is None or wingspan > cur_big["wingspan"]:
        _STATE["biggest"] = {"code": ac_code, "wingspan": wingspan}
    cur_small = _STATE.get("smallest")
    if cur_small is None or wingspan < cur_small["wingspan"]:
        _STATE["smallest"] = {"code": ac_code, "wingspan": wingspan}


def _record_furthest(ori: str, dest: str) -> None:
    if _HOME_COORD is None:
        return
    for iata in (ori, dest):
        coord = _AIRPORT_COORDS.get(iata)
        if coord is None:
            continue
        d = distance_haversine(list(_HOME_COORD), list(coord))
        cur = _STATE.get("furthest")
        if cur is None or d > cur["miles"]:
            _STATE["furthest"] = {"iata": iata, "miles": int(d)}


def _record_routes(ori: str, dest: str) -> None:
    ori_coord = _AIRPORT_COORDS.get(ori)
    dest_coord = _AIRPORT_COORDS.get(dest)
    if ori_coord is None or dest_coord is None:
        return
    d = distance_haversine(list(ori_coord), list(dest_coord))
    route = {"ori": ori, "dest": dest, "miles": int(d)}
    cur_long = _STATE.get("longest_route")
    if cur_long is None or d > cur_long["miles"]:
        _STATE["longest_route"] = route
    cur_short = _STATE.get("shortest_route")
    if cur_short is None or d < cur_short["miles"]:
        _STATE["shortest_route"] = route


def _record_geography(flight_info: dict[str, Any]) -> None:
    ori = flight_info.get("ori", "")
    dest = flight_info.get("dest", "")
    _record_furthest(ori, dest)
    _record_routes(ori, dest)


def record_flight(flight_info: dict[str, Any]) -> None:
    """Update all daily stats with a newly displayed flight."""
    _reset_if_new_day()
    _record_counters(flight_info)
    _record_extremes(flight_info)
    _record_time(flight_info)
    _record_size(flight_info)
    _record_geography(flight_info)
    _save()


def next_stat_index() -> int:
    """Increment the rotation counter and return the next stat index."""
    global _STAT_INDEX
    idx = _STAT_INDEX % NUM_STATS
    _STAT_INDEX += 1
    _save()
    return idx


def _fmt_top(key: str, label: str) -> str:
    counts = _STATE.get(key, {})
    if not counts:
        return f"{label}: {EMPTY}"
    top_name, top_count = max(counts.items(), key=lambda kv: kv[1])
    return f"{label}: {top_name} x{top_count}"


def _fmt_rare(key: str, label: str) -> str:
    counts = _STATE.get(key, {})
    rares = sorted(k for k, v in counts.items() if v == 1)
    if not rares:
        return f"{label}: {EMPTY}"
    return f"{label}: {rares[0]}"


def _fmt_peak_hour() -> str:
    hourly = _STATE.get("hourly", {})
    if not hourly:
        return f"PEAK: {EMPTY}"
    peak_hour, peak_count = max(hourly.items(), key=lambda kv: kv[1])
    return f"PEAK: {peak_hour}h ({peak_count} flt)"


def _fmt_max_altitude() -> str:
    v = _STATE.get("max_altitude")
    return f"MAX ALT: {v['value']}ft" if v else f"MAX ALT: {EMPTY}"


def _fmt_fastest() -> str:
    v = _STATE.get("fastest")
    return f"FASTEST: {v['value']}kt" if v else f"FASTEST: {EMPTY}"


def _fmt_first_flight() -> str:
    v = _STATE.get("first_flight")
    return f"1ST: {v['time']} {v['flight']}" if v else f"1ST: {EMPTY}"


def _fmt_furthest() -> str:
    v = _STATE.get("furthest")
    return f"FAR: {v['iata']} {v['miles']}mi" if v else f"FAR: {EMPTY}"


def _fmt_biggest() -> str:
    v = _STATE.get("biggest")
    return f"BIG: {v['code']} ({v['wingspan']}m)" if v else f"BIG: {EMPTY}"


def _fmt_smallest() -> str:
    v = _STATE.get("smallest")
    return f"SMALL: {v['code']} ({v['wingspan']}m)" if v else f"SMALL: {EMPTY}"


def _fmt_longest_route() -> str:
    v = _STATE.get("longest_route")
    return f"LONG: {v['ori']}-{v['dest']} {v['miles']}mi" if v else f"LONG: {EMPTY}"


def _fmt_shortest_route() -> str:
    v = _STATE.get("shortest_route")
    return f"SHORT: {v['ori']}-{v['dest']} {v['miles']}mi" if v else f"SHORT: {EMPTY}"


_FORMATTERS: list[Callable[[], str]] = [
    lambda: _fmt_top("origins", "MOST FROM"),
    lambda: _fmt_top("aircraft_types", "TOP"),
    _fmt_max_altitude,
    _fmt_fastest,
    _fmt_first_flight,
    _fmt_peak_hour,
    _fmt_furthest,
    _fmt_biggest,
    _fmt_smallest,
    _fmt_longest_route,
    _fmt_shortest_route,
    lambda: _fmt_top("airlines", "AIRLINE"),
    lambda: _fmt_rare("aircraft_types", "RARE"),
]


def format_stat(index: int) -> str:
    """Return the formatted string for a specific rotation index."""
    _reset_if_new_day()
    if 0 <= index < len(_FORMATTERS):
        return _FORMATTERS[index]()
    return EMPTY
