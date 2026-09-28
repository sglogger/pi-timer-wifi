"""Bounded, asynchronous HTTP/1.0 exchange; no blocking requests library."""
import asyncio
import json


async def exchange(host, port, token, report):
    reader, writer = await asyncio.open_connection(host, port)
    try:
        payload = json.dumps(report).encode()
        writer.write(("POST /api/device/sync HTTP/1.0\r\nHost: %s\r\n"
                      "Authorization: Bearer %s\r\nContent-Type: application/json\r\n"
                      "Content-Length: %d\r\nConnection: close\r\n\r\n" %
                      (host, token, len(payload))).encode() + payload)
        await writer.drain()
        # Bounded byte reads prevent runaway headers from exhausting the MCU.
        header = bytearray()
        while not header.endswith(b"\r\n\r\n"):
            part = await reader.read(1)
            if not part or len(header) >= 2048:
                raise ValueError("Invalid HTTP header")
            header.extend(part)
        lines = bytes(header).split(b"\r\n")
        if lines[0].split()[1] != b"200":
            raise ValueError("HTTP " + lines[0].decode())
        length = None
        for line in lines[1:]:
            if line.lower().startswith(b"content-length:"):
                length = int(line.split(b":", 1)[1].strip())
        if length is None or not 0 < length <= 2048:
            raise ValueError("Invalid HTTP body size")
        return json.loads(await reader.readexactly(length))
    finally:
        # Synchronous close only: awaiting wait_closed() could let cleanup hang.
        writer.close()
