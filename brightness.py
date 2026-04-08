"""Day/night brightness control with sunrise-aware cutover.

Fetches local sunrise time from api.sunrise-sunset.org once per day and
uses it together with a user-configured night-time window to decide
between day and night brightness levels on the LED panel.
"""

from __future__ import annotations

import logging
from datetime import datetime, tzinfo

import requests

import modbus_led as ml

logger = logging.getLogger(__name__)

_TZ: tzinfo | None = None
_DAY: int = 500
_NIGHT: int = 10
_CURRENT: int = 500
_SUN_RISE: dict[str, datetime] | None = None


def init(tz: tzinfo, day: int, night: int) -> None:
    """Configure the module with timezone and brightness levels."""
    global _TZ, _DAY, _NIGHT, _CURRENT
    _TZ = tz
    _DAY = day
    _NIGHT = night
    _CURRENT = day


def _update_sunrise(dt: datetime, geo_loc: list[float]) -> None:
    global _SUN_RISE
    try:
        params: dict[str, str] = {
            "lat": str((geo_loc[0] + geo_loc[1]) / 2),
            "lng": str((geo_loc[2] + geo_loc[3]) / 2),
            "date": dt.date().isoformat(),
            "formatted": "0",
        }
        response = requests.get(
            "https://api.sunrise-sunset.org/json",
            params=params,
            timeout=10,
        )
        try:
            sunrise = datetime.fromisoformat(response.json()["results"]["sunrise"]).astimezone(_TZ)
            _SUN_RISE = {dt.date().isoformat(): sunrise}
        finally:
            response.close()
    except (requests.RequestException, KeyError, ValueError):
        _SUN_RISE = None


def _is_night(dt: datetime, night_time: list[int]) -> bool:
    before_sunrise = (
        dt.hour < night_time[1] if _SUN_RISE is None else dt < _SUN_RISE[dt.date().isoformat()]
    )
    start, end = night_time[0], night_time[1]
    if start < end:
        return start <= dt.hour and before_sunrise
    return start <= dt.hour or before_sunrise


def check(
    night_time: list[int],
    geo_loc: list[float] | None = None,
) -> None:
    """Evaluate day/night and apply the appropriate brightness level."""
    global _CURRENT
    dt = datetime.now(_TZ)
    needs_sunrise = _SUN_RISE is None or dt.date().isoformat() not in _SUN_RISE
    if geo_loc is not None and needs_sunrise:
        _update_sunrise(dt, geo_loc)
    is_night = _is_night(dt, night_time)
    if is_night and _CURRENT != _NIGHT:
        logger.debug("Night Brightness")
        _CURRENT = _NIGHT
        ml.set_brightness(_NIGHT)
    elif not is_night and _CURRENT != _DAY:
        logger.debug("Day Brightness")
        _CURRENT = _DAY
        ml.set_brightness(_DAY)
