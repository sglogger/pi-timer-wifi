# Direktes WLAN ohne Router und ohne Internet

Der Raspberry Pi Zero 2 W im Waveshare-Headend stellt ein eigenes 2.4-GHz-WLAN
bereit. Der ESP32-C6 verbindet sich damit und erreicht den Timer auf `10.42.0.1:8000`.
Vor Ort werden kein Router, kein gemeinsames Veranstaltungs-WLAN und kein Internet
benötigt. Die native Touch-App auf dem Pi verwendet `http://127.0.0.1:8000`.

```text
Waveshare / Pi Zero 2 W       ESP32-C6             Luxafor Bluetooth Pro
Hotspot: SwiNOG-Timer  <----> WLAN-Client   -----> BLE-Lampe
Pi-IP: 10.42.0.1              IP via DHCP         direkt neben ESP32
```

Dies verwendet den Access-Point-Modus des Pi und den normalen WLAN-Client-Modus
des ESP32. Es ist kein klassischer IBSS-Ad-hoc- oder Wi-Fi-Direct/P2P-Modus.
Die bestehende ESP32-Firmware unterstützt diese Verbindung ohne Protokolländerung.

## 1. Vor der Veranstaltung vorbereiten

Die Installation von Paketen, MicroPython und aioble braucht zunächst einen
Internetanschluss auf dem jeweiligen Installationsrechner. **Alles vorher zu Hause
installieren und beide Geräte danach vollständig ohne Internet testen.**

Voraussetzungen auf dem Pi: Raspberry Pi OS Bookworm oder neuer, NetworkManager,
eingebautes WLAN als `wlan0`. Bestehende hostapd-/dnsmasq-Sonderkonfigurationen nicht
parallel betreiben. Das folgende Setup ist für das reguläre NetworkManager-Setup.

```sh
sudo apt install network-manager dnsmasq-base python3-venv git
nmcli device status
nmcli --get-values WIFI-PROPERTIES.AP device show wlan0
```

Die letzte Ausgabe muss `yes` sein. Das WLAN-Land über `sudo raspi-config` auf das
tatsächliche Einsatzland einstellen (z. B. CH in der Schweiz). Das Funknetz muss
aktiviert sein. Falls nötig: `sudo nmcli radio wifi on`.

Zuerst [Server und Autostart installieren](README.md), anschließend im Repository:

```sh
sudo python3 deploy/setup_hotspot.py
```

Das Hilfsprogramm legt ausschließlich das neue Profil `pi-timer-direct` an:

- WLAN-Name `SwiNOG-Timer`, WPA2-Personal/AES, zufälliges Passwort mit 24 Zeichen.
- 2.4 GHz, Kanal 6, WLAN-Energiesparen am Pi deaktiviert.
- Pi-Adresse `10.42.0.1/24`; NetworkManager vergibt per DHCP eigene dynamische
  Adressen an ESP32, Handys und weitere WLAN-Clients, auch ohne Internet.
- Kein Standard-Gateway für den Pi auf dieser Verbindung, IPv6 deaktiviert.
- Zunächst kein Autostart und keine Aktivierung, damit die Vorbereitung über SSH
  die bestehende Verbindung nicht unerwartet trennt.

Existiert das Profil bereits, wird es nicht überschrieben. Das Passwort lässt
sich direkt am Pi wieder anzeigen:

```sh
sudo nmcli --show-secrets --get-values 802-11-wireless-security.psk connection show pi-timer-direct
```

Die ausgegebenen Werte in `firmware/config.py` übernehmen und auf den ESP32 kopieren.
`API_TOKEN` bleibt der separate Schlüssel aus `.env`. WLAN-Passwort und API-Schlüssel
haben unterschiedliche Aufgaben; beide müssen auf den Geräten übereinstimmen.

