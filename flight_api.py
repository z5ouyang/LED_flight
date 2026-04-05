from __future__ import annotations

import logging
import os
import re
import time
import types
from collections.abc import Sequence
from typing import Any

import requests as requests_lib

from flight_region import (
    estimate_dest_trails,
    get_distance,
    get_iata_loc,
    is_dest_trails,
    is_in_region,
    is_ori_trail,
)

logger = logging.getLogger(__name__)

FLIGHT_SEARCH_HEAD = "https://data-cloud.flightradar24.com/zones/fcgi/feed.js?"
FLIGHT_SEARCH_TAIL = (
    "&faa=1&satellite=1&mlat=1&flarm=1&adsb=1&gnd=0&air=1"
    "&vehicles=0&estimated=0&maxage=14400&gliders=0&stats=0&ems=1"
)
FLIGHT_LONG_DETAILS_HEAD = "https://data-live.flightradar24.com/clickhandler/?flight="
HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "cache-control": ("no-store, no-cache, must-revalidate," " post-check=0, pre-check=0"),
    "accept": "application/json",
}
_session = requests_lib.Session()
_session.headers.update(HTTP_HEADERS)
FLIGHT_SHORT_KEYS = [
    "ICAO_aircraft",
    "latitude",
    "longitude",
    "heading",
    "altitude",
    "speed",
    "squawk",
    "radar",
    "aircraft_type",
    "aircraft_reg",
    "timestamp",
    "ori",
    "dest",
    "flight_number",
    "vertical_speed",
    "squawk_status",
    "callsign",
    "ADS_B",
    "ICAO_airline",
]
TIME_ZONE_SEARCH_HEAD = (
    "https://api.timezonedb.com/v2.1/get-time-zone" "?key=APIKEY&format=json&by=zone&zone="
)
FLIGHT_DETAILS_LATEST: dict[str, Any] | None = None


def get_dict_value(d: Any, keys: Sequence[str | int]) -> Any:
    if d is None:
        return "NA"
    if len(keys) == 0:
        return d
    if isinstance(keys[0], int):
        return get_dict_value(d[keys[0]], keys[1:])
    if keys[0] in d.keys():
        return get_dict_value(d.get(keys[0]), keys[1:])
    return "NA"


def get_request_response(
    requests: types.ModuleType,
    url: str,
    DEBUG_VERBOSE: bool = False,
    timeout: int = 5,
) -> dict[str, Any] | None:
    try:
        response = _session.get(url=url, timeout=timeout)
        response_json = response.json()
        response.close()
    except (requests_lib.RequestException, ValueError, KeyError) as e:
        logger.debug("Request failed", exc_info=e)
        return None
    return response_json


def _to_flight_short(v: list[Any]) -> dict[str, Any]:
    return {FLIGHT_SHORT_KEYS[i]: v[i] for i in range(min(len(FLIGHT_SHORT_KEYS), len(v)))}


def _update_from_cached(
    requests: types.ModuleType,
    flight_index: str,
    flight_short: dict[str, dict[str, Any]],
) -> None:
    global FLIGHT_DETAILS_LATEST
    if FLIGHT_DETAILS_LATEST is None:
        return
    if FLIGHT_DETAILS_LATEST["flight_index"] != flight_index:
        return
    if len(FLIGHT_DETAILS_LATEST["dest"]) != 3:
        get_flight_detail(requests, flight_index)
        time.sleep(1)
    flight_short[flight_index].update(
        {k: v for k, v in FLIGHT_DETAILS_LATEST.items() if k in ["flight_number", "ori", "dest"]}
    )


def _filter_flights(
    flight: dict[str, Any],
    geoloc: tuple[float, ...],
    rInfo: dict[str, Any],
) -> tuple[dict[str, float], dict[str, dict[str, Any]]]:
    altitude = rInfo.get("altitude")
    heading = rInfo.get("heading")
    speed = rInfo.get("speed")
    altitude_rev = rInfo.get("altitude_rev")
    heading_rev = rInfo.get("heading_rev")
    center_geoloc = rInfo.get("center_loc")
    dest = rInfo.get("dest")
    flight_dist: dict[str, float] = {}
    flight_short: dict[str, dict[str, Any]] = {}
    if len(flight) <= 2:
        return flight_dist, flight_short
    for k, v in flight.items():
        if not (isinstance(v, list) and len(v) > 13):
            continue
        if not is_in_region(
            v,
            geoloc,
            altitude,
            heading,
            speed,
            altitude_rev,
            heading_rev,
        ):
            continue
        if dest is not None and v[12] != "" and dest != v[12]:
            continue
        flight_dist[k] = get_distance(center_geoloc, v[1:3])
        flight_short[k] = _to_flight_short(v)
    return flight_dist, flight_short


def get_flights(
    requests: types.ModuleType,
    geoloc: tuple[float, ...],
    rInfo: dict[str, Any],
    DEBUG_VERBOSE: bool = False,
) -> tuple[str | None, dict[str, Any] | None, bool]:
    url = FLIGHT_SEARCH_HEAD + "bounds=" + ",".join(str(i) for i in geoloc) + FLIGHT_SEARCH_TAIL
    flight = get_request_response(requests, url, DEBUG_VERBOSE)
    if flight is None:
        return None, None, False
    logger.debug("Flight search response: %s", flight)
    flight_dist, flight_short = _filter_flights(flight, geoloc, rInfo)
    flight_index = None if len(flight_dist) == 0 else min(flight_dist, key=lambda k: flight_dist[k])
    if flight_index is not None:
        _update_from_cached(requests, flight_index, flight_short)
    return (
        flight_index,
        (None if flight_index is None else flight_short[flight_index]),
        len(flight) > 0,
    )


