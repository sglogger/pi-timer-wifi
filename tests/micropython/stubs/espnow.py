"""Minimal ESP-NOW stub: records sent packets, delivers queued ones."""


class ESPNow:
    def __init__(self):
        self.sent = []
        self.inbox = []

    def active(self, state=None):
        return True

    def add_peer(self, mac):
        pass

    def any(self):
        return bool(self.inbox)

    def recv(self, timeout_ms=None):
        return self.inbox.pop(0) if self.inbox else (None, None)

    def send(self, mac, message, sync=True):
        self.sent.append((mac, message))
        return True
