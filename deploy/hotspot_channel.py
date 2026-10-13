#!/usr/bin/env python3
"""Scan the 2.4 GHz band and start the hotspot on the least occupied channel (1, 6 or 11).

wlan0 cannot scan while it runs as access point, so the hotspot is briefly
disconnected, the scan runs, the channel is stored in the profile and the hotspot
is started again. The hotspot is always restarted, even if the scan fails.
"""
import os
import subprocess
import sys
import time

PROFILE = "pi-timer-direct"
INTERFACE = "wlan0"
# Non-overlapping 2.4 GHz channels; 12/13 are avoided because not every client uses them.
CANDIDATES = (1, 6, 11)
# 20 MHz channels 5 apart do not overlap; closer neighbours interfere proportionally.
SPREAD = 5


def nmcli(*arguments, timeout=30):
    result = subprocess.run(["nmcli", *arguments], check=True, capture_output=True, text=True,
                            timeout=timeout, env={**os.environ, "LC_ALL": "C"})
    return result.stdout.strip()


def parse_scan(output):
    """Parse `nmcli --terse --fields CHAN,SIGNAL device wifi list` into [(channel, signal)]."""
    networks = []
    for line in output.splitlines():
        parts = line.split(":")
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            channel = int(parts[0])
            if 1 <= channel <= 14:
                networks.append((channel, int(parts[1])))
    return networks


def interference(networks, channel):
    """Sum of overlap-weighted signal strengths.

    Weighted linearly, not squared: at the edge of the range the ESP32 signal is weak,
    so even weak foreign networks raise the noise floor and cost range.
    """
    total = 0.0
    for other, signal in networks:
        distance = abs(other - channel)
        if distance < SPREAD:
            total += (1 - distance / SPREAD) * signal / 100
    return total


def choose(networks, current):
    """Return (best channel, {channel: score}); on a tie the current channel is kept."""
    scores = {channel: interference(networks, channel) for channel in CANDIDATES}
    best = min(CANDIDATES, key=lambda channel: (round(scores[channel], 4), channel != current, channel))
    return best, scores


def scan(attempts=3):
    for attempt in range(attempts):
        try:
            return parse_scan(nmcli("--terse", "--fields", "CHAN,SIGNAL", "device", "wifi", "list",
                                    "ifname", INTERFACE, "--rescan", "yes", timeout=60))
        except subprocess.SubprocessError:
            # Right after disconnecting, NetworkManager may still refuse to scan.
            if attempt == attempts - 1:
                raise
            time.sleep(3)


def autoconnect_enabled():
    return nmcli("--get-values", "connection.autoconnect", "connection", "show", PROFILE) == "yes"


def current_channel():
    value = nmcli("--get-values", "802-11-wireless.channel", "connection", "show", PROFILE)
    return int(value) if value.isdigit() else 0


def select_and_start():
    """Scan, store the best channel and start the hotspot; returns the active channel."""
    current = current_channel()
    channel = current
    try:
        try:
            nmcli("device", "disconnect", INTERFACE)
        except subprocess.CalledProcessError:
            pass  # Already disconnected.
        networks = scan()
        channel, scores = choose(networks, current)
        print("Gefundene Netze: %d" % len(networks))
        for candidate in CANDIDATES:
            print("Kanal %2d: Belegung %.2f%s" % (candidate, scores[candidate],
                                                 "  <- gewählt" if candidate == channel else ""))
        if channel != current:
            nmcli("connection", "modify", PROFILE, "802-11-wireless.channel", str(channel))
    except (subprocess.SubprocessError, OSError) as exc:
        channel = current
        print("Scan fehlgeschlagen (%s); Hotspot bleibt auf Kanal %d." % (exc, current), file=sys.stderr)
    finally:
        nmcli("connection", "up", PROFILE, timeout=60)
    return channel


def main(argv):
    if sys.platform != "linux" or os.geteuid() != 0:
        print("Nur auf dem Raspberry Pi ausführen: sudo python3 deploy/hotspot_channel.py", file=sys.stderr)
        return 1
    boot = "--boot" in argv
    try:
        if boot:
            # Let NetworkManager finish its own autoconnect first, so it does not race the scan.
            subprocess.run(["nm-online", "-s", "-q", "-t", "60"], check=False)
            if not autoconnect_enabled():
                print("Direktbetrieb nicht aktiviert (autoconnect no); nichts geändert.")
                return 0
        else:
            print("Hotspot wird für den Scan kurz getrennt (ca. 10-20 s).")
        channel = select_and_start()
    except (subprocess.SubprocessError, OSError) as exc:
        print("Hotspot konnte nicht gestartet werden: %s" % exc, file=sys.stderr)
        return 1
    print("Hotspot %s aktiv auf Kanal %d." % (PROFILE, channel))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
