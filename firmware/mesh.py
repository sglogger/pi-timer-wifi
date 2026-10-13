"""ESP-NOW mesh packets between equal ESP32 peers, signed with API_TOKEN.

Two packet kinds, each MAGIC + JSON list + 16-byte HMAC-SHA256 tag:
- state  (SWT1): [session, revision, remaining_ms, generation, ms], the freshest
  server state; whoever reached the server most recently is the source.
- status (SWS1): [id, name, session, revision, ble_connected, ble_status, firmware,
  age_ms], a device without Wi-Fi reporting towards a peer that has it.
Broadcasts cannot use ESP-NOW encryption, so the tag keeps strangers from
injecting packets; the server stamp makes replayed states lose against newer ones.
"""
import hashlib
import json

STATE = b"SWT1"
STATUS = b"SWS1"
MAGIC_LENGTH = 4
TAG = 16
BROADCAST = b"\xff" * 6
# ESP-NOW v1 payload limit.
MAX_PACKET = 250
STATUS_FIELDS = ("id", "name", "session", "revision", "ble_connected", "ble_status", "firmware", "age_ms")


class Codec:
    def __init__(self, token):
        # HMAC (RFC 2104) by hand: MicroPython has no hmac module.
        key = token.encode()
        if len(key) > 64:
            key = hashlib.sha256(key).digest()
        key = key + bytes(64 - len(key))
        self.inner = bytes(b ^ 0x36 for b in key)
        self.outer = bytes(b ^ 0x5C for b in key)

    def tag(self, data):
        inner = hashlib.sha256(self.inner + data).digest()
        return hashlib.sha256(self.outer + inner).digest()[:TAG]

    def seal(self, magic, items):
        data = magic + json.dumps(items).encode()
        packet = data + self.tag(data)
        if len(packet) > MAX_PACKET:
            raise ValueError("Mesh packet too large")
        return packet

    def encode(self, session, revision, remaining, stamp):
        return self.seal(STATE, [session, revision, remaining, stamp[0], stamp[1]])

    def encode_status(self, status):
        items = [status[key] for key in STATUS_FIELDS]
        try:
            return self.seal(STATUS, items)
        except ValueError:
            # Non-ASCII BLE errors grow sixfold as JSON escapes; keep the rest.
            items[5] = items[5][:12]
            return self.seal(STATUS, items)

    def decode(self, packet):
        """Return ("state" | "status", dict), or None for foreign/forged packets."""
        if not packet or len(packet) <= MAGIC_LENGTH + TAG:
            return None
        magic = packet[:MAGIC_LENGTH]
        if magic != STATE and magic != STATUS:
            return None
        data, tag = packet[:-TAG], packet[-TAG:]
        # Constant-time comparison.
        difference = 0
        for a, b in zip(self.tag(data), tag):
            difference |= a ^ b
        if difference:
            return None
        try:
            items = json.loads(data[MAGIC_LENGTH:])
        except (ValueError, TypeError):
            return None
        if not isinstance(items, list):
            return None
        if magic == STATE and len(items) == 5:
            session, revision, remaining, generation, ms = items
            return "state", {"protocol": 1, "session": session, "revision": revision,
                             "remaining_ms": remaining, "stamp": (generation, ms)}
        if magic == STATUS and len(items) == len(STATUS_FIELDS):
            status = dict(zip(STATUS_FIELDS, items))
            # Fields used for bookkeeping on the ESP32; the server checks the rest.
            if (isinstance(status["id"], str) and 0 < len(status["id"]) <= 32
                    and type(status["age_ms"]) is int and status["age_ms"] >= 0):
                return "status", status
        return None
