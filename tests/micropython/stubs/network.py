"""Minimal network stub: the station never connects."""
STA_IF = 0


class WLAN:
    def __init__(self, interface):
        pass

    def active(self, state=None):
        return True

    def isconnected(self):
        return False

    def connect(self, ssid, password):
        pass

    def disconnect(self):
        pass
