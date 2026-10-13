# ESP32-Firmware (ESP32-C6-LCD-1.47, ESP32-C6-Touch-LCD-1.47 und ESP32-S3-LCD-1.69)

Für die vollständige Erstinstallation einschließlich Sicherung und Flash-Befehlen
der [Schritt-für-Schritt-Anleitung](../docs/INSTALLATION.md) folgen.
Eigenbau der MicroPython-Laufzeit: [Build-Anleitung](../docs/BUILD.md).
Die folgenden Schritte dienen als Kurzreferenz für ein bereits vorbereitetes Board.

Ziel ist dasselbe Waveshare-Board wie im ursprünglichen Projekt (172 × 320 Pixel,
ST7789, Querformat); dieselben Dateien laufen auch auf dem
[ESP32-C6-Touch-LCD-1.47](#esp32-c6-touch-lcd-147) und dem
[ESP32-S3-LCD-1.69](#esp32-s3-lcd-169). MicroPython bleibt erhalten; der ESP32 wird jetzt WLAN-Client
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
installieren (auch für das C6-Touch-Board), für das S3-Board [ESP32_GENERIC_S3](https://micropython.org/download/ESP32_GENERIC_S3/)
in der Variante **SPIRAM_OCT** (siehe [unten](#esp32-s3-lcd-169)). Ausgangspunkt des alten Projekts: MicroPython 1.28.0. Keine Binärdatei
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
Bei mehreren Geräten mit `HOSTNAME = "saal-1"` jedem ESP32 einen eigenen Namen geben
(Buchstaben, Ziffern, `-`, max. 32 Zeichen). Das Headend zeigt ihn in der
Statusspalte und unter **WLAN / IP**, das ESP32-Display oben rechts (erste 25 Zeichen).
Ohne `HOSTNAME` erscheint das Gerät am Headend mit seiner MAC-Adresse.

Mesh (experimentell): `MESH = True` lässt das Gerät per ESP-NOW mit anderen ESP32
den Timer austauschen. `WIFI = False` macht es zum reinen Mesh-Empfänger ohne
Hotspot-Verbindung; es braucht einen ESP32 mit WLAN und `MESH = True` in der Nähe.
Ohne WLAN-Verbindung (so auch, wenn bei `MESH = True` der Hotspot nicht erreichbar
ist) schaltet der ESP32 für die Suche nach der Luxafor ESP-NOW kurz ab (1–3 s),
sonst fände der BLE-Scan nichts.
Details: [Architektur](../docs/architecture.md#esp-now-mesh-zwischen-den-esp32).
Unten rechts zeigt das Display die Firmware-Version, z. B. `v1.0.0`.
`FLIP = True` dreht die Anzeige um 180°, etwa wenn das USB-Kabel auf der anderen
Seite herausgeführt werden muss.

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
.venv-board/bin/mpremote connect PORT fs cp firmware/boards.py :boards.py
.venv-board/bin/mpremote connect PORT fs cp firmware/st7789.py :st7789.py
.venv-board/bin/mpremote connect PORT fs cp firmware/display.py :display.py
.venv-board/bin/mpremote connect PORT fs cp firmware/main.py :main.py
.venv-board/bin/mpremote connect PORT reset
```

Zum Lesen der Laufzeitmeldungen `mpremote connect PORT repl` verwenden. Mit
Ctrl-C wird die laufende Firmware gestoppt; danach Ctrl-D für Neustart.
Optional kann Thonny dieselben Dateien ins Wurzelverzeichnis übertragen.

Spätere Updates und Versionsprüfung: [Betrieb, ESP32-Firmware aktualisieren](../docs/BETRIEB.md#3-esp32-firmware-aktualisieren).

## Board-Profile

Alle Boards verwenden dieselben Dateien und dieselbe `config.py`. Die Firmware
erkennt das Board beim Start und wählt das passende Profil aus [`boards.py`](boards.py):
Pins, Display-Controller, Display-Offset und Layout. Die REPL zeigt das gewählte
Profil in der ersten Zeile, z. B. `Pi Timer Firmware 1.4.0 s3-169`.

| Profil | Board | Auswahl |
|---|---|---|
| `c6-147` | ESP32-C6-LCD-1.47 | automatisch (C6 ohne Touch-Bausteine am I2C-Bus) |
| `c6-touch-147` | ESP32-C6-Touch-LCD-1.47 | automatisch (Touch-Controller oder Lagesensor antwortet) |
| `s3-169` | ESP32-S3-LCD-1.69, Revision V2 (Aufdruck „V2QC“) | automatisch auf dem S3 |
| `s3-169-v1` | ESP32-S3-LCD-1.69, erste Revision | `BOARD = "s3-169-v1"` in `config.py` |

## ESP32-C6-Touch-LCD-1.47

Das [Waveshare ESP32-C6-Touch-LCD-1.47](https://docs.waveshare.com/ESP32-C6-Touch-LCD-1.47)
hat dasselbe Panel (172 × 320 Pixel) wie das C6-Board ohne Touch, aber einen
**JD9853**-Display-Controller und andere Pins. Mit Firmware vor 1.4.0 bleibt sein
Display schwarz. Der JD9853 versteht die vom Timer benutzten ST7789-Befehle;
[`st7789.py`](st7789.py) schickt ihm zusätzlich die Initialisierungssequenz aus
Waveshares Democode (`esp_lcd_jd9853.c`). Bildschirmaufteilung, Offset und Farben
sind dieselben wie beim C6-Board ohne Touch. Touch, Lagesensor und TF-Slot nutzt
die Firmware nicht.

| Funktion | GPIO |
|---|---|
| Display SCK / MOSI | 1 / 2 (geteilt mit dem TF-Slot) |
| SPI-MISO | 3 (TF-Slot; nur gesetzt, damit MicroPython nicht GPIO2 als MISO belegt) |
| Display CS / DC / RST | 14 / 15 / 22 |
| Hintergrundbeleuchtung | 23 (High = an) |
| TF-Slot CS | 4, von der Firmware auf High gehalten |
| I2C SCL / SDA (Touch AXS5106L 0x63, Lagesensor QMI8658 0x6B) | 19 / 18, nur zur Erkennung |

Zur Erkennung fragt die Firmware auf jedem C6 einmal den I2C-Bus an GPIO18/19 ab.
Beim Board ohne Touch sind diese Pins frei und antworten nicht. Ist dort eigene
Hardware mit Adresse 0x63 oder 0x6B angeschlossen, `BOARD = "c6-147"` setzen;
umgekehrt erzwingt `BOARD = "c6-touch-147"` das Touch-Profil.

| Beobachtung | Prüfen |
|---|---|
| Display schwarz, REPL zeigt `… c6-147` | Erkennung fehlgeschlagen: `BOARD = "c6-touch-147"` in `config.py` |
| Display schwarz trotz Beleuchtung, REPL zeigt `… c6-touch-147` | `boards.py` und `display.py` ab Firmware 1.4.0 übertragen? Ohne `miso` im Profil belegt MicroPython GPIO2 (MOSI) als MISO-Eingang, und das Display bekommt keine Daten |
| Display schwarz, auch ohne Beleuchtung | Hintergrundbeleuchtung allein testen: `mpremote connect PORT exec "from machine import Pin; Pin(23, Pin.OUT).value(1)"` |
| Bild steht auf dem Kopf | `FLIP = True` in `config.py` |
| Rot und Blau vertauscht | `madctl` im Profil `c6-touch-147` von `0x68` auf `0x60` |
| Bild um 34 px verschoben | `offset` (eingetragen: `(0, 34)`) |

## ESP32-S3-LCD-1.69

Das [Waveshare ESP32-S3-LCD-1.69](https://www.waveshare.com/wiki/ESP32-S3-LCD-1.69)
(ST7789V2, 240 × 280 Pixel, abgerundete Ecken, 8 MB PSRAM) verwendet dieselben
Dateien und dieselbe `config.py` wie das C6-Board; die Firmware wählt das Profil
`s3-169` am Chip ([Board-Profile](#board-profile)).

Die Revisionen unterscheiden sich im Haltepin SYS_EN (V2: GPIO41, erste Revision:
GPIO35) und im Buzzer (GPIO42 bzw. GPIO33). GPIO33–37 führen beim ESP32-S3R8 die
Leitungen des Octal-PSRAM ([Datenblatt](https://documentation.espressif.com/esp32-s3_datasheet_en.pdf),
Abschnitt 2.3.4); `s3-169-v1` daher nur auf einem Board verwenden, dessen PSRAM
diese Pins frei lässt. Die Firmware setzt SYS_EN sofort beim
Start auf High; sonst schaltet sich das Board im Akkubetrieb nach dem Loslassen
der PWR-Taste wieder ab. Den passiven Buzzer zieht sie auf Low.

Im Querformat (280 × 240) sitzen Titel, Countdown und Statuszeile mit 20 px
Rand wegen der runden Ecken. Statuszeile und Version stehen zentriert auf zwei
Zeilen, der Hostname ist auf 17 Zeichen gekürzt.

Auf der Hardware geprüft mit Firmware 1.3.1, dem automatisch gewählten Profil
`s3-169` und MicroPython 1.29 (Standard-Image ohne PSRAM). Sollte ein Board davon
abweichen:

| Beobachtung | Anpassung in `boards.py`, Profil `s3-169` |
|---|---|
| Display bleibt dunkel | REPL öffnen (`mpremote connect PORT repl`, Ctrl-D): Erste Zeile muss `… s3-169` lauten; eine Fehlermeldung davor zeigt den Grund. Die Pins (SCK 6, MOSI 7, CS 5, DC 4, RST 8, Backlight 15) entsprechen dem Waveshare-Schaltplan |
| Display ganz schwarz, auch ohne Leuchten | Hintergrundbeleuchtung allein testen: `mpremote connect PORT exec "from machine import Pin; Pin(15, Pin.OUT).value(1)"` |
| Bild um 20 px verschoben oder Streifen am Rand | `offset` (eingetragen: `(20, 0)`) |
| Bild steht auf dem Kopf | `madctl` von `0x68` auf `0xA8` (gilt dann für alle S3-Boards; für ein einzelnes Gerät stattdessen `FLIP = True` in `config.py`) |
| Rot und Blau vertauscht | `madctl` ohne BGR-Bit: `0x60` statt `0x68` |

Das C6 (beide Boards: gleicher Chip) hatte mit aktivem Mesh zu wenig Speicher für WLAN und BLE gleichzeitig
(siehe `MESH` in `config.example.py`). Das S3 hat schon ohne PSRAM mehr RAM; ob das
SPIRAM_OCT-Image zusätzlich hilft, ist nicht gemessen.

## Pairing / Diagnose

Schrittweises Vorgehen bei BLE-Problemen: [Betrieb, BLE-Fehlersuche](../docs/BETRIEB.md#ble-fehlersuche).

Bei Authentifizierungsfehlern `LUXAFOR_PAIR = True` setzen, Konfiguration erneut
übertragen und Gerät neu starten. aioble speichert Bonds in `ble_secrets.json`.
Das Datei- und Display-Verhalten sowie die Pairing-Variante hängen von der
installierten MicroPython- und Luxafor-Firmware ab und sind vor Ort zu prüfen.

### BLE-Test ohne Timer

[`ble_test.py`](ble_test.py) prüft nur die Strecke zur Luxafor, ohne WLAN, Mesh und
Display. Es nutzt `LUXAFOR_NAME`, `LUXAFOR_MAC` und `LUXAFOR_PAIR` aus der
`config.py` auf dem Board und muss nicht kopiert werden:

```sh
.venv-board/bin/mpremote connect PORT soft-reset run firmware/ble_test.py
```

`soft-reset` beendet vorher eine noch offene BLE-Verbindung des Timers; eine
verbundene Lampe sendet keine Advertisements und wäre im Scan unsichtbar. Das
Skript macht drei Runden aus Scan, Verbinden, Abonnieren und den Farben rot, grün,
aus, rot, aus und gibt jeden Schritt mit Zeit und freiem Speicher aus. In der ersten
Runde listet es alle GATT-Services und Characteristics. Am Ende steht eine Zeile wie
`Ergebnis: ['OK', 'OK', 'OK']`; danach `mpremote connect PORT reset` für den Timer.

Für den Vergleich mit Mesh-Last (wie bei `WIFI = False`) in `ble_test.py`
`ESPNOW_LOAD = True` setzen und erneut ausführen. Scheitert nur dieser Lauf, liegt
es an der gemeinsamen Funknutzung, nicht an Lampe oder Konfiguration. Ohne
WLAN-Verbindung findet der Scan unter dieser Last nichts; zusätzlich
`PAUSE_FOR_SCAN = True` stellt nach, wie der Timer das seit Firmware 1.3.2 löst
(ESP-NOW nur während Suche und Verbindungsaufbau aus).

| Meldung | Prüfen |
|---|---|
| WIFI OFFLINE | SSID/Passwort, 2.4 GHz, Pi-IP, Port 8000, AP-Isolation, gleicher API-Schlüssel; kein anderer ESP32 mit WLAN in Funkreichweite |
| MESH OK | Kein eigenes WLAN, Timer kommt per ESP-NOW von einem anderen ESP32 ([Mesh](../docs/architecture.md#esp-now-mesh-zwischen-den-esp32)) |
| Luxafor nicht gefunden | Name/MAC, Lampe eingeschaltet, Dongle/andere Clients getrennt; Vorgehen: [BLE-Fehlersuche](../docs/BETRIEB.md#ble-fehlersuche) |
| BLE OFFLINE bei `WIFI = False` oder unerreichbarem Hotspot mit Mesh | Firmware ab 1.3.2 nötig: ESP-NOW blockiert ohne WLAN-Verbindung den BLE-Scan |
| Service 1234 fehlt | Tatsächlich Bluetooth Pro? Geräte-Firmware und GATT-Scan prüfen |
| GATT/Auth-Fehler | Pairing-Option, alte Bond-Verknüpfung, andere BLE-Verbindungen |
| BLE OK, Licht falsch | Sichtprüfung/BLE-Protokoll-Abnahme; BLE OK ist keine LED-Rückmeldung |

Der Countdown ist asynchron; WLAN-Timeouts und BLE-Suchen blockieren die
Display-Schleife nicht absichtlich. Der TFT-Transfer selbst ist synchron und kurz.
Numerische Pi-IP ist vorgeschrieben, da DNS in MicroPython blockierend auflöst.
