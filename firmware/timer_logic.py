"""Pure timer rules shared by host tests and MicroPython firmware."""

# ESP32 firmware version, reported on every sync; the server compares it with this
# repository copy. Bump only when files copied to the ESP32 change (see CHANGELOG.md).
FIRMWARE_VERSION = "1.0.0"

# Upper bound (inclusive, ms) per phase; the web UI receives these via the server.
THRESHOLDS = (("overdue", -30000), ("red", 0), ("orange", 60000), ("yellow", 300000))


def phase(remaining_ms):
    if remaining_ms is None:
        return "off"
    for name, limit in THRESHOLDS:
        if remaining_ms <= limit:
            return name
    return "green"


def clock_text(remaining_ms):
    if remaining_ms is None:
        return "READY"
    # Positive countdown rounds up; overtime rounds down in absolute seconds.
    seconds = (remaining_ms + 999) // 1000
    minutes, seconds_abs = divmod(abs(seconds), 60)
    return "%s%02d:%02d" % ("-" if seconds < 0 else "", minutes, seconds_abs)


def packet_for_phase(value):
    if value == "overdue":
        return bytes((0xA3, 0xFF, 255, 0, 0, 15, 0, 0))
    colors = {"off": (0, 0, 0), "green": (0, 255, 0),
              "yellow": (255, 255, 0), "orange": (255, 127, 0), "red": (255, 0, 0)}
    r, g, b = colors[value]
    return bytes((0xA1, 0xFF, r, g, b, 0x10, 0x10, 0x10))


class Replica:
    """Monotonic replica; ticks_diff makes the MicroPython clock wrap safe."""

    def __init__(self, ticks_ms, ticks_diff):
        self.ticks_ms = ticks_ms
        self.ticks_diff = ticks_diff
        self.at = ticks_ms()
        self.remaining = None
        self.session = None
        self.revision = -1
        self.last_sync = None

    def advance(self):
        now = self.ticks_ms()
        if self.remaining is not None:
            self.remaining -= self.ticks_diff(now, self.at)
        self.at = now
        return self.remaining

    def apply(self, state, roundtrip_ms):
        if state.get("protocol") != 1:
            raise ValueError("Unsupported protocol")
        session, revision = state["session"], state["revision"]
        remaining = state["remaining_ms"]
        if not isinstance(session, str) or not session or type(revision) is not int or revision < 0:
            raise ValueError("Invalid state identity")
        if remaining is not None and (type(remaining) is not int or remaining > 7200000):
            raise ValueError("Invalid remaining time")
        if session == self.session and revision < self.revision:
            return False
        if roundtrip_ms > 2000:
            return False
        self.remaining = None if remaining is None else remaining - roundtrip_ms // 2
        self.at = self.ticks_ms()
        self.last_sync = self.at
        self.session, self.revision = session, revision
        return True
