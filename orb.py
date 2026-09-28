"""Luxafor Orb (or any Luxafor USB-HID light) on the headend, driven by the timer phase.

Same USB commands as luxafor-linux.py in the original pi-timer project.
"""
import threading
import time

VENDOR, PRODUCT = 0x04D8, 0xF372
COLORS = {"off": (0, 0, 0), "green": (0, 255, 0), "yellow": (255, 255, 0),
          "orange": (255, 127, 0), "red": (255, 0, 0)}


def packet_for_phase(value):
    if value == "overdue":
        # Strobe red: speed 15, 30 repetitions, as in the original config.yaml.
        return [3, 255, 255, 0, 0, 15, 0, 30]
    return [1, 255, *COLORS[value], 0, 0]


class PyUSB:
    @staticmethod
    def key(device):
        return device.bus, device.address

    def present(self):
        # Cheap re-plug detection: enumerating does not touch the light's configuration.
        import usb.core
        return sorted(self.key(d) for d in usb.core.find(find_all=True, idVendor=VENDOR, idProduct=PRODUCT))

    def find(self):
        import usb.core  # Imported lazily so the server runs without pyusb/libusb.
        devices = list(usb.core.find(find_all=True, idVendor=VENDOR, idProduct=PRODUCT))
        for device in devices:
            try:
                # The kernel HID driver holds the interface; writes fail with "Resource busy".
                if device.is_kernel_driver_active(0):
                    device.detach_kernel_driver(0)
            except (NotImplementedError, usb.core.USBError):
                pass
            device.set_configuration()
        return devices

    def write(self, device, packet):
        # The original tool writes twice to ensure the light picks it up.
        device.write(1, packet)
        device.write(1, packet)


class Orb:
    def __init__(self, timer, backend=None, interval=0.2, rescan=2.0):
        self.timer, self.backend = timer, backend or PyUSB()
        self.interval, self.rescan = interval, rescan
        self.lock = threading.Lock()
        self.devices = []
        self.sent = None
        self.next_scan = 0
        self.connected = False
        self.status = "Suche Luxafor USB"
        self.thread = threading.Thread(target=self.run, daemon=True, name="luxafor-usb")

    def report(self):
        with self.lock:
            return {"connected": self.connected, "status": self.status}

    def _set(self, connected, status):
        with self.lock:
            self.connected, self.status = connected, status

    def step(self, now):
        if self.devices and now >= self.next_scan:
            self.next_scan = now + self.rescan
            try:
                replugged = self.backend.present() != sorted(map(self.backend.key, self.devices))
            except Exception:
                replugged = True
            if replugged:
                self.devices, self.next_scan = [], now
        if not self.devices:
            if now < self.next_scan:
                return
            self.next_scan = now + self.rescan
            try:
                self.devices = self.backend.find()
            except Exception as exc:
                self._set(False, ("USB: " + str(exc))[:120])
                return
            if not self.devices:
                self._set(False, "Luxafor USB nicht gefunden")
                return
            self.sent = None  # Freshly plugged in: send the current phase.
        packet = packet_for_phase(self.timer.snapshot()["phase"])
        if packet == self.sent:
            return
        try:
            for device in self.devices:
                self.backend.write(device, packet)
        except Exception as exc:
            self.devices, self.sent = [], None
            self.next_scan = now + self.rescan
            self._set(False, ("USB: " + str(exc))[:120])
            return
        self.sent = packet
        count = len(self.devices)
        self._set(True, "Verbunden; Farbe gesendet" if count == 1 else
                  "%d Lampen verbunden; Farbe gesendet" % count)

    def run(self):
        while True:
            self.step(time.monotonic())
            time.sleep(self.interval)
