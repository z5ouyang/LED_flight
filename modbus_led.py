from __future__ import annotations

import logging
import re
import time
import unicodedata

import serial

logger = logging.getLogger(__name__)

DEBUG_VERBOSE: bool = False
PORT = "/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_B001K6BE-if00-port0"
BAUDRATE = 115200
SF = b"\xaa\xa5"
GID = b""
SRC = b"\x00\x00"
TID = b"\xb0\xa1"
CRC = b"\x00\x00"
EF = b"\x5a\x55"


def _safe_ascii(txt: str) -> bytes:
    """Strip accents and encode to ASCII for GB2312 display."""
    normalized = unicodedata.normalize("NFKD", txt)
    return normalized.encode("ascii", errors="replace")


def send_modbus(tx_data: bytes) -> bytes:
    with serial.Serial(
        port=PORT,
        baudrate=BAUDRATE,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        bytesize=serial.EIGHTBITS,
        timeout=1,
    ) as ser:
        ser.reset_input_buffer()
        ser.write(tx_data)
        time.sleep(0.1)
        rx_data = ser.read_all()
    return rx_data if rx_data is not None else b""


def get_response(DES: bytes, CMD: bytes, CNT: bytes = b"") -> bytes | None:
    CTRL = int(8 + len(CNT)).to_bytes(2, byteorder="little")
    rx_data = send_modbus(SF + CTRL + DES + SRC + TID + CMD + CNT + CRC + EF)
    rx_len = len(rx_data)
    if rx_data[:2] != SF:
        logger.debug("SF flag not match! %s", rx_data[:2])
        return None
    if rx_data[8:10] != TID:
        logger.debug("TID not match! %s vs %s", TID, rx_data[8:10])
        return None
    if rx_data[12:14] != b"\x00\x00":
        logger.error("ERROR code: %s", rx_data[12:14].hex())
        return None
    if rx_data[rx_len - 2 :] != EF:
        logger.debug("EF flag not match! %s", rx_data[16:])
    return rx_data


def get_GID() -> None:
    global GID
    rx_data = get_response(b"\xff\xff", b"\x01\x00")
    if rx_data is None:
        logger.error("Failed to get GID — no response")
        return
    GID = rx_data[6:8]


def get_W_H() -> tuple[int, int] | None:
    rx_data = get_response(GID, b"\x1f\x00")
    if rx_data is None:
        return None
    W = int.from_bytes(rx_data[14:16], byteorder="little")
    H = int.from_bytes(rx_data[16:18], byteorder="little")
    return W, H


def get_brightness() -> int | None:
    rx_data = get_response(GID, b"\x37\x00")
    if rx_data is None:
        return None
    return int.from_bytes(rx_data[14:16], byteorder="little")


def set_brightness(lum: int) -> None:
    if lum < 0 or lum > 990:
        logger.warning("Out of brightness range, set to 500")
        lum = 500
    get_response(GID, b"\x38\x00", int(lum).to_bytes(2, byteorder="little"))


def get_text_color() -> str | None:
    rx_data = get_response(GID, b"\x43\x00")
    if rx_data is None:
        return None
    color = ["", "F00", "0F0", "FF0", "00F", "F0F", "0FF", "FFF", "000"]
    return color[int(rx_data[14])]


def set_text_color(col: str) -> None:
    if len(col) > 3 or not set(col).issubset({"F", "0"}):
        logger.warning("Incorrect color code: %s — set to white", col)
        col = "FFF"
    col = re.sub("F", "1", col)[::-1]
    col = "1000".zfill(8) if col == "000" else col.zfill(8)
    col_bytes = int(col, 2).to_bytes(1)
    get_response(GID, b"\x44\x00", col_bytes)


def get_paint_color() -> str | None:
    rx_data = get_response(GID, b"\x4b\x00")
    if rx_data is None:
        return None
    color = ["", "F00", "0F0", "FF0", "00F", "F0F", "0FF", "FFF", "000"]
    return color[int(rx_data[14])]


