"""Per-character pixel widths for the LED display's font 4.

Font 4 is fixed-width: every character renders in an 8-pixel cell.
Verified by analyzing test_char_width.py's rendered output — the
stride from one letter's start to the next is exactly 8 logical
pixels for every letter and digit.
"""

from __future__ import annotations

CELL_W = 8


def pixel_width(text: str) -> int:
    """Return the rendered pixel width of a font-4 string."""
    return len(text) * CELL_W
