from __future__ import annotations

import gc
import json
import logging
import multiprocessing
import multiprocessing.connection
import os
import subprocess
import sys
import time
import traceback
import tracemalloc
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import requests

import brightness
import daily_stats as stats
import display_helpers as dh
import font4
import kdnode as kd
import modbus_led as ml
import plane_icon as pi
import utility as ut

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

DEBUG_VERBOSE = False  # 0: no print out; 1: important; 2: everything
TZ = ZoneInfo("America/Los_Angeles")
TIMEOUT = 60
LED_DAY_BRIGHTNESS = 500
LED_NIGHT_BRIGHTNESS = 10
PLANE_SPEED = 0.001
SHORT_CANVAS = 1
LONG_CANVAS = 2
PLANE_CANVAS = 3
STAT_SCROLL_CANVAS = 4
STAT_LABEL_PAD = 3  # gap in pixels between label and scrolling content
FLIP_EAST_WEST = False
FLIGHTS_TODAY: set[str] = set()
FLIGHTS_TODAY_DATE: str = ""
FLIGHTS_TODAY_FILE = "flights_today.json"
LOCAL_AIRPORT: str = ""
PLANE_HEADING = 0
PLANE_VDIR = -99  # -99 = force redraw on next display


def get_serial() -> str:
    strSerial = "/proc/device-tree/serial-number"
    if os.path.isfile(strSerial):
        with open(strSerial) as f:
            return f.read().strip()
    strSerial = "/proc/cpuinfo"
    if os.path.isfile(strSerial):
        with open(strSerial) as f:
            for line in f:
                if line.strip().startswith("Serial"):
                    return line.strip().split(":")[1].strip()
    try:
        result = subprocess.run(
            ["system_profiler", "SPHardwareDataType"],
            stdout=subprocess.PIPE,
            check=True,
        )
        for line in result.stdout.decode().splitlines():
            if "Serial Number" in line:
                return line.strip().split(":")[1].strip()
    except (subprocess.CalledProcessError, OSError):
        pass
    return "0000000000000000"


def get_wifi_ssid(tryN: int = 3) -> str:
    while tryN > 0:
        tryN -= 1
        try:
            ssid = subprocess.check_output(["/usr/sbin/iwgetid", "-r"]).decode().strip()
            return ssid if ssid else "Not connected to Wi-Fi"
        except (subprocess.CalledProcessError, OSError) as e:
            logger.warning("Error: %s", e)
        time.sleep(5)
    return "Wi-Fi SSID not found"


def ping_google(tryN: int = 3) -> bool:
    while tryN > 0:
        tryN -= 1
        try:
            subprocess.check_output(["ping", "-c", "1", "8.8.8.8"], stderr=subprocess.STDOUT)
            return True
        except subprocess.CalledProcessError as e:
            logger.debug("Ping failed: %s", e.output.decode())
        time.sleep(5)
    return False


def check_wifi() -> bool:
    fwifi = ping_google()
    if fwifi:
        ml.show_text(0, 0, 192, 32, "FFF", f"Connected to\n{get_wifi_ssid()}", multiline=True)
    else:
        ml.show_text(0, 0, 192, 32, "FFF", "WIFI\nFailed", multiline=True)
    time.sleep(5)
    return fwifi


def set_time_zone(tz: str) -> None:
    global TZ
    try:
        TZ = ZoneInfo(tz)
    except Exception as e:
        logger.debug("Time zone error: %s", e)
    ml.show_text(
        0,
        0,
        192,
        32,
        "FFF",
        f"Local Time Zone\n{datetime.now(TZ).strftime('%Z')}",
        multiline=True,
    )
    time.sleep(5)


def _load_flights_today() -> None:
    """Load flight counter from disk. Resets if date doesn't match."""
    global FLIGHTS_TODAY, FLIGHTS_TODAY_DATE
    try:
        with open(FLIGHTS_TODAY_FILE) as f:
            data = json.load(f)
        if data.get("date") == datetime.now(TZ).date().isoformat():
            FLIGHTS_TODAY = set(data.get("flights", []))
            FLIGHTS_TODAY_DATE = data["date"]
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        pass


def _save_flights_today() -> None:
    """Persist flight counter to disk."""
    with open(FLIGHTS_TODAY_FILE, "w") as f:
        json.dump({"date": FLIGHTS_TODAY_DATE, "flights": list(FLIGHTS_TODAY)}, f)


