"""Per-character pixel widths for the LED display's font 4.

Font 4 is fixed-width: every character renders in an 8-pixel cell.
This was verified by rendering ``ABEFGHIKLMNOPRSTX 1:`` via
test_char_width.py and measuring the pixel-accurate stride from one
letter's start to the next — exactly 8 logical pixels for every
character analyzed.

:data:`CELL_W` is the stride used for all layout calculations (it's
what determines where the next character starts, and therefore where
the scroll canvas should begin after a label).

:data:`GLYPH_W` records the width of the actual lit pixels within
each cell (useful if you ever need tight kerning).  Only measured for
characters where clean sampling was possible.
"""

from __future__ import annotations

CELL_W = 8

GLYPH_W: dict[str, int] = {
    "A": 7,
    "B": 6,
    "E": 6,
    "F": 6,
    "G": 6,
    "H": 6,
    "I": 5,
    "K": 6,
    "L": 6,
    "M": 6,
    "N": 6,
    "O": 6,
    "P": 6,
    "R": 7,
    "S": 6,
    "T": 7,
    "X": 7,
    "1": 5,
    ":": 1,
}


def pixel_width(text: str) -> int:
    """Return the rendered pixel width of a font-4 string (cell-based)."""
    return len(text) * CELL_W
