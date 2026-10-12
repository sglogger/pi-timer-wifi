"""Single HTTP worker and presentation model; no Tk calls outside the UI thread."""
import json
import queue
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, ProxyHandler

from firmware.timer_logic import clock_text, phase


class Transport:
    def __init__(self, token, port=8000):
        self.token = token
        self.base = 'http://127.0.0.1:%d' % port
        # Local control must not be routed through an environment HTTP proxy.
        self.opener = build_opener(ProxyHandler({}))

    def request(self, path, body=None):
        request = Request(self.base + path,
                          data=None if body is None else json.dumps(body).encode(),
                          headers={'Authorization': 'Bearer ' + self.token,
                                   'Content-Type': 'application/json'})
        with self.opener.open(request, timeout=2) as response:
            return json.loads(response.read(8192))


class Client:
    """Serial requests, no automatic command retries or queue of offline starts."""
    def __init__(self, transport, clock=time.monotonic):
        self.transport, self.clock = transport, clock
        self.commands = queue.Queue(maxsize=1)
        self.results = queue.Queue(maxsize=4)
        self.closed = threading.Event()
        self.lock = threading.Lock()
        self.generation = 0
        self.busy = False
        self.thread = threading.Thread(target=self.run, daemon=True, name='timer-http')

    def command(self, minutes=None):
        with self.lock:
            if self.busy or self.closed.is_set():
                return None
            self.generation += 1
            self.busy = True
            item = (self.generation, self.clock(), minutes)
            self.commands.put_nowait(item)
            return self.generation

    def publish(self, event):
        # Preserve bounded memory if the window is paused or unresponsive.
        try:
            self.results.put_nowait(event)
        except queue.Full:
            try:
                self.results.get_nowait()
            except queue.Empty:
                pass
            self.results.put_nowait(event)

    def perform(self, generation, path, body=None):
        started = self.clock()
        try:
            data = self.transport.request(path, body)
            self.publish((generation, (started + self.clock()) / 2, data, None))
        except (OSError, ValueError, HTTPError, URLError) as exc:
            detail = ('API-Schlüssel prüfen (.env)' if isinstance(exc, HTTPError) and exc.code == 401
                      else 'Timer-Server nicht erreichbar')
            if isinstance(exc, HTTPError):
                exc.close()
            if body is not None:
                detail = 'Befehl unbestätigt. ' + detail
            self.publish((generation, self.clock(), None, detail))

    def run(self):
        while not self.closed.is_set():
            try:
                generation, submitted, minutes = self.commands.get(timeout=.5)
            except queue.Empty:
                with self.lock:
                    if self.busy or self.closed.is_set():
                        continue
                    generation = self.generation
                self.perform(generation, '/api/state')
                continue
            try:
                if self.closed.is_set():
                    return
                if self.clock() - submitted > 3:
                    self.publish((generation, self.clock(), None, 'Befehl verworfen: zu lange gewartet'))
                else:
                    path, body = ('/api/stop', {}) if minutes is None else ('/api/start', {'minutes': minutes})
                    self.perform(generation, path, body)
            finally:
                with self.lock:
                    self.busy = False
            # On success or uncertainty, read the authoritative state, never retry START.
            self.perform(generation, '/api/state')

    def close(self):
        self.closed.set()


def firmware_text(node):
    firmware = node.get('firmware')
    if not firmware:
        return ''
    if firmware['current']:
        return '\nFirmware %s' % firmware['version']
    return '\nFirmware %s veraltet – aktuell %s' % (firmware['version'] or '< 1.0.0', firmware['expected'])


class ViewState:
    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.generation = 0
        self.snapshot = None
        self.sampled_at = 0
        self.received_at = None
        self.error = None

    def accept(self, event):
        generation, sampled, data, error = event
        if generation < self.generation:
            return
        self.generation = generation
        self.error = error
        if data is not None:
            self.snapshot = data
            self.sampled_at = sampled
            self.received_at = self.clock()

    def render(self):
        now = self.clock()
        state = self.snapshot
        fresh = self.received_at is not None and now - self.received_at < 4 and not self.error
        remaining = None if state is None else state['remaining_ms']
        if remaining is not None:
            remaining -= int((now - self.sampled_at) * 1000)
        node = state.get('node') if state else None
        online = bool(fresh and node and node['online'] and
                      node['age_s'] + (now - self.sampled_at) < 5)
        applied = online and node['applied']
        ble = online and node['report']['ble_connected']
        orb = state.get('orb') if state else None
        message = (self.error or 'Warte auf Timer-Server') if state is None else (
            self.error or ('Server offline – Zustand unbestätigt' if not fresh else
                           'ESP32 offline – Start/Stop erst nach Wiederverbindung' if not online else
                           'Warte auf ESP32-Bestätigung' if not applied else
                           'Timer synchronisiert – Luxafor nicht verbunden' if not ble else
                           'Timer synchronisiert – BLE verbunden'))
        return dict(text=clock_text(remaining) if remaining is not None else '00:00',
                    phase=phase(remaining), server=bool(fresh), node=online, ble=bool(ble),
                    node_text=('Timer synchronisiert' if applied else 'Übertragung ausstehend' if online
                               else 'Offline / unbekannt') + (firmware_text(node) if online else ''),
                    ble_text=node['report']['ble_status'] if online else 'Status unbekannt',
                    orb=bool(fresh and orb and orb['connected']),
                    orb_text=('Status unbekannt' if not fresh else orb['status'] if orb else 'Deaktiviert'),
                    message=message)
