import os
import select
import tempfile
import threading
import unittest

from orb import BusyTag, Lights, Orb, SerialPort
from server import Timer


class FakeBusyTag:
    """Answers AT commands on the master side of a pty like firmware 1.0 does (events included)."""

    def __init__(self, stored=(), shown='def.png'):
        # Holding the slave open keeps the master quiet until the code under test writes.
        self.master, self.slave = os.openpty()
        self.path = os.ttyname(self.slave)
        self.stored, self.shown = dict(stored), shown
        self.commands, self.uploads = [], {}
        self.buffer = b''
        self.stopped = False
        self.thread = threading.Thread(target=self.serve, daemon=True)
        self.thread.start()

    def reply(self, *lines):
        os.write(self.master, b''.join(line.encode() + b'\r\n' for line in lines))

    def receive(self):
        # Polls so close() can stop the thread: closing a pty that another thread reads blocks on macOS.
        while not select.select([self.master], [], [], 0.05)[0]:
            if self.stopped:
                raise OSError('closed')
        self.buffer += os.read(self.master, 4096)

    def read_line(self):
        while b'\r\n' not in self.buffer:
            self.receive()
        line, self.buffer = self.buffer.split(b'\r\n', 1)
        return line.decode()

    def read_bytes(self, size):
        while len(self.buffer) < size:
            self.receive()
        data, self.buffer = self.buffer[:size], self.buffer[size:]
        return data

    def serve(self):
        try:
            while True:
                self.handle(self.read_line())
        except OSError:
            pass

    def handle(self, line):
        self.commands.append(line)
        if line == 'AT+GDN':
            self.reply('+evn:PP,0', '+DN:busytag-EEC860')
        elif line == 'AT+GPL':
            self.reply(*['+PL:%s,%d' % item for item in self.stored.items()], 'OK')
        elif line.startswith('AT+UF='):
            name, size = line[6:].split(',')
            self.reply('>')
            data = self.read_bytes(int(size))
            if name == self.shown:  # Firmware 1.0 refuses to overwrite the picture on screen.
                self.reply('ERROR:3')
                return
            self.uploads[name] = data
            self.stored[name] = int(size)
            self.reply('', '+evn:WIS,1', 'OK')
        elif line == 'AT+SP?':
            self.reply('+SP:' + self.shown)
        elif line.startswith('AT+SP='):
            self.shown = line[6:]
            self.reply('+evn:SP,' + self.shown, 'OK')
        elif line.startswith('AT+CP='):
            self.reply('>')
            for _ in range(int(line[6:])):
                self.commands.append(self.read_line())
            self.reply('', 'OK')
        elif line == 'AT+SC=127,BADBAD':
            self.reply('ERROR:2')
        else:
            self.reply('+evn:PP,0', 'OK')

    def close(self):
        self.stopped = True
        self.thread.join()
        os.close(self.slave)
        os.close(self.master)


