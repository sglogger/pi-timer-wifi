"""Minimal network stub: the station never connects."""
STA_IF = 0
current_hostname = ""


def hostname(name=None):
    global current_hostname
    if name is None:
        return current_hostname
    current_hostname = name


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
