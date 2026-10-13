import time
import struct

# (command, data, wait in ms). Without the waits the panel may ignore
# Sleep Out and stay dark (black screen on the ESP32-S3-LCD-1.69).
ST7789_INIT = (
    (0x01, None, 150),  # Software reset
    (0x11, None, 120),  # Sleep out
    (0x3A, b'\x05', 0),
)
# JD9853 (ESP32-C6-Touch-LCD-1.47): vendor sequence from the Waveshare demo
# (esp_lcd_jd9853.c) up to the pixel format; 0xDF unlocks the vendor commands.
JD9853_INIT = (
    (0x11, None, 120),  # Sleep out
    (0xDF, b'\x98\x53', 0),
    (0xDF, b'\x98\x53', 0),
    (0xB2, b'\x23', 0),
    (0xB7, b'\x00\x47\x00\x6F', 0),
    (0xBB, b'\x1C\x1A\x55\x73\x63\xF0', 0),
    (0xC0, b'\x44\xA4', 0),
    (0xC1, b'\x16', 0),
    (0xC3, b'\x7D\x07\x14\x06\xCF\x71\x72\x77', 0),
    (0xC4, b'\x00\x00\xA0\x79\x0B\x0A\x16\x79\x0B\x0A\x16\x82', 0),
    (0xC8, b'\x3F\x32\x29\x29\x27\x2B\x27\x28\x28\x26\x25\x17\x12\x0D\x04\x00' * 2, 0),
    (0xD0, b'\x04\x06\x6B\x0F\x00', 0),
    (0xD7, b'\x00\x30', 0),
    (0xE6, b'\x14', 0),
    (0xDE, b'\x01', 0),
    (0xB7, b'\x03\x13\xEF\x35\x35', 0),
    (0xC1, b'\x14\x15\xC0', 0),
    (0xC2, b'\x06\x3A', 0),
    (0xC4, b'\x72\x12', 0),
    (0xBE, b'\x00', 0),
    (0xDE, b'\x02', 0),
    (0xE5, b'\x00\x02\x00', 0),
    (0xE5, b'\x01\x02\x00', 0),
    (0xDE, b'\x00', 0),
    (0x35, b'\x00', 0),
    (0x3A, b'\x05', 0),  # RGB565
    (0xDE, b'\x02', 0),
    (0xE5, b'\x00\x02\x00', 0),
    (0xDE, b'\x00', 0),
)
INIT = {"st7789": ST7789_INIT, "jd9853": JD9853_INIT}


class ST7789:
    """Driver without a full-screen framebuffer.

    A 320x172 RGB565 frame would take 110 KB in one block; on the ESP32-C6 that
    left Wi-Fi and BLE without memory (sync timeouts, BLE ENOMEM, crashes).
    Callers draw small strips and blit them to a screen region instead.
    Also drives the JD9853, which shares the ST7789 commands used here.
    """

    def __init__(self, spi, width, height, reset, dc, cs, backlight, rotation=1,
                 offset=(0, 34), madctl=0x68, controller="st7789"):
        self.spi = spi
        # Panel position in the controller's 240 x 320 RAM, landscape (x, y).
        self.offset = offset
        self._width = width   # Physikalisch 172
        self._height = height # Physikalisch 320
        self.reset = reset
        self.dc = dc
        self.cs = cs
        self.backlight = backlight
        self.rotation = rotation

        # Dimensionen für Querformat tauschen
        if self.rotation in [1, 3]:
            self.width = height
            self.height = width
        else:
            self.width = width
            self.height = height

        self.cs.value(1)
        self.reset.value(0)
        time.sleep_ms(50)
        self.reset.value(1)
        # ST7789 datasheet: up to 120 ms after a reset before Sleep Out is accepted.
        time.sleep_ms(120)

        # MADCTL (0x36): 0x60 = Landscape, 0x08 = BGR-Farbreihenfolge
        madctl = madctl if rotation == 1 else 0x08
        self.madctl = madctl

        for cmd, data, wait in INIT[controller] + (
            (0x36, bytes([madctl]), 0),
            (0x21, None, 0),    # Inversion on (IPS panels)
            (0x13, None, 10),
            (0x29, None, 20),   # Display on
        ):
            self._write(cmd, data)
            if wait:
                time.sleep_ms(wait)

        if self.backlight: self.backlight.value(1)

    def _write(self, command, data=None):
        self.dc.value(0)
        self.cs.value(0)
        self.spi.write(bytearray([command]))
        self.cs.value(1)
        if data is not None:
            self.dc.value(1)
            self.cs.value(0)
            self.spi.write(data)
            self.cs.value(1)

    def _window(self, x, y, w, h):
        # Offset-Korrektur, z. B. Waveshare 1.47" im Querformat: Y-Offset 34
        ox, oy = self.offset
        self._write(0x2A, struct.pack(">HH", ox + x, ox + x + w - 1))
        self._write(0x2B, struct.pack(">HH", oy + y, oy + y + h - 1))

    def blit(self, buffer, x, y, w, h):
        """Send a w x h RGB565 region from the start of `buffer`."""
        self._window(x, y, w, h)
        self._write(0x2C, memoryview(buffer)[:w * h * 2])

    def clear(self, pattern):
        """Fill the whole screen by repeating `pattern` (RGB565 bytes)."""
        self._window(0, 0, self.width, self.height)
        self.dc.value(0)
        self.cs.value(0)
        self.spi.write(b"\x2c")
        self.dc.value(1)
        remaining = self.width * self.height * 2
        while remaining > 0:
            chunk = memoryview(pattern)[:min(len(pattern), remaining)]
            self.spi.write(chunk)
            remaining -= len(chunk)
        self.cs.value(1)
