"""Scroll overflow test: determine whether ``create_txt_programe`` auto-
marquees text that is wider than its canvas, or clips and holds.

Row 1: static label 'TEST:' (green)
Row 2: a narrow 60-pixel canvas at (60, 16) containing a long text that
definitely does not fit.  If the text scrolls continuously through the
canvas to reveal the whole thing, the unified ``en=2, du=30, ex=2,
repeat=99`` path will work for all stats.  If it clips and holds, we
need different parameters for overflow content.

Run directly on the Pi after stopping led_flight.py.  Ctrl+C exits.
"""

from __future__ import annotations

import logging
import time

import modbus_led as ml

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

TEST_CANVAS = 7  # unique id to avoid collision with existing canvases
LONG_TEXT = "This is a long text that definitely does not fit the canvas"


def main() -> None:
    ml.get_GID()
    ml.set_brightness(400)
    ml.set_text_color("FF0")
    for wid in (1, 2, 3, 4, 5, 6, 7):
        ml.delete_programe(wid)
        ml.delete_canvas(wid)
    ml.clear_screen()

    ml.show_text(0, 0, 192, 16, "0F0", "TEST:", h_align="00", font=4)

    ml.create_canvas(TEST_CANVAS, 60, 16, 60, 16)
    # Match the known-working flight labels animation: en=2 sp=5 du=0 ex=2 repeat=20
    ml.create_txt_programe(
        TEST_CANVAS,
        "0FF",
        2,  # en
        5,  # sp
        0,  # du
        2,  # ex
        20,  # repeat
        LONG_TEXT,
        h_align="00",
        font=4,
    )

    logger.info("Scroll overflow test displayed.")
    logger.info("Observe row 2 canvas at x=60..120 (60px wide):")
    logger.info("  Long text: %r", LONG_TEXT)
    logger.info("  Does it marquee through the whole text, or clip and hold?")
    try:
        while True:
            time.sleep(1)
    finally:
        ml.delete_programe(TEST_CANVAS)
        ml.delete_canvas(TEST_CANVAS)
        ml.clear_screen()
        logger.info("Done.")


if __name__ == "__main__":
    main()
