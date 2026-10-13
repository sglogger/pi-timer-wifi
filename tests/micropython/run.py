"""Run firmware code on the MicroPython unix port to catch CPython-only APIs.

Usage from the repository root: micropython tests/micropython/run.py
"""
import sys

sys.path[:0] = ["tests/micropython/stubs", "firmware"]

import asyncio
import time
import config
from timer_logic import Replica, clock_text, packet_for_phase, phase
from http_sync import exchange
from mesh import Codec

PORT = config.SERVER_PORT
failures = 0


def check(name, condition):
    global failures
    print(("ok    " if condition else "FAIL  ") + name)
    if not condition:
        failures += 1


def test_timer_logic():
    values = (None, 300001, 300000, 60000, 0, -30000)
    check("phase thresholds", [phase(v) for v in values] ==
          ["off", "green", "yellow", "orange", "red", "overdue"])
    check("clock text", clock_text(None) == "READY" and clock_text(61001) == "01:02"
          and clock_text(-30000) == "-00:30")
    check("BLE packets", all(len(packet_for_phase(p)) == 8 for p in
                             ("off", "green", "yellow", "orange", "red", "overdue")))
    ticks = [time.ticks_add(0, -500)]
    replica = Replica(lambda: ticks[0], time.ticks_diff)
    replica.apply(dict(protocol=1, session="s", revision=1, remaining_ms=10000), 100)
    ticks[0] = time.ticks_add(0, 500)
    check("replica counts across tick wrap", replica.advance() == 8950)


def test_mesh_codec():
    codec = Codec(config.API_TOKEN)
    # Produced by CPython (tests/test_mesh.py uses the same token): interop check.
    cpython = (b'SWT1["s-1", 3, 61000, 7, 1500]'
               b'\xaf\xe7U\xda-\x0b\xa9)"\xc1\xe2vd\x0b\x91=')
    kind, state = codec.decode(cpython)
    check("mesh decodes CPython packet", kind == "state" and state["session"] == "s-1"
          and state["remaining_ms"] == 61000 and state["stamp"] == (7, 1500))
    check("mesh roundtrip", codec.decode(codec.encode("s", 1, None, (2, 3)))[1]["stamp"] == (2, 3))
    status = {"id": "a1", "name": "saal-2", "session": None, "revision": -1, "ble_connected": False,
              "ble_status": "\u00e4" * 48, "firmware": "1.2.0", "age_ms": 5}
    packet = codec.encode_status(status)
    check("mesh status fits", len(packet) <= 250 and codec.decode(packet)[0] == "status")
    check("mesh rejects tampering", codec.decode(cpython.replace(b"61000", b"91000")) is None)
    replica = Replica(time.ticks_ms, time.ticks_diff)
    check("mesh merge", replica.merge(state) and not replica.merge(state))


async def respond(response, split=False):
    async def handler(reader, writer):
        length = 0
        while True:
            line = await reader.readline()
            if line in (b"\r\n", b""):
                break
            if line.lower().startswith(b"content-length:"):
                length = int(line.split(b":", 1)[1])
        await reader.readexactly(length)
        if split:
            writer.write(response[:-5])
            await writer.drain()
            await asyncio.sleep_ms(50)
            response_rest = response[-5:]
        else:
            response_rest = response
        writer.write(response_rest)
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    server = await asyncio.start_server(handler, "127.0.0.1", PORT)
    try:
        return await asyncio.wait_for_ms(
            exchange("127.0.0.1", PORT, config.API_TOKEN, {"revision": 1}), 2000)
    finally:
        server.close()
        await server.wait_closed()


async def expect_error(name, response):
    try:
        await respond(response)
    except Exception as exc:
        check(name, isinstance(exc, (ValueError, EOFError)))
        return
    check(name, False)


