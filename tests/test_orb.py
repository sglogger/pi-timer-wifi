import unittest
from orb import Orb, packet_for_phase
from server import Timer, create_app

TOKEN = 'orbTestToken1234567890123456'


class Clock:
    now = 1000

    def __call__(self):
        return self.now


class FakeUSB:
    name = 'Luxafor USB'
    error_prefix = 'USB'

    @staticmethod
    def packet(value, now):
        return packet_for_phase(value)

    def __init__(self):
        self.plugged = []
        self.writes = []
        self.fail = False
        self.scans = 0

    def find(self):
        self.scans += 1
        return list(self.plugged)

    def present(self):
        return sorted(self.plugged)

    @staticmethod
    def key(device):
        return device

    def write(self, device, packet):
        if self.fail:
            raise OSError('No such device')
        self.writes.append((device, packet))


class OrbTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.timer = Timer(self.clock)
        self.usb = FakeUSB()
        self.usb.plugged = ['orb']
        self.orb = Orb(self.timer, self.usb, rescan=2)

    def packets(self):
        return [packet for _, packet in self.usb.writes]

    def test_packets_match_original_luxafor_commands(self):
        self.assertEqual(packet_for_phase('green'), [1, 255, 0, 255, 0, 0, 0])
        self.assertEqual(packet_for_phase('orange'), [1, 255, 255, 127, 0, 0, 0])
        self.assertEqual(packet_for_phase('off'), [1, 255, 0, 0, 0, 0, 0])
        self.assertEqual(packet_for_phase('overdue'), [3, 255, 255, 0, 0, 15, 0, 30])

    def test_follows_phases_and_sends_only_on_change(self):
        self.orb.step(0)
        self.timer.command(10)
        for elapsed in (0, 1, 300, 540, 600, 630, 631):
            self.clock.now = 1000 + elapsed
            self.orb.step(elapsed)
        self.timer.command()
        self.orb.step(700)
        self.assertEqual(self.packets(), [packet_for_phase(p) for p in
                                          ('off', 'green', 'yellow', 'orange', 'red', 'overdue', 'off')])
        self.assertEqual(self.orb.report(), {'connected': True, 'status': 'Luxafor USB verbunden; Farbe gesendet'})

    def test_write_error_drops_device_and_rescans(self):
        self.timer.command(10)
        self.orb.step(0)
        self.usb.fail = True
        self.timer.command(1)
        self.orb.step(1)
        self.assertFalse(self.orb.report()['connected'])
        self.usb.fail = False
        self.usb.plugged = []
        self.orb.step(2)
        self.assertEqual(self.usb.scans, 1, 'Rescan waits for the interval')
        self.orb.step(3)
        self.assertEqual(self.orb.report()['status'], 'Luxafor USB nicht gefunden')
        self.usb.plugged = ['orb']
        self.orb.step(5)
        self.assertEqual(self.packets(), [packet_for_phase('green'), packet_for_phase('orange')])
        self.assertTrue(self.orb.report()['connected'])

    def test_replug_without_phase_change_restores_color(self):
        self.timer.command(10)
        self.orb.step(0)
        self.usb.plugged = []
        self.orb.step(1)
        self.assertTrue(self.orb.report()['connected'], 'Presence is checked every rescan interval')
        self.orb.step(2)
        self.assertEqual(self.orb.report()['status'], 'Luxafor USB nicht gefunden')
        self.usb.plugged = ['orb2']
        self.orb.step(4)
        self.assertEqual(self.usb.writes, [('orb', packet_for_phase('green')),
                                           ('orb2', packet_for_phase('green'))])
        self.orb.step(6)
        self.assertEqual(len(self.usb.writes), 2, 'Unchanged device set is not reconfigured')
        self.assertEqual(self.usb.scans, 3, 'Presence checks do not reconfigure the light')

    def test_missing_usb_driver_does_not_stop_the_timer(self):
        def broken():
            raise ModuleNotFoundError("No module named 'usb'")
        self.usb.find = broken
        self.orb.step(0)
        self.assertEqual(self.orb.report(), {'connected': False, 'status': "USB: No module named 'usb'"})

    def test_all_connected_lights_get_the_color(self):
        self.usb.plugged = ['orb', 'flag']
        self.orb.step(0)
        self.assertEqual([device for device, _ in self.usb.writes], ['orb', 'flag'])
        self.assertIn('2 × Luxafor USB', self.orb.report()['status'])


class APITests(unittest.TestCase):
    def test_state_reports_orb_only_when_enabled(self):
        headers = {'Authorization': 'Bearer ' + TOKEN}
        timer = Timer()
        plain = create_app(TOKEN, timer).test_client()
        self.assertNotIn('orb', plain.get('/api/state', headers=headers).get_json())
        orb = Orb(timer, FakeUSB())
        client = create_app(TOKEN, timer, orb).test_client()
        self.assertEqual(client.get('/api/state', headers=headers).get_json()['orb'],
                         {'connected': False, 'status': 'Suche Luxafor USB'})
        started = client.post('/api/start', json={'minutes': 5}, headers=headers).get_json()
        self.assertIn('orb', started)


if __name__ == '__main__':
    unittest.main()
