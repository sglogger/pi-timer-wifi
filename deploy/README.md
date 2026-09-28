# Raspberry Pi / Waveshare Headend

Frisches Pi-System einschließlich Display, Console Autologin und nativer Touch-App:
[vollständige Installationsanleitung](../docs/INSTALLATION.md).
Der folgende Kurzablauf setzt ein vorbereitetes Betriebssystem voraus.

Auf dem vorhandenen Pi Zero 2 W mit Zero-DISP-7A kann das bisherige Raspberry Pi OS
weiterlaufen. Die Display-Konfiguration bleibt nutzbar; den bisherigen Browser-Kiosk
durch die [native App](../docs/NATIVE_UI.md) ersetzen.

```sh
sudo apt install python3-venv python3-tk fonts-dejavu-core git gh
# Privates Repository: GitHub-Zugriff einmalig einrichten.
gh auth login
gh auth setup-git
git clone https://github.com/sglogger/pi-timer-wifi.git
cd pi-timer-wifi
./install.sh
sudo cp deploy/99-luxafor.rules /etc/udev/rules.d/  # Luxafor Orb per USB
sudo udevadm control --reload-rules && sudo udevadm trigger
./run.sh
```

Die Luxafor Orb am Headend steuert der Server selbst; Details in der
[Installationsanleitung](../docs/INSTALLATION.md#luxafor-orb-am-headend).

Native Touch-App: in einer grafischen Sitzung im zweiten Terminal
`./run-native.sh` starten. Der Schlüssel wird aus `.env` geladen. Ohne Desktop
X11/Autostart nach der [Installationsanleitung](../docs/INSTALLATION.md) einrichten.
Die optionale Weboberfläche unter `http://localhost:8000` fragt den Schlüssel pro
Browser-Sitzung ab. Der Pi stellt sein eigenes WLAN unter `10.42.0.1` bereit,
siehe [Direktes WLAN](direct-wifi.md).
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

Die native App startet separat über `deploy/native.xinitrc` bzw. den Desktop.
Der Server läuft
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
