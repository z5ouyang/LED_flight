"""Cycle through every stat label at font 4 with a pixel ruler below.

Each label displays for 5 seconds with the ruler at y=16-23 (marks at
every 5/10/20 px).  Photograph each label in turn; the snapshots let
us hardcode exact per-label visual widths.

Run directly on the Pi after stopping led_flight.py.  Ctrl+C exits.
"""

from __future__ import annotations

import logging
import time

import modbus_led as ml

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

LABELS = [
    "MOST FROM:",
    "TOP:",
    "MAX ALT:",
    "FASTEST:",
    "1ST:",
    "PEAK:",
    "FAR:",
    "BIG:",
    "SMALL:",
    "LONG:",
    "SHORT:",
    "AIRLINE:",
    "RARE:",
]

DISPLAY_SECS = 5


def _mark_height(x: int) -> int:
    if x % 20 == 0:
        return 8
    if x % 10 == 0:
        return 5
    if x % 5 == 0:
        return 3
    return 0


def _build_ruler(width: int, rows: int) -> list[str]:
    heights = [_mark_height(x) for x in range(width)]
    return [
        "".join("1" if heights[x] > row_index else "0" for x in range(width))
        for row_index in range(rows)
    ]


def _reset_display() -> None:
    for wid in range(16):
        ml.delete_programe(wid)
        ml.delete_canvas(wid)
    ml.clear_screen()


def main() -> None:
    ml.get_GID()
    ml.set_brightness(400)
    ml.set_text_color("FF0")
    _reset_display()
    ruler = _build_ruler(192, 8)
    ml.set_paint_color("FFF")
    ml.show_image(0, 16, ruler)

    try:
        while True:
            for label in LABELS:
                ml.clear_area(0, 0, 192, 16)
                ml.show_text(0, 0, 192, 16, "0F0", label, h_align="00", font=4)
                logger.info("Showing: %s", label)
                time.sleep(DISPLAY_SECS)
    finally:
        _reset_display()
        logger.info("Done.")


if __name__ == "__main__":
    main()
