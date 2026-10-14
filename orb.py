"""USB lights on the headend, driven by the timer phase: Luxafor Orb (or any Luxafor USB-HID
light) and Busy Tag (USB serial). Each kind is scanned by its own Orb loop; Lights combines them.

The Luxafor commands are the same as luxafor-linux.py in the original pi-timer project.
"""
import glob
import os
import select
import threading
import time

VENDOR, PRODUCT = 0x04D8, 0xF372
COLORS = {"off": (0, 0, 0), "green": (0, 255, 0), "yellow": (255, 255, 0),
          "orange": (255, 127, 0), "red": (255, 0, 0)}
IMAGES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "busytag")


def packet_for_phase(value):
    if value == "overdue":
        # Strobe red: speed 15, 30 repetitions, as in the original config.yaml.
        return [3, 255, 255, 0, 0, 15, 0, 30]
    return [1, 255, *COLORS[value], 0, 0]


class PyUSB:
    name = "Luxafor USB"
    error_prefix = "USB"

    @staticmethod
    def packet(value, now):
        return packet_for_phase(value)

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


def linux_busytag_ports():
    """Serial ports whose USB device calls itself BUSY TAG.

    Matching the product name first keeps AT commands away from other USB serial
    devices, e.g. an ESP32 plugged in for flashing (same Espressif vendor ID).
    """
    ports = []
    for tty in sorted(glob.glob("/sys/class/tty/ttyACM*")):
        try:
            with open(os.path.join(os.path.realpath(tty + "/device"), "..", "product")) as file:
                if file.read().strip() == "BUSY TAG":
                    ports.append("/dev/" + os.path.basename(tty))
        except OSError:
            pass
    return ports


class SerialPort:
    """Line-based AT command channel to one Busy Tag (USB CDC; the baud rate is ignored)."""

    def __init__(self, path, timeout=2.0):
        import termios
        import tty
        self.path, self.timeout, self.buffer = path, timeout, b""
        self.key = (path, os.stat(path).st_ino)
        self.fd = os.open(path, os.O_RDWR | os.O_NOCTTY)
        try:
            tty.setraw(self.fd)
            attrs = termios.tcgetattr(self.fd)
            attrs[4] = attrs[5] = termios.B115200
            termios.tcsetattr(self.fd, termios.TCSANOW, attrs)
        except BaseException:
            os.close(self.fd)
            raise

    def close(self):
        os.close(self.fd)

    def send(self, data):
        while data:
            data = data[os.write(self.fd, data):]

    def line(self):
        deadline = time.monotonic() + self.timeout
        while b"\n" not in self.buffer:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not select.select([self.fd], [], [], remaining)[0]:
                raise OSError("keine Antwort")
            chunk = os.read(self.fd, 4096)
            if not chunk:
                raise OSError("getrennt")
            self.buffer += chunk
        line, self.buffer = self.buffer.split(b"\n", 1)
        return line.strip().decode(errors="replace")

    def expect(self, prefix):
        """Return the next line starting with prefix; skips events (+evn:...) and blank lines."""
        while True:
            line = self.line()
            if line.startswith("ERROR"):
                raise OSError("Busy Tag meldet " + line)
            if line.startswith(prefix):
                return line

    def command(self, text, prefix="OK"):
        self.buffer = b""
        self.send(text.encode() + b"\r\n")
        return self.expect(prefix)


