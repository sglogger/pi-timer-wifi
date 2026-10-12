#!/usr/bin/env python3
"""Prepare a NetworkManager AP profile on the Pi; never activate it implicitly."""
import os
import secrets
import shutil
import subprocess
import sys

PROFILE = "pi-timer-direct"
SSID = "SwiNOG-Timer"
INTERFACE = "wlan0"
ADDRESS = "10.42.0.1/24"


def nmcli(*arguments):
    result = subprocess.run(["nmcli", *arguments], check=True, capture_output=True,
                            text=True, env={**os.environ, "LC_ALL": "C"})
    return result.stdout.strip()


def prepare():
    profiles = nmcli("--terse", "--fields", "NAME", "connection", "show").splitlines()
    if PROFILE in profiles:
        raise ValueError("Profil pi-timer-direct existiert bereits; es wurde nichts geändert. "
                         "Aktivierung und Passwortanzeige: siehe deploy/direct-wifi.md.")
    capability = nmcli("--get-values", "WIFI-PROPERTIES.AP", "device", "show", INTERFACE)
    if capability != "yes":
        raise ValueError("wlan0 unterstützt laut NetworkManager keinen AP-Modus.")
    password = secrets.token_hex(12)
    nmcli("connection", "add", "type", "wifi", "ifname", INTERFACE,
          "con-name", PROFILE,
          "connection.autoconnect", "no",
          "connection.autoconnect-priority", "1000",
          "802-11-wireless.ssid", SSID,
          "802-11-wireless.mode", "ap",
          "802-11-wireless.band", "bg",
          "802-11-wireless.channel", "6",
          "802-11-wireless.powersave", "2",
          "802-11-wireless-security.key-mgmt", "wpa-psk",
          "802-11-wireless-security.proto", "rsn",
          "802-11-wireless-security.pairwise", "ccmp",
          "802-11-wireless-security.group", "ccmp",
          "802-11-wireless-security.psk", password,
          "ipv4.method", "shared", "ipv4.addresses", ADDRESS,
          "ipv4.never-default", "yes", "ipv6.method", "disabled")
    return password


def main():
    if sys.platform != "linux" or os.geteuid() != 0:
        print("Nur auf dem Raspberry Pi ausführen: sudo python3 deploy/setup_hotspot.py", file=sys.stderr)
        return 1
    if shutil.which("nmcli") is None:
        print("NetworkManager/nmcli fehlt. Siehe deploy/direct-wifi.md.", file=sys.stderr)
        return 1
    try:
        password = prepare()
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as exc:
        # Do not print the failed command: it can contain the generated PSK.
        print("NetworkManager konnte das Profil nicht vorbereiten. "
              "Dienststatus, wlan0 und bestehende Profile prüfen.", file=sys.stderr)
        print("nmcli Exit-Code:", exc.returncode, file=sys.stderr)
        detail = (exc.stderr or "").strip()
        if detail:
            psk = exc.cmd[exc.cmd.index("802-11-wireless-security.psk") + 1] \
                if "802-11-wireless-security.psk" in exc.cmd else None
            print("nmcli:", detail.replace(psk, "***") if psk else detail, file=sys.stderr)
        return 1
    print("Profil gespeichert; aktuelle WLAN-Verbindung bleibt aktiv.")
    print("Diese Werte in firmware/config.py übernehmen:")
    print('WIFI_SSID = "%s"' % SSID)
    print('WIFI_PASSWORD = "%s"' % password)
    print('SERVER_IP = "10.42.0.1"')
    print("API_TOKEN bleibt der separate Schlüssel aus .env.")
    print("Aktivierung am Pi: bestehende WLAN-/SSH-Verbindung wird dabei getrennt.")
    print("sudo nmcli connection modify pi-timer-direct connection.autoconnect yes")
    print("sudo nmcli connection up pi-timer-direct")
    return 0


if __name__ == "__main__":
    sys.exit(main())
