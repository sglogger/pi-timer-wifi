"""Run manually with mpremote run firmware/scan.py before configuring the node."""
import asyncio
import aioble


async def main():
    print("BLE scan (15 s). Disconnect Luxafor dongle and phone/desktop apps first.")
    async with aioble.scan(15000, interval_us=100000, window_us=30000, active=True) as scanner:
        async for result in scanner:
            if result.name():
                mac = ":".join("%02x" % b for b in result.device.addr)
                print(result.name(), mac, "RSSI", result.rssi)


asyncio.run(main())