async def test_http():
    body = b'{"protocol":1}'
    ok = b"HTTP/1.0 200 OK\r\nContent-Length: 14\r\n\r\n" + body
    check("HTTP exchange", await respond(ok) == {"protocol": 1})
    check("HTTP body in separate reads", await respond(ok, split=True) == {"protocol": 1})
    padded = b"HTTP/1.0 200 OK\r\nX-Pad: " + b"x" * 1500 + b"\r\nContent-Length: 14\r\n\r\n" + body
    check("HTTP long header", await respond(padded) == {"protocol": 1})
    await expect_error("HTTP error status", b"HTTP/1.0 401 Unauthorized\r\nContent-Length: 0\r\n\r\n")
    await expect_error("HTTP oversized header",
                       b"HTTP/1.0 200 OK\r\nX-Pad: " + b"x" * 3000 + b"\r\n\r\n")
    await expect_error("HTTP oversized body", b"HTTP/1.0 200 OK\r\nContent-Length: 10000\r\n\r\n")


def import_main():
    sys.modules.pop("main", None)
    import main
    return main


def test_main():
    # Invalid token: main() must reject it (not crash on a missing str method).
    config.API_TOKEN = "short"
    try:
        import_main()
        check("main rejects invalid token", False)
    except ValueError as exc:
        check("main rejects invalid token", str(exc) == "Invalid API_TOKEN")

    # Valid configuration: replace the endless loops, then render one frame.
    config.API_TOKEN = "microPythonTestToken1234"
    started = []
    gather = asyncio.gather

    async def fake_gather(*coroutines):
        for coroutine in coroutines:
            coroutine.close()
        started.append(len(coroutines))

    asyncio.gather = fake_gather
    try:
        main = import_main()
    finally:
        asyncio.gather = gather
    check("main accepts valid config", started == [4])
    import network
    check("hostname applied", network.hostname() == "timer-test-1")
    check("firmware version", isinstance(main.FIRMWARE_VERSION, str) and main.FIRMWARE_VERSION.count(".") == 2)
    for remaining in (None, 61000, -31000):
        main.display.previous = None
        main.display.render(remaining, main.link_text(), False)
    check("display renders", main.display.previous is not None)
    check("offline link text", main.link_text() == "WIFI OFFLINE")
    check("timeout is named", main.describe_error(asyncio.TimeoutError()) == "TimeoutError")
    radio = main.mesh.radio
    main.mesh.send()
    check("mesh silent without server state", radio.sent == [])
    radio.inbox.append((b"\x00" * 6, main.mesh.codec.encode("s", 2, 30000, (5, 10))))
    radio.inbox.append((b"\x00" * 6, b"foreign"))
    main.mesh.receive()
    check("mesh peer state applied", main.replica.session == "s" and main.mesh.alive()
          and main.mesh.channel == 6 and main.link_text() == "MESH OK")
    main.mesh.send()
    relayed = main.mesh.codec.decode(radio.sent[-1][1])[1]
    check("mesh relays state", relayed["stamp"] == (5, 10) and relayed["revision"] == 2)
    check("device id from MAC", main.DEVICE_ID == "a1b2c3d4e5f6")
    peer = {"id": "0000000000c3", "name": "saal-3", "session": "s", "revision": 2, "ble_connected": True,
            "ble_status": "OK", "firmware": main.FIRMWARE_VERSION, "age_ms": 1200}
    radio.inbox.append((b"\x00" * 6, main.mesh.codec.encode_status(peer)))
    radio.inbox.append((b"\x00" * 6, main.mesh.codec.encode_status(dict(peer, age_ms=9000))))
    radio.inbox.append((b"\x00" * 6, main.mesh.codec.encode_status(dict(peer, id=main.DEVICE_ID))))
    main.mesh.receive()
    reports = main.mesh.peer_reports()
    check("mesh keeps freshest peer status", len(reports) == 1 and 1200 <= reports[0]["age_ms"] < 2000)
    sent = len(radio.sent)
    main.mesh.send_status()
    statuses = [main.mesh.codec.decode(packet)[1] for _, packet in radio.sent[sent:]]
    check("mesh sends own status and relays peers",
          [s["id"] for s in statuses] == [main.DEVICE_ID, "0000000000c3"] and statuses[0]["name"] == "timer-test-1")
    check("display shows hostname and version",
          main.display.hostname == "timer-test-1" and main.display.version == "v" + main.FIRMWARE_VERSION)


test_timer_logic()
test_mesh_codec()
asyncio.run(test_http())
test_main()
print("%d failure(s)" % failures)
sys.exit(1 if failures else 0)
