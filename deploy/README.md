# Raspberry Pi / Waveshare Headend

Frisches Pi-System einschließlich Display, Console Autologin und Browser-Kiosk:
[vollständige Installationsanleitung](../docs/INSTALLATION.md).
Der folgende Kurzablauf setzt ein vorbereitetes Betriebssystem voraus.

Auf dem vorhandenen Pi Zero 2 W mit Zero-DISP-7A kann das bisherige Raspberry Pi OS
weiterlaufen. Display-Konfiguration und Browser werden nicht verändert.

```sh
sudo apt install python3-venv git
git clone https://github.com/sglogger/pi-timer-wifi.git
cd pi-timer-wifi
./install.sh
./run.sh
```

Browser: `http://localhost:8000`. Den Wert `PI_TIMER_TOKEN` aus `.env` eingeben.
Der Schlüssel bleibt nur für diese Browser-Sitzung gespeichert. Nach einem
Browser-Neustart erneut eingeben. Für den Direktbetrieb stellt der Pi sein eigenes
WLAN unter der festen Adresse `10.42.0.1` bereit, siehe [Direktes WLAN](direct-wifi.md).
Die Installation und Paketdownloads vorab mit Internet durchführen; der Betrieb
vor Ort benötigt keinen Internetanschluss.

## Autostart

Den alten Timer-Dienst zuerst ermitteln (`systemctl list-unit-files | grep -i timer`)
und gezielt stoppen/deaktivieren; beide Server können nicht Port 8000 belegen.
Keine pauschalen Systemdienste, Bluetooth, Journald oder Zeitsynchronisation abschalten.

`deploy/pi-timer-wifi.service` verwendet Benutzer `pitimer` und
`/home/pitimer/pi-timer-wifi`. Vor Installation ggf. anpassen:

```sh
sudo cp deploy/pi-timer-wifi.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now pi-timer-wifi
journalctl -u pi-timer-wifi -f
```

Der bestehende Kiosk kann weiter `http://localhost:8000` öffnen. Der Server läuft
mit Waitress in **einem Prozess**; mehrere Worker-Prozesse würden getrennte Timer
erzeugen und sind nicht unterstützt. Ein Server-Neustart erzeugt eine neue Sitzung
mit gestopptem Timer. Das Gerät übernimmt diesen Zustand bei nächster Verbindung.

## Netzwerk

Standard: **Pi als 2.4-GHz-Hotspot, ESP32 direkt verbunden**. Die
[Einrichtungsanleitung](direct-wifi.md) umfasst WPA2, DHCP, feste Pi-IP, Autostart
und Rückkehr zum normalen WLAN. Ein externer Access Point ist nicht erforderlich.

Alternativ beide Geräte in ein vorhandenes gemeinsames WLAN einbinden: kein
Captive Portal, keine Client-Isolation, feste DHCP-Zuweisung für den Pi und diese
Pi-Adresse in `firmware/config.py`. Der ESP32 muss den Pi auf TCP 8000 erreichen.
Auch dieses Netz braucht kein Internet. Die 20–30 m müssen in beiden Varianten
vor Ort getestet werden; Wände, Menschen und belegte Kanäle können WLAN stören.

HTTP überträgt den gemeinsamen Zugriffsschlüssel unverschlüsselt im lokalen Netz.
Deshalb nur in einem vertrauenswürdigen Veranstaltungsnetz betreiben; Port 8000
nicht ins Internet freigeben. Der Schlüssel schützt die API vor unbeabsichtigter
Bedienung durch andere Teilnehmer im Netz, ersetzt aber keine TLS-Verschlüsselung.

Rollback: neuen Dienst stoppen, ursprünglichen Timer-Dienst und ursprüngliche
ESP32-Firmware wieder aktivieren, Luxafor-Dongle wieder einstecken.
