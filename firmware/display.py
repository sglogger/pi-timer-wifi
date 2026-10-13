import machine
import framebuf
import time
import st7789
from timer_logic import phase, clock_text

# Tallest region: countdown at scale 6 (8 px font). One strip buffer (30 KB on
# the C6) replaces the former 110 KB full-screen framebuffer (see st7789.py).
STRIP_HEIGHT = 48
WHITE = 0xFFFF
# Width of the scale-2 "SwiNOG" title plus a gap before the hostname.
TITLE_WIDTH = 104


class Display:
    def __init__(self, board, hostname="", version="", flip=False):
        # Screen regions (y, height) and margins come from the board profile (boards.py).
        self.width = board["panel"][1]
        self.margin = board["margin"]
        self.header, self.clock, self.status = board["header"], board["clock"], board["status"]
        # Right of the title: 25 characters on the C6, fewer on narrower screens.
        self.hostname = hostname[:(self.width - 2 * self.margin - TITLE_WIDTH) // 8]
        self.version = "v" + version if version else ""
        # 180 degrees: mirror both axes (MADCTL MX and MY). The panel sits centred in
        # the controller RAM on both boards, so the offset stays the same.
        madctl = board["madctl"] ^ 0xC0 if flip else board["madctl"]
        spi = machine.SPI(1, baudrate=40000000, sck=machine.Pin(board["sck"]),
                          mosi=machine.Pin(board["mosi"]))
        self.tft = st7789.ST7789(spi, board["panel"][0], board["panel"][1],
                               reset=machine.Pin(board["reset"], machine.Pin.OUT),
                               dc=machine.Pin(board["dc"], machine.Pin.OUT),
                               cs=machine.Pin(board["cs"], machine.Pin.OUT),
                               backlight=machine.Pin(board["backlight"], machine.Pin.OUT),
                               rotation=1, offset=board["offset"], madctl=madctl,
                               controller=board.get("controller", "st7789"))
        self.buffer = bytearray(self.width * STRIP_HEIGHT * 2)
        # One frame buffer per region height, all on the same bytes.
        self.strips = {height: framebuf.FrameBuffer(self.buffer, self.width, height, framebuf.RGB565)
                       for height in (self.header[1], self.clock[1], self.status[1])}
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

    def right(self, text):
        """x of 8 px text aligned to the right margin."""
        return self.width - self.margin - len(text) * 8

    def centre(self, text):
        return (self.width - len(text) * 8) // 2

    def region(self, area):
        """Cleared strip for a screen region; draw into it, then send()."""
        strip = self.strips[area[1]]
        strip.fill(0)
        return strip

    def send(self, area):
        self.tft.blit(self.buffer, 0, area[0], self.width, area[1])

    def render(self, remaining, link, ble):
        current = phase(remaining)
        blink = current == "overdue" and (time.ticks_ms() // 500) % 2 == 1
        label = clock_text(remaining)
        key = (label, current, link, ble, blink)
        if key == self.previous:
            return
        full = self.previous is None
        if full:
            strip = self.region(self.header)
            self.text(strip, "SwiNOG", self.margin, 0, 2, WHITE)
            # Same 8 px size as the status line, right-aligned.
            if self.hostname:
                self.text(strip, self.hostname, self.right(self.hostname), 4, 1, WHITE)
            self.send(self.header)
        if full or (label, current, blink) != (self.previous[0], self.previous[1], self.previous[4]):
            # RGB565, byte-swapped for the SPI transfer; MADCTL BGR swaps red/blue.
            colors = {"off": 0xFFFF, "green": 0xE007, "yellow": 0xFF07,
                      "orange": 0x5F03, "red": 0x1F00, "overdue": 0x1F00}
            strip = self.region(self.clock)
            scale = min(6, (self.width - 2 * self.margin) // (len(label) * 8))
            self.text(strip, label, (self.width - len(label) * 8 * scale) // 2, 0, scale,
                      0 if blink else colors[current])
            self.send(self.clock)
        if full or key[2:4] != self.previous[2:4]:
            strip = self.region(self.status)
            status = "%s   BLE %s" % (link, "OK" if ble else "OFFLINE")
            if self.status[1] >= 20:
                # Two centred lines: the status line alone fills a narrow screen.
                self.text(strip, status, self.centre(status), 0, 1, WHITE)
                if self.version:
                    self.text(strip, self.version, self.centre(self.version), 12, 1, WHITE)
            else:
                self.text(strip, status, self.margin, 0, 1, WHITE)
                if self.version:
                    self.text(strip, self.version, self.right(self.version), 0, 1, WHITE)
            self.send(self.status)
        self.previous = key
