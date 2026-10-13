"""Pure timer rules shared by host tests and MicroPython firmware."""

# ESP32 firmware version, reported on every sync; the server compares it with this
# repository copy. Bump only when files copied to the ESP32 change (see CHANGELOG.md).
FIRMWARE_VERSION = "1.2.7"

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


def stamp_of(value):
    """Server stamp (generation, ms) as a comparable tuple; None if absent (older server)."""
    if value is None:
        return None
    if (not isinstance(value, (list, tuple)) or len(value) != 2
            or any(type(part) is not int or part < 0 for part in value)):
        raise ValueError("Invalid stamp")
    return (value[0], value[1])


class Replica:
    """Monotonic replica; ticks_diff makes the MicroPython clock wrap safe.

    `stamp` marks when the server issued the replicated state. Mesh peers exchange
    states and keep the one with the newest stamp, so whoever reached the server
    most recently acts as master.
    """

    def __init__(self, ticks_ms, ticks_diff):
        self.ticks_ms = ticks_ms
        self.ticks_diff = ticks_diff
        self.at = ticks_ms()
        self.remaining = None
        self.session = None
        self.revision = -1
        self.stamp = None
        self.last_sync = None
        self.last_mesh = None

    def advance(self):
        now = self.ticks_ms()
        if self.remaining is not None:
            self.remaining -= self.ticks_diff(now, self.at)
        self.at = now
        return self.remaining

    def _identity(self, state):
        if state.get("protocol") != 1:
            raise ValueError("Unsupported protocol")
        session, revision = state["session"], state["revision"]
        remaining = state["remaining_ms"]
        if not isinstance(session, str) or not session or type(revision) is not int or revision < 0:
            raise ValueError("Invalid state identity")
        if remaining is not None and (type(remaining) is not int or remaining > 7200000):
            raise ValueError("Invalid remaining time")
        return session, revision, remaining, stamp_of(state.get("stamp"))

    def _set(self, session, revision, remaining, stamp):
        self.remaining = remaining
        self.at = self.ticks_ms()
        self.session, self.revision, self.stamp = session, revision, stamp
        return self.at

    def apply(self, state, roundtrip_ms):
        """Direct server answer via HTTP."""
        session, revision, remaining, stamp = self._identity(state)
        if session == self.session and revision < self.revision:
            return False
        if session == self.session and stamp is not None and self.stamp is not None and stamp < self.stamp:
            return False  # A peer already relayed a newer state of this server session.
        if roundtrip_ms > 2000:
            return False
        self.last_sync = self._set(session, revision,
                                   None if remaining is None else remaining - roundtrip_ms // 2, stamp)
        return True

    def merge(self, state):
        """State relayed by a mesh peer; only a strictly newer server stamp wins."""
        session, revision, remaining, stamp = self._identity(state)
        if stamp is None or (self.stamp is not None and stamp <= self.stamp):
            return False
        if session == self.session and revision < self.revision:
            return False
        self.last_mesh = self._set(session, revision, remaining, stamp)
        return True
