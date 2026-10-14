# Betrieb, Updates und Fehlersuche

Erstinstallation: [INSTALLATION.md](INSTALLATION.md). Vor Ort ist keine
Internetverbindung nötig, sofern Installation und Test vorher abgeschlossen wurden.

## Start vor einer Veranstaltung

1. Pi/Waveshare, ESP32 und Luxafor mit Strom versorgen. Luxafor nah beim ESP32
   platzieren; Pi so aufstellen, dass der WLAN-Weg möglichst frei ist. Luxafor Orb
   und/oder Busy Tag per USB-Datenkabel am Zero-DISP-7A anschließen.
2. Pi bootet in das eigene WLAN `SwiNOG-Timer`; Server und native App starten automatisch,
   wenn die Autostart-Schritte der Installation abgeschlossen wurden.
3. Die native App lädt den API-Schlüssel automatisch aus `.env`. Nur bei Nutzung
   der optionalen Weboberfläche den Schlüssel pro Browser-Sitzung eingeben.
4. „Timer synchronisiert“ und Luxafor-BLE-Verbindung abwarten. Beide anzeigen lassen;
   „Headend verbunden“ allein bestätigt nur den Kontakt Oberfläche → Pi.
5. Kurz Start/Stop testen und die Lampe mit den Augen kontrollieren.

Zeitknopf startet einen **neuen** Timer und ersetzt einen laufenden. Stop löscht
den Timer-Sollzustand; es gibt in dieser Version keine Pause-/Fortsetzen-Funktion.
Nach Ablauf zählt die Anzeige negativ weiter. Ein 1-Minuten-Timer beginnt orange,
ein 5-Minuten-Timer gelb. Nach 30 s Überzeit blinkt die Lampe rot.

## Ausfälle richtig interpretieren

| Anzeige / Ereignis | Bedeutung und Vorgehen |
|---|---|
| Headend verbunden | Oberfläche erreicht Server; noch keine Gerätebestätigung |
| ESP32 · 2/3 OK | Zwei von drei ESP32 haben Start/Stop übernommen und Luxafor verbunden; die Liste darunter nennt das dritte |
| synchronisiert / OK | ESP32 hat aktuelle Sitzung/Revision gemeldet |
| Übertragung ausstehend / wartet | Start/Stop am Pi vorhanden, dieser ESP32 hat ihn noch nicht bestätigt |
| Mesh über saal-1 | ESP32 ohne eigenes WLAN; Timer und Status laufen über den ESP32 `saal-1` |
| ESP32 rot: offline | Direkt 5 s, über Mesh 10 s keine Meldung; lokaler Countdown kann weiterlaufen |
| ESP32-Display: MESH OK | Kein eigenes WLAN, Timer kommt per ESP-NOW von einem anderen ESP32 |
| ESP32-Display: MESH OFFLINE | Gerät mit `WIFI = False` hört keinen Nachbarn: Ist ein ESP32 mit WLAN und `MESH = True` in Reichweite? Gleicher `API_TOKEN`? |
| Luxafor/BLE offline | Licht kann alte Farbe behalten; Timer/WLAN separat prüfen |
| BLE verbunden; Befehl gesendet | Befehl an GATT geschickt, tatsächliche LED-Farbe visuell prüfen |
| LED Light: Luxafor USB verbunden; Farbe gesendet | Orb am Headend angesteuert; unabhängig von ESP32 und WLAN |
| LED Light: Busy Tag verbunden; Farbe gesendet | Busy Tag am Headend angesteuert (LEDs und Display) |
| Luxafor USB nicht gefunden · Busy Tag nicht gefunden | Keine USB-Lampe eingesteckt/erkannt; Timer läuft trotzdem, alle 2 s neue Suche. Ist eine Lampe verbunden, wird die fehlende andere nicht gemeldet |
| Pi startet neu | Hotspot fällt kurz aus, Kanalwahl scannt (10–20 s), Server startet mit Stop; ESP32 übernimmt nach Reconnect |
| ESP32 startet neu | Ohne Pi noch kein gültiger Countdown; nach Sync aktueller Sollzustand |

