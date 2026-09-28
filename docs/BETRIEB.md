# Betrieb, Updates und Fehlersuche

Erstinstallation: [INSTALLATION.md](INSTALLATION.md). Vor Ort ist keine
Internetverbindung nötig, sofern Installation und Test vorher abgeschlossen wurden.

## Start vor einer Veranstaltung

1. Pi/Waveshare, ESP32 und Luxafor mit Strom versorgen. Luxafor nah beim ESP32
   platzieren; Pi so aufstellen, dass der WLAN-Weg möglichst frei ist.
2. Pi bootet in das eigene WLAN `SwiNOG-Timer`; Server und Kiosk starten automatisch,
   wenn die Autostart-Schritte der Installation abgeschlossen wurden.
3. Im Browser den API-Schlüssel aus der Pi-`.env` eingeben. Er wird nur während
   der Browser-Sitzung gespeichert. Danach Tastatur bei Bedarf entfernen.
4. „Timer synchronisiert“ und Luxafor-BLE-Verbindung abwarten. Beide anzeigen lassen;
   „Headend verbunden“ allein bestätigt nur den Kontakt Browser → Pi.
5. Kurz Start/Stop testen und die Lampe mit den Augen kontrollieren.

Zeitknopf startet einen **neuen** Timer und ersetzt einen laufenden. Stop löscht
den Timer-Sollzustand; es gibt in dieser Version keine Pause-/Fortsetzen-Funktion.
Nach Ablauf zählt die Anzeige negativ weiter. Ein 1-Minuten-Timer beginnt orange,
ein 5-Minuten-Timer gelb. Nach 30 s Überzeit blinkt die Lampe rot.

## Ausfälle richtig interpretieren

| Anzeige / Ereignis | Bedeutung und Vorgehen |
|---|---|
| Headend verbunden | Browser erreicht Server; noch keine Gerätebestätigung |
| Timer synchronisiert | ESP32 hat aktuelle Sitzung/Revision gemeldet |
| Übertragung ausstehend | Start/Stop am Pi vorhanden, ESP32 hat ihn noch nicht bestätigt |
| ESP32 offline | Mehr als 5 s keine Gerätemeldung; lokaler Countdown kann weiterlaufen |
| Luxafor/BLE offline | Licht kann alte Farbe behalten; Timer/WLAN separat prüfen |
| BLE verbunden; Befehl gesendet | Befehl an GATT geschickt, tatsächliche LED-Farbe visuell prüfen |
| Pi startet neu | Hotspot fällt kurz aus, Server startet mit Stop; ESP32 übernimmt nach Reconnect |
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
| HTTP 401 | `API_TOKEN` auf ESP32 und `PI_TIMER_TOKEN` in Pi-`.env` vergleichen |
| HTTP-Verbindung verweigert / Timeout | Pi-IP/Port, Timer-Dienst und lokale Firewall prüfen |
| Luxafor nicht gefunden | Name/MAC exakt? Dongle und andere BLE-Clients getrennt? Lampe geladen? |
| GATT-Authentifizierungsfehler | `LUXAFOR_PAIR = True` testen, Konfiguration übertragen und neu starten |
| Display dunkel/verschoben/falsche Farben | Richtiges Board ohne Touch? Stromversorgung und Display-Pins prüfen; nicht durch WLAN-Änderungen lösen |
| Browser zeigt „nicht erreichbar“ | Dienst/Port 8000 prüfen; danach Browserseite neu laden |
| Kiosk startet nicht | Lokal tty1 angemeldet? `.bash_profile`, `.xinitrc`, X11/Falkon installiert? Vorhandenen Desktop-Autostart prüfen |

## Software aktualisieren — vor der Veranstaltung mit Internet

### 1. Stop und Sicherung

Stop bestätigen. Außerhalb des Repositories eine Sicherung anlegen, als `pitimer`:

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

Bei lokalen Änderungen oder fehlgeschlagenem Pull zuerst diese Änderungen klären;
kein `git reset --hard`. Bei Testfehlern die neue Version nicht in den Einsatz
nehmen. Bei geänderter systemd-Unit diese erneut prüfen/kopieren und
`sudo systemctl daemon-reload` ausführen. `.env` bleibt bei `install.sh` erhalten.

### 3. ESP32 aktualisieren

Auf dem Rechner `git pull --ff-only` ausführen, Konfigurationsänderungen mit
`firmware/config.example.py` vergleichen und die sieben Dateien aus
[Installation, Schritt 6](INSTALLATION.md#6-luxafor-auswählen-timer-konfigurieren-und-übertragen--rechner)
erneut übertragen. Eine bereits gepflegte `config.py` nicht mit Beispielwerten
überschreiben. Basisfirmware nur ändern, wenn erforderlich; aioble bei normalen
Anwendungsupdates beibehalten, sofern die Änderungen keine neue Version verlangen.

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
