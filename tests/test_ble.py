"""Exercise the BLE control coroutine with a fake GATT peer (no radio claims)."""
import asyncio
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch
from firmware import timer_logic


class BLETests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.now = 0
        spec = importlib.util.spec_from_file_location('luxafor_test', Path(__file__).parents[1] / 'firmware/luxafor.py')
        self.module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {'bluetooth': SimpleNamespace(UUID=lambda v:v),
                                      'aioble': SimpleNamespace(), 'timer_logic':timer_logic}):
            spec.loader.exec_module(self.module)
        self.replica = timer_logic.Replica(lambda:self.now, lambda a,b:a-b)
        self.replica.apply(dict(protocol=1, session='test', revision=1, remaining_ms=600000), 0)
        self.light = self.module.Luxafor(SimpleNamespace(LUXAFOR_PAIR=False), self.replica)

    async def test_subscribe_initialize_and_use_live_state_after_notification(self):
        events = []
        active = True
        notifications = 0

        async def write(packet):
            events.append(('write', packet))

        async def subscribe(**kwargs):
            events.append(('subscribe', kwargs))

        async def notified(**kwargs):
            nonlocal notifications, active
            notifications += 1
            if notifications == 2:
                # Timer passes zero while the BLE coroutine awaits the peer.
                self.now = 600001
            if notifications == 3:
                active = False
            return b'1\r'

        rx = SimpleNamespace(write=write)
        tx = SimpleNamespace(subscribe=subscribe, notified=notified)
        service = SimpleNamespace(characteristic=AsyncMock(side_effect=[rx, tx]))
        connection = SimpleNamespace(service=AsyncMock(return_value=service), is_connected=lambda:active)
        with patch.object(asyncio, 'sleep_ms', AsyncMock(), create=True), \
             patch.object(self.module.time, 'ticks_ms', lambda:self.now, create=True), \
             patch.object(self.module.time, 'ticks_diff', lambda a,b:a-b, create=True):
            await self.light.control(connection)
        self.assertEqual(events[0], ('subscribe', {'notify':True}))
        self.assertEqual([event[1] for event in events[1:]],
                         [timer_logic.packet_for_phase(p) for p in ('off','green','red')])
        self.assertTrue(self.light.connected)

    async def test_missing_service_does_not_claim_connected(self):
        connection = SimpleNamespace(service=AsyncMock(return_value=None))
        with self.assertRaisesRegex(ValueError, 'Service'):
            await self.light.control(connection)
        self.assertFalse(self.light.connected)

    async def test_pairing_is_opt_in_and_precedes_discovery(self):
        self.light.config.LUXAFOR_PAIR = True
        connection = SimpleNamespace(pair=AsyncMock(side_effect=OSError('pair failed')),
                                     service=AsyncMock())
        with self.assertRaises(OSError):
            await self.light.control(connection)
        connection.pair.assert_awaited_once()
        connection.service.assert_not_awaited()
        self.assertFalse(self.light.connected)
