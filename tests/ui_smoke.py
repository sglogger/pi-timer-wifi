"""Linux/Tk layout and interaction checks; run under xvfb, outside unit discovery."""
import queue
import os
import faulthandler
import sys
from pathlib import Path
import tkinter as tk
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import native_ui
from native_ui import TimerWindow, PRESETS


class FakeClient:
    busy = False

    def __init__(self):
        self.results = queue.Queue()
        self.calls = []
        self.closed = False

    def command(self, minutes=None):
        self.calls.append(minutes)
        return len(self.calls)

    def close(self):
        self.closed = True


class WindowTests(unittest.TestCase):
    def test_touch_targets_layout_and_window_restart(self):
        root = tk.Tk()
        client = FakeClient()
        window = TimerWindow(root, client, fullscreen=False)
        try:
            root.update()
            for remaining in (None, 60000, -6000000):
                window.view.accept((0, window.view.clock(), {'remaining_ms': remaining}, None))
                window.tick()
                root.update()
                for widget in window.buttons + [window.countdown, window.feedback, window.ble_detail,
                                                window.orb_detail]:
                    self.assertGreaterEqual(widget.winfo_rootx(), root.winfo_rootx())
                    self.assertLessEqual(widget.winfo_rootx() + widget.winfo_width(),
                                         root.winfo_rootx() + 1024)
                    self.assertLessEqual(widget.winfo_rooty() + widget.winfo_height(),
                                         root.winfo_rooty() + 600)
                self.assertLessEqual(window.time_font.measure(window.countdown.cget('text')),
                                     window.countdown.winfo_width())
            for button in window.buttons:
                self.assertGreaterEqual(button.winfo_height(), 44)
                button.invoke()
            self.assertEqual(client.calls, list(PRESETS) + [None])
            if os.environ.get('UI_SCREENSHOT'):
                from PIL import ImageGrab
                ImageGrab.grab().save(os.environ['UI_SCREENSHOT'])
            client.busy = True
            window.tick()
            self.assertTrue(all(str(button.cget('state')) == 'disabled' for button in window.buttons))
        finally:
            window.close()
        self.assertTrue(client.closed)
        self.assertEqual(client.calls, list(PRESETS) + [None], 'Closing the window must not send STOP')

    def test_info_overlay_opens_fits_and_closes_without_timer_commands(self):
        root = tk.Tk()
        client = FakeClient()
        window = TimerWindow(root, client, fullscreen=False)
        matrix = [[(x + y) % 3 == 0 for x in range(37)] for y in range(37)]
        info = {'ssid': 'SwiNOG-Timer', 'psk': '0123456789abcdef01234567', 'matrix': matrix, 'error': None,
                'addresses': [('wlan0', '10.42.0.1/24'), ('eth0', '192.168.1.20/24')],
                'urls': ['http://pi-timer.local:8000/', 'http://10.42.0.1:8000/'],
                'clients': [('10.42.0.%d' % n, 'aa:bb:cc:dd:ee:%02x' % n, 'espressif', n < 60)
                            for n in range(50, 66)]}
        original = native_ui.netinfo.snapshot
        native_ui.netinfo.snapshot = lambda: info
        try:
            root.update()
            opener = window.info_button
            self.assertGreaterEqual(opener.winfo_rootx() + opener.winfo_width(), root.winfo_rootx() + 1000)
            self.assertGreaterEqual(opener.winfo_rooty() + opener.winfo_height(), root.winfo_rooty() + 580)
            opener.invoke()
            overlay = window.overlay
            for _ in range(40):
                root.update()
                if overlay.details.cget('text'):
                    break
                root.after(50)
            self.assertTrue(overlay.details.cget('text'), 'overlay did not render')
            self.assertIn('10.42.0.50', overlay.details.cget('text'))
            self.assertIn('2 weitere', overlay.details.cget('text'))
            self.assertIn('0123456789abcdef01234567', overlay.wifi.cget('text'))
            self.assertIn('http://10.42.0.1:8000/', overlay.wifi.cget('text'))
            self.assertGreater(len(overlay.qr.find_all()), 100)
            for widget in (overlay.qr, overlay.wifi, overlay.details):
                self.assertLessEqual(widget.winfo_rootx() + widget.winfo_reqwidth(), root.winfo_rootx() + 1024)
                self.assertLessEqual(widget.winfo_rooty() + widget.winfo_reqheight(), root.winfo_rooty() + 600)
            if os.environ.get('UI_SCREENSHOT'):
                from PIL import ImageGrab
                path = os.environ['UI_SCREENSHOT']
                ImageGrab.grab().save(path.replace('.png', '-info.png'))
            overlay.close()
            root.update()
            self.assertFalse(overlay.frame.winfo_exists())
            window.open_info()
            self.assertIsNot(window.overlay, overlay, 'overlay must reopen after closing')
            window.overlay.close()
            self.assertEqual(client.calls, [])
        finally:
            native_ui.netinfo.snapshot = original
            window.close()


if __name__ == '__main__':
    faulthandler.dump_traceback_later(int(os.environ.get("UI_TIMEOUT", "10")))
    unittest.main()
