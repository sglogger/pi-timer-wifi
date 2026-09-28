import time
import framebuf
import struct

class ST7789(framebuf.FrameBuffer):
    def __init__(self, spi, width, height, reset, dc, cs, backlight, rotation=1):
        self.spi = spi
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

        self.buffer = bytearray(self.width * self.height * 2)
        super().__init__(self.buffer, self.width, self.height, framebuf.RGB565)

        self.reset.value(0)
        time.sleep_ms(50)
        self.reset.value(1)
        time.sleep_ms(50)

        # MADCTL (0x36): 0x60 = Landscape, 0x08 = BGR-Farbreihenfolge
        madctl = 0x68 if rotation == 1 else 0x08

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

    def show(self):
        # Offset-Korrektur für Waveshare 1.47" (Landscape: Y-Offset 34)
        ox, oy = 0, 34
        self._write(0x2A, struct.pack(">HH", ox, ox + self.width - 1))
        self._write(0x2B, struct.pack(">HH", oy, oy + self.height - 1))
        self._write(0x2C, self.buffer)
