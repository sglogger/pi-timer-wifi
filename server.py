"""WLAN headend. One process owns the timer and the optional Luxafor USB light (orb.py)."""
import os
import secrets
import threading
import time
import uuid

from flask import Flask, jsonify, render_template, request
from firmware.timer_logic import FIRMWARE_VERSION, THRESHOLDS, phase
from orb import Orb
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


class Timer:
    def __init__(self, clock=time.monotonic, generation=0):
        self.clock = clock
        self.started = clock()
        self.generation = generation
        self.lock = threading.Lock()
        self.session = str(uuid.uuid4())
        self.revision = 0
        self.deadline = None
        self.node = None
        self.seen = None

    def _snapshot(self):
        remaining = None if self.deadline is None else round((self.deadline - self.clock()) * 1000)
        # The stamp orders states across ESP32 mesh peers: newest server contact wins.
        stamp = [self.generation, round((self.clock() - self.started) * 1000)]
        return {"protocol": 1, "session": self.session, "revision": self.revision,
                "remaining_ms": remaining, "phase": phase(remaining), "stamp": stamp}

    def _with_node(self, state):
        age = None if self.seen is None else self.clock() - self.seen
        online = age is not None and age < 5
        state["node"] = {"online": online, "age_s": None if age is None else round(age, 3),
                         "report": self.node,
                         "applied": bool(online and self.node["session"] == self.session
                                         and self.node["revision"] == self.revision)}
        # Firmware before 1.0.0 sends no version; treat it as outdated.
        reported = self.node.get("firmware") if self.node else None
        state["node"]["firmware"] = {"version": reported, "expected": FIRMWARE_VERSION,
                                     "current": reported == FIRMWARE_VERSION}
        return state

    def command(self, minutes=None):
        # Includes node status so UIs keep showing the device while awaiting its ack.
        with self.lock:
            self.deadline = None if minutes is None else self.clock() + minutes * 60
            self.revision += 1
            return self._with_node(self._snapshot())

    def sync(self, report):
        with self.lock:
            self.node = report
            self.seen = self.clock()
            return self._snapshot()

    def snapshot(self):
        with self.lock:
            return self._with_node(self._snapshot())


def create_app(token=None, timer=None, orb=None):
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 4096
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
        if not isinstance(body, dict):
            return jsonify(error="Ungültiger Gerätestatus"), 400
        valid = (type(body.get("revision")) is int and body["revision"] >= -1
                 and (body.get("session") is None or
                      isinstance(body.get("session"), str) and len(body["session"]) <= 64)
                 and type(body.get("ble_connected")) is bool
                 and isinstance(body.get("ble_status"), str) and len(body["ble_status"]) <= 120
                 and (body.get("firmware") is None or
                      isinstance(body.get("firmware"), str) and len(body["firmware"]) <= 20))
        if not valid:
            return jsonify(error="Ungültiger Gerätestatus"), 400
        report = {key: body[key] for key in ("session", "revision", "ble_connected", "ble_status")}
        report["firmware"] = body.get("firmware")
        return jsonify(timer.sync(report))

    return app


if __name__ == "__main__":
    from waitress import serve
    timer = Timer(generation=next_generation())
    orb = None if os.environ.get("PI_TIMER_ORB", "1") == "0" else Orb(timer)
    app = create_app(timer=timer, orb=orb)
    if orb is not None:
        orb.thread.start()
    serve(app, host=os.environ.get("PI_TIMER_HOST", "0.0.0.0"),
          port=int(os.environ.get("PI_TIMER_PORT", "8000")), threads=4)