Bei Netzwerkausfall wird ein neuer Stop **erst nach Wiederverbindung** übernommen.
Bei ausstehender Bestätigung den Redner nötigenfalls persönlich informieren.
Vortragsbetrieb nicht durch Test-Resets/Updates unterbrechen.

## Geordnet beenden

Stop auslösen, Übernahme bestätigen und Licht aus prüfen. Pi anschließend über
Terminal/SSH mit `sudo poweroff` herunterfahren und erst nach beendetem Shutdown
stromlos machen. ESP32/Luxafor danach ausschalten. Keinen ESP32-Dateitransfer oder
Flash-Vorgang durch Abziehen des Kabels unterbrechen.

## Diagnose am Pi

```sh
systemctl status pi-timer-wifi
journalctl -u pi-timer-wifi -n 80 --no-pager
nmcli --fields NAME,TYPE,DEVICE connection show --active
ip -4 address show wlan0
curl -I http://127.0.0.1:8000/
```

Erwartet: Dienst active, Hotspot auf `wlan0`, IP `10.42.0.1/24`, HTTP 200.
Gewählter Hotspot-Kanal und Belegung beim letzten Booten:
`journalctl -u pi-timer-hotspot-channel -b --no-pager`.
`GET /api/state` ohne Authorization liefert absichtlich 401. Für eine authentisierte
Abfrage als normaler Benutzer im Projektverzeichnis (Token wird nicht gedruckt):

```sh
set -a
. ./.env
set +a
.venv/bin/python - <<'PY'
import json, os
from urllib.request import Request, urlopen
request = Request('http://127.0.0.1:8000/api/state', headers={
    'Authorization': 'Bearer ' + os.environ['PI_TIMER_TOKEN']})
with urlopen(request, timeout=3) as response:
    print(json.dumps(json.load(response), indent=2))
PY
```

## Diagnose am ESP32 — USB-Rechner

```sh
.venv-board/bin/mpremote connect list
ESP_PORT=/dev/cu.usbmodem2101
.venv-board/bin/mpremote connect "$ESP_PORT" repl
```

Port anpassen. `repl` liest die laufenden Meldungen; Ctrl-C stoppt die Anwendung,
Ctrl-D startet sie neu. Mit Ctrl-] bzw. Ctrl-X das Terminal verlassen. Nach
Datei-/Diagnosebefehlen abschließend explizit neu starten:

```sh
.venv-board/bin/mpremote connect "$ESP_PORT" reset
```

