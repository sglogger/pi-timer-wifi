import unittest
from firmware.timer_logic import Replica, phase, clock_text, packet_for_phase
from server import Timer, create_app


class Clock:
    def __init__(self):
        self.now = 1000

    def __call__(self):
        return self.now


class TimerTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.timer = Timer(self.clock)

    def test_thresholds_and_overtime(self):
        self.timer.command(10)
        for elapsed, expected in ((0, 'green'), (300, 'yellow'), (540, 'orange'),
                                  (600, 'red'), (629.999, 'red'), (630, 'overdue')):
            self.clock.now = 1000 + elapsed
            self.assertEqual(self.timer.snapshot()['phase'], expected)

    def test_short_timer_starts_in_correct_phase(self):
        self.assertEqual(self.timer.command(1)['phase'], 'orange')
        self.assertEqual(self.timer.command(5)['phase'], 'yellow')

    def test_start_stop_replacement_has_no_pending_jobs(self):
        self.timer.command(30)
        self.clock.now += 100
        self.timer.command(1)
        self.assertEqual(self.timer.snapshot()['remaining_ms'], 60000)
        self.timer.command()
        self.clock.now += 4000
        self.assertEqual(self.timer.snapshot()['phase'], 'off')
        self.assertEqual(self.timer.revision, 3)

    def test_ack_and_online_are_separate_from_server_acceptance(self):
        state = self.timer.command(10)
        report = dict(session=state['session'], revision=state['revision'],
                      ble_connected=False, ble_status='Suche')
        self.timer.sync(report)
        self.assertTrue(self.timer.snapshot()['node']['applied'])
        self.timer.command()
        self.assertFalse(self.timer.snapshot()['node']['applied'])
        self.clock.now += 5
        self.assertFalse(self.timer.snapshot()['node']['online'])


class ReplicaTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.replica = Replica(self.clock, lambda a, b: a-b)

    def state(self, revision=1, remaining=60000, session='a'):
        return dict(protocol=1, session=session, revision=revision, remaining_ms=remaining)

    def test_offline_countdown_and_colors_continue(self):
        self.replica.apply(self.state(), 100)
        self.clock.now += 60000
        self.assertEqual(self.replica.advance(), -50)
        self.assertEqual(phase(self.replica.remaining), 'red')
        self.clock.now += 30000
        self.assertEqual(phase(self.replica.advance()), 'overdue')

    def test_stop_received_after_outage_overrides_running_countdown(self):
        self.replica.apply(self.state(), 0)
        self.clock.now += 20000
        self.replica.apply(self.state(revision=2, remaining=None), 200)
        self.assertIsNone(self.replica.advance())

    def test_stale_revision_cannot_restart_stopped_timer(self):
        self.replica.apply(self.state(revision=2, remaining=None), 0)
        self.assertFalse(self.replica.apply(self.state(), 0))
        self.assertIsNone(self.replica.advance())

    def test_reconnect_uses_current_remaining_time(self):
        self.replica.apply(self.state(), 0)
        self.clock.now += 20000
        self.replica.apply(self.state(remaining=39500), 100)
        self.assertEqual(self.replica.advance(), 39450)

    def test_server_restart_resets_replica(self):
        self.replica.apply(self.state(revision=9), 0)
        self.replica.apply(self.state(revision=0, remaining=None, session='b'), 0)
        self.assertIsNone(self.replica.advance())
        self.assertEqual(self.replica.session, 'b')

    def test_clock_wrap(self):
        period = 1 << 30
        ticks_diff = lambda a, b: ((a-b + period//2) % period) - period//2
        self.clock.now = period - 100
        replica = Replica(self.clock, ticks_diff)
        replica.apply(self.state(), 0)
        self.clock.now = 100
        self.assertEqual(replica.advance(), 59800)

    def test_invalid_or_slow_snapshot_preserves_last_state(self):
        self.replica.apply(self.state(), 0)
        with self.assertRaises(ValueError):
            self.replica.apply(self.state(remaining='bad'), 0)
        self.assertFalse(self.replica.apply(self.state(remaining=None), 2001))
        self.assertEqual(self.replica.advance(), 60000)

    def test_display_boundaries(self):
        for value, label in ((1,'00:01'), (60000,'01:00'), (0,'00:00'),
                             (-999,'00:00'), (-1000,'-00:01'), (None,'READY')):
            self.assertEqual(clock_text(value), label)

    def test_ble_frames_are_direct_ble_not_usb(self):
        self.assertEqual(packet_for_phase('green'), bytes.fromhex('a1ff00ff00101010'))
        self.assertEqual(packet_for_phase('off'), bytes.fromhex('a1ff000000101010'))
        self.assertEqual(packet_for_phase('overdue'), bytes.fromhex('a3ffff00000f0000'))


class APITests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.timer = Timer(self.clock)
        self.app = create_app('testtoken12345678901234567890', self.timer)
        self.client = self.app.test_client()
        self.headers = {'Authorization': 'Bearer testtoken12345678901234567890'}

    def test_auth_required(self):
        self.assertEqual(self.client.get('/api/state').status_code, 401)
        self.assertEqual(self.client.post('/api/stop', json={}).status_code, 401)
        self.assertEqual(self.client.get('/').status_code, 200)

    def test_no_get_mutations(self):
        self.assertEqual(self.client.get('/api/start', headers=self.headers).status_code, 405)
        self.assertEqual(self.client.get('/api/stop', headers=self.headers).status_code, 405)

    def test_duration_validation(self):
        for value in (0, -1, 121, True, 1.5, '5', None):
            response = self.client.post('/api/start', json={'minutes':value}, headers=self.headers)
            self.assertEqual(response.status_code, 400, value)
        self.assertEqual(self.timer.revision, 0)

    def test_json_required(self):
        self.assertEqual(self.client.post('/api/stop', data='', headers=self.headers).status_code, 415)

    def test_device_sync_roundtrip(self):
        self.client.post('/api/start', json={'minutes':10}, headers=self.headers)
        report = dict(session=None, revision=-1, ble_connected=False, ble_status='Suche')
        state = self.client.post('/api/device/sync', json=report, headers=self.headers).json
        self.assertEqual(state['remaining_ms'], 600000)
        report.update(session=state['session'], revision=state['revision'])
        self.client.post('/api/device/sync', json=report, headers=self.headers)
        self.assertTrue(self.client.get('/api/state', headers=self.headers).json['node']['applied'])
        self.assertEqual(self.client.post('/api/stop', json={}, headers=self.headers).json['phase'], 'off')

    def test_bad_device_report(self):
        for body in ([], {}, {'revision':True}, {'ble_status':'x'*121}):
            self.assertEqual(self.client.post('/api/device/sync', json=body, headers=self.headers).status_code, 400)

    def test_restart_has_new_session_and_stops(self):
        old = self.timer.command(30)
        new = Timer(self.clock).snapshot()
        self.assertNotEqual(old['session'], new['session'])
        self.assertIsNone(new['remaining_ms'])

    def test_command_response_keeps_node_status(self):
        self.client.post('/api/device/sync', headers=self.headers,
                         json=dict(session=None, revision=-1, ble_connected=True, ble_status='OK'))
        node = self.client.post('/api/start', json={'minutes':5}, headers=self.headers).json['node']
        self.assertTrue(node['online'])
        self.assertFalse(node['applied'])

    def test_invalid_json_returns_json_error(self):
        for path in ('/api/start', '/api/device/sync'):
            response = self.client.post(path, data='{', content_type='application/json', headers=self.headers)
            self.assertEqual(response.status_code, 400)
            self.assertIn('error', response.json)

    def test_page_embeds_shared_ui_config(self):
        page = self.client.get('/').get_data(as_text=True)
        self.assertIn('id="ui-config"', page)
        self.assertIn('[["overdue", -30000]', page)

    def test_response_is_never_cached(self):
        self.assertEqual(self.client.get('/api/state', headers=self.headers).headers['Cache-Control'], 'no-store')
