import os
import subprocess
import unittest
from unittest.mock import mock_open, patch

import netinfo


class NetinfoTests(unittest.TestCase):
    def test_qr_payload_escapes_special_characters(self):
        self.assertEqual(netinfo.wifi_qr_payload('Swi;NOG', 'a:b,c"d\\'),
                         'WIFI:T:WPA;S:Swi\\;NOG;P:a\\:b\\,c\\"d\\\\;;')

    def test_qr_matrix_is_square_with_quiet_zone(self):
        matrix = netinfo.qr_matrix(netinfo.wifi_qr_payload('SwiNOG-Timer', '0123456789abcdef01234567'))
        self.assertEqual(len(matrix), len(matrix[0]))
        self.assertFalse(any(matrix[0]))
        self.assertTrue(any(matrix[2]))

    def test_credentials_from_networkmanager(self):
        with patch.object(netinfo, 'run', return_value='SwiNOG-Timer\nsecret\n') as run:
            self.assertEqual(netinfo.wifi_credentials(), ('SwiNOG-Timer', 'secret'))
        self.assertIn('pi-timer-direct', run.call_args.args)

    def test_credentials_fall_back_to_environment(self):
        error = subprocess.CalledProcessError(4, 'nmcli')
        with patch.object(netinfo, 'run', side_effect=error), \
                patch.dict(os.environ, {'PI_TIMER_WIFI_SSID': 'S', 'PI_TIMER_WIFI_PSK': 'P'}):
            self.assertEqual(netinfo.wifi_credentials(), ('S', 'P'))
        with patch.object(netinfo, 'run', side_effect=error), patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(LookupError):
                netinfo.wifi_credentials()

    def test_addresses_skip_loopback(self):
        output = ('1: lo    inet 127.0.0.1/8 scope host lo       valid_lft forever\n'
                  '3: wlan0    inet 10.42.0.1/24 brd 10.42.0.255 scope global wlan0\n')
        self.assertEqual(netinfo.parse_addresses(output), [('wlan0', '10.42.0.1/24')])

    def test_clients_merge_leases_and_neighbours(self):
        leases = ('1760000000 aa:aa:aa:aa:aa:01 10.42.0.50 espressif *\n'
                  '1760000000 aa:aa:aa:aa:aa:02 10.42.0.7 * 01:aa\n')
        neighbours = ('10.42.0.7 lladdr aa:aa:aa:aa:aa:02 REACHABLE\n'
                      '10.42.0.9 lladdr aa:aa:aa:aa:aa:03 STALE\n'
                      '10.42.0.11  FAILED\n')
        with patch('builtins.open', mock_open(read_data=leases)), \
                patch.object(netinfo, 'run', return_value=neighbours):
            rows = netinfo.clients()
        self.assertEqual(rows, [('10.42.0.7', 'aa:aa:aa:aa:aa:02', '', True),
                                ('10.42.0.9', 'aa:aa:aa:aa:aa:03', '', True),
                                ('10.42.0.50', 'aa:aa:aa:aa:aa:01', 'espressif', False)])

    def test_remote_urls_use_mdns_name_and_hotspot_address(self):
        with patch.object(netinfo.socket, 'gethostname', return_value='pi-timer'):
            urls = netinfo.remote_urls([('eth0', '192.168.1.20/24'), ('wlan0', '10.42.0.1/24')], '8000')
        self.assertEqual(urls, ['http://pi-timer.local:8000/', 'http://10.42.0.1:8000/'])

    def test_snapshot_never_raises(self):
        with patch.object(netinfo, 'run', side_effect=OSError), patch('builtins.open', side_effect=OSError), \
                patch.dict(os.environ, {}, clear=True):
            info = netinfo.snapshot()
        self.assertIsNone(info['matrix'])
        self.assertIn('PI_TIMER_WIFI_PSK', info['error'])
        self.assertEqual(info['clients'], [])


if __name__ == '__main__':
    unittest.main()
