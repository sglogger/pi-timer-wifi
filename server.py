"""WLAN headend. One process owns the timer; no hardware access on the Pi."""
import os
import secrets
import threading
import time
import uuid

from flask import Flask, jsonify, render_template, request
from firmware.timer_logic import THRESHOLDS, phase
from ui_config import COLORS, LABELS, PRESETS


class Timer:
    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.lock = threading.Lock()
        self.session = str(uuid.uuid4())
        self.revision = 0
        self.deadline = None
        self.node = None
        self.seen = None

    def _snapshot(self):
        remaining = None if self.deadline is None else round((self.deadline - self.clock()) * 1000)
        return {"protocol": 1, "session": self.session, "revision": self.revision,
                "remaining_ms": remaining, "phase": phase(remaining)}

    def _with_node(self, state):
        age = None if self.seen is None else self.clock() - self.seen
        online = age is not None and age < 5
        state["node"] = {"online": online, "age_s": age, "report": self.node,
                         "applied": bool(online and self.node["session"] == self.session
                                         and self.node["revision"] == self.revision)}
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


def create_app(token=None, timer=None):
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 4096
    token = token if token is not None else os.environ.get("PI_TIMER_TOKEN", "")
    if len(token) < 20 or not token.isascii() or not token.isalnum():
        raise ValueError("Set PI_TIMER_TOKEN to at least 20 ASCII letters/digits")
    timer = timer or Timer()

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
        return render_template("index.html", presets=PRESETS, ui=ui)

    @app.get("/api/state")
    def state():
        return jsonify(timer.snapshot())

    @app.post("/api/start")
    def start():
        body = request.get_json(silent=True)
        minutes = body.get("minutes") if isinstance(body, dict) else None
        if type(minutes) is not int or not 1 <= minutes <= 120:
            return jsonify(error="Dauer muss 1–120 ganze Minuten betragen"), 400
        return jsonify(timer.command(minutes))

    @app.post("/api/stop")
    def stop():
        return jsonify(timer.command())

    @app.post("/api/device/sync")
    def sync():
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return jsonify(error="Ungültiger Gerätestatus"), 400
        valid = (type(body.get("revision")) is int and body["revision"] >= -1
                 and (body.get("session") is None or
                      isinstance(body.get("session"), str) and len(body["session"]) <= 64)
                 and type(body.get("ble_connected")) is bool
                 and isinstance(body.get("ble_status"), str) and len(body["ble_status"]) <= 120)
        if not valid:
            return jsonify(error="Ungültiger Gerätestatus"), 400
        report = {key: body[key] for key in ("session", "revision", "ble_connected", "ble_status")}
        return jsonify(timer.sync(report))

    return app


if __name__ == "__main__":
    from waitress import serve
    serve(create_app(), host=os.environ.get("PI_TIMER_HOST", "0.0.0.0"),
          port=int(os.environ.get("PI_TIMER_PORT", "8000")), threads=4)
