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

    def config(self, name=None, **settings):
        if "channel" in settings:
            self.channel = settings["channel"]
        if name == "mac":
            return b"\xa1\xb2\xc3\xd4\xe5\xf6"
        return getattr(self, "channel", 6)
