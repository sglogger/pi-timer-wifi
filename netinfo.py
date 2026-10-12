"""Hotspot credentials, headend addresses and DHCP clients for the native info overlay."""
import os
import socket
import subprocess

PROFILE = 'pi-timer-direct'
INTERFACE = 'wlan0'
LEASES = '/var/lib/NetworkManager/dnsmasq-%s.leases' % INTERFACE


def run(*arguments):
    result = subprocess.run(arguments, check=True, capture_output=True, text=True, timeout=3,
                            env={**os.environ, 'LC_ALL': 'C'})
    return result.stdout


def wifi_credentials():
    """Return (ssid, psk); NetworkManager first, .env values as fallback."""
    try:
        lines = run('nmcli', '--show-secrets', '--get-values',
                    '802-11-wireless.ssid,802-11-wireless-security.psk',
                    'connection', 'show', PROFILE).splitlines()
        if len(lines) >= 2 and lines[0] and lines[1]:
            return lines[0], lines[1]
    except (OSError, subprocess.SubprocessError):
        pass
    ssid, psk = os.environ.get('PI_TIMER_WIFI_SSID', ''), os.environ.get('PI_TIMER_WIFI_PSK', '')
    if ssid and psk:
        return ssid, psk
    raise LookupError('WLAN-Passwort nicht lesbar. PI_TIMER_WIFI_SSID und '
                      'PI_TIMER_WIFI_PSK in .env eintragen (siehe deploy/direct-wifi.md).')


def wifi_qr_payload(ssid, psk):
    # Standard Wi-Fi QR format understood by iOS/Android camera apps.
    def escape(value):
        for char in '\\;,:"':
            value = value.replace(char, '\\' + char)
        return value
    return 'WIFI:T:WPA;S:%s;P:%s;;' % (escape(ssid), escape(psk))


def qr_matrix(payload):
    """Return a list of rows (True = dark module) including the quiet zone."""
    import qrcode
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, border=2)
    qr.add_data(payload)
    qr.make(fit=True)
    return qr.get_matrix()


def parse_addresses(output):
    """Parse `ip -4 -o address show` into [(interface, address/prefix)] without loopback."""
    addresses = []
    for line in output.splitlines():
        parts = line.split()
        if len(parts) >= 4 and parts[2] == 'inet' and parts[1] != 'lo':
            addresses.append((parts[1], parts[3]))
    return addresses


def parse_leases(text):
    """Parse dnsmasq leases into [(ip, mac, hostname)]."""
    clients = []
    for line in text.splitlines():
        parts = line.split()
        if len(parts) >= 4:
            clients.append((parts[2], parts[1], '' if parts[3] == '*' else parts[3]))
    return clients


def parse_neighbours(output):
    """Return {ip: mac} for neighbours that recently answered on the hotspot interface."""
    live = {}
    for line in output.splitlines():
        parts = line.split()
        if len(parts) >= 4 and parts[1] == 'lladdr' and parts[-1] in ('REACHABLE', 'DELAY', 'PROBE', 'STALE'):
            live[parts[0]] = parts[2]
    return live


def clients():
    """Return [(ip, mac, hostname, active)] for hotspot clients, active ones first."""
    try:
        with open(LEASES, encoding='utf-8') as handle:
            leases = parse_leases(handle.read())
    except OSError:
        leases = []
    try:
        live = parse_neighbours(run('ip', '-4', 'neigh', 'show', 'dev', INTERFACE))
    except (OSError, subprocess.SubprocessError):
        live = {}
    known = {ip for ip, _, _ in leases}
    rows = [(ip, mac, name, ip in live) for ip, mac, name in leases]
    rows += [(ip, mac, '', True) for ip, mac in live.items() if ip not in known]
    return sorted(rows, key=lambda row: (not row[3], tuple(int(p) for p in row[0].split('.'))))


def remote_urls(addresses, port):
    """Web UI addresses for other devices: mDNS name first, then the hotspot IP."""
    urls = ['http://%s.local:%s/' % (socket.gethostname(), port)]
    urls += ['http://%s:%s/' % (cidr.split('/')[0], port) for name, cidr in addresses if name == INTERFACE]
    return urls


def snapshot():
    """Collect everything the overlay shows; never raises."""
    info = {'ssid': None, 'psk': None, 'matrix': None, 'error': None, 'addresses': [], 'clients': []}
    try:
        info['ssid'], info['psk'] = wifi_credentials()
        info['matrix'] = qr_matrix(wifi_qr_payload(info['ssid'], info['psk']))
    except LookupError as exc:
        info['error'] = str(exc)
    except ImportError:
        info['error'] = 'Python-Paket qrcode fehlt: .venv/bin/pip install -r requirements.txt'
    try:
        info['addresses'] = parse_addresses(run('ip', '-4', '-o', 'address', 'show'))
    except (OSError, subprocess.SubprocessError):
        pass
    info['clients'] = clients()
    info['urls'] = remote_urls(info['addresses'], os.environ.get('PI_TIMER_PORT', '8000'))
    return info
