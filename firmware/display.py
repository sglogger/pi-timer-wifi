import machine
import framebuf
import time
import st7789
from timer_logic import phase, clock_text


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
        self.char = framebuf.FrameBuffer(bytearray(8), 8, 8, framebuf.MONO_HLSB)
        self.previous = None

    def text(self, text, x, y, scale, color):
        for index, char in enumerate(text):
            self.char.fill(0)
            self.char.text(char, 0, 0, 1)
            for py in range(8):
                for px in range(8):
                    if self.char.pixel(px, py):
                        self.tft.fill_rect(x + (index * 8 + px) * scale,
                                           y + py * scale, scale, scale, color)

    def render(self, remaining, link, ble):
        current = phase(remaining)
        blink = current == "overdue" and (time.ticks_ms() // 500) % 2 == 1
        label = clock_text(remaining)
        key = (label, current, link, ble, blink)
        if key == self.previous:
            return
        self.previous = key
        # RGB565, byte-swapped for the SPI transfer; MADCTL BGR swaps red/blue.
        colors = {"off": 0xFFFF, "green": 0xE007, "yellow": 0xFF07,
                  "orange": 0x5F03, "red": 0x1F00, "overdue": 0x1F00}
        color = 0 if blink else colors[current]
        self.tft.fill(0)
        scale = min(6, 300 // (len(label) * 8))
        self.text(label, (320 - len(label) * 8 * scale) // 2, 60, scale, color)
        self.text("SwiNOG", 8, 10, 2, 0xFFFF)
        status = "%s   BLE %s" % (link, "OK" if ble else "OFFLINE")
        self.text(status, 8, 145, 1, 0xFFFF)
        # Same 8 px size as the status line, right-aligned to the 320 px width.
        if self.hostname:
            self.text(self.hostname, 312 - len(self.hostname) * 8, 14, 1, 0xFFFF)
        if self.version:
            self.text(self.version, 312 - len(self.version) * 8, 145, 1, 0xFFFF)
        self.tft.show()
