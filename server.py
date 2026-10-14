"""WLAN headend. One process owns the timer and the optional USB lights (orb.py: Luxafor, Busy Tag)."""
import os
import secrets
import threading
import time
import uuid

from flask import Flask, jsonify, render_template, request
from firmware.timer_logic import FIRMWARE_VERSION, THRESHOLDS, phase
from orb import Lights
from ui_config import COLORS, LABELS, LEGEND, LEGEND_COLORS, PRESETS
from version import describe as describe_version


# 2020-01-01: keeps time-based generations small enough for MicroPython small ints.
EPOCH = 1577836800


def next_generation(directory=None, now=time.time):
    """Return a number that grows with every server start; ESP32 mesh peers compare it.

    Persisted in systemd's StateDirectory, so it also grows when the Pi has no clock
    after a power loss. Without that directory the wall clock serves as fallback.
    """
    generation = max(1, int(now()) - EPOCH)
    directory = directory if directory is not None else os.environ.get("STATE_DIRECTORY")
    if not directory:
        return generation
    path = os.path.join(directory, "generation")
    try:
        with open(path) as file:
            generation = max(generation, int(file.read().strip() or 0) + 1)
    except (OSError, ValueError):
        pass
    try:
        with open(path + ".tmp", "w") as file:
            file.write(str(generation))
            file.flush()
            os.fsync(file.fileno())
        os.replace(path + ".tmp", path)
    except OSError as exc:
        print("Generation nicht gespeichert:", exc)
    return generation


# Bounds memory against a flood of invented device IDs.
DEVICE_LIMIT = 16
# Seconds without a report until a device counts as offline. Mesh reports arrive
# later: status broadcast every 2 s, relays, then the relaying device's next poll.
TIMEOUT_S = {"wifi": 5, "mesh": 10}
# Devices switched off for good disappear from the list after this many seconds.
FORGET_S = 1800


def version_key(value):
    """'1.2.10' -> (1, 2, 10) for ordering; None if not a dotted number."""
    try:
        return tuple(int(part) for part in value.split("."))
    except (AttributeError, ValueError):
        return None


def valid_name(value, limit):
    return (isinstance(value, str) and len(value) <= limit
            and all(c.isascii() and (c.isalnum() or c == "-") for c in value))


def device_report(body, peer=False):
    """Return the stored fields of a valid device report, else None."""
    if not isinstance(body, dict):
        return None
    valid = (type(body.get("revision")) is int and body["revision"] >= -1
             and (body.get("session") is None or
                  isinstance(body.get("session"), str) and len(body["session"]) <= 64)
             and type(body.get("ble_connected")) is bool
             and isinstance(body.get("ble_status"), str) and len(body["ble_status"]) <= 120
             and (body.get("firmware") is None or
                  isinstance(body.get("firmware"), str) and len(body["firmware"]) <= 20)
             and (body.get("id") is None or valid_name(body["id"], 32) and body["id"])
             and (body.get("name") is None or valid_name(body["name"], 32)))
    if peer:
        valid = valid and body.get("id") and type(body.get("age_ms")) is int and 0 <= body["age_ms"] <= 60000
    if not valid:
        return None
    report = {key: body[key] for key in ("session", "revision", "ble_connected", "ble_status")}
    for key in ("firmware", "id", "name"):
        report[key] = body.get(key)
    if peer:
        report["age_ms"] = body["age_ms"]
    return report