def _display_stat_row(label: str, content: str) -> None:
    """Render the idle row 2 with a pinned label and scrolling content."""
    # Tear down previous row 2 state BEFORE drawing the label — deleting
    # the previous STAT_SCROLL_CANVAS can clear pixels in its old rectangle,
    # which would eat the trailing letters of the new label if we did it
    # after show_text.
    ml.delete_programe(LONG_CANVAS)
    ml.delete_programe(STAT_SCROLL_CANVAS)
    ml.delete_canvas(STAT_SCROLL_CANVAS)
    ml.clear_area(0, 16, 192, 16)
    label_end = font4.pixel_width(label)
    scroll_x = label_end + STAT_LABEL_PAD
    canvas_w = 192 - scroll_x
    content_w = font4.pixel_width(content)
    # Full row width for the label box — show_text only draws glyph pixels,
    # so an oversized box can never clip trailing characters.
    ml.show_text(0, 16, 192, 16, "0FF", label, h_align="00", font=4)
    ml.create_canvas(STAT_SCROLL_CANVAS, scroll_x, 16, canvas_w, 16)
    if content_w <= canvas_w:
        # Fits — scroll in from right, hold in place for the rest of the cycle
        ml.create_txt_programe(
            STAT_SCROLL_CANVAS, "0FF", 2, 5, 9999, 2, 1, content, h_align="00", font=4
        )
    else:
        # Overflow — continuous marquee (verified via test_scroll_overflow.py)
        ml.create_txt_programe(
            STAT_SCROLL_CANVAS, "0FF", 2, 5, 0, 2, 20, content, h_align="00", font=4
        )


def display_date_time() -> None:
    dt = datetime.now(TZ)
    ml.show_text(0, 0, 64, 16, "FF0", f"{dt.strftime('%b')} {dt.day}", font=4)
    ml.show_text(64, 0, 64, 16, "FF0", dt.strftime("%H:%M"), font=4)
    ml.show_text(128, 0, 64, 16, "FF0", f"{len(FLIGHTS_TODAY)} flt", font=4)
    label, content = stats.format_stat_parts(stats.next_stat_index())
    _display_stat_row(label, content)


def plane_animation(heading: int | None = None) -> None:
    heading = 270 if heading is None or isinstance(heading, str) else heading
    heading = (360 - heading) % 360 if FLIP_EAST_WEST else heading
    if heading < 180:
        ml.create_img_program(PLANE_CANVAS, 3, 0, 0, 3, 0, 1)
    else:
        ml.create_img_program(PLANE_CANVAS, 2, 0, 0, 2, 0, 2)
    time.sleep(4)
    ml.delete_programe(PLANE_CANVAS)


DIR_X = 0
DIR_Y = 2
VDIR_X = 164
VDIR_Y = 0
VDIR_W = 22
VDIR_H = 16
TEXT_X = 76
TEXT_RIGHT = 162


def display_alt_sp(fInfo: dict[str, Any]) -> None:
    global PLANE_HEADING, PLANE_VDIR
    if fInfo["heading"] == "NA":
        return
    raw_heading = (360 - int(fInfo["heading"])) % 360 if FLIP_EAST_WEST else int(fInfo["heading"])
    heading = ut.closest_heading(raw_heading)
    img = getattr(pi, "get_plane_" + str(heading))()
    w = len(img)
    if heading != PLANE_HEADING:
        ml.clear_area(DIR_X, DIR_Y, w, w)
        ml.show_image(DIR_X, DIR_Y, img)
        PLANE_HEADING = heading
    vdir = dh.vertical_direction(fInfo["altitude"])
    if vdir != PLANE_VDIR:
        ml.clear_area(VDIR_X, VDIR_Y, VDIR_W, VDIR_H)
        if vdir == 1:
            ml.set_paint_color("0F0")
            ml.show_image(VDIR_X, VDIR_Y, pi.get_plane_climbing())
        elif vdir == -1:
            ml.set_paint_color("F00")
            ml.show_image(VDIR_X, VDIR_Y, pi.get_plane_descending())
        PLANE_VDIR = vdir
    ml.show_text(
        TEXT_X,
        0,
        TEXT_RIGHT - TEXT_X,
        16,
        dh.altitude_color(fInfo["altitude"]),
        f"{fInfo['altitude']}ft {fInfo['speed']}kts",
        h_align="00",
        font=3,
    )


