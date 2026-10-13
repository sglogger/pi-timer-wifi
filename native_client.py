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


def ago_text(seconds):
    return 'vor %d s' % seconds if seconds < 120 else 'vor %d min' % (seconds // 60)


def device_view(device, online):
    """One device row: (title, detail text, level, short text) with level ok / warn / offline.

    Firmware versions are shown on the "WLAN & Adressen" page, not here.
    """
    if not online:
        return device['name'], 'Offline · letzte Meldung %s' % ago_text(device['age_s']), 'offline', 'offline'
    link = 'WLAN' if device['via'] == 'wifi' else 'Mesh über %s' % device['relay']
    sync = 'synchronisiert' if device['applied'] else 'Übertragung ausstehend'
    ble = 'Luxafor verbunden' if device['ble_connected'] else device['ble_status']
    ok = device['applied'] and device['ble_connected']
    problem = 'OK' if ok else 'wartet' if not device['applied'] else 'kein BLE'
    short = '%s · %s' % ('WLAN' if device['via'] == 'wifi' else 'Mesh', problem)
    return device['name'], '%s · %s\n%s' % (link, sync, ble), 'ok' if ok else 'warn', short


def firmware_text(device):
    firmware = device['firmware']
    version = firmware['version'] or '< 1.0.0'
    return 'FW %s' % version if firmware['current'] else 'FW %s → %s' % (version, firmware['expected'])


def hotspot_lines(clients, devices, limit):
    """Rows of the "Geräte im Hotspot" list on the "WLAN & Adressen" page.

    DHCP clients that are ESP32 timers (matched by MAC) show name and firmware;
    ESP32 reachable only through the mesh follow with their route instead of an IP.
    """
    by_mac = {device['id']: device for device in devices}
    active_rows, inactive_rows = [], []
    for ip, mac, name, active in clients:
        device = by_mac.pop(mac.replace(':', '').lower(), None)
        suffix = '' if active else '  (inaktiv)'
        if device is None:
            row = '  %-15s %s  %s%s' % (ip, mac, name or '–', suffix)
        else:
            row = '  %-15s %-14s %s%s' % (ip, device['name'][:14], firmware_text(device), suffix)
        (active_rows if active else inactive_rows).append(row)
    mesh_rows = []
    for device in by_mac.values():
        route = ('offline' if not device['online'] else
                 'WLAN' if device['via'] == 'wifi' else 'Mesh/' + (device['relay'] or '?'))
        mesh_rows.append('  %-15s %-14s %s' % (route[:15], device['name'][:14], firmware_text(device)))
    # ESP32 outside the DHCP list matter more than stale leases.
    rows = active_rows + mesh_rows + inactive_rows
    if len(rows) > limit:
        rows = rows[:limit - 1] + ['  … und %d weitere' % (len(rows) - limit + 1)]
    return rows or ['  keine']


def names(devices):
    return ', '.join(device['name'] for device in devices)


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
        elapsed = now - self.sampled_at
        devices = state.get('devices', []) if state else []
        online = [device for device in devices
                  if fresh and device['online'] and device['age_s'] + elapsed < device['timeout_s']]
        rows = [device_view(dict(device, age_s=device['age_s'] + elapsed), device in online)
                for device in devices]
        pending = [device for device in online if not device['applied']]
        offline = [device for device in devices if device not in online]
        no_ble = [device for device in online if not device['ble_connected']]
        orb = state.get('orb') if state else None
        message = (self.error or 'Warte auf Timer-Server') if state is None else (
            self.error or ('Server offline – Zustand unbestätigt' if not fresh else
                           'Kein ESP32 online – Start/Stop erst nach Wiederverbindung' if not online else
                           'Warte auf Bestätigung: ' + names(pending) if pending else
                           'Synchronisiert – offline: ' + names(offline) if offline else
                           'Synchronisiert – Luxafor fehlt: ' + names(no_ble) if no_ble else
                           ('Alle %d ESP32 synchronisiert – BLE verbunden' % len(online)
                            if len(online) > 1 else 'ESP32 synchronisiert – BLE verbunden')))
        return dict(text=clock_text(remaining) if remaining is not None else '00:00',
                    phase=phase(remaining), server=bool(fresh), devices=rows,
                    online=len(online), synced=len(online) - len(pending),
                    orb=bool(fresh and orb and orb['connected']),
                    orb_text=('Status unbekannt' if not fresh else orb['status'] if orb else 'Deaktiviert'),
                    message=message)
