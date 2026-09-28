"""Native frontend behaviour, including real HTTP and lost command responses."""
import threading
import unittest
from urllib.error import HTTPError
from werkzeug.serving import make_server

from native_client import Client, Transport, ViewState
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
        state = self.timer.command(1)
        self.timer.sync(dict(session=state['session'], revision=state['revision'],
                             ble_connected=True, ble_status='Verbunden'))
        self.refresh()
        self.assertTrue(self.view.render()['ble'])
        self.clock.now += 90
        state = self.view.render()
        self.assertEqual((state['text'], state['phase']), ('-00:30', 'overdue'))
        self.assertFalse(state['node'])
        self.assertFalse(state['server'])
        self.assertIn('unbestätigt', state['message'])

    def test_old_poll_cannot_overwrite_a_new_command(self):
        old = self.timer.command(30)
        stopped = self.timer.command()
        self.view.accept((2, self.clock(), stopped, None))
        self.view.accept((1, self.clock(), old, None))
        self.assertEqual(self.view.render()['text'], '00:00')
        self.assertEqual(self.view.render()['phase'], 'off')
        self.assertIn('warte auf ESP32', self.view.render()['message'])

    def test_no_node_does_not_crash_or_claim_connection(self):
        self.refresh()
        self.assertFalse(self.view.render()['node'])
        self.assertIn('ESP32 offline', self.view.render()['message'])

    def test_aged_node_expires_even_with_recent_server_response(self):
        state = self.timer.command(5)
        self.timer.sync(dict(session=state['session'], revision=state['revision'],
                             ble_connected=True, ble_status='Verbunden'))
        self.clock.now += 4
        self.refresh()
        self.clock.now += 1
        self.assertTrue(self.view.render()['server'])
        self.assertFalse(self.view.render()['node'])

    def test_start_ack_is_separate_from_ble_connection(self):
        self.timer.sync(dict(session=self.timer.session, revision=0,
                             ble_connected=True, ble_status='Verbunden'))
        self.timer.command(10)
        self.refresh()
        self.assertEqual(self.view.render()['node_text'], 'Übertragung ausstehend')
        self.assertIn('Bestätigung', self.view.render()['message'])


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
