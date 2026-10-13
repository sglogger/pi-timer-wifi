"""Native frontend behaviour, including real HTTP and lost command responses."""
import threading
import unittest
from urllib.error import HTTPError
from werkzeug.serving import make_server

from native_client import Client, Transport, ViewState, hotspot_lines
from server import Timer, create_app

TOKEN = 'nativeTestToken123456789012345'


class Clock:
    now = 1000

    def __call__(self):
        return self.now


class ViewTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.timer = Timer(self.clock)
        self.view = ViewState(self.clock)

    def refresh(self):
        self.view.accept((0, self.clock(), self.timer.snapshot(), None))

    def test_countdown_continues_but_offline_is_never_confirmed(self):
        from firmware.timer_logic import FIRMWARE_VERSION
        state = self.timer.command(1)
        self.timer.sync(dict(session=state['session'], revision=state['revision'],
                             ble_connected=True, ble_status='Verbunden', firmware=FIRMWARE_VERSION))
        self.refresh()
        self.assertEqual(self.view.render()['devices'][0][2], 'ok')
        self.clock.now += 90
        state = self.view.render()
        self.assertEqual((state['text'], state['phase']), ('-00:30', 'overdue'))
        self.assertEqual(state['online'], 0)
        self.assertEqual(state['devices'][0][2], 'offline')
        self.assertFalse(state['server'])
        self.assertIn('unbestätigt', state['message'])

    def test_old_poll_cannot_overwrite_a_new_command(self):
        old = self.timer.command(30)
        stopped = self.timer.command()
        self.view.accept((2, self.clock(), stopped, None))
        self.view.accept((1, self.clock(), old, None))
        self.assertEqual(self.view.render()['text'], '00:00')
        self.assertEqual(self.view.render()['phase'], 'off')
        self.assertIn('Kein ESP32 online', self.view.render()['message'])

    def test_firmware_is_not_on_the_main_screen(self):
        from firmware.timer_logic import FIRMWARE_VERSION
        state = self.timer.command(5)
        report = dict(session=state['session'], revision=state['revision'], ble_connected=True, ble_status='OK')
        self.timer.sync(dict(report, firmware=FIRMWARE_VERSION))
        self.refresh()
        self.assertEqual(self.view.render()['devices'][0][2], 'ok')
        self.timer.sync(report)
        self.refresh()
        self.assertNotIn('Firmware', self.view.render()['devices'][0][1])

    def test_no_node_does_not_crash_or_claim_connection(self):
        self.refresh()
        self.assertEqual(self.view.render()['devices'], [])
        self.assertIn('Kein ESP32 online', self.view.render()['message'])

    def test_aged_node_expires_even_with_recent_server_response(self):
        state = self.timer.command(5)
        self.timer.sync(dict(session=state['session'], revision=state['revision'],
                             ble_connected=True, ble_status='Verbunden'))
        self.clock.now += 4
        self.refresh()
        self.clock.now += 1
        self.assertTrue(self.view.render()['server'])
        self.assertEqual(self.view.render()['online'], 0)

    def test_start_ack_is_separate_from_ble_connection(self):
        self.timer.sync(dict(session=self.timer.session, revision=0,
                             ble_connected=True, ble_status='Verbunden'))
        self.timer.command(10)
        self.refresh()
        self.assertEqual(self.view.render()['devices'][0][1].splitlines()[0], 'WLAN · Übertragung ausstehend')
        self.assertIn('Bestätigung', self.view.render()['message'])

    def test_multiple_devices_and_mesh_relay(self):
        state = self.timer.command(10)
        peer = dict(id='c6c6c6c6c6c6', name='saal-2', session=state['session'], revision=state['revision'],
                    ble_connected=False, ble_status='Luxafor nicht gefunden', firmware=None, age_ms=3000)
        self.timer.sync(dict(id='a1a1a1a1a1a1', name='saal-1', session=state['session'],
                             revision=state['revision'], ble_connected=True, ble_status='OK',
                             firmware=None), [peer])
        self.refresh()
        view = self.view.render()
        self.assertEqual([row[0] for row in view['devices']], ['saal-1', 'saal-2'])
        self.assertTrue(view['devices'][1][1].startswith('Mesh über saal-1 · synchronisiert'))
        self.assertIn('Luxafor nicht gefunden', view['devices'][1][1])
        self.assertEqual((view['online'], view['synced']), (2, 2))
        # Mesh reports may be older than direct ones before counting as offline.
        self.clock.now += 6
        self.refresh()
        self.assertEqual([row[2] for row in self.view.render()['devices']], ['offline', 'warn'])
        self.assertIn('offline: saal-1', self.view.render()['message'])


