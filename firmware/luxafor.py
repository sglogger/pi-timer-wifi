"""Direct BLE central for Luxafor Bluetooth Pro. See docs/ble-protocol.md."""
import asyncio
import bluetooth
import aioble
import time
from timer_logic import phase, packet_for_phase

SERVICE = bluetooth.UUID(0x1234)
WRITE = bluetooth.UUID(0x1235)
NOTIFY = bluetooth.UUID(0x1236)


class Luxafor:
    def __init__(self, config, replica):
        self.config, self.replica = config, replica
        self.connected = False
        self.status = "Suche Luxafor"

    async def find(self):
        # Reduced scan duty cycle leaves airtime for Wi-Fi on the shared radio.
        async with aioble.scan(5000, interval_us=100000, window_us=30000, active=True) as scanner:
            async for result in scanner:
                mac = ":".join("%02x" % b for b in result.device.addr)
                expected = self.config.LUXAFOR_MAC.lower()
                if (expected and mac == expected) or (
                        not expected and result.name() == self.config.LUXAFOR_NAME):
                    return result.device
        return None

    async def control(self, connection):
        if self.config.LUXAFOR_PAIR:
            await connection.pair(bond=True, mitm=False, timeout_ms=15000)
        service = await connection.service(SERVICE)
        if service is None:
            raise ValueError("Luxafor-Service 1234 fehlt")
        write = await service.characteristic(WRITE)
        notify = await service.characteristic(NOTIFY)
        if write is None or notify is None:
            raise ValueError("Luxafor-GATT unvollstaendig")
        await notify.subscribe(notify=True)
        # Reference implementation waits for ready or a 2 s fallback.
        try:
            await notify.notified(timeout_ms=2000)
        except asyncio.TimeoutError:
            pass
        await write.write(packet_for_phase("off"))
        await asyncio.sleep_ms(400)
        last_packet = None
        last_send = time.ticks_ms()
        while connection.is_connected():
            packet = packet_for_phase(phase(self.replica.advance()))
            if packet != last_packet or time.ticks_diff(time.ticks_ms(), last_send) >= 5000:
                await write.write(packet)
                last_packet, last_send = packet, time.ticks_ms()
                self.connected, self.status = True, "BLE verbunden; Befehl gesendet"
            try:
                data = await notify.notified(timeout_ms=100)
                if data in (b"0\r", b"1\r", b"2\r", b"3\r", b"\r0", b"\r2", b"\r3"):
                    last_packet = None  # Ready / pre-sleep: re-send current state.
            except asyncio.TimeoutError:
                pass

    async def run(self):
        delay = 1
        while True:
            try:
                device = await self.find()
                if device is None:
                    self.status = "Luxafor nicht gefunden"
                else:
                    self.status = "Verbinde Luxafor"
                    async with await device.connect(timeout_ms=5000) as connection:
                        delay = 1
                        await self.control(connection)
            except Exception as exc:
                self.status = ("BLE: " + str(exc))[:120]
                print(self.status)
            finally:
                self.connected = False
            await asyncio.sleep(delay)
            delay = min(15, delay * 2)
