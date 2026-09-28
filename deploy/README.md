# Raspberry Pi / Waveshare Headend

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
Browser-Neustart erneut eingeben. Für die ESP32-Verbindung eine feste DHCP-Zuweisung
für den Pi einrichten und die IPv4-Adresse in `firmware/config.py` übernehmen.

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

Empfohlen: eigener 2.4-GHz-Access-Point mit guter Sicht zur Bühne und Regie,
WPA2/WPA3-Personal, kein Captive Portal und keine Client-Isolation.
Der ESP32 muss den Pi auf TCP 8000 erreichen können. Kein Internet und kein
MQTT-Broker notwendig. Die 20–30 m müssen mit WLAN vor Ort getestet werden;
Wände, Menschen und überfüllte Kanäle können auch WLAN stören.

HTTP überträgt den gemeinsamen Zugriffsschlüssel unverschlüsselt im lokalen Netz.
Deshalb nur in einem vertrauenswürdigen Veranstaltungsnetz betreiben; Port 8000
nicht ins Internet freigeben. Der Schlüssel schützt die API vor unbeabsichtigter
Bedienung durch andere Teilnehmer im Netz, ersetzt aber keine TLS-Verschlüsselung.

Rollback: neuen Dienst stoppen, ursprünglichen Timer-Dienst und ursprüngliche
ESP32-Firmware wieder aktivieren, Luxafor-Dongle wieder einstecken.
