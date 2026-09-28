import asyncio
import json
import unittest
from firmware.http_sync import exchange


class HTTPTests(unittest.IsolatedAsyncioTestCase):
    async def exchange_with(self, response):
        received = []

        async def handler(reader, writer):
            try:
                headers = await reader.readuntil(b'\r\n\r\n')
                received.append(headers)
                length = next(int(line.split(b':',1)[1]) for line in headers.split(b'\r\n')
                              if line.lower().startswith(b'content-length:'))
                received.append(await reader.readexactly(length))
                writer.write(response)
                await writer.drain()
            finally:
                writer.close()
                await writer.wait_closed()

        async with await asyncio.start_server(handler, '127.0.0.1', 0) as server:
            port = server.sockets[0].getsockname()[1]
            result = await asyncio.wait_for(exchange('127.0.0.1', port, 'exampletoken', {'revision':1}), 1)
        return result, received

    async def test_real_socket_http_exchange(self):
        result, received = await self.exchange_with(b'HTTP/1.0 200 OK\r\nContent-Length: 14\r\n\r\n{"protocol":1}')
        self.assertEqual(result, {'protocol':1})
        self.assertIn(b'Authorization: Bearer exampletoken', received[0])
        self.assertEqual(json.loads(received[1]), {'revision':1})

    async def test_http_error(self):
        with self.assertRaisesRegex(ValueError, 'HTTP'):
            await self.exchange_with(b'HTTP/1.0 401 Unauthorized\r\nContent-Length: 0\r\n\r\n')

    async def test_oversized_body(self):
        with self.assertRaisesRegex(ValueError, 'size'):
            await self.exchange_with(b'HTTP/1.0 200 OK\r\nContent-Length: 10000\r\n\r\n')

    async def test_oversized_header(self):
        with self.assertRaisesRegex(ValueError, 'header'):
            await self.exchange_with(b'HTTP/1.0 200 OK\r\nX-Pad: ' + b'x' * 3000 + b'\r\n\r\n')

    async def test_incomplete_body(self):
        with self.assertRaises(asyncio.IncompleteReadError):
            await self.exchange_with(b'HTTP/1.0 200 OK\r\nContent-Length: 14\r\n\r\n{}')
