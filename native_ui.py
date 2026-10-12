"""Native Tk touch frontend for the Pi Zero 2 W. Run via run-native.sh."""
import argparse
import os
import queue
import threading
import tkinter as tk
from tkinter import font

import netinfo
import version
from native_client import Client, Transport, ViewState
from ui_config import COLORS, LABELS, LEGEND, LEGEND_COLORS, OVERDUE_DIM, PRESETS

BG, PANEL, TEXT, MUTED = '#111820', '#202d38', COLORS['off'], '#a7b5bf'


class TimerWindow:
    def __init__(self, root, client, fullscreen=True, cursor=''):
        self.root, self.client = root, client
        self.view = ViewState()
        self.previous = {}
        self.center_width = None
        self.buttons = []
        self.overlay = None
        root.title('SwiNOG – Pi Timer')
        root.configure(bg=BG)
        root.geometry('1024x600')
        root.minsize(800, 480)
        root.attributes('-fullscreen', fullscreen)
        # Without a desktop X11 shows its default 'X' pointer; child widgets inherit this one.
        try:
            root.configure(cursor=cursor)
        except tk.TclError:
            pass
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.bind('<F11>', lambda event: root.attributes('-fullscreen', not root.attributes('-fullscreen')))
        root.bind('<Escape>', lambda event: root.attributes('-fullscreen', False))
        root.grid_rowconfigure(1, weight=1)
        root.grid_columnconfigure(0, weight=1)
        header = tk.Frame(root, bg=BG)
        header.grid(row=0, column=0, sticky='ew', padx=22, pady=(18, 10))
        self.label(header, 'SwiNOG  /  PI TIMER', size=20).pack(side='left')
        self.server = self.label(header, 'Warte auf Server', size=12)
        self.server.pack(side='right')
        body = tk.Frame(root, bg=BG)
        body.grid(row=1, column=0, sticky='nsew', padx=18, pady=(0, 18))
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(0, weight=1)
        presets = tk.Frame(body, bg=BG)
        presets.grid(row=0, column=0, sticky='ns', padx=(0, 18))
        for index, minutes in enumerate(PRESETS):
            presets.grid_rowconfigure(index, weight=1)
            button = tk.Button(presets, text='%d min' % minutes, command=lambda m=minutes: self.command(m),
                               font=('DejaVu Sans', 22, 'bold'), width=6, bg=PANEL, fg=TEXT,
                               activebackground='#304353', activeforeground=TEXT, relief='flat', bd=0,
                               highlightthickness=0)
            button.grid(row=index, column=0, sticky='nsew', pady=4, ipady=4)
            self.buttons.append(button)
        center = tk.Frame(body, bg=BG)
        center.grid(row=0, column=1, sticky='nsew')
        # The available screen width determines text size, never vice versa.
        # Otherwise font/wrap changes can repeatedly resize the parent frame.
        center.grid_propagate(False)
        center.grid_columnconfigure(0, weight=1)
        center.grid_rowconfigure(0, weight=1)
        center.grid_rowconfigure(4, weight=1)
        self.phase = self.label(center, 'BEREIT', size=13)
        self.phase.grid(row=1, column=0, pady=8)
        self.time_font = font.Font(family='DejaVu Sans', size=-108, weight='bold')
        self.countdown = tk.Label(center, text='00:00', bg=BG, fg=TEXT, font=self.time_font)
        self.countdown.grid(row=2, column=0, sticky='ew', pady=(0, 20))
        stop = tk.Button(center, text='STOP', command=self.command, font=('DejaVu Sans', 25, 'bold'),
                         bg='#b6323c', fg='white', activebackground='#d6404d', activeforeground='white',
                         relief='flat', bd=0, highlightthickness=0)
        stop.grid(row=3, column=0, sticky='ew', padx=12, ipady=12)
        self.buttons.append(stop)
        self.feedback = self.label(center, 'Warte auf Timer-Server', size=12)
        self.feedback.configure(wraplength=430)
        self.feedback.grid(row=4, column=0, sticky='n', padx=8, pady=18)
        status = tk.Frame(body, bg=BG, width=220)
        status.pack_propagate(False)
        status.grid(row=0, column=2, sticky='ns', padx=(18, 0))
        self.label(status, 'VERBINDUNGEN', size=11).pack(anchor='w', pady=(12, 20))
        self.node = self.label(status, 'ESP32 · WLAN', size=14)
        self.node.pack(anchor='w')
        self.node_detail = self.label(status, 'Unbekannt', size=11)
        self.node_detail.configure(wraplength=180, justify='left')
        self.node_detail.pack(anchor='w', pady=(6, 26))
        self.ble = self.label(status, 'Luxafor · BLE', size=14)
        self.ble.pack(anchor='w')
        self.ble_detail = self.label(status, 'Unbekannt', size=11)
        self.ble_detail.configure(wraplength=180, justify='left')
        self.ble_detail.pack(anchor='w', pady=(6, 26))
        self.orb = self.label(status, 'Luxafor · USB', size=14)
        self.orb.pack(anchor='w')
        self.orb_detail = self.label(status, 'Unbekannt', size=11)
        self.orb_detail.configure(wraplength=180, justify='left')
        self.orb_detail.pack(anchor='w', pady=(6, 30))
        for phase_name, text in LEGEND:
            row = tk.Frame(status, bg=BG)
            row.pack(anchor='w', pady=1)
            tk.Frame(row, bg=LEGEND_COLORS[phase_name], width=11, height=11).pack(side='left', padx=(0, 8))
            self.label(row, text, size=11).pack(side='left')
        self.center = center
        center.bind('<Configure>', self.resize)
        self.info_button = tk.Button(root, text='WLAN / IP', command=self.open_info, font=('DejaVu Sans', 11),
                  bg=PANEL, fg=MUTED, activebackground='#304353', activeforeground=TEXT, relief='flat',
                  bd=0, highlightthickness=0, padx=12, pady=6)
        self.info_button.place(relx=1, rely=1, x=-8, y=-8, anchor='se')
        self.tick()

    @staticmethod
    def label(parent, text, size=12):
        return tk.Label(parent, text=text, bg=BG, fg=MUTED, font=('DejaVu Sans', size), justify='left')

    def resize(self, event):
        if event.width == self.center_width:
            return
        self.center_width = event.width
        # Reserve room for a leading minus and a three-digit minute counter.
        size = -max(36, min(108, int(event.width / 4.9)))
        if self.time_font.cget('size') != size:
            self.time_font.configure(size=size)
        self.feedback.configure(wraplength=max(160, event.width - 24))

    def open_info(self):
        if self.overlay is None or self.overlay.closed:
            self.overlay = InfoOverlay(self.root)

    def command(self, minutes=None):
        generation = self.client.command(minutes)
        if generation is not None:
            self.view.generation = generation
            self.update(self.feedback, text='Befehl wird übertragen …')

    def update(self, widget, **values):
        # Tk redraws only changed properties, not a whole page/frame each tick.
        key = str(widget)
        if self.previous.get(key) != values:
            widget.configure(**values)
            self.previous[key] = values

    def tick(self):
        while True:
            try:
                self.view.accept(self.client.results.get_nowait())
            except queue.Empty:
                break
        state = self.view.render()
        color = COLORS[state['phase']]
        if state['phase'] == 'overdue' and int(self.view.clock() * 2) % 2:
            color = OVERDUE_DIM
        self.update(self.countdown, text=state['text'], fg=color)
        self.update(self.phase, text=LABELS[state['phase']])
        self.update(self.server, text='Headend verbunden' if state['server'] else 'Server offline / suche …')
        self.update(self.node, text='ESP32 · WLAN', fg=COLORS['green'] if state['node'] else COLORS['orange'])
        self.update(self.ble, text='Luxafor · BLE', fg=COLORS['green'] if state['ble'] else COLORS['orange'])
        self.update(self.node_detail, text=state['node_text'])
        self.update(self.ble_detail, text=state['ble_text'])
        self.update(self.orb, text='Luxafor · USB', fg=COLORS['green'] if state['orb'] else COLORS['orange'])
        self.update(self.orb_detail, text=state['orb_text'])
        self.update(self.feedback, text='Befehl wird übertragen …' if self.client.busy else state['message'])
        for button in self.buttons:
            self.update(button, state='disabled' if self.client.busy else 'normal')
        self.root.after(250, self.tick)

    def close(self):
        # Window lifecycle never changes the timer; only the STOP button does.
        self.client.close()
        self.root.destroy()