def show_flight(flight_info: dict[str, Any]) -> None:
    global PLANE_HEADING, PLANE_VDIR
    PLANE_HEADING = -1
    PLANE_VDIR = -99
    dh.reset_vertical(flight_info.get("initial_vdir", 0))
    logger.debug("%s %s", datetime.now(TZ), flight_info)
    ml.delete_programe(SHORT_CANVAS)
    ml.delete_programe(LONG_CANVAS)
    ml.delete_programe(STAT_SCROLL_CANVAS)
    ml.clear_screen()
    plane_animation(int(flight_info["heading"]))
    labels_s = [
        flight_info["flight_number"],
        flight_info["airports_short"],
        flight_info["aircraft_code"],
    ]
    labels_l = [
        flight_info["airline_name"],
        flight_info["airports_long"],
        flight_info["aircraft_model"],
    ]
    ml.create_txt_programe(
        SHORT_CANVAS, "F0F", 4, 5, 200, 4, 50, "\n".join(labels_s), multiline=True, font=4
    )
    ml.create_txt_programe(
        LONG_CANVAS, "F0F", 2, 5, 0, 2, 20, " ".join(labels_l), h_align="00", font=3
    )
    display_alt_sp(flight_info)
    time.sleep(5)


def clear_flight(flight_index: str) -> None:
    logger.debug("%s Clear", datetime.now(TZ))
    ml.delete_programe(SHORT_CANVAS)
    ml.delete_programe(LONG_CANVAS)
    flight = ut.get_flight_short(requests, flight_index, DEBUG_VERBOSE=DEBUG_VERBOSE)
    if flight is None:
        ml.clear_screen()
        return
    ml.show_text(
        0,
        0,
        192,
        16,
        dh.altitude_color(flight["altitude"]),
        f"{flight['flight_number']} {flight['ori']}-{flight['dest']} {flight['aircraft_type']}",
        font=4,
    )
    ml.show_text(
        0,
        16,
        192,
        16,
        "0FF",
        dh.flight_exit_message(flight, LOCAL_AIRPORT, ut.LANDING_ALTITUDE),
        font=3,
    )
    time.sleep(5)
    ml.clear_screen()


def init(config: dict[str, Any]) -> bool:
    global FLIP_EAST_WEST, LOCAL_AIRPORT
    try:
        center_lat = (config["geo_loc"][0] + config["geo_loc"][1]) / 2
        center_lng = (config["geo_loc"][2] + config["geo_loc"][3]) / 2
        local_airport_info = kd.nearest(kd.IATA_INFO, [center_lat, center_lng])
        LOCAL_AIRPORT = local_airport_info[2] if local_airport_info else ""
        logger.info("Local airport: %s", LOCAL_AIRPORT)
        stats.init(
            home_coord=(center_lat, center_lng),
            airport_coords=kd.build_iata_lookup(kd.IATA_INFO),
            tz=TZ,
        )
        brightness.init(tz=TZ, day=LED_DAY_BRIGHTNESS, night=LED_NIGHT_BRIGHTNESS)
        ml.get_GID()
        ml.set_text_color("FF0")
        ml.delete_canvas(SHORT_CANVAS)
        ml.delete_canvas(LONG_CANVAS)
        ml.delete_canvas(PLANE_CANVAS)
        ml.delete_canvas(STAT_SCROLL_CANVAS)
        ml.create_canvas(SHORT_CANVAS, 14, 0, 60, 16)
        ml.create_canvas(LONG_CANVAS, 0, 16, 192, 16)
        ml.create_canvas(PLANE_CANVAS, 0, 0, 192, 32)
        # STAT_SCROLL_CANVAS is recreated per-stat with a width that depends
        # on the label — this is just a placeholder so delete_canvas below
        # has something to remove on the first invocation.
        ml.create_canvas(STAT_SCROLL_CANVAS, 0, 16, 192, 16)
        FLIP_EAST_WEST = bool(config.get("flip_east_west"))
        ml.DEBUG_VERBOSE = DEBUG_VERBOSE
        if not check_wifi():
            return False
        set_time_zone(config["time_zone"])
        ml.clear_screen()
    except Exception as e:
        logger.debug("Init failed: %s", e)
        return False
    return True


