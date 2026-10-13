import asyncio
import network
import random
import time
import config
import boards
from timer_logic import FIRMWARE_VERSION, Replica
from http_sync import exchange
from mesh import BROADCAST, Codec
from luxafor import Luxafor
from display import Display

# First: on battery the S3 board powers off unless its hold pin goes high.
BOARD, board = boards.select(getattr(config, "BOARD", ""))
boards.setup(board)
print("Pi Timer Firmware", FIRMWARE_VERSION, BOARD)
# Optional DHCP name; the headend lists hotspot clients by this name.
HOSTNAME = getattr(config, "HOSTNAME", "")
if len(HOSTNAME) > 32 or not all(c.isalpha() or c.isdigit() or c == "-" for c in HOSTNAME):
    raise ValueError("Invalid HOSTNAME")
# Allocate the display strip buffer (30 KB on the C6) before Wi-Fi/BLE fragment the heap.
display = Display(board, HOSTNAME, FIRMWARE_VERSION)
replica = Replica(time.ticks_ms, time.ticks_diff)
light = Luxafor(config, replica)
# Must be set before the station interface is activated.
if HOSTNAME:
    network.hostname(HOSTNAME)
wlan = network.WLAN(network.STA_IF)
wlan.active(True)
# Stable per-board ID for the headend's device list.
DEVICE_ID = "".join("%02x" % b for b in wlan.config("mac"))

# While peers relay fresh server states, Wi-Fi is retried rarely: scanning for the hotspot
# hops channels and misses mesh packets meanwhile.
WIFI_RETRY_MS = 30000
MESH_TIMEOUT_MS = 5000
MESH_SEND_MS = 1000
# States are only broadcast while a peer without Wi-Fi asked for them (its status
# packets) within this window. Idle ESP-NOW traffic cost BLE its connection slots:
# connecting to the Luxafor timed out repeatedly with the mesh on.
MESH_DEMAND_MS = 15000
# Devices without Wi-Fi broadcast their status this often; relayed statuses
# older than PEER_MAX_AGE_MS are dropped.
STATUS_SEND_MS = 2000
PEER_MAX_AGE_MS = 10000
PEER_LIMIT = 16
# The hotspot picks one of these at boot (deploy/hotspot_channel.py).
MESH_CHANNELS = (1, 6, 11)


class Mesh:
    """ESP-NOW side channel between equal peers; see docs/architecture.md."""

    def __init__(self, radio, codec):
        self.radio, self.codec = radio, codec
        self.heard = None  # Last valid peer packet.
        self.channel = None  # Hotspot channel, or where peers were last heard.
        self.peers = {}  # id -> (status, ticks when received, age_ms at receipt)
        self.demand = None  # Last status packet: some peer lacks Wi-Fi.

    def alive(self, since=None):
        if self.heard is None:
            return False
        if since is not None and time.ticks_diff(self.heard, since) < 0:
            return False
        return time.ticks_diff(time.ticks_ms(), self.heard) < MESH_TIMEOUT_MS

    def receive(self):
        while self.radio.any():
            _, packet = self.radio.recv(0)
            decoded = self.codec.decode(packet) if packet else None
            if decoded is None:
                continue
            self.heard = time.ticks_ms()
            if not wlan.isconnected():
                self.channel = wlan.config("channel")
            kind, data = decoded
            if kind == "status":
                self.demand = time.ticks_ms()
                self.store(data)
                continue
            try:
                replica.merge(data)
            except (ValueError, KeyError):
                pass

    def needed(self):
        return self.demand is not None and time.ticks_diff(time.ticks_ms(), self.demand) < MESH_DEMAND_MS

    def age(self, entry):
        return entry[2] + time.ticks_diff(time.ticks_ms(), entry[1])

    def store(self, status):
        """Keep the freshest status per device; several relays may forward the same one."""
        if status["id"] == DEVICE_ID or status["age_ms"] >= PEER_MAX_AGE_MS:
            return
        current = self.peers.get(status["id"])
        if current is not None and self.age(current) <= status["age_ms"]:
            return
        if current is None and len(self.peers) >= PEER_LIMIT:
            return
        self.peers[status["id"]] = (status, time.ticks_ms(), status["age_ms"])

    def peer_reports(self):
        """Fresh statuses of devices without Wi-Fi, with their current age."""
        reports = []
        for device_id in list(self.peers):
            entry = self.peers[device_id]
            age = self.age(entry)
            if age >= PEER_MAX_AGE_MS:
                del self.peers[device_id]
            else:
                report = dict(entry[0])
                report["age_ms"] = age
                reports.append(report)
        return reports

    def send_status(self):
        """Without fresh Wi-Fi: report own status and relay others' towards the headend."""
        for status in [own_status()] + self.peer_reports():
            try:
                self.radio.send(BROADCAST, self.codec.encode_status(status), False)
            except (OSError, ValueError):
                pass

    def send(self):
        if replica.stamp is None:
            return  # Nothing from a server yet, or a server without stamps.
        packet = self.codec.encode(replica.session, replica.revision, replica.advance(), replica.stamp)
        try:
            self.radio.send(BROADCAST, packet, False)
        except OSError:
            pass  # Radio busy, e.g. while scanning for the hotspot.

    async def run(self):
        due = status_due = time.ticks_ms()
        while True:
            # Any escaping exception would end asyncio.gather and stop the timer.
            try:
                self.receive()
                if time.ticks_diff(time.ticks_ms(), due) >= 0:
                    if self.needed():
                        self.send()
                    # Jitter keeps peers from transmitting in lockstep.
                    due = time.ticks_add(time.ticks_ms(), MESH_SEND_MS + random.getrandbits(7))
                if time.ticks_diff(time.ticks_ms(), status_due) >= 0:
                    # A device with Wi-Fi reports itself and its peers over HTTP instead.
                    if not recent(replica.last_sync):
                        self.send_status()
                    status_due = time.ticks_add(time.ticks_ms(), STATUS_SEND_MS + random.getrandbits(8))
            except Exception as exc:
                print("Mesh:", exc)
            await asyncio.sleep_ms(50)

    async def listen(self):
        """After a failed Wi-Fi attempt, park the radio where peers broadcast."""
        wlan.disconnect()  # Stops the driver's background reconnect scans.
        channels = [channel for channel in MESH_CHANNELS if channel != self.channel]
        if self.channel:
            channels.insert(0, self.channel)
        for channel in channels:
            try:
                wlan.config(channel=channel)
            except (OSError, ValueError):
                continue
            since = time.ticks_ms()
            for _ in range(15):
                await asyncio.sleep_ms(100)
                if self.alive(since):
                    return