class Timer:
    def __init__(self, clock=time.monotonic, generation=0):
        self.clock = clock
        self.started = clock()
        self.generation = generation
        self.lock = threading.Lock()
        self.session = str(uuid.uuid4())
        self.revision = 0
        self.deadline = None
        self.devices = {}

    def _snapshot(self):
        remaining = None if self.deadline is None else round((self.deadline - self.clock()) * 1000)
        # The stamp orders states across ESP32 mesh peers: newest server contact wins.
        stamp = [self.generation, round((self.clock() - self.started) * 1000)]
        return {"protocol": 1, "session": self.session, "revision": self.revision,
                "remaining_ms": remaining, "phase": phase(remaining), "stamp": stamp}

    def _record(self, device_id, report, seen, via, relay=None):
        current = self.devices.get(device_id)
        # A direct report always wins; relayed ones only if newer than what is stored.
        if via == "mesh" and current is not None and current["seen"] >= seen:
            return
        self.devices[device_id] = {"report": report, "seen": seen, "via": via, "relay": relay}
        if len(self.devices) > DEVICE_LIMIT:
            del self.devices[min(self.devices, key=lambda key: self.devices[key]["seen"])]

    def _with_devices(self, state):
        now = self.clock()
        for device_id in [key for key, device in self.devices.items() if now - device["seen"] > FORGET_S]:
            del self.devices[device_id]
        devices = []
        for device_id, device in self.devices.items():
            report, age = device["report"], now - device["seen"]
            timeout = TIMEOUT_S[device["via"]]
            online = age < timeout
            # Firmware before 1.0.0 sends no version; treat it as outdated.
            reported = report.get("firmware")
            devices.append({
                "id": device_id, "name": report.get("name") or device_id,
                "via": device["via"], "relay": device["relay"],
                "online": online, "age_s": round(age, 3), "timeout_s": timeout,
                "applied": bool(online and report["session"] == self.session
                                and report["revision"] == self.revision),
                "ble_connected": report["ble_connected"], "ble_status": report["ble_status"],
                # newer: the device runs a later firmware than this Pi checkout knows,
                # i.e. the Pi software needs the update, not the ESP32.
                "firmware": {"version": reported, "expected": FIRMWARE_VERSION,
                             "current": reported == FIRMWARE_VERSION,
                             "newer": (version_key(reported) or ()) > version_key(FIRMWARE_VERSION)}})
        state["devices"] = sorted(devices, key=lambda device: (device["name"], device["id"]))
        return state

    def command(self, minutes=None):
        # Includes device status so UIs keep showing the devices while awaiting their ack.
        with self.lock:
            self.deadline = None if minutes is None else self.clock() + minutes * 60
            self.revision += 1
            return self._with_devices(self._snapshot())

    def sync(self, report, peers=(), fallback_id="legacy"):
        """Direct report of a device; `peers` are mesh reports it relays for others."""
        with self.lock:
            now = self.clock()
            device_id = report.get("id") or fallback_id
            self._record(device_id, report, now, "wifi")
            relay = report.get("name") or device_id
            for peer in peers:
                if peer["id"] != device_id:
                    self._record(peer["id"], peer, now - peer["age_ms"] / 1000, "mesh", relay)
            return self._snapshot()

    def snapshot(self):
        with self.lock:
            return self._with_devices(self._snapshot())


def create_app(token=None, timer=None, orb=None):
    app = Flask(__name__)
    # A relaying ESP32 sends up to DEVICE_LIMIT peer reports (~250 bytes each).
    app.config["MAX_CONTENT_LENGTH"] = 8192
    token = token if token is not None else os.environ.get("PI_TIMER_TOKEN", "")
    if len(token) < 20 or not token.isascii() or not token.isalnum():
        raise ValueError("Set PI_TIMER_TOKEN to at least 20 ASCII letters/digits")
    timer = timer or Timer()
    version = describe_version()

    def respond(state):
        if orb is not None:
            state["orb"] = orb.report()
        return jsonify(state)

    @app.before_request
    def authenticate():
        if request.path.startswith("/api/"):
            provided = request.headers.get("Authorization", "")
            if not secrets.compare_digest(provided.encode(), ("Bearer " + token).encode()):
                return jsonify(error="Zugriffsschlüssel fehlt oder ist ungültig"), 401
            if request.method == "POST" and not request.is_json:
                return jsonify(error="JSON erforderlich"), 415

    @app.after_request
    def no_cache(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        return response

    @app.get("/")
    def index():
        ui = dict(thresholds=THRESHOLDS, colors=COLORS, labels=LABELS)
        return render_template("index.html", presets=PRESETS, legend=LEGEND, colors=COLORS, ui=ui,
                               legend_colors=LEGEND_COLORS, version=version)

    @app.get("/api/state")
    def state():
        return respond(timer.snapshot())

    @app.post("/api/start")
    def start():
        body = request.get_json(silent=True)
        minutes = body.get("minutes") if isinstance(body, dict) else None
        if type(minutes) is not int or not 1 <= minutes <= 120:
            return jsonify(error="Dauer muss 1–120 ganze Minuten betragen"), 400
        return respond(timer.command(minutes))

    @app.post("/api/stop")
    def stop():
        return respond(timer.command())

    @app.post("/api/device/sync")
    def sync():
        body = request.get_json(silent=True)
        report = device_report(body)
        peers = body.get("peers", []) if report else None
        if report is None or not isinstance(peers, list) or len(peers) > DEVICE_LIMIT:
            return jsonify(error="Ungültiger Gerätestatus"), 400
        # One malformed relayed entry must not cut the relaying device off.
        peers = [peer for peer in (device_report(peer, peer=True) for peer in peers) if peer]
        # Firmware before 1.2.0 sends no ID; one entry per IP address keeps them apart.
        return jsonify(timer.sync(report, peers, "ip-" + (request.remote_addr or "unknown")))

    return app


if __name__ == "__main__":
    from waitress import serve
    timer = Timer(generation=next_generation())
    orb = None if os.environ.get("PI_TIMER_ORB", "1") == "0" else Lights(timer)
    app = create_app(timer=timer, orb=orb)
    if orb is not None:
        orb.start()
    serve(app, host=os.environ.get("PI_TIMER_HOST", "0.0.0.0"),
          port=int(os.environ.get("PI_TIMER_PORT", "8000")), threads=4)
