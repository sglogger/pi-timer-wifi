import asyncio
import network
import time
import config
from timer_logic import Replica
from http_sync import exchange
from luxafor import Luxafor
from display import Display

# Allocate the ~110 KB framebuffer before Wi-Fi/BLE fragment the heap.
display = Display()
replica = Replica(time.ticks_ms, time.ticks_diff)
light = Luxafor(config, replica)
wlan = network.WLAN(network.STA_IF)
wlan.active(True)


async def sync_loop():
    retry = 1
    while True:
        try:
            if not wlan.isconnected():
                wlan.disconnect()
                wlan.connect(config.WIFI_SSID, config.WIFI_PASSWORD)
                for _ in range(100):
                    if wlan.isconnected():
                        break
                    await asyncio.sleep_ms(100)
                if not wlan.isconnected():
                    raise OSError("WLAN nicht verbunden")
            report = {"session": replica.session, "revision": replica.revision,
                      "ble_connected": light.connected, "ble_status": light.status}
            started = time.ticks_ms()
            state = await asyncio.wait_for_ms(exchange(config.SERVER_IP, config.SERVER_PORT,
                                                      config.API_TOKEN, report), 2000)
            replica.apply(state, time.ticks_diff(time.ticks_ms(), started))
            retry = 1
            await asyncio.sleep_ms(500)
        except Exception as exc:
            print("Sync:", exc)
            await asyncio.sleep(retry)
            retry = min(5, retry * 2)


async def render_loop():
    while True:
        remaining = replica.advance()
        online = replica.last_sync is not None and time.ticks_diff(time.ticks_ms(), replica.last_sync) < 5000
        display.render(remaining, online, light.connected)
        await asyncio.sleep_ms(100)


async def main():
    # Numeric host required: DNS resolution can block the entire MCU event loop.
    parts = config.SERVER_IP.split(".")
    if len(parts) != 4 or any(not p.isdigit() or not 0 <= int(p) <= 255 for p in parts):
        raise ValueError("SERVER_IP must be numeric IPv4")
    # MicroPython's str has no isalnum().
    if len(config.API_TOKEN) < 20 or not all(c.isalpha() or c.isdigit() for c in config.API_TOKEN):
        raise ValueError("Invalid API_TOKEN")
    await asyncio.gather(sync_loop(), light.run(), render_loop())


asyncio.run(main())