class InfoOverlay:
    """Full-window overlay with hotspot QR code and addresses; closing never touches the timer."""
    REFRESH_MS = 5000

    def __init__(self, root):
        self.root = root
        self.result = None
        self.closed = False
        self.frame = tk.Frame(root, bg=BG)
        self.frame.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.frame.grid_columnconfigure(1, weight=1)
        self.frame.grid_rowconfigure(1, weight=1)
        title = tk.Frame(self.frame, bg=BG)
        title.grid(row=0, column=0, columnspan=2, sticky='ew', padx=22, pady=(18, 10))
        TimerWindow.label(title, 'WLAN & ADRESSEN', size=20).pack(side='left')
        TimerWindow.label(title, 'Version ' + version.describe(), size=11).pack(side='left', padx=18)
        tk.Button(title, text='Schließen', command=self.close, font=('DejaVu Sans', 18, 'bold'),
                  bg=PANEL, fg=TEXT, activebackground='#304353', activeforeground=TEXT, relief='flat',
                  bd=0, highlightthickness=0, padx=24, pady=10).pack(side='right')
        left = tk.Frame(self.frame, bg=BG)
        left.grid(row=1, column=0, sticky='n', padx=(22, 18))
        self.qr = tk.Canvas(left, width=300, height=300, bg=BG, highlightthickness=0)
        self.qr.pack(anchor='w')
        self.wifi = TimerWindow.label(left, 'Lese WLAN-Daten …', size=13)
        self.wifi.configure(fg=TEXT, wraplength=300)
        self.wifi.pack(anchor='w', pady=(10, 0))
        self.details = TimerWindow.label(self.frame, '', size=13)
        self.details.configure(fg=TEXT, anchor='nw', font=('DejaVu Sans Mono', 13))
        self.details.grid(row=1, column=1, sticky='nsew', padx=(0, 22), pady=(0, 18))
        self.refresh()

    def refresh(self):
        if self.closed:
            return
        def collect():
            self.result = netinfo.snapshot()
        threading.Thread(target=collect, daemon=True).start()
        self.poll()

    def poll(self):
        if self.closed:
            return
        if self.result is None:
            self.root.after(100, self.poll)
            return
        info, self.result = self.result, None
        self.render(info)
        self.root.after(self.REFRESH_MS, self.refresh)

    def render(self, info):
        self.qr.delete('all')
        if info['matrix']:
            size = len(info['matrix'])
            cell = 300 // size
            offset = (300 - cell * size) // 2
            # White background is required: phone scanners expect dark modules on light.
            self.qr.create_rectangle(0, 0, 300, 300, fill='white', outline='')
            for y, row in enumerate(info['matrix']):
                for x, dark in enumerate(row):
                    if dark:
                        self.qr.create_rectangle(offset + x * cell, offset + y * cell, offset + (x + 1) * cell,
                                                 offset + (y + 1) * cell, fill='black', outline='')
            text = 'WLAN: %s\nPasswort: %s' % (info['ssid'], info['psk'])
        else:
            text = info['error'] or 'Kein WLAN-Profil'
        # Web UI on phones/laptops in the hotspot; it asks for the API key from .env.
        text += '\n\nGUI remote öffnen:\n' + '\n'.join(info.get('urls', []))
        self.wifi.configure(text=text)
        lines = ['HEADEND']
        lines += ['  %-8s %s' % row for row in info['addresses']] or ['  keine IPv4-Adresse']
        lines += ['', 'GERÄTE IM HOTSPOT']
        # Room for about 20 lines at 600 px; active clients are listed first.
        shown = info['clients'][:max(1, 19 - len(lines))]
        for ip, mac, name, active in shown:
            lines.append('  %-15s %s  %s%s' % (ip, mac, name or '–', '' if active else '  (inaktiv)'))
        if len(info['clients']) > len(shown):
            lines.append('  … und %d weitere' % (len(info['clients']) - len(shown)))
        if not info['clients']:
            lines.append('  keine')
        self.details.configure(text='\n'.join(lines))

    def close(self):
        self.closed = True
        self.frame.destroy()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--windowed', action='store_true', help='Fenster statt Vollbild')
    args = parser.parse_args()
    token = os.environ.get('PI_TIMER_TOKEN', '')
    if len(token) < 20 or not token.isascii() or not token.isalnum():
        parser.error('PI_TIMER_TOKEN fehlt/ungültig. Mit ./run-native.sh starten.')
    port = int(os.environ.get('PI_TIMER_PORT', '8000'))
    root = tk.Tk()
    client = Client(Transport(token, port))
    # Touch kiosk: hide the pointer in fullscreen ('dot' = small dot, '' = X11 default).
    cursor = os.environ.get('PI_TIMER_CURSOR', 'none') if not args.windowed else ''
    TimerWindow(root, client, fullscreen=not args.windowed, cursor=cursor)
    client.thread.start()
    root.mainloop()


if __name__ == '__main__':
    main()
