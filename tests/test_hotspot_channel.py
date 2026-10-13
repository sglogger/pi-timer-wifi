import subprocess
import unittest
from unittest.mock import patch
from deploy import hotspot_channel


class FakeNmcli:
    """Records nmcli calls and answers the read-only queries."""

    def __init__(self, scan='', channel='6', fail_scan=0, fail_disconnect=False):
        self.calls = []
        self.scan, self.channel = scan, channel
        self.fail_scan, self.fail_disconnect = fail_scan, fail_disconnect

    def __call__(self, *arguments, timeout=30):
        self.calls.append(arguments)
        if arguments[:2] == ('device', 'disconnect') and self.fail_disconnect:
            raise subprocess.CalledProcessError(6, 'nmcli')
        if 'wifi' in arguments:
            if self.fail_scan:
                self.fail_scan -= 1
                raise subprocess.CalledProcessError(1, 'nmcli')
            return self.scan
        if '802-11-wireless.channel' in arguments and 'show' in arguments:
            return self.channel
        return ''

    def modifications(self):
        return [call for call in self.calls if call[:2] == ('connection', 'modify')]


class ChannelChoiceTests(unittest.TestCase):
    def test_parse_ignores_malformed_and_5ghz_lines(self):
        self.assertEqual(hotspot_channel.parse_scan('6:72\n11:30\n36:80\n--:50\n\n1:x'),
                         [(6, 72), (11, 30)])

    def test_busy_channel_is_avoided(self):
        channel, scores = hotspot_channel.choose([(6, 90), (6, 60), (1, 40)], current=6)
        self.assertEqual(channel, 11)
        self.assertGreater(scores[6], scores[1])

    def test_overlapping_neighbours_count_partially(self):
        # Channel 3 overlaps 1 more than 6; channel 11 is untouched.
        scores = dict((c, hotspot_channel.interference([(3, 100)], c)) for c in (1, 6, 11))
        self.assertAlmostEqual(scores[1], 0.6)
        self.assertAlmostEqual(scores[6], 0.4)
        self.assertEqual(scores[11], 0)

    def test_weak_networks_still_count_for_range(self):
        # Three weak networks hurt the range edge more than one moderate network.
        channel, _ = hotspot_channel.choose([(1, 50), (6, 25), (6, 25), (6, 25), (11, 60)], current=6)
        self.assertEqual(channel, 1)

    def test_empty_band_keeps_current_channel(self):
        self.assertEqual(hotspot_channel.choose([], current=11)[0], 11)
        self.assertEqual(hotspot_channel.choose([], current=0)[0], 1)


class SelectAndStartTests(unittest.TestCase):
    def run_select(self, fake):
        with patch.object(hotspot_channel, 'nmcli', fake), patch.object(hotspot_channel.time, 'sleep'), \
                patch('builtins.print'):
            return hotspot_channel.select_and_start()

    def test_scans_while_disconnected_then_stores_channel_and_starts(self):
        fake = FakeNmcli(scan='6:80\n1:70\n11:10')
        self.assertEqual(self.run_select(fake), 11)
        disconnect = fake.calls.index(('device', 'disconnect', 'wlan0'))
        scan = next(i for i, call in enumerate(fake.calls) if 'wifi' in call)
        self.assertLess(disconnect, scan)
        self.assertIn('--rescan', fake.calls[scan])
        self.assertEqual(fake.modifications(),
                         [('connection', 'modify', 'pi-timer-direct', '802-11-wireless.channel', '11')])
        self.assertEqual(fake.calls[-1], ('connection', 'up', 'pi-timer-direct'))

    def test_unchanged_channel_is_not_rewritten(self):
        fake = FakeNmcli(scan='1:80\n11:80', channel='6')
        self.assertEqual(self.run_select(fake), 6)
        self.assertEqual(fake.modifications(), [])

    def test_already_disconnected_and_busy_scanner_are_retried(self):
        fake = FakeNmcli(scan='1:80', fail_scan=2, fail_disconnect=True)
        self.assertEqual(self.run_select(fake), 6)
        self.assertEqual(sum('wifi' in call for call in fake.calls), 3)
        self.assertEqual(fake.calls[-1], ('connection', 'up', 'pi-timer-direct'))

    def test_failed_scan_still_starts_hotspot_on_old_channel(self):
        fake = FakeNmcli(fail_scan=5)
        self.assertEqual(self.run_select(fake), 6)
        self.assertEqual(fake.modifications(), [])
        self.assertEqual(fake.calls[-1], ('connection', 'up', 'pi-timer-direct'))


class BootTests(unittest.TestCase):
    def test_boot_does_nothing_unless_direct_mode_is_enabled(self):
        with patch.object(hotspot_channel.sys, 'platform', 'linux'), \
                patch.object(hotspot_channel.os, 'geteuid', return_value=0, create=True), \
                patch.object(hotspot_channel.subprocess, 'run'), \
                patch.object(hotspot_channel, 'nmcli', return_value='no') as nm, \
                patch.object(hotspot_channel, 'select_and_start') as select, patch('builtins.print'):
            self.assertEqual(hotspot_channel.main(['--boot']), 0)
        select.assert_not_called()
        self.assertEqual(nm.call_count, 1)


if __name__ == '__main__':
    unittest.main()
