"""Linux/Tk layout and interaction checks; run under xvfb, outside unit discovery."""
import queue
import os
import faulthandler
import sys
from pathlib import Path
import tkinter as tk
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
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
                for widget in window.buttons + [window.countdown, window.feedback, window.ble_detail]:
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


if __name__ == '__main__':
    faulthandler.dump_traceback_later(10)
    unittest.main()