def _follow_previous_flight(
    findex_old: str,
    flight_followed: int,
) -> tuple[str | None, dict[str, Any] | None, int]:
    logger.debug("=== Follow previous plane out of boundary ===")
    fshort = ut.get_flight_short(requests, findex_old, DEBUG_VERBOSE=DEBUG_VERBOSE)
    if fshort is not None and int(fshort["altitude"]) < ut.LANDING_ALTITUDE:
        flight_followed = 0
    return findex_old, fshort, flight_followed - 1


def _handle_flight_change(
    findex: str | None,
    findex_old: str | None,
) -> int:
    if findex is None:
        assert findex_old is not None
        clear_flight(findex_old)
        display_date_time()
        return ut.WAIT_TIME
    finfo = ut.get_flight_detail(requests, findex, DEBUG_VERBOSE=DEBUG_VERBOSE)
    if finfo is not None:
        stats.record_flight(finfo)
        show_flight(finfo)
        return ut.UPDATE_TIME
    return ut.WAIT_TIME


def _resolve_flight(
    findex: str | None,
    fshort: dict[str, Any] | None,
    findex_old: str | None,
    flight_followed: int,
) -> tuple[str | None, dict[str, Any] | None, str | None, int, int]:
    should_follow = findex is None and findex_old is not None and flight_followed > 0
    if should_follow:
        assert findex_old is not None
        findex, fshort, flight_followed = _follow_previous_flight(findex_old, flight_followed)
    if findex != findex_old:
        if findex is not None:
            FLIGHTS_TODAY.add(findex)
            _save_flights_today()
        wait_time = _handle_flight_change(findex, findex_old)
        return findex, fshort, findex, ut.MAX_FOLLOW_PLAN, wait_time
    if findex is not None and fshort is not None:
        display_alt_sp(fshort)
        return findex, fshort, findex_old, flight_followed, ut.UPDATE_TIME
    display_date_time()
    return findex, fshort, findex_old, flight_followed, ut.WAIT_TIME


def main(wdt_pipe: multiprocessing.connection.Connection) -> None:
    global FLIGHTS_TODAY_DATE
    config = ut.get_config()
    if not init(config):
        return
    _load_flights_today()
    findex_old: str | None = None
    flight_followed = ut.MAX_FOLLOW_PLAN
    gc.collect()
    tracemalloc.start()
    while True:
        today = datetime.now(TZ).date().isoformat()
        if today != FLIGHTS_TODAY_DATE:
            FLIGHTS_TODAY.clear()
            FLIGHTS_TODAY_DATE = today
        brightness.check(config["display_time_night"], config["geo_loc"])
        findex, fshort, req_success = ut.get_flights(
            requests, config["geo_loc"], config, DEBUG_VERBOSE=DEBUG_VERBOSE
        )
        if req_success:
            wdt_pipe.send("feed")
        _, _, findex_old, flight_followed, wait_time = _resolve_flight(
            findex, fshort, findex_old, flight_followed
        )
        time.sleep(wait_time)
        gc.collect()
        current, peak = tracemalloc.get_traced_memory()
        logger.info("Current: %d bytes\tPeak: %d bytes", current, peak)


def watchdog(
    timeout: int,
    child_process: multiprocessing.Process,
    wdt_pipe: multiprocessing.connection.Connection,
) -> None:
    last_feed = time.time()
    while True:
        if wdt_pipe.poll():
            msg = wdt_pipe.recv()
            if msg == "feed":
                last_feed = time.time()
        if not child_process.is_alive():
            logger.warning(
                "%s Child process died — restarting immediately",
                datetime.now(TZ),
            )
            child_process.join()
            restart_program()
            sys.exit()
        if time.time() - last_feed > timeout:
            logger.warning(
                "%s Watchdog timeout! Restarting process...",
                datetime.now(TZ),
            )
            child_process.terminate()
            child_process.join()
            restart_program()
            sys.exit()
        time.sleep(1)


def main_try(
    wdt_pipe: multiprocessing.connection.Connection,
) -> None:
    try:
        main(wdt_pipe)
    except Exception as e:
        traceback.print_exception(type(e), e, e.__traceback__)
        raise


def restart_program() -> None:
    python = sys.executable
    os.execv(python, [python] + sys.argv)


if __name__ == "__main__":
    parent_conn, child_conn = multiprocessing.Pipe()
    p = multiprocessing.Process(target=main_try, args=(child_conn,))
    p.start()
    watchdog(timeout=TIMEOUT, child_process=p, wdt_pipe=parent_conn)
