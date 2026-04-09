"""Calibration test: display 'SMALL:' at font 4 above a pixel ruler.

Row 1 (y=0-15): ``SMALL:`` left-justified, font 4
Row 2 (y=16-31): ruler with marks at every 5 and 10 pixels

Run directly on the Pi to display the pattern, then photograph the LED
panel.  The mark heights let you identify each pixel position:
  - every 5px: 3 pixels tall
  - every 10px: 5 pixels tall
  - every 20px: 8 pixels tall

Count how far ``SMALL:`` extends to calibrate ``STAT_CHAR_W``.

Stop the main led_flight.py first (``pkill -f led_flight.py``), then
``source ledflight/bin/activate && python3 test_char_width.py``.
Ctrl+C exits and clears the screen.
"""

from __future__ import annotations

import logging
import time

import modbus_led as ml

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


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


def main() -> None:
    ml.get_GID()
    ml.set_brightness(400)
    ml.set_text_color("FF0")
    # Remove any leftover programmes/canvases from a prior led_flight.py run
    for wid in range(16):
        ml.delete_programe(wid)
        ml.delete_canvas(wid)
    ml.clear_screen()

    # Every character used across the stat labels: uppercase letters that
    # appear in any label, digit "1" (for "1ST"), space, and colon.
    chars = "ABEFGHIKLMNOPRSTX 1:"
    ml.show_text(0, 0, 192, 16, "0F0", chars, h_align="00", font=4)

    ml.set_paint_color("FFF")
    ml.show_image(0, 16, _build_ruler(192, 8))

    logger.info("Calibration pattern displayed.")
    logger.info("Photograph the display, then press Ctrl+C to exit.")
    try:
        while True:
            time.sleep(1)
    finally:
        ml.clear_screen()
        logger.info("Done.")


if __name__ == "__main__":
    main()