def set_paint_color(col: str) -> None:
    if len(col) > 3 or not set(col).issubset({"F", "0"}):
        logger.warning("Incorrect color code: %s — set to white", col)
        col = "FFF"
    col = re.sub("F", "1", col)[::-1]
    col = "1000".zfill(8) if col == "000" else col.zfill(8)
    col_bytes = int(col, 2).to_bytes(1)
    get_response(GID, b"\x4c\x00", col_bytes)


def get_font_number() -> int | None:
    rx_data = get_response(GID, b"\x00\x01")
    if rx_data is None:
        return None
    return int(rx_data[14])


def clear_screen() -> None:
    get_response(GID, b"\x00\x02")


def clear_area(x: int, y: int, w: int, h: int) -> None:
    pCol = get_paint_color()
    set_paint_color("000")
    X = int(x).to_bytes(2, byteorder="little")
    Y = int(y).to_bytes(2, byteorder="little")
    W = int(w).to_bytes(2, byteorder="little")
    H = int(h).to_bytes(2, byteorder="little")
    get_response(GID, b"\x1c\x02", X + Y + W + H)
    if pCol is not None:
        set_paint_color(pCol)


def _validate_color(col: str) -> str:
    if len(col) > 3 or not set(col).issubset({"F", "0"}):
        logger.warning("Incorrect color code: %s — set to white", col)
        return "FFF"
    return col


def _encode_text_format(
    col: str,
    h_align: str,
    v_align: str,
    multiline: bool,
    font: int | None,
) -> bytes:
    col = re.sub("F", "1", col)[::-1]
    col = "1000" if col == "000" else "0" + col
    font_id = "00000000" if font is None else format(font, "08b")
    others = "0000" if multiline else "0010"
    return int("000000000000" + col + font_id + h_align + v_align + others, 2).to_bytes(
        4, byteorder="little"
    )


def show_text(
    x: int,
    y: int,
    w: int,
    h: int,
    col: str,
    txt: str,
    h_align: str = "01",
    v_align: str = "01",
    multiline: bool = False,
    font: int | None = None,
) -> None:
    col = _validate_color(col)
    X = int(x).to_bytes(2, byteorder="little")
    Y = int(y).to_bytes(2, byteorder="little")
    W = int(w).to_bytes(2, byteorder="little")
    H = int(h).to_bytes(2, byteorder="little")
    FORMAT = _encode_text_format(col, h_align, v_align, multiline, font)
    txt_bytes = _safe_ascii(txt)
    CNT = int(len(txt_bytes)).to_bytes(2, byteorder="little")
    get_response(
        GID,
        b"\x38\x02",
        X + Y + W + H + FORMAT + CNT + txt_bytes,
    )


def show_image(x: int, y: int, img: list[str]) -> None:
    PG = b""
    PN = 0
    for i, r in enumerate(img):
        for j, p in enumerate(r):
            if p == "1":
                PN += 1
                PG += int(x + j).to_bytes(2, byteorder="little")
                PG += int(y + i).to_bytes(2, byteorder="little")
    get_response(
        GID,
        b"\x04\x02",
        int(PN).to_bytes(2, byteorder="little") + PG,
    )


def move_frame_left(x: int, y: int, w: int, h: int) -> None:
    X = int(x).to_bytes(2, byteorder="little")
    Y = int(y).to_bytes(2, byteorder="little")
    W = int(w).to_bytes(2, byteorder="little")
    H = int(h).to_bytes(2, byteorder="little")
    get_response(GID, b"\x44\x02", X + Y + W + H)


def move_frame_right(x: int, y: int, w: int, h: int) -> None:
    X = int(x).to_bytes(2, byteorder="little")
    Y = int(y).to_bytes(2, byteorder="little")
    W = int(w).to_bytes(2, byteorder="little")
    H = int(h).to_bytes(2, byteorder="little")
    get_response(GID, b"\x45\x02", X + Y + W + H)


def move_frame_up(x: int, y: int, w: int, h: int) -> None:
    X = int(x).to_bytes(2, byteorder="little")
    Y = int(y).to_bytes(2, byteorder="little")
    W = int(w).to_bytes(2, byteorder="little")
    H = int(h).to_bytes(2, byteorder="little")
    get_response(GID, b"\x46\x02", X + Y + W + H)


