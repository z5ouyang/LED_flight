from __future__ import annotations

import json
import time
from typing import Any

import kdnode as kd
from flight_api import (
    FLIGHT_LONG_DETAILS_HEAD as FLIGHT_LONG_DETAILS_HEAD,
)
from flight_api import (
    FLIGHT_SEARCH_HEAD as FLIGHT_SEARCH_HEAD,
)
from flight_api import (
    FLIGHT_SEARCH_TAIL as FLIGHT_SEARCH_TAIL,
)
from flight_api import (
    FLIGHT_SHORT_KEYS as FLIGHT_SHORT_KEYS,
)
from flight_api import (
    HTTP_HEADERS as HTTP_HEADERS,
)
from flight_api import (
    TIME_ZONE_SEARCH_HEAD as TIME_ZONE_SEARCH_HEAD,
)
from flight_api import (
    get_dict_value as get_dict_value,
)
from flight_api import (
    get_flight_detail as get_flight_detail,
)
from flight_api import (
    get_flight_short as get_flight_short,
)
from flight_api import (
    get_flights as get_flights,
)
from flight_api import (
    get_request_response as get_request_response,
)
from flight_api import (
    get_time_zone_offset as get_time_zone_offset,
)
from flight_region import (
    closest_heading as closest_heading,
)
from flight_region import (
    estimate_dest_trails as estimate_dest_trails,
)
from flight_region import (
    get_distance as get_distance,
)
from flight_region import (
    get_iata_loc as get_iata_loc,
)
from flight_region import (
    is_between as is_between,
)
from flight_region import (
    is_dest_trails as is_dest_trails,
)
from flight_region import (
    is_in_altitude as is_in_altitude,
)
from flight_region import (
    is_in_dynamic_altitude as is_in_dynamic_altitude,
)
from flight_region import (
    is_in_heading as is_in_heading,
)
from flight_region import (
    is_in_region as is_in_region,
)
from flight_region import (
    is_ori_trail as is_ori_trail,
)

kd.init_iata_info()

WAIT_TIME = 15
UPDATE_TIME = 5
WAIT_TIME_MAX = 75
MAX_FOLLOW_PLAN = 70
LANDING_ALTITUDE = 51
LANDING_ALTITUDE_MAX = 4000
IATA_INFO = None


def get_config() -> dict[str, Any]:
    with open("private.json") as f:
        config: dict[str, Any] = json.load(f)
    return config


def get_est_arrival(eta: float | str) -> int:
    if isinstance(eta, str):
        return 5
    return min(WAIT_TIME_MAX, max(5, int(eta - time.time() - 50)))