Das Subnetz `10.42.0.0/24` darf nicht mit einer anderen Pi-Verbindung/VPN kollidieren.
Für den Direktbetrieb ist keine weitere Netzkonfiguration nötig. Die ESP32
verwenden bereits DHCP; auf Handys/Laptops IP-Konfiguration „automatisch“ lassen.
Mehrere ESP32 können denselben Timer abrufen, allerdings zeigt der Server derzeit
nur den zuletzt gemeldeten Gerätestatus. Einrichtung und Grenzen:
[Mehrere Rednergeräte](../README.md#mehrere-rednergeräte-an-einem-pi).
`ipv4.method=shared` stellt hier DHCP bereit, auch ohne Internet-Uplink. Bei später
hinzugefügtem Internet-Uplink kann NetworkManager ihn zusätzlich an Clients teilen;
der Timer benötigt diese Funktion nicht.

## 2. Direktbetrieb aktivieren und beim Booten starten

**Am Pi ausführen, nachdem alle Pakete und ESP32-Dateien installiert sind.** Die
Aktivierung ersetzt eine bestehende WLAN-Client-Verbindung auf `wlan0`; eine darüber
laufende SSH-Sitzung bricht ab. Der Touchscreen am Pi bleibt nutzbar.

```sh
sudo nmcli connection modify pi-timer-direct connection.autoconnect yes
sudo nmcli connection up pi-timer-direct
```

Autoconnect-Priorität 999 bevorzugt dieses Profil beim nächsten Booten gegenüber
normalen gespeicherten WLANs mit Standardpriorität 0. Andere Profile bleiben
erhalten. Es wird kein gleichzeitiger AP-/Client-Betrieb auf `wlan0` eingerichtet.

Kontrollieren:

```sh
nmcli --fields NAME,TYPE,DEVICE connection show --active
ip -4 address show wlan0
systemctl status pi-timer-wifi
```

Erwartet: Profil `pi-timer-direct` aktiv, Adresse `10.42.0.1/24`, Timer-Dienst aktiv.
ESP32 einschalten: Display zeigt `WIFI OK`; die Touch-Oberfläche bestätigt die
Synchronisation. Luxafor-Dongle/andere BLE-Clients trennen und BLE separat prüfen.

## 3. Kaltstart ohne Internet prüfen

Beide Geräte ausschalten, vorhandene Ethernet-/USB-Netzwerkverbindungen entfernen,
dann Pi und ESP32 neu starten. In beiden Einschaltreihenfolgen testen. Hotspot,
DHCP, Server und ESP32 müssen ohne Eingriff zusammenfinden. Nach Neustart des
optionalen Kiosk-Browsers ist der API-Schlüssel erneut einzugeben. Die native
App liest den Schlüssel automatisch aus `.env`.

Ein Minuten-Timer muss vollständig bis rot/blinkend laufen und Stop bestätigen.
Danach mit 20–30 m Abstand und Personen im Raum testen. Der integrierte Pi-Hotspot
garantiert diese Reichweite nicht; Antennenposition und Kanalbelegung sind relevant.

Bei Störungen kann der Kanal am Pi auf 1 oder 11 geändert werden, z. B.:

```sh
sudo nmcli connection modify pi-timer-direct 802-11-wireless.channel 1
sudo nmcli connection up pi-timer-direct
```

Dies unterbricht kurz die Verbindung. Ein laufender ESP32-Timer zählt lokal weiter.

## Alternative: vorhandenes WLAN

Für Updates oder einen Einsatz mit gemeinsamem WLAN direkt am Pi:

```sh
sudo nmcli connection modify pi-timer-direct connection.autoconnect no
sudo nmcli connection down pi-timer-direct
sudo nmcli --ask device wifi connect 'NAME-DES-WLANS' ifname wlan0
```

Für Timerbetrieb im gemeinsamen WLAN müssen auch ESP32-SSID/Passwort und `SERVER_IP`
angepasst werden. Die Pi-IP in diesem WLAN per DHCP-Reservierung stabil halten.
Der ESP32 braucht lediglich WLAN-Zugang zum Pi; auch dieses Netz braucht kein Internet.

**Sicherheit:** Die API läuft über unverschlüsseltes HTTP. Im eigenen Hotspot schützt
WPA2 den Zugriffsschlüssel; in einem gemeinsamen WLAN kann jeder Teilnehmer desselben
Netzes den Schlüssel mitlesen und den Timer steuern. Gemeinsames WLAN deshalb nur in
vertrauenswürdigen Netzen verwenden und den Schlüssel danach in `.env` und
`firmware/config.py` erneuern.
Für Rückkehr zum Direktbetrieb die ESP32-Hotspot-Werte wiederherstellen und Schritt 2
ausführen. Es findet kein automatischer Wechsel zwischen den Betriebsarten statt.

## Quellen und Testgrenze

- [Raspberry Pi: eingebautes WLAN als Hotspot](https://www.raspberrypi.com/documentation/computers/configuration.html#host-a-wireless-network-from-your-raspberry-pi)
- [NetworkManager: IPv4 shared / DHCP](https://www.networkmanager.dev/docs/api/latest/settings-ipv4.html)
- [NetworkManager: WLAN-AP, Band, Kanal und Energiesparen](https://www.networkmanager.dev/docs/api/latest/settings-802-11-wireless.html)

Konfiguration und Fehlerfälle sind mit simuliertem NetworkManager getestet.
**Pi-/ESP32-Hotspot, Kaltstart und Reichweite sind noch nicht an der Hardware verifiziert.**
