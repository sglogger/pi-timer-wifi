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
        # Chunked reads with a size cap keep runaway headers from exhausting the MCU.
        data = b""
        while b"\r\n\r\n" not in data:
            if len(data) >= 2048:
                raise ValueError("Invalid HTTP header")
            part = await reader.read(256)
            if not part:
                raise ValueError("Invalid HTTP header")
            data += part
        header, body = data.split(b"\r\n\r\n", 1)
        lines = header.split(b"\r\n")
        if lines[0].split()[1] != b"200":
            raise ValueError("HTTP " + lines[0].decode())
        length = None
        for line in lines[1:]:
            if line.lower().startswith(b"content-length:"):
                length = int(line.split(b":", 1)[1].strip())
        if length is None or not 0 < length <= 2048:
            raise ValueError("Invalid HTTP body size")
        if len(body) < length:
            body += await reader.readexactly(length - len(body))
        return json.loads(body[:length])
    finally:
        # Synchronous close only: awaiting wait_closed() could let cleanup hang.
        writer.close()
