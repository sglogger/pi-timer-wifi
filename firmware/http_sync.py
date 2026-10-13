"""Bounded, asynchronous HTTP/1.0 exchange; no blocking requests library."""
import asyncio
import json
import socket
import sys

MICROPYTHON = sys.implementation.name == "micropython"


def writable(sock):
    # Same wait as MicroPython's open_connection(): resumes once connected.
    yield asyncio.core._io_queue.queue_write(sock)


async def open_stream(host, port):
    """Connect without leaking the socket.

    MicroPython's open_connection() loses its socket when a timeout cancels it
    while connecting, and its Stream.close() does not close the socket at all
    (only wait_closed() does). Leaked sockets exhaust lwIP within minutes: every
    later connect times out and BLE fails with ENOMEM. Here the socket exists
    before the first await, so the caller's finally always reaches it.
    """
    if not MICROPYTHON:
        return await asyncio.open_connection(host, port)
    from errno import EINPROGRESS
    sock = socket.socket()
    try:
        sock.setblocking(False)
        sock.connect(socket.getaddrinfo(host, port, 0, socket.SOCK_STREAM)[0][-1])
    except OSError as exc:
        if exc.errno != EINPROGRESS:
            sock.close()
            raise
    stream = asyncio.StreamWriter(sock, {})
    return stream, stream


async def connected(writer):
    if MICROPYTHON:
        await writable(writer.s)


def close_stream(writer):
    writer.close()
    # Synchronous on purpose: awaiting wait_closed() could let cleanup hang.
    if MICROPYTHON:
        writer.s.close()


async def exchange(host, port, token, report):
    reader, writer = await open_stream(host, port)
    try:
        await connected(writer)
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
        close_stream(writer)
