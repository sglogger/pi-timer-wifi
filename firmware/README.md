# ESP32-C6-LCD-1.47

Für die vollständige Erstinstallation einschließlich Sicherung und Flash-Befehlen
der [Schritt-für-Schritt-Anleitung](../docs/INSTALLATION.md) folgen.
Eigenbau der MicroPython-Laufzeit: [Build-Anleitung](../docs/BUILD.md).
Die folgenden Schritte dienen als Kurzreferenz für ein bereits vorbereitetes Board.

Ziel ist dasselbe Waveshare-Board wie im ursprünglichen Projekt (172 × 320 Pixel,
ST7789, Querformat). MicroPython bleibt erhalten; der ESP32 wird jetzt WLAN-Client
und BLE-Central statt BLE-Peripheral. Standardmäßig verbindet er sich direkt mit
dem [WLAN-Hotspot des Pi](../deploy/direct-wifi.md); Internet wird im Betrieb nicht
benötigt. Firmware und Bibliotheken vor der Veranstaltung installieren.

![ESP32-C6-LCD-1.47 und Luxafor Bluetooth Pro vor dem Touchdisplay](../images/front.jpg "Vorderseite")

Unten im Bild: ESP32-C6-LCD-1.47 mit Countdown und daneben die Luxafor Bluetooth Pro.
Das Foto stammt aus dem [ursprünglichen Projekt](https://github.com/sglogger/pi-timer);
die Browser-Oberfläche am Touchdisplay gehört zum alten Aufbau. Die Luxafor Orb
oben rechts hängt per USB am Headend und wird vom Pi angesteuert, nicht vom ESP32.

## 1. MicroPython und aioble

Passende Firmware von [MicroPython ESP32_GENERIC_C6](https://micropython.org/download/ESP32_GENERIC_C6/)
installieren. Ausgangspunkt des alten Projekts: MicroPython 1.28.0. Keine Binärdatei
wird hier erneut mitgeliefert. Vor Flashen vorhandene Dateien/Konfiguration sichern.
Ein Flash-Löschen ist bei bereits funktionierendem MicroPython nicht nötig.

Auf dem Rechner mit USB-Verbindung zum Board:

```sh
python3 -m venv .venv-board
.venv-board/bin/pip install mpremote
.venv-board/bin/mpremote connect PORT mip install aioble
```

`PORT` überall durch den seriellen Port ersetzen, z. B. `/dev/cu.usbmodem2101` unter
macOS oder `/dev/ttyACM0` unter Linux. `mpremote mip` lädt die Bibliothek über den
Rechner; WLAN auf dem ESP32 muss dafür noch nicht konfiguriert sein.

## 2. Luxafor eindeutig auswählen

Luxafor laden/einschalten, USB-Dongle abziehen und Desktop-/Telefon-Apps trennen.
Das Luxafor in den vom Hersteller beschriebenen Bluetooth-Verbindungsmodus bringen.
Dann:

```sh
.venv-board/bin/mpremote connect PORT run firmware/scan.py
```

Der Scan zeigt Name, MAC und Empfangsstärke. `config.example.py` nach `config.py`
kopieren. Für Direktbetrieb `WIFI_SSID = "SwiNOG-Timer"`, das vom Hotspot-Setup
ausgegebene WLAN-Passwort, `SERVER_IP = "10.42.0.1"` und denselben API-Schlüssel
wie `.env` eintragen. Ein vorhandenes gemeinsames WLAN bleibt möglich: dessen
SSID/Passwort und die dortige Pi-IP eintragen. Für `LUXAFOR_NAME` den **exakten** Namen aus dem Scan verwenden
(typischerweise beginnt er mit `LUX DOT`). Bei gleichen Namen `LUXAFOR_MAC`
eintragen; sie hat Vorrang. Es wird niemals automatisch das erstbeste BLE-Gerät
angesteuert. Bei wechselnder privater MAC den eindeutigen Namen benutzen.
Optional mit `HOSTNAME = "timer-saal-1"` jedem ESP32 einen eigenen Namen geben
(Buchstaben, Ziffern, `-`, max. 32 Zeichen). Das Headend zeigt ihn unter
**WLAN / IP** in der Geräteliste, das ESP32-Display oben rechts (erste 25 Zeichen).
Unten rechts zeigt das Display die Firmware-Version, z. B. `v1.0.0`.

```sh
cp firmware/config.example.py firmware/config.py
# config.py jetzt lokal bearbeiten
```

## 3. Dateien übertragen

```sh
.venv-board/bin/mpremote connect PORT fs cp firmware/config.py :config.py
.venv-board/bin/mpremote connect PORT fs cp firmware/timer_logic.py :timer_logic.py
.venv-board/bin/mpremote connect PORT fs cp firmware/http_sync.py :http_sync.py
.venv-board/bin/mpremote connect PORT fs cp firmware/mesh.py :mesh.py
.venv-board/bin/mpremote connect PORT fs cp firmware/luxafor.py :luxafor.py
.venv-board/bin/mpremote connect PORT fs cp firmware/st7789.py :st7789.py
.venv-board/bin/mpremote connect PORT fs cp firmware/display.py :display.py
.venv-board/bin/mpremote connect PORT fs cp firmware/main.py :main.py
.venv-board/bin/mpremote connect PORT reset
```

Zum Lesen der Laufzeitmeldungen `mpremote connect PORT repl` verwenden. Mit
Ctrl-C wird die laufende Firmware gestoppt; danach Ctrl-D für Neustart.
Optional kann Thonny dieselben Dateien ins Wurzelverzeichnis übertragen.

Spätere Updates und Versionsprüfung: [Betrieb, ESP32-Firmware aktualisieren](../docs/BETRIEB.md#3-esp32-firmware-aktualisieren).

## Pairing / Diagnose

Bei Authentifizierungsfehlern `LUXAFOR_PAIR = True` setzen, Konfiguration erneut
übertragen und Gerät neu starten. aioble speichert Bonds in `ble_secrets.json`.
Das Datei- und Display-Verhalten sowie die Pairing-Variante hängen von der
installierten MicroPython- und Luxafor-Firmware ab und sind vor Ort zu prüfen.

| Meldung | Prüfen |
|---|---|
| WIFI OFFLINE | SSID/Passwort, 2.4 GHz, Pi-IP, Port 8000, AP-Isolation, gleicher API-Schlüssel; kein anderer ESP32 mit WLAN in Funkreichweite |
| MESH OK | Kein eigenes WLAN, Timer kommt per ESP-NOW von einem anderen ESP32 ([Mesh](../docs/architecture.md#esp-now-mesh-zwischen-den-esp32)) |
| Luxafor nicht gefunden | Name/MAC, Lampe eingeschaltet, Dongle/andere Clients getrennt |
| Service 1234 fehlt | Tatsächlich Bluetooth Pro? Geräte-Firmware und GATT-Scan prüfen |
| GATT/Auth-Fehler | Pairing-Option, alte Bond-Verknüpfung, andere BLE-Verbindungen |
| BLE OK, Licht falsch | Sichtprüfung/BLE-Protokoll-Abnahme; BLE OK ist keine LED-Rückmeldung |

Der Countdown ist asynchron; WLAN-Timeouts und BLE-Suchen blockieren die
Display-Schleife nicht absichtlich. Der TFT-Transfer selbst ist synchron und kurz.
Numerische Pi-IP ist vorgeschrieben, da DNS in MicroPython blockierend auflöst.