class BusyTagTests(unittest.TestCase):
    def setUp(self):
        self.images = tempfile.mkdtemp()
        for name, data in (('timer-off.png', b'off-image'), ('timer-green.png', b'green')):
            with open(os.path.join(self.images, name), 'wb') as file:
                file.write(data)
        self.device = FakeBusyTag(stored={'timer-green.png': 5, 'def.png': 16224})
        self.addCleanup(self.device.close)
        self.backend = BusyTag(ports=lambda: [self.device.path], images=self.images)
        self.addCleanup(lambda: [port.close() for port in self.backend.open])

    def test_find_uploads_only_missing_or_changed_pictures(self):
        devices = self.backend.find()
        self.assertEqual(len(devices), 1)
        self.assertEqual(self.device.uploads, {'timer-off.png': b'off-image'})
        self.assertEqual(self.device.commands, ['AT+GDN', 'AT+GPL', 'AT+SP?', 'AT+UF=timer-off.png,9'])
        self.assertEqual(self.backend.present(), [self.backend.key(devices[0])])

    def test_nothing_to_upload_sends_only_the_listing(self):
        self.device.stored['timer-off.png'] = 9
        self.backend.find()
        self.assertEqual(self.device.commands, ['AT+GDN', 'AT+GPL'])

    def test_picture_on_screen_is_replaced_after_switching_away(self):
        self.device.shown = 'timer-off.png'
        self.device.stored['timer-off.png'] = 4466
        self.backend.find()
        self.assertEqual(self.device.uploads, {'timer-off.png': b'off-image'})
        self.assertIn('AT+SP=timer-green.png', self.device.commands)

    def test_phases_set_leds_and_picture(self):
        device, = self.backend.find()
        del self.device.commands[:]
        for value, now in (('green', 0), ('overdue', 0), ('overdue', 0.5), ('overdue', 1), ('off', 1)):
            self.backend.write(device, self.backend.packet(value, now))
        self.assertEqual(self.device.commands, [
            'AT+SC=127,00FF00', 'AT+SP=timer-green.png',
            'AT+SC=127,FF0000', 'AT+SP=timer-overdue.png', 'AT+SC=127,000000', 'AT+SC=127,FF0000',
            'AT+SC=127,000000', 'AT+SP=timer-off.png'])

    def test_overdue_blinks_through_the_orb_loop(self):
        clock = lambda: 1000
        timer = Timer(clock)
        orb = Orb(timer, self.backend)
        timer.command(1)
        timer.clock = lambda: 1000 + 120
        for now in (0, 0.2, 0.4, 0.6, 0.8, 1.0):
            orb.step(now)
        colours = [c for c in self.device.commands if c.startswith('AT+SC=')]
        self.assertEqual(colours, ['AT+SC=127,FF0000', 'AT+SC=127,000000', 'AT+SC=127,FF0000'])

    def test_error_reply_raises(self):
        device, = self.backend.find()
        with self.assertRaisesRegex(OSError, 'ERROR:2'):
            device.command('AT+SC=127,BADBAD')

    def test_silent_device_times_out(self):
        master, slave = os.openpty()
        self.addCleanup(os.close, master)
        port = SerialPort(os.ttyname(slave), timeout=0.2)
        os.close(slave)
        self.addCleanup(port.close)
        with self.assertRaisesRegex(OSError, 'keine Antwort'):
            port.command('AT+GDN', '+DN:')

    def test_orb_loop_reports_busy_tag(self):
        timer = Timer(lambda: 1000)
        orb = Orb(timer, self.backend)
        orb.step(0)
        self.assertEqual(orb.report(), {'connected': True, 'status': 'Busy Tag verbunden; Farbe gesendet'})
        self.assertEqual(self.device.commands[-1], 'AT+SP=timer-off.png')

    def test_no_busy_tag(self):
        orb = Orb(Timer(lambda: 1000), BusyTag(ports=lambda: [], images=self.images))
        orb.step(0)
        self.assertEqual(orb.report(), {'connected': False, 'status': 'Busy Tag nicht gefunden'})


class LightsTests(unittest.TestCase):
    def lights(self, *reports):
        lights = Lights(Timer(), backends=[BusyTag(ports=lambda: [])] * len(reports))
        for orb, (connected, status) in zip(lights.orbs, reports):
            orb._set(connected, status)
        return lights.report()

    def test_shows_connected_lights_only(self):
        self.assertEqual(self.lights((False, 'Luxafor USB nicht gefunden'), (True, 'Busy Tag verbunden')),
                         {'connected': True, 'status': 'Busy Tag verbunden'})

    def test_shows_all_problems_when_none_is_connected(self):
        self.assertEqual(self.lights((False, 'USB: Access denied'), (False, 'Busy Tag nicht gefunden')),
                         {'connected': False, 'status': 'USB: Access denied · Busy Tag nicht gefunden'})


if __name__ == '__main__':
    unittest.main()