def move_frame_down(x: int, y: int, w: int, h: int) -> None:
    X = int(x).to_bytes(2, byteorder="little")
    Y = int(y).to_bytes(2, byteorder="little")
    W = int(w).to_bytes(2, byteorder="little")
    H = int(h).to_bytes(2, byteorder="little")
    get_response(GID, b"\x47\x02", X + Y + W + H)


def create_canvas(wid: int, x: int, y: int, w: int, h: int) -> None:
    WID = int(wid).to_bytes(2, byteorder="little")
    OP = b"\x00\x00"
    X = int(x).to_bytes(2, byteorder="little")
    Y = int(y).to_bytes(2, byteorder="little")
    W = int(w).to_bytes(2, byteorder="little")
    H = int(h).to_bytes(2, byteorder="little")
    STYLE = b"\x00\x00\x00\x00"
    USR = b"\x00\x00\x00\x00"
    get_response(GID, b"\x03\x03", WID + OP + X + Y + W + H + STYLE + USR)


def delete_canvas(wid: int) -> None:
    WID = int(wid).to_bytes(2, byteorder="little")
    get_response(GID, b"\x05\x03", WID)


def _encode_animation_timing(en: int, sp: int, du: int, ex: int, repeat: int) -> bytes:
    ENTRY = int(en).to_bytes(2, byteorder="little")
    SPENTRY = int(sp).to_bytes(2, byteorder="little")
    DUENTRY = int(du).to_bytes(2, byteorder="little")
    HIGHLIGHT = b"\x00\x00"
    SPHL = b"\x00\x00"
    DUHL = b"\x00\x00"
    EXIT = int(ex).to_bytes(2, byteorder="little")
    SPEXIT = SPENTRY
    TIMES = int(repeat).to_bytes(2, byteorder="little")
    return ENTRY + SPENTRY + DUENTRY + HIGHLIGHT + SPHL + DUHL + EXIT + SPEXIT + TIMES


def create_txt_programe(
    wid: int,
    col: str,
    en: int,
    sp: int,
    du: int,
    ex: int,
    repeat: int,
    txt: str,
    h_align: str = "01",
    v_align: str = "01",
    multiline: bool = False,
    font: int | None = None,
) -> None:
    col = _validate_color(col)
    WID = int(wid).to_bytes(2, byteorder="little")
    REV = b"\x00\x00"
    STYLE = b"\x00\x00\x00\x00"
    FORMAT = _encode_text_format(col, h_align, v_align, multiline, font)
    TIMING = _encode_animation_timing(en, sp, du, ex, repeat)
    txt_bytes = _safe_ascii(txt)
    CNT = int(len(txt_bytes)).to_bytes(2, byteorder="little")
    try:
        get_response(
            GID,
            b"\x10\x03",
            WID + REV + STYLE + FORMAT + TIMING + CNT + txt_bytes,
        )
    except (serial.SerialException, OSError) as e:
        logger.error("Error in create_txt_programe: %s", txt)
        logger.error("\tmessage: %s", e)
        raise


def create_img_program(
    wid: int,
    en: int,
    sp: int,
    du: int,
    ex: int,
    repeat: int,
    img: int,
) -> None:
    WID = int(wid).to_bytes(2, byteorder="little")
    REV = b"\x00\x00"
    STYLE = b"\x00\x00\x00\x00"
    FORMAT = b"\x00\x00\x00\x00"
    TIMING = _encode_animation_timing(en, sp, du, ex, repeat)
    REV1 = b"\x00\x00"
    BMPSRC = b"\x00\x00\x00\x00\x02\x00\x00\x00"
    SRC = int(img).to_bytes(2, byteorder="little")
    try:
        get_response(
            GID,
            b"\x12\x03",
            WID + REV + STYLE + FORMAT + TIMING + REV1 + BMPSRC + SRC,
        )
    except (serial.SerialException, OSError) as e:
        logger.error("Error: %s", e)
        raise


def delete_programe(wid: int) -> None:
    WID = int(wid).to_bytes(2, byteorder="little")
    OP = b"\x00\xff"
    get_response(GID, b"\x0f\x03", WID + OP)


def calculate_modbus_crc(data: bytes) -> bytes:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc.to_bytes(2, "little")
