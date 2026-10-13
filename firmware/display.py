import machine
import framebuf
import time
import st7789
from timer_logic import phase, clock_text

WIDTH = 320
# Tallest region: countdown at scale 6 (8 px font). One 30 KB strip buffer
# replaces the former 110 KB full-screen framebuffer (see st7789.py).
STRIP_HEIGHT = 48
WHITE = 0xFFFF
# Screen regions: (y, height).
HEADER = (10, 16)
CLOCK = (60, STRIP_HEIGHT)
STATUS = (145, 8)


class Display:
    def __init__(self, hostname="", version=""):
        # Right of the scale-2 "SwiNOG" title there is room for 25 characters.
        self.hostname = hostname[:25]
        self.version = "v" + version if version else ""
        spi = machine.SPI(1, baudrate=40000000, sck=machine.Pin(7), mosi=machine.Pin(6))
        self.tft = st7789.ST7789(spi, 172, 320,
                               reset=machine.Pin(21, machine.Pin.OUT),
                               dc=machine.Pin(15, machine.Pin.OUT),
                               cs=machine.Pin(14, machine.Pin.OUT),
                               backlight=machine.Pin(22, machine.Pin.OUT), rotation=1)
        self.buffer = bytearray(WIDTH * STRIP_HEIGHT * 2)
        # One frame buffer per region height, all on the same bytes.
        self.strips = {height: framebuf.FrameBuffer(self.buffer, WIDTH, height, framebuf.RGB565)
                       for height in (HEADER[1], CLOCK[1], STATUS[1])}
        self.char = framebuf.FrameBuffer(bytearray(8), 8, 8, framebuf.MONO_HLSB)
        self.previous = None
        # Black screen; the strip buffer is still all zeros here.
        self.tft.clear(self.buffer)

    def text(self, target, text, x, y, scale, color):
        for index, char in enumerate(text):
            self.char.fill(0)
            self.char.text(char, 0, 0, 1)
            for py in range(8):
                for px in range(8):
                    if self.char.pixel(px, py):
                        target.fill_rect(x + (index * 8 + px) * scale,
                                         y + py * scale, scale, scale, color)

    def region(self, area):
        """Cleared strip for a screen region; draw into it, then send()."""
        strip = self.strips[area[1]]
        strip.fill(0)
        return strip

    def send(self, area):
        self.tft.blit(self.buffer, 0, area[0], WIDTH, area[1])

    def render(self, remaining, link, ble):
        current = phase(remaining)
        blink = current == "overdue" and (time.ticks_ms() // 500) % 2 == 1
        label = clock_text(remaining)
        key = (label, current, link, ble, blink)
        if key == self.previous:
            return
        full = self.previous is None
        if full:
            strip = self.region(HEADER)
            self.text(strip, "SwiNOG", 8, 0, 2, WHITE)
            # Same 8 px size as the status line, right-aligned to the 320 px width.
            if self.hostname:
                self.text(strip, self.hostname, 312 - len(self.hostname) * 8, 4, 1, WHITE)
            self.send(HEADER)
        if full or (label, current, blink) != (self.previous[0], self.previous[1], self.previous[4]):
            # RGB565, byte-swapped for the SPI transfer; MADCTL BGR swaps red/blue.
            colors = {"off": 0xFFFF, "green": 0xE007, "yellow": 0xFF07,
                      "orange": 0x5F03, "red": 0x1F00, "overdue": 0x1F00}
            strip = self.region(CLOCK)
            scale = min(6, 300 // (len(label) * 8))
            self.text(strip, label, (WIDTH - len(label) * 8 * scale) // 2, 0, scale,
                      0 if blink else colors[current])
            self.send(CLOCK)
        if full or key[2:4] != self.previous[2:4]:
            strip = self.region(STATUS)
            self.text(strip, "%s   BLE %s" % (link, "OK" if ble else "OFFLINE"), 8, 0, 1, WHITE)
            if self.version:
                self.text(strip, self.version, 312 - len(self.version) * 8, 0, 1, WHITE)
            self.send(STATUS)
        self.previous = key
