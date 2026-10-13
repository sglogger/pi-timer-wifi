"""Hardware profiles of the supported Waveshare boards; see firmware/README.md.

The firmware picks the profile from the chip (ESP32-S3 or not); BOARD in
config.py overrides it, e.g. for the older S3 board revision.
"""
import sys
import machine

BOARDS = {
    # ESP32-C6-LCD-1.47: 172 x 320 panel, centred in the ST7789's 240 x 320 RAM.
    "c6-147": {
        "sck": 7, "mosi": 6, "cs": 14, "dc": 15, "reset": 21, "backlight": 22,
        "panel": (172, 320), "offset": (0, 34), "madctl": 0x68,
        # Screen regions (y, height) in landscape and the left/right text margin.
        "margin": 8, "header": (10, 16), "clock": (60, 48), "status": (145, 8),
    },
    # ESP32-S3-LCD-1.69, revision V2 ("V2QC" label): 240 x 280 panel with rounded
    # corners. On battery the board switches itself off unless SYS_EN stays high.
    "s3-169": {
        "sck": 6, "mosi": 7, "cs": 5, "dc": 4, "reset": 8, "backlight": 15,
        "panel": (240, 280), "offset": (20, 0), "madctl": 0x68,
        # Wider margin for the rounded corners; status and version on two lines.
        "margin": 20, "header": (24, 16), "clock": (96, 48), "status": (190, 20),
        "power_hold": 41, "buzzer": 42,
    },
}
# First revision of the S3 board: same display, other power and buzzer pins.
# GPIO33-37 carry octal PSRAM on an ESP32-S3R8 (datasheet, section 2.3.4); only
# use this profile on a board whose PSRAM leaves them free.
BOARDS["s3-169-v1"] = dict(BOARDS["s3-169"], power_hold=35, buzzer=33)


def select(name=""):
    """Profile for BOARD from config.py, else detected from the chip."""
    if not name:
        # E.g. "Generic ESP32S3 module with ESP32S3"; the unix port has its own text.
        machine_name = getattr(sys.implementation, "_machine", "")
        name = "s3-169" if "ESP32S3" in machine_name else "c6-147"
    if name not in BOARDS:
        raise ValueError("Invalid BOARD")
    return name, BOARDS[name]


def setup(board):
    """Board pins that must be set before anything else runs."""
    if "power_hold" in board:
        machine.Pin(board["power_hold"], machine.Pin.OUT).value(1)
    if "buzzer" in board:
        # A passive buzzer left floating draws current and heats the board.
        machine.Pin(board["buzzer"], machine.Pin.OUT).value(0)
