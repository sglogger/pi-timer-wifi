"""Hardware profiles of the supported Waveshare boards; see firmware/README.md.

The firmware picks the profile from the chip (ESP32-S3 or not) and, on the C6,
from the touch board's I2C devices; BOARD in config.py overrides it, e.g. for
the older S3 board revision.
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
    # ESP32-C6-Touch-LCD-1.47: same panel size and offset, but a JD9853 controller
    # (ST7789 command set, own init sequence) and other pins. Touch stays unused.
    "c6-touch-147": {
        "sck": 1, "mosi": 2, "cs": 14, "dc": 15, "reset": 22, "backlight": 23,
        # Without miso, MicroPython takes GPIO2 (the C6's SPI IOMUX MISO) as input
        # and MOSI never reaches the display. GPIO3 is the TF slot's MISO.
        "miso": 3,
        "panel": (172, 320), "offset": (0, 34), "madctl": 0x68, "controller": "jd9853",
        "margin": 8, "header": (10, 16), "clock": (60, 48), "status": (145, 8),
        # The TF slot shares SCK/MOSI with the display: keep its CS high.
        "deselect": 4,
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
# On the C6 touch board: I2C bus of touch controller and IMU (Waveshare demo code).
TOUCH_I2C = (19, 18)  # SCL, SDA
TOUCH_DEVICES = (0x63, 0x6B)  # AXS5106L touch, QMI8658 IMU


def touch_board():
    """True if the touch board's touch controller or IMU answers on I2C."""
    try:
        # Hardware I2C enables the internal pull-ups: on the board without touch
        # the open pins read high and the scan finds nothing.
        found = machine.I2C(0, scl=machine.Pin(TOUCH_I2C[0]), sda=machine.Pin(TOUCH_I2C[1]),
                            freq=100000).scan()
    except (AttributeError, OSError, ValueError):
        return False
    # Lines held low answer every address; that is not this board.
    return len(found) < 8 and any(address in found for address in TOUCH_DEVICES)


def select(name=""):
    """Profile for BOARD from config.py, else detected from the chip."""
    if not name:
        # E.g. "Generic ESP32S3 module with ESP32-S3"; the unix port has its own text.
        machine_name = getattr(sys.implementation, "_machine", "")
        s3 = "ESP32S3" in machine_name or "ESP32-S3" in machine_name
        name = "s3-169" if s3 else "c6-touch-147" if touch_board() else "c6-147"
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
    if "deselect" in board:
        machine.Pin(board["deselect"], machine.Pin.OUT).value(1)