| Fehler | Nächster konkreter Schritt |
|---|---|
| Kein USB-Port | Datenkabel, andere Programme schließen, BOOT/RESET-Downloadmodus prüfen |
| `Permission denied` unter Linux | Zugriffsrechte der Portdatei prüfen; ggf. Benutzer in `dialout` aufnehmen und neu anmelden |
| `No module named config` | Persönliche `config.py` ins Geräte-Wurzelverzeichnis kopieren |
| `No module named aioble` | Vom Rechner `mpremote … mip install aioble` ausführen |
| `incompatible .mpy file` | [Build-/Versionshinweise](BUILD.md#d-mpy-dateien-und-bibliotheken) beachten |
| WLAN nicht verbunden | Hotspot aktiv? Richtige SSID/WLAN-Passwort? Pi/ESP32 nahe zusammen testen |
| Nach Headend-Neustart lange kein `WIFI OK` | Bis zu etwa 2 min sind normal: Der Pi bootet, startet Hotspot und Dienst, danach braucht der ESP32 bis etwa 20 s. Die Konsolenzeile `WLAN verbunden nach … s ohne WLAN, … Versuch(e)` (ab Firmware 1.3.2) zeigt die Dauer; Pi-Seite mit `systemd-analyze` und `journalctl -u pi-timer-wifi -b` prüfen. Bis dahin zählen die ESP32 den alten Timer weiter |
| Display bleibt WIFI OFFLINE trotz ESP32 mit WLAN daneben | Mesh: auf beiden `MESH = True` (Standard ist aus)? Gleicher `API_TOKEN`? Firmware ab 1.1.0, Pi-Software ab 1.2.0? |
| Konsole: `Sync: TimeoutError` bei gutem RSSI, BLE `ENOMEM` | Speichermangel der Firmware vor 1.2.4 (Socket-Leck, 110-KB-Bildpuffer): Firmware aktualisieren. Tritt es mit 1.2.4 und `MESH = True` auf, `MESH = False` setzen |
| Konsole nach Ctrl-D: `MemoryError … 110080 bytes` | Firmware vor 1.2.4: mit Reset-Knopf statt Soft-Reset starten, Firmware aktualisieren |
| Hotspot sichtbar, Verbinden schlägt fehl | PMF im Profil abschalten: [Direktes WLAN](../deploy/direct-wifi.md#hotspot-sichtbar-aber-verbinden-schlägt-fehl) |
| Touch-App: ESP32/BLE „Unbekannt“ | Noch kein Abgleich vom ESP32 angekommen; BLE-Status kommt nur über den ESP32. Zuerst dessen WLAN prüfen |
| Dienst: „unavailable resources“ | `User`/Pfade in `/etc/systemd/system/pi-timer-wifi.service` passen nicht zum Benutzer |
| HTTP 401 | `API_TOKEN` auf ESP32 und `PI_TIMER_TOKEN` in Pi-`.env` vergleichen |
| HTTP-Verbindung verweigert / Timeout | Pi-IP/Port, Timer-Dienst und lokale Firewall prüfen |
| Luxafor nicht gefunden | Name/MAC exakt? Dongle und andere BLE-Clients getrennt? Lampe geladen? Vorgehen: [BLE-Fehlersuche](#ble-fehlersuche) |
| Dauerhaft `BLE OFFLINE` bei `WIFI = False` oder `MESH = True` ohne Hotspot | Firmware vor 1.3.2: Ohne WLAN-Verbindung blockiert ESP-NOW den BLE-Scan. Firmware aktualisieren |
| `BLE OFFLINE` direkt nach `ble_test.py` | Normal: `soft-reset run` beendet den Timer, das Display zeigt das letzte Bild. `mpremote … reset` |
| Konsole: `BLE: AttributeError … LUXAFOR_PAIR` | Firmware vor 1.3.1 und Zeile fehlt in `config.py`: `LUXAFOR_PAIR = False` eintragen oder aktualisieren |
| Konsole: `ImportError: no module named 'boards'`, Display schwarz | `firmware/boards.py` fehlt auf dem ESP32 (ab Firmware 1.3.0 nötig) |
| GATT-Authentifizierungsfehler | `LUXAFOR_PAIR = True` testen, Konfiguration übertragen und neu starten |
| Orb: „USB: Access denied“ | udev-Regel `deploy/99-luxafor.rules` installiert? Benutzer in `plugdev`? Orb neu einstecken |
| Orb: „USB: No backend available“ | `sudo apt install libusb-1.0-0`, dann Dienst neu starten |
| „Luxafor USB nicht gefunden“, obwohl eingesteckt | `lsusb` zeigt kein `04d8:f372` und `sudo dmesg -w` bleibt beim Einstecken leer: kein USB-Signal. Datenkabel statt Ladekabel, andere Buchse |
| „Busy Tag: [Errno 13] Permission denied“ | Dienstbenutzer nicht in `dialout`: `deploy/install-services.sh` erneut ausführen |
| „Busy Tag nicht gefunden“, obwohl eingesteckt | `ls /dev/ttyACM*` leer: Datenkabel, andere Buchse. Aus- und wieder einstecken |
| Display dunkel/verschoben/falsche Farben | Erste REPL-Zeile nennt das Board-Profil (`c6-147`/`c6-touch-147`/`s3-169`); Touch-Board erst ab Firmware 1.4.0, Hinweise zum [C6-Touch](../firmware/README.md#esp32-c6-touch-lcd-147) und [S3](../firmware/README.md#esp32-s3-lcd-169); nicht durch WLAN-Änderungen lösen |
| Display steht auf dem Kopf | `FLIP = True` in `config.py` (ab Firmware 1.3.1) |
| App zeigt „Server offline“ | Dienst/Port 8000 und `.env` prüfen; App verbindet automatisch neu |
| `No module named tkinter` | Systempaket `python3-tk` installieren, venv mit System-Python erstellen |
| Keine Touch-App nach Boot | Console Autologin, `~/.bash_profile`, `~/.xinitrc` und darin Projektpfad prüfen |
| Kiosk startet nicht | Lokal tty1 angemeldet? `.bash_profile`, `.xinitrc`, X11/Falkon installiert? Vorhandenen Desktop-Autostart prüfen |

## BLE-Fehlersuche

BLE-Probleme am Timer haben meist eine von drei Ursachen: Lampe nicht erreichbar,
Konfiguration falsch oder das Funkmodul ist durch WLAN/ESP-NOW belegt. WLAN, Mesh,
BLE und Display laufen im Timer gleichzeitig; deshalb die Strecke schrittweise
isolieren, statt Einstellungen zu raten. Port wie oben in `ESP_PORT`.

1. **Was meldet der Timer?** `mpremote connect "$ESP_PORT" repl`, Ctrl-D, ein bis zwei
   Minuten mitlesen, Ctrl-]. Jede `BLE: …`-Zeile nennt Fehlertyp und Meldung, z. B.
   `TimeoutError`, `DeviceDisconnectedError` (Lampe aus) oder `ENOMEM`. Dazu
   notieren: Board (erste Zeile, `c6-147`/`c6-touch-147`/`s3-169`), `WIFI`/`MESH` aus `config.py`,
   Display unten (`BLE OK`/`BLE OFFLINE`, `WIFI`/`MESH`).
2. **Sieht der ESP32 die Lampe?** `mpremote connect "$ESP_PORT" soft-reset run firmware/scan.py`
   zeigt alle Geräte mit Name, MAC und RSSI. Fehlt die Lampe: einschalten, Dongle
   abziehen, Apps trennen (eine verbundene Lampe sendet keine Advertisements).
   Name/MAC mit `config.py` vergleichen. RSSI schwächer als etwa −80 dBm: näher stellen.
3. **Funktioniert BLE allein?** `mpremote connect "$ESP_PORT" soft-reset run firmware/ble_test.py`:
   drei Runden Suche, Verbindung, GATT-Liste, Farben rot/grün/aus mit Zeitstempel und
   freiem Speicher ([Details](../firmware/README.md#ble-test-ohne-timer)). Lampe dabei
   beobachten. Danach `mpremote … reset`, sonst bleibt der Timer aus.
4. **Stört die Funklast?** In `firmware/ble_test.py` `ESPNOW_LOAD = True` setzen und
   Schritt 3 wiederholen; die lokale Datei wird übertragen, nichts kopieren. Danach
   zurücksetzen.
5. **Ergebnis einordnen:**

| Schritt 3 | Schritt 4 | Ursache | Nächster Schritt |
|---|---|---|---|
| nicht gefunden | – | Lampe, Name/MAC, andere Verbindung | Schritt 2 |
| Verbinden: `TimeoutError` | – | Abstand, Lampe belegt | näher, Dongle/Apps trennen, Lampe neu starten |
| Service/Characteristic fehlt | – | anderes Gerät oder Lampen-Firmware | GATT-Liste mit [BLE-Protokoll](ble-protocol.md) vergleichen |
| `OK`, Lampe zeigt Farben nicht | – | Protokoll passt nicht | GATT-Liste und Lampen-Firmware dokumentieren |
| `OK` | nicht gefunden / Fehler | gemeinsames Funkmodul | `ESPNOW_LOAD` und `PAUSE_FOR_SCAN = True` testen; Firmware ab 1.3.2 macht das ohne WLAN-Verbindung selbst |
| `OK` | `OK` | Zusammenspiel im Timer | Meldungen aus Schritt 1 auswerten; mit `MESH = False` vergleichen |

Bisher so gefundene Fehler (Oktober 2026, Details im CHANGELOG 1.4.1 und 1.4.2):

- **Mesh-only blockiert den Scan:** Mit WLAN und ESP-NOW an, aber ohne
  WLAN-Verbindung, sah der Scan kein Gerät; ohne Last fand er die Lampe nach
  0,3–2,3 s. Eine bestehende Verbindung lief unter Last weiter. Betrifft auch den
  Fallback mit `WIFI = True` bei unerreichbarem Hotspot. Lösung: ohne
  WLAN-Verbindung ESP-NOW nur für Suche und Verbindungsaufbau aus.
- **Bestätigung als Ready gedeutet:** Die Lampe beantwortet jeden Schreibbefehl
  mit `1\r`; die Firmware schickte darauf die Farbe erneut, etwa zehnmal pro Sekunde.
  Sichtbar im Test als `Notification b'1\r'` etwa 90 ms nach jedem `sende`.
- **Fehlender Konfigurationseintrag:** Ohne `LUXAFOR_PAIR` brach jede Verbindung
  mit `AttributeError` ab.

Allgemeine Hinweise: Im Testskript auf Zeiten achten, nicht nur auf `OK`
(deutlich längere Such-, Verbindungs- oder Antwortzeiten unter Last sind ein
Frühzeichen). Sinkt der freie Speicher über Runden stetig, liegt ein Leck vor. Neue
Erkenntnisse mit Board, MicroPython-Version, Firmware-Version und Testausgabe im
CHANGELOG festhalten und, wo sinnvoll, als Fall in `ble_test.py` oder als Test unter
`tests/` nachbauen.

## Software aktualisieren — vor der Veranstaltung mit Internet

### 1. Stop und Sicherung

Stop bestätigen. Außerhalb des Repositories eine Sicherung anlegen, als Timer-Benutzer:

```sh
cd ~/pi-timer-wifi
TIMER_BACKUP_DIR="$HOME/pi-timer-backups/$(date +%Y%m%d-%H%M%S)"
mkdir -p "$TIMER_BACKUP_DIR"
chmod 700 "$TIMER_BACKUP_DIR"
cp .env "$TIMER_BACKUP_DIR/"
git rev-parse HEAD > "$TIMER_BACKUP_DIR/project-commit.txt"
.venv/bin/python -m pip freeze > "$TIMER_BACKUP_DIR/python-packages.txt"
```

Auf dem USB-Rechner außerdem die persönliche `firmware/config.py`, vorhandene
Gerätedateien/Bondingdaten und bei Wechsel der Basisfirmware das Flash-Abbild
sichern. Passwörter/Bondingdaten nicht hochladen.

### 2. Pi aktualisieren

Wenn der Pi nur sein Direkt-WLAN nutzt, für Downloads erst kontrolliert ins
Heimnetz wechseln oder einen separaten Internet-Uplink verwenden; siehe
[WLAN-Betriebsarten](../deploy/direct-wifi.md#alternative-vorhandenes-wlan).

```sh
cd ~/pi-timer-wifi
git status --short
sudo systemctl stop pi-timer-wifi
git pull --ff-only
./install.sh
.venv/bin/python -m unittest discover -s tests -v
sudo systemctl start pi-timer-wifi
```

Anschließend auch die native App schließen und neu starten, damit sie den neuen
Code lädt. Bei geänderter `native.xinitrc` die lokale Kopie prüfen/aktualisieren.

Bei lokalen Änderungen oder fehlgeschlagenem Pull zuerst diese Änderungen klären;
kein `git reset --hard`. Bei Testfehlern die neue Version nicht in den Einsatz
nehmen. Bei geänderter systemd-Unit (1.1.0: neuer Dienst `pi-timer-hotspot-channel`; 1.2.0:
`StateDirectory` in `pi-timer-wifi.service`) diese erneut prüfen/kopieren und
`sudo systemctl daemon-reload` ausführen. `.env` bleibt bei `install.sh` erhalten.

### 3. ESP32-Firmware aktualisieren

**Wann:** Wenn die Touch-App unter **WLAN / IP** bei einem ESP32 `FW alt → X.Y.Z`
bzw. die Weboberfläche „Firmware … veraltet“ zeigt, oder wenn der [CHANGELOG](../CHANGELOG.md) eine
ESP32-Änderung nennt. Die Version im Repository steht als `FIRMWARE_VERSION` in
`firmware/timer_logic.py`; der ESP32 meldet seine bei jedem Abgleich.
Firmware vor 1.0.0 meldet keine Version und erscheint als `FW < 1.0.0 → X.Y.Z`.

Jeden ESP32 einzeln per USB-Datenkabel am Rechner anschließen, im Repository:

```sh
git pull --ff-only
diff firmware/config.example.py firmware/config.py
```

Neue Einträge aus `config.example.py` (z. B. `HOSTNAME`) bei Bedarf in die eigene
`config.py` übernehmen; fehlende optionale Einträge sind erlaubt. Die gepflegte
`config.py` nicht mit der Vorlage überschreiben. Bei mehreren ESP32 mit eigener
`config.py` (z. B. anderem `HOSTNAME`) jeweils die passende Datei verwenden.

Programmdateien übertragen und neu starten (`PORT` wie in
[Installation, Schritt 6](INSTALLATION.md#6-luxafor-auswählen-timer-konfigurieren-und-übertragen--rechner),
z. B. `/dev/cu.usbmodem2101` oder `auto`):

```sh
.venv-board/bin/mpremote connect PORT fs cp firmware/timer_logic.py firmware/http_sync.py firmware/mesh.py \
  firmware/luxafor.py firmware/boards.py firmware/st7789.py firmware/display.py firmware/main.py :
.venv-board/bin/mpremote connect PORT fs cp firmware/config.py :config.py   # nur wenn geändert
.venv-board/bin/mpremote connect PORT reset
```

Prüfen: `.venv-board/bin/mpremote connect PORT repl`, dann Ctrl-D. Die erste Zeile
lautet `Pi Timer Firmware X.Y.Z`. Danach zeigt das Headend die neue Version ohne
„veraltet“. Ctrl-] beendet die REPL.

Basisfirmware (MicroPython) und aioble bleiben bei normalen Updates unverändert,
außer der CHANGELOG verlangt eine neue Version. Bei einem Fehler nach dem Update
den vorherigen Stand auschecken (`git checkout <commit> -- firmware/`) und die
Dateien erneut übertragen.

Nach Updates Direkt-WLAN wieder aktivieren, ESP32 neu starten und einen vollständigen
Ein-Minuten-/Stop-/Kaltstarttest durchführen.

## Rückkehr zu einer vorherigen Version

Den gesicherten Commit in **ein separates Verzeichnis** klonen/auschecken und dort
Abhängigkeiten installieren; `.env` aus der Sicherung übernehmen. Die systemd-Pfade
auf dieses Verzeichnis anpassen und den Server neu starten. Dadurch bleibt der
aktuelle Checkout mit lokalen Änderungen erhalten. Passende ESP32-Quelldateien
aus demselben Commit installieren und die persönliche Konfiguration verwenden.
Bei Basisfirmwarewechsel nötigenfalls das vollständige gesicherte 4-MB-Flash-Abbild
mit esptool ab Adresse `0x0` auf dasselbe Board zurückschreiben.

Rückkehr zum ursprünglichen `sglogger/pi-timer`: neuen Dienst stoppen/deaktivieren,
ursprünglichen Dienst und ursprüngliche ESP32-Dateien wiederherstellen und den
Luxafor-Dongle anschließen. Wenn der alte Aufbau ein anderes WLAN benötigt,
das Direktprofil deaktivieren und die ursprüngliche Netzkonfiguration aktivieren.
