"""Per-character pixel widths for the LED display's font 4.

Measured from ``test_char_width.py`` against the pixel ruler.  The
values cover every character used in any stat label plus common
punctuation.  Unknown characters fall back to ``DEFAULT_CHAR_W``.
"""

from __future__ import annotations

DEFAULT_CHAR_W = 10

CHAR_W: dict[str, int] = {
    "A": 10,
    "B": 10,
    "C": 10,
    "D": 10,
    "E": 8,
    "F": 8,
    "G": 11,
    "H": 10,
    "I": 5,
    "J": 7,
    "K": 10,
    "L": 7,
    "M": 13,
    "N": 11,
    "O": 11,
    "P": 10,
    "Q": 11,
    "R": 10,
    "S": 9,
    "T": 9,
    "U": 10,
    "V": 10,
    "W": 13,
    "X": 10,
    "Y": 10,
    "Z": 9,
    "0": 9,
    "1": 5,
    "2": 9,
    "3": 9,
    "4": 9,
    "5": 9,
    "6": 9,
    "7": 9,
    "8": 9,
    "9": 9,
    " ": 6,
    ":": 4,
    "-": 5,
    "(": 5,
    ")": 5,
    ".": 4,
    ",": 4,
    "/": 5,
}


def pixel_width(text: str) -> int:
    """Return the rendered pixel width of a font-4 string."""
    return sum(CHAR_W.get(c, DEFAULT_CHAR_W) for c in text)
