"""BLE diagnosis for the Luxafor; run manually with mpremote run firmware/ble_test.py.

Uses LUXAFOR_NAME/LUXAFOR_MAC/LUXAFOR_PAIR from config.py on the board. Stop the
timer first (mpremote stops main.py when it connects). Each round: scan, connect,
list GATT, subscribe, cycle red/green/blue/off, disconnect. Watch the lamp.
"""
import asyncio
import gc
import time
import aioble
import bluetooth
import config
from timer_logic import packet_for_phase

ROUNDS = 3
# True: Wi-Fi station and ESP-NOW active, one broadcast per second, like a
# mesh-only device (WIFI = False). Compare a run with False and one with True.
ESPNOW_LOAD = False
# Same reduced scan duty cycle as luxafor.py (30 ms of every 100 ms).
SCAN_INTERVAL_US, SCAN_WINDOW_US = 100000, 30000

PAIR = getattr(config, "LUXAFOR_PAIR", False)
SERVICE = bluetooth.UUID(0x1234)
WRITE = bluetooth.UUID(0x1235)
NOTIFY = bluetooth.UUID(0x1236)
FLAGS = ((0x02, "read"), (0x04, "write-no-response"), (0x08, "write"),
         (0x10, "notify"), (0x20, "indicate"))


def log(*parts):
    print("%8d ms  %6d B frei " % (time.ticks_ms(), gc.mem_free()), *parts)


def mac_of(device):
    return ":".join("%02x" % b for b in device.addr)


def matches(result):
    expected = config.LUXAFOR_MAC.lower()
    if expected:
        return mac_of(result.device) == expected
    return result.name() == config.LUXAFOR_NAME


async def find():
    started = time.ticks_ms()
    seen = {}
    async with aioble.scan(5000, interval_us=SCAN_INTERVAL_US, window_us=SCAN_WINDOW_US,
                           active=True) as scanner:
        async for result in scanner:
            name = result.name()
            if name and name.startswith("LUX"):
                seen[mac_of(result.device)] = (name, result.rssi)
            if matches(result):
                log("gefunden nach %d ms: %s %s RSSI %d" % (
                    time.ticks_diff(time.ticks_ms(), started), name, mac_of(result.device),
                    result.rssi))
                return result.device
    log("NICHT gefunden in 5 s. Gesehene LUX-Geräte:", seen or "keine")
    return None


async def gatt(connection):
    # aioble allows one discovery at a time: collect the services first.
    services = []
    async for service in connection.services():
        services.append(service)
    for service in services:
        print("    Service", service.uuid)
        async for characteristic in service.characteristics():
            flags = [name for bit, name in FLAGS if characteristic.properties & bit]
            print("      Characteristic", characteristic.uuid, ",".join(flags))


async def drain(notify, timeout_ms):
    """Print every notification until none arrives for timeout_ms."""
    while True:
        try:
            log("Notification", await notify.notified(timeout_ms=timeout_ms))
        except asyncio.TimeoutError:
            return


async def round_trip(number):
    print("\n=== Runde %d von %d ===" % (number, ROUNDS))
    device = await find()
    if device is None:
        return "nicht gefunden"
    started = time.ticks_ms()
    try:
        connection = await device.connect(timeout_ms=10000)
    except Exception as exc:
        log("Verbinden fehlgeschlagen: %s %s" % (type(exc).__name__, exc))
        return "Verbinden: " + type(exc).__name__
    log("verbunden nach %d ms" % time.ticks_diff(time.ticks_ms(), started))
    try:
        if PAIR:
            await connection.pair(bond=True, mitm=False, timeout_ms=15000)
            log("gepairt")
        if number == 1:
            await gatt(connection)
        service = await connection.service(SERVICE)
        if service is None:
            return "Service 1234 fehlt"
        write = await service.characteristic(WRITE)
        notify = await service.characteristic(NOTIFY)
        if write is None or notify is None:
            return "Characteristic 1235/1236 fehlt"
        await notify.subscribe(notify=True)
        log("Notifications abonniert, warte bis 2 s auf Ready")
        await drain(notify, 2000)
        for color in ("red", "green", "off", "red", "off"):
            log("sende", color, packet_for_phase(color))
            await write.write(packet_for_phase(color))
            await drain(notify, 1500)
        return "OK"
    except Exception as exc:
        log("Fehler: %s %s" % (type(exc).__name__, exc))
        return type(exc).__name__
    finally:
        if connection.is_connected():
            await connection.disconnect()
        log("getrennt")


async def espnow_load():
    import network
    import espnow
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    radio = espnow.ESPNow()
    radio.active(True)
    radio.add_peer(b"\xff" * 6)
    log("ESP-NOW-Last aktiv, Kanal", wlan.config("channel"))
    while True:
        try:
            radio.send(b"\xff" * 6, b"ble-test" * 25, False)  # 200 bytes, like mesh states
        except OSError:
            pass
        while radio.any():
            radio.recv(0)
        await asyncio.sleep_ms(1000)


async def main():
    target = config.LUXAFOR_MAC or config.LUXAFOR_NAME
    print("BLE-Test für", target, "| Pairing", PAIR, "| ESP-NOW-Last", ESPNOW_LOAD)
    print("Dongle abziehen, Luxafor-Apps trennen; Lampe beobachten: rot, grün, aus, rot, aus.")
    gc.collect()
    if ESPNOW_LOAD:
        asyncio.create_task(espnow_load())
        await asyncio.sleep_ms(500)
    results = []
    for number in range(1, ROUNDS + 1):
        results.append(await round_trip(number))
        await asyncio.sleep_ms(1000)
    print("\nErgebnis:", results)


asyncio.run(main())
