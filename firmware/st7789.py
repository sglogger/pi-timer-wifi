import time
import struct

class ST7789:
    """Driver without a full-screen framebuffer.

    A 320x172 RGB565 frame would take 110 KB in one block; on the ESP32-C6 that
    left Wi-Fi and BLE without memory (sync timeouts, BLE ENOMEM, crashes).
    Callers draw small strips and blit them to a screen region instead.
    """

    def __init__(self, spi, width, height, reset, dc, cs, backlight, rotation=1,
                 offset=(0, 34), madctl=0x68):
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

        self.reset.value(0)
        time.sleep_ms(50)
        self.reset.value(1)
        time.sleep_ms(50)

        # MADCTL (0x36): 0x60 = Landscape, 0x08 = BGR-Farbreihenfolge
        madctl = madctl if rotation == 1 else 0x08

        for cmd, data in [
            (0x01, None),
            (0x11, None),
            (0x3A, b'\x05'),
            (0x36, bytes([madctl])),
            (0x21, None),
            (0x13, None),
            (0x29, None),
        ]:
            self._write(cmd, data)

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