class BusyTag:
    """Busy Tag: the 7 LEDs show the phase colour, the display a picture from static/busytag.

    Overdue blinking is switched by the server: on firmware 1.0 the pattern commands
    (AT+CP, AT+PP) stored truncated or garbage patterns, and playing them reset the device.
    """
    name = "Busy Tag"
    error_prefix = "Busy Tag"
    BLINK = 0.5
    COLORS = {"off": "000000", "green": "00FF00", "yellow": "FFFF00",
              "orange": "FF7F00", "red": "FF0000", "overdue": "FF0000"}

    def __init__(self, ports=linux_busytag_ports, opener=SerialPort, images=IMAGES):
        self.ports, self.opener, self.images = ports, opener, images
        self.open = []
        self.shown = {}

    @classmethod
    def packet(cls, value, now):
        return value, value != "overdue" or int(now / cls.BLINK) % 2 == 0

    @staticmethod
    def key(device):
        return device.key

    def present(self):
        return sorted((path, os.stat(path).st_ino) for path in self.ports())

    def find(self):
        for device in self.open:
            try:
                device.close()
            except OSError:
                pass
        self.open, self.shown = [], {}
        for path in self.ports():
            device = self.opener(path)
            self.open.append(device)
            device.command("AT+GDN", "+DN:")
            self.upload_missing(device)
        return list(self.open)

    def upload_missing(self, device):
        device.send(b"AT+GPL\r\n")
        stored = {}
        while True:
            line = device.expect("")
            if line == "OK":
                break
            if line.startswith("+PL:"):
                name, _, size = line[4:].rpartition(",")
                stored[name] = size
        missing = {}
        for name in sorted(os.listdir(self.images)):
            with open(os.path.join(self.images, name), "rb") as file:
                data = file.read()
            if stored.get(name) != str(len(data)):
                missing[name] = data
        if not missing:
            return
        # The picture on screen cannot be overwritten (ERROR:3); show another one meanwhile.
        shown = device.command("AT+SP?", "+SP:")[4:]
        spare = [name for name in stored if name not in missing]
        if shown in missing and spare:
            device.command("AT+SP=" + spare[0])
        for name, data in missing.items():
            device.command("AT+UF=%s,%d" % (name, len(data)), ">")
            device.send(data)
            device.expect("OK")

    def write(self, device, packet):
        value, lit = packet
        # AT+SC also stops a pattern started from the Busy Tag app.
        device.command("AT+SC=127," + (self.COLORS[value] if lit else "000000"))
        picture = "timer-%s.png" % value
        if self.shown.get(device.key) != picture:
            device.command("AT+SP=" + picture)
            self.shown[device.key] = picture


class Orb:
    def __init__(self, timer, backend=None, interval=0.2, rescan=2.0):
        self.timer, self.backend = timer, backend or PyUSB()
        self.interval, self.rescan = interval, rescan
        self.lock = threading.Lock()
        self.devices = []
        self.sent = None
        self.next_scan = 0
        self.connected = False
        self.status = "Suche " + self.backend.name
        self.thread = threading.Thread(target=self.run, daemon=True, name=self.backend.name)

    def report(self):
        with self.lock:
            return {"connected": self.connected, "status": self.status}

    def _set(self, connected, status):
        with self.lock:
            self.connected, self.status = connected, status

    def _error(self, exc):
        self._set(False, ("%s: %s" % (self.backend.error_prefix, exc))[:120])

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
                self.devices = []
                self._error(exc)
                return
            if not self.devices:
                self._set(False, self.backend.name + " nicht gefunden")
                return
            self.sent = None  # Freshly plugged in: send the current phase.
        packet = self.backend.packet(self.timer.snapshot()["phase"], now)
        if packet == self.sent:
            return
        try:
            for device in self.devices:
                self.backend.write(device, packet)
        except Exception as exc:
            self.devices, self.sent = [], None
            self.next_scan = now + self.rescan
            self._error(exc)
            return
        self.sent = packet
        count = len(self.devices)
        self._set(True, "%s verbunden; Farbe gesendet" % self.backend.name if count == 1 else
                  "%d × %s verbunden; Farbe gesendet" % (count, self.backend.name))

    def run(self):
        while True:
            self.step(time.monotonic())
            time.sleep(self.interval)


class Lights:
    """All supported USB lights; one Orb loop per kind so a slow Busy Tag never delays the Orb."""

    def __init__(self, timer, backends=None):
        self.orbs = [Orb(timer, backend) for backend in (backends or (PyUSB(), BusyTag()))]

    def report(self):
        reports = [orb.report() for orb in self.orbs]
        connected = [r["status"] for r in reports if r["connected"]]
        return {"connected": bool(connected),
                "status": " · ".join(connected or [r["status"] for r in reports])}

    def start(self):
        for orb in self.orbs:
            orb.thread.start()
