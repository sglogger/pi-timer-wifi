import unittest
from unittest.mock import patch
from deploy import setup_hotspot


class HotspotTests(unittest.TestCase):
    def test_prepares_private_ap_without_switching_current_connection(self):
        with patch.object(setup_hotspot, 'nmcli', side_effect=['home-wifi\noffice', 'yes', '']) as nm:
            password = setup_hotspot.prepare()
        mutation = nm.call_args_list[-1].args
        self.assertEqual(mutation[:2], ('connection', 'add'))
        settings = dict(zip(mutation[2::2], mutation[3::2]))
        self.assertEqual(settings['802-11-wireless.mode'], 'ap')
        self.assertEqual(settings['802-11-wireless.band'], 'bg')
        self.assertEqual(settings['802-11-wireless-security.key-mgmt'], 'wpa-psk')
        self.assertEqual(settings['802-11-wireless-security.proto'], 'rsn')
        self.assertEqual(settings['802-11-wireless-security.pmf'], 'disable')
        self.assertEqual(settings['connection.autoconnect-priority'], '999')
        self.assertEqual(settings['802-11-wireless-security.psk'], password)
        self.assertEqual(len(password), 24)
        self.assertEqual(settings['ipv4.method'], 'shared')
        self.assertEqual(settings['ipv4.addresses'], '10.42.0.1/24')
        self.assertEqual(settings['connection.autoconnect'], 'no')
        self.assertFalse(any('up' in call.args or 'delete' in call.args for call in nm.call_args_list))

    def test_existing_profile_and_password_are_preserved(self):
        with patch.object(setup_hotspot, 'nmcli', return_value='home-wifi\npi-timer-direct') as nm:
            with self.assertRaisesRegex(ValueError, 'existiert'):
                setup_hotspot.prepare()
        self.assertEqual(nm.call_count, 1)

    def test_adapter_without_ap_support_is_not_changed(self):
        with patch.object(setup_hotspot, 'nmcli', side_effect=['home-wifi', 'no']) as nm:
            with self.assertRaisesRegex(ValueError, 'AP-Modus'):
                setup_hotspot.prepare()
        self.assertEqual(nm.call_count, 2)

    def test_disconnected_networkmanager_fails_before_mutation(self):
        with patch.object(setup_hotspot, 'nmcli', side_effect=setup_hotspot.subprocess.CalledProcessError(10, 'nmcli')) as nm:
            with self.assertRaises(setup_hotspot.subprocess.CalledProcessError):
                setup_hotspot.prepare()
        self.assertEqual(nm.call_count, 1)