class HotspotLinesTests(unittest.TestCase):
    def test_esp32_clients_show_firmware_and_mesh_devices_follow(self):
        from firmware.timer_logic import FIRMWARE_VERSION

        def device(device_id, name, via, version, online=True):
            return dict(id=device_id, name=name, via=via, relay='saal-1', online=online,
                        firmware=dict(version=version, expected=FIRMWARE_VERSION,
                                      current=version == FIRMWARE_VERSION))
        clients = [('10.42.0.50', 'a1:b2:c3:d4:e5:f6', 'saal-1', True),
                   ('10.42.0.51', '11:22:33:44:55:66', 'iphone', True)]
        devices = [device('a1b2c3d4e5f6', 'saal-1', 'wifi', FIRMWARE_VERSION),
                   device('000000000002', 'saal-2', 'mesh', '1.0.0'),
                   device('000000000003', 'saal-3', 'wifi', None, online=False)]
        lines = hotspot_lines(clients, devices, 10)
        self.assertEqual(lines[0].split(), ['10.42.0.50', 'saal-1', 'FW', FIRMWARE_VERSION])
        self.assertIn('11:22:33:44:55:66  iphone', lines[1])
        self.assertIn('Mesh/saal-1', lines[2])
        self.assertIn('FW 1.0.0 → ' + FIRMWARE_VERSION, lines[2])
        self.assertIn('offline', lines[3])
        self.assertIn('< 1.0.0', lines[3])
        newer = dict(devices[0], firmware=dict(version='9.0.0', expected='1.2.2', current=False, newer=True))
        self.assertIn('FW 9.0.0 (Pi kennt 1.2.2)', hotspot_lines(clients[:1], [newer], 5)[0])
        self.assertTrue(all(len(line) <= 56 for line in lines))
        short = hotspot_lines(clients, devices, 3)
        self.assertEqual(short[-1], '  … und 2 weitere')
        self.assertEqual(hotspot_lines([], [], 5), ['  keine'])


class WorkerTests(unittest.TestCase):
    def test_lost_start_response_is_not_retried_and_state_is_reconciled(self):
        timer = Timer()
        completed = threading.Event()
        calls = []

        class LostResponse:
            def request(self, path, body=None):
                calls.append(path)
                if path == '/api/start':
                    timer.command(body['minutes'])
                    raise OSError('response lost after server accepted command')
                client.close()
                completed.set()
                return timer.snapshot()

        client = Client(LostResponse())
        self.assertEqual(client.command(1), 1)
        self.assertIsNone(client.command(30))
        client.thread.start()
        try:
            self.assertTrue(completed.wait(2))
            client.thread.join(2)
            self.assertFalse(client.thread.is_alive())
            self.assertEqual(calls, ['/api/start', '/api/state'])
            self.assertIn('unbestätigt', client.results.get_nowait()[3])
            self.assertEqual(client.results.get_nowait()[2]['revision'], 1)
        finally:
            client.close()

    def test_expired_queued_start_is_discarded(self):
        clock = Clock()
        calls = []

        class Fake:
            def request(self, path, body=None):
                calls.append(path)
                client.close()
                return Timer().snapshot()

        client = Client(Fake(), clock)
        client.command(30)
        clock.now += 4
        client.run()
        self.assertEqual(calls, ['/api/state'])
        self.assertIn('verworfen', client.results.get_nowait()[3])

    def test_results_are_bounded_and_close_never_sends_stop(self):
        client = Client(None)
        for index in range(100):
            client.publish((index, 0, None, None))
        self.assertEqual(client.results.qsize(), 4)
        client.close()
        self.assertIsNone(client.command())
        self.assertTrue(client.commands.empty())

    def test_auth_failure_is_actionable(self):
        class Unauthorized:
            def request(self, path, body=None):
                raise HTTPError(path, 401, 'Unauthorized', {}, None)

        client = Client(Unauthorized())
        client.perform(1, '/api/start', {'minutes': 1})
        self.assertIn('API-Schlüssel prüfen', client.results.get_nowait()[3])


class TransportTests(unittest.TestCase):
    def test_real_http_start_state_stop_and_authentication(self):
        timer = Timer()
        server = make_server('127.0.0.1', 0, create_app(TOKEN, timer))
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            transport = Transport(TOKEN, server.server_port)
            self.assertEqual(transport.request('/api/start', {'minutes': 1})['revision'], 1)
            self.assertEqual(transport.request('/api/state')['phase'], 'orange')
            self.assertIsNone(transport.request('/api/stop', {})['remaining_ms'])
            with self.assertRaises(HTTPError) as error:
                Transport('wrong', server.server_port).request('/api/state')
            self.assertEqual(error.exception.code, 401)
            error.exception.close()
        finally:
            server.shutdown()
            server.server_close()
            worker.join(2)