def own_status():
    return {"id": DEVICE_ID, "name": HOSTNAME, "session": replica.session,
            "revision": replica.revision, "ble_connected": light.connected,
            "ble_status": light.status[:48], "firmware": FIRMWARE_VERSION, "age_ms": 0}


# WIFI = False: receiver that only uses the ESP-NOW mesh, never the hotspot.
WIFI = getattr(config, "WIFI", True)
mesh = None
# Off unless configured (or required by WIFI = False): see config.example.py.
if getattr(config, "MESH", False) or not WIFI:
    import espnow
    radio = espnow.ESPNow()
    radio.active(True)
    radio.add_peer(BROADCAST)
    mesh = Mesh(radio, Codec(config.API_TOKEN))


async def mesh_only_loop():
    """WIFI = False: stay where peers are heard, search channels 1/6/11 otherwise."""
    while True:
        if not mesh.alive():
            await mesh.listen()
        await asyncio.sleep_ms(1000)


async def sync_loop():
    retry = 1
    attempt = None
    while True:
        try:
            if not wlan.isconnected():
                # Only fresh server states count: if the Pi is down, peers still
                # broadcast their stale state and Wi-Fi must be retried quickly.
                if (mesh and recent(replica.last_mesh) and attempt is not None
                        and time.ticks_diff(time.ticks_ms(), attempt) < WIFI_RETRY_MS):
                    await asyncio.sleep_ms(500)
                    continue
                attempt = time.ticks_ms()
                wlan.disconnect()
                wlan.connect(config.WIFI_SSID, config.WIFI_PASSWORD)
                for _ in range(100):
                    if wlan.isconnected():
                        break
                    await asyncio.sleep_ms(100)
                if not wlan.isconnected():
                    if mesh:
                        await mesh.listen()
                    raise OSError("WLAN nicht verbunden")
                if mesh:
                    mesh.channel = wlan.config("channel")
            report = {"id": DEVICE_ID, "name": HOSTNAME, "session": replica.session,
                      "revision": replica.revision, "ble_connected": light.connected,
                      "ble_status": light.status, "firmware": FIRMWARE_VERSION,
                      "peers": mesh.peer_reports() if mesh else []}
            started = time.ticks_ms()
            state = await asyncio.wait_for_ms(exchange(config.SERVER_IP, config.SERVER_PORT,
                                                      config.API_TOKEN, report), 2000)
            replica.apply(state, time.ticks_diff(time.ticks_ms(), started))
            retry = 1
            await asyncio.sleep_ms(500)
        except Exception as exc:
            print("Sync:", describe_error(exc))
            await asyncio.sleep(retry)
            retry = min(5, retry * 2)


def describe_error(exc):
    """asyncio.TimeoutError has an empty message: name the type, add radio details."""
    detail = ("%s %s" % (type(exc).__name__, exc)).strip()
    if wlan.isconnected():
        try:
            detail += " (RSSI %d dBm, Kanal %d, IP %s)" % (
                wlan.status("rssi"), wlan.config("channel"), wlan.ifconfig()[0])
        except Exception:
            pass
    return detail


def recent(ticks):
    return ticks is not None and time.ticks_diff(time.ticks_ms(), ticks) < 5000


def link_text():
    if recent(replica.last_sync):
        return "WIFI OK"
    if recent(replica.last_mesh):
        return "MESH OK"  # Fresh server state relayed by a peer.
    return "WIFI OFFLINE" if WIFI else "MESH OFFLINE"


async def render_loop():
    while True:
        remaining = replica.advance()
        display.render(remaining, link_text(), light.connected)
        await asyncio.sleep_ms(100)


async def main():
    # Numeric host required: DNS resolution can block the entire MCU event loop.
    parts = config.SERVER_IP.split(".") if WIFI else ["0"] * 4
    if len(parts) != 4 or any(not p.isdigit() or not 0 <= int(p) <= 255 for p in parts):
        raise ValueError("SERVER_IP must be numeric IPv4")
    # MicroPython's str has no isalnum().
    if len(config.API_TOKEN) < 20 or not all(c.isalpha() or c.isdigit() for c in config.API_TOKEN):
        raise ValueError("Invalid API_TOKEN")
    # The API_TOKEN also signs mesh packets, so it is needed without Wi-Fi too.
    tasks = [sync_loop() if WIFI else mesh_only_loop(), light.run(), render_loop()]
    if mesh:
        tasks.append(mesh.run())
    await asyncio.gather(*tasks)


asyncio.run(main())
