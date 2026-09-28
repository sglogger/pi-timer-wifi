# Native Touch-Oberfläche für den Pi Zero 2 W

Standard ist eine **Python-/Tkinter-App auf X11**, mit sieben Zeitknöpfen, großer
Zeitanzeige, STOP und getrennten Anzeigen für Server, ESP32 und Luxafor. Im normalen
Betrieb laufen Xorg, die Tk-App und der Timer-Server. Ein kompletter Desktop,
Windowmanager und Browser sind dafür nicht erforderlich.

Der Pi stellt gleichzeitig sein eigenes WLAN bereit. Die App spricht den lokalen
Server über Loopback an; sie benötigt weder Internet noch eine Verbindung zum
Veranstaltungsnetz. Der Server synchronisiert den ESP32 über das direkte WLAN.

## Warum diese Umsetzung

Tk verwendet native GUI-Bibliotheken und lädt keine HTML-/JavaScript-Engine.
Die Anzeige wird viermal pro Sekunde geprüft; nur geänderte Widget-Eigenschaften
werden neu gesetzt. Ein einzelner Hintergrundthread fragt den lokalen Server
alle 500 ms ab. HTTP wartet höchstens zwei Sekunden auf Netzwerkoperationen,
während die Touch-Oberfläche weiter reagiert. Nach einem verlorenen Start-Ergebnis
wird der aktuelle Zustand gelesen; START wird nicht automatisch wiederholt.

Das reduziert die benötigten Komponenten. **CPU-/RAM-Verbrauch und Startzeit auf
dem Pi Zero 2 W wurden noch nicht gemessen.** Die Architektur ist auf dieses Gerät
ausgerichtet; die tatsächliche Bediengeschwindigkeit gehört zur Hardware-Abnahme.

## Installation und Start

Vollständige Erstinstallation und Autostart:
[INSTALLATION.md, Schritt 3](INSTALLATION.md#3-native-touch-app-und-autologin--pi).

Auf Raspberry Pi OS mit Python 3.11 oder neuer:

```sh
sudo apt install python3-venv python3-tk fonts-dejavu-core xserver-xorg xinit x11-xserver-utils
./install.sh
.venv/bin/python -c 'import tkinter; print(tkinter.TkVersion)'
```

Server als systemd-Dienst starten. In einer vorhandenen grafischen Sitzung:

```sh
./run-native.sh
# Optional für Entwicklung auf einem Desktop:
./run-native.sh --windowed
```

`run-native.sh` lädt `PI_TIMER_TOKEN` und `PI_TIMER_PORT` aus `.env`. Kein Schlüssel
muss auf dem Touchscreen eingegeben werden. F11 schaltet Vollbild um, Esc verlässt
Vollbild. Zielauflösung ist 1024 × 600. Touch arbeitet wie ein Mauszeiger; die App
benötigt keine Bildschirmtastatur und verwendet keine kleinen Menüeinträge.

Für Lite ohne Desktop `deploy/native.xinitrc` als `~/.xinitrc` installieren und
Console Autologin/`startx` wie in der Hauptanleitung einrichten. Diese Startdatei
startet die App nach einem Absturz erneut. Einen abweichenden Projektpfad anpassen.

### Vorhandenes Raspberry Pi OS mit Desktop

Das System muss nicht neu installiert werden. `python3-tk` und die Anwendung
installieren, vorhandenen Browser-Kiosk deaktivieren und zunächst im Terminal
der grafischen Sitzung `./run-native.sh` testen. Unter Wayland muss XWayland für
Tk verfügbar sein. Nicht parallel die Lite-Variante mit `startx` einrichten.

Wenn der Desktop XDG-Autostart unterstützt, beispielsweise diese Datei als
`~/.config/autostart/pi-timer.desktop` anlegen (Verzeichnis vorher erstellen):

```ini
[Desktop Entry]
Type=Application
Name=Pi Timer
Exec=/home/pitimer/pi-timer-wifi/run-native.sh
Path=/home/pitimer/pi-timer-wifi
Terminal=false
```

Benutzername/Verzeichnis anpassen und Desktop-Autologin aktivieren. Bei einer
Desktop-Umgebung mit eigenem Autostartformat deren Programmeinstellungen benutzen.
Für geringstmöglichen Grundbedarf bleibt Lite + X11 die Standardinstallation.

## Neustarts und Ausfälle

- App schließen/neu starten: laufender Timer bleibt im Server erhalten.
- Timer-Server neu starten: neue Sitzung, gestoppter Timer; ESP32 übernimmt nach Sync.
- Lokaler Server vorübergehend nicht erreichbar: App zeigt Zustand als unbestätigt
  und zählt aus dem letzten Stand weiter. Nach Rückkehr übernimmt sie den Sollzustand.
- ESP32 offline: Start/Stop wird am Server gespeichert, aber erst nach erfolgreichem
  Sync am Gerät wirksam. Eine grüne Serveranzeige ist keine Gerätebestätigung.
- Luxafor-BLE verbunden: GATT-Verbindung gemeldet, keine optische Bestätigung der LED.

Während eine Bedienanfrage läuft, sind Start/Stop kurz gesperrt. Es gibt keine
unbegrenzte Befehlswarteschlange; weitere Berührungen währenddessen werden nicht
gesammelt. Ein länger als drei Sekunden wartender Befehl wird verworfen.

## Optionale Weboberfläche

Die vorhandene Weboberfläche bleibt für Wartung/Fernbedienung verfügbar:
`http://10.42.0.1:8000` im direkten WLAN, lokal `http://localhost:8000`.
Den API-Schlüssel aus `.env` pro Browser-Sitzung eingeben.

Wer ausdrücklich einen Browser-Kiosk verwenden möchte, kann `openbox`, `falkon`
und `dbus-x11` installieren und `deploy/kiosk.xinitrc` statt `native.xinitrc` nach
`~/.xinitrc` kopieren. Falkon verwendet QtWebEngine; er gehört deshalb nicht zur
Standardinstallation für den Pi Zero 2 W. Nur eine der beiden Oberflächen lokal
automatisch starten.

## Auf dem Pi messen

Nach Kaltstart sowie nach einer Stunde Betrieb erfassen:

```sh
free -m
ps -eo pid,comm,rss,pcpu,args --sort=-rss | head -20
vcgencmd get_throttled
```

RSS wird in KiB ausgegeben, `%CPU` ist hier ein über die Prozesslaufzeit gemittelter
Wert. Mit `top` zusätzlich die laufende Last beim Bedienen beobachten. CPU/RAM von
`native_ui.py`, `server.py` und Xorg sowie Swap-Nutzung und Zeit bis zur bedienbaren
Oberfläche im [Abnahmeprotokoll](acceptance.md) notieren. Auch 120-Minuten- und
negative Zeitanzeige auf dem echten 1024×600-Display auf Abschneiden prüfen.
