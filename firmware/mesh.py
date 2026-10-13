"""ESP-NOW mesh packets: peers relay the freshest server state, signed with API_TOKEN.

Packet: MAGIC + JSON [session, revision, remaining_ms, generation, ms] + 16-byte
HMAC-SHA256 tag. Broadcasts cannot use ESP-NOW encryption, so the tag keeps
strangers from injecting states; the server stamp makes replayed packets lose
against any newer state.
"""
import hashlib
import json

MAGIC = b"SWT1"
TAG = 16
BROADCAST = b"\xff" * 6
# ESP-NOW v1 payload limit.
MAX_PACKET = 250


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

    def encode(self, session, revision, remaining, stamp):
        data = MAGIC + json.dumps([session, revision, remaining, stamp[0], stamp[1]]).encode()
        packet = data + self.tag(data)
        if len(packet) > MAX_PACKET:
            raise ValueError("Mesh packet too large")
        return packet

    def decode(self, packet):
        """Return a state dict for Replica.merge, or None for foreign/forged packets."""
        if not packet or len(packet) <= len(MAGIC) + TAG or packet[:len(MAGIC)] != MAGIC:
            return None
        data, tag = packet[:-TAG], packet[-TAG:]
        # Constant-time comparison.
        difference = 0
        for a, b in zip(self.tag(data), tag):
            difference |= a ^ b
        if difference:
            return None
        try:
            session, revision, remaining, generation, ms = json.loads(data[len(MAGIC):])
        except (ValueError, TypeError):
            return None
        return {"protocol": 1, "session": session, "revision": revision,
                "remaining_ms": remaining, "stamp": (generation, ms)}