def _resolve_airport(
    flight: dict[str, Any],
    endpoint: str,
    trails: list[dict[str, Any]],
) -> tuple[str, str]:
    iata = get_dict_value(flight, ["airport", endpoint, "code", "iata"])
    city = get_dict_value(
        flight,
        ["airport", endpoint, "position", "region", "city"],
    )
    if iata != "NA" and city != "NA":
        return iata, city
    if endpoint == "origin" and is_ori_trail(trails):
        try:
            return get_iata_loc(
                get_dict_value(flight, ["trail", -1]),
                iata,
                city,
            )
        except (TypeError, KeyError, IndexError) as e:
            logger.error("Error: get_iata_loc ori: %s", e)
    elif endpoint == "destination" and is_dest_trails(trails):
        try:
            return get_iata_loc(
                estimate_dest_trails(get_dict_value(flight, ["trail", 0])),
                iata,
                city,
            )
        except (TypeError, KeyError, IndexError) as e:
            logger.error("Error: get_iata_loc dest: %s", e)
    return iata, city


def _resolve_flight_number(
    flight: dict[str, Any],
) -> str:
    for key in ["number", "callsign"]:
        path = ["identification", key]
        if key == "number":
            path.append("default")
        val = get_dict_value(flight, path)
        if val != "NA":
            return str(val)
    return "NA"


def _build_flight_details(
    flight: dict[str, Any],
    flight_index: str,
    ori_iata: str,
    dest_iata: str,
    ori_city: str,
    dest_city: str,
) -> dict[str, Any]:
    airline = get_dict_value(flight, ["airline", "name"])
    fn = _resolve_flight_number(flight)
    airports_short = re.sub(
        r"^NA-NA$|^NA-|-NA$",
        "-",
        ori_iata + "-" + dest_iata,
    )
    return {
        "flight_index": flight_index,
        "flight_number": fn if fn != "NA" else airline,
        "airline_name": airline,
        "airports_short": airports_short,
        "airports_long": ori_city + "-" + dest_city,
        "aircraft_code": get_dict_value(flight, ["aircraft", "model", "code"]),
        "aircraft_model": get_dict_value(flight, ["aircraft", "model", "text"]),
        "status": get_dict_value(flight, ["status", "text"]),
        "altitude": get_dict_value(flight, ["trail", 0, "alt"]),
        "heading": get_dict_value(flight, ["trail", 0, "hd"]),
        "speed": get_dict_value(flight, ["trail", 0, "spd"]),
        "eta": get_dict_value(flight, ["time", "estimated", "arrival"]),
        "ori": re.sub("^NA$", "", ori_iata),
        "dest": re.sub("^NA$", "", dest_iata),
    }


def get_flight_detail(
    requests: types.ModuleType,
    flight_index: str,
    DEBUG_VERBOSE: bool = False,
) -> dict[str, Any] | None:
    global FLIGHT_DETAILS_LATEST
    logger.debug("flight_index: %s", flight_index)
    flight = get_request_response(
        requests,
        FLIGHT_LONG_DETAILS_HEAD + flight_index,
        DEBUG_VERBOSE,
    )
    if flight is None:
        return None
    trails = get_dict_value(flight, ["trail"])
    ori_iata, ori_city = _resolve_airport(flight, "origin", trails)
    dest_iata, dest_city = _resolve_airport(flight, "destination", trails)
    flight_details = _build_flight_details(
        flight,
        flight_index,
        ori_iata,
        dest_iata,
        ori_city,
        dest_city,
    )
    FLIGHT_DETAILS_LATEST = flight_details
    return flight_details


def get_flight_short(
    requests: types.ModuleType,
    flight_index: str | None,
    DEBUG_VERBOSE: bool = False,
) -> dict[str, Any] | None:
    if flight_index is None:
        return None
    url = FLIGHT_SEARCH_HEAD + "flight_id=" + flight_index
    flight = get_request_response(requests, url, DEBUG_VERBOSE)
    if flight is None or flight_index not in flight.keys():
        return None
    flight_details = _to_flight_short(flight[flight_index])
    if FLIGHT_DETAILS_LATEST is not None and FLIGHT_DETAILS_LATEST["flight_index"] == flight_index:
        if len(FLIGHT_DETAILS_LATEST["dest"]) != 3:
            get_flight_detail(requests, flight_index)
            time.sleep(1)
        flight_details.update(
            {
                k: v
                for k, v in FLIGHT_DETAILS_LATEST.items()
                if k in ["flight_number", "ori", "dest"]
            }
        )
    return flight_details


def get_time_zone_offset(
    requests: types.ModuleType,
    tz: str,
    DEBUG_VERBOSE: bool,
) -> tuple[float | None, str | None]:
    api_key = os.environ["TIMEZONEDB_API_KEY"]
    url = (
        re.sub(
            "APIKEY",
            api_key,
            TIME_ZONE_SEARCH_HEAD,
        )
        + tz
    )
    tInfo = get_request_response(
        requests,
        url,
        DEBUG_VERBOSE=DEBUG_VERBOSE,
        timeout=20,
    )
    if tInfo is not None and tInfo["status"] == "OK":
        return tInfo["gmtOffset"] / 3600, tInfo["abbreviation"]
    return None, None
