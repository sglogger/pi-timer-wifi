# Kompilieren und Versionen

## Drei unterschiedliche Bausteine

| Baustein | Normaler Installationsweg | Muss kompiliert werden? |
|---|---|---|
| Pi-Server (`server.py`, HTML/CSS/JS) | `./install.sh`, danach `./run.sh` oder systemd | Kein eigener Build erforderlich |
| ESP32-Timer (`firmware/*.py`, aioble) | Als Python-Dateien auf MicroPython kopieren | MicroPython verarbeitet den Quelltext beim Import/Start |
| MicroPython-Laufzeit für ESP32-C6 | Offizielle kombinierte `.bin` flashen | Nur bei Eigenbau der Laufzeit |

Das Projekt enthält keine einzelne vorkompilierte Komplett-Firmware mit WLAN-
Passwort/API-Schlüssel. Die persönlichen Daten liegen in `config.py`, aioble
wird separat installiert. Im Normalfall [INSTALLATION.md](INSTALLATION.md) folgen.

## A. Server und Timer-Code prüfen — Mac/Linux-Rechner

Im Projektverzeichnis; Python 3.11 oder neuer:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m compileall -q server.py orb.py ui_config.py native_client.py native_ui.py firmware tools deploy
.venv/bin/python -m pip install mpy-cross==1.29.0.post2
.venv/bin/python tools/check_firmware.py
```

Erwartet: Tests `OK`, danach pro Firmwaredatei `MicroPython syntax OK`. Lokale
TCP-Sockets müssen für die HTTP-Tests erlaubt sein. `compileall` prüft CPython-
Syntax; `check_firmware.py` lässt die Dateien zusätzlich durch den MicroPython-
Compiler laufen und löscht dessen temporäre `.mpy`-Ergebnisse wieder.

### MicroPython-Laufzeittest

`mpy-cross` prüft nur die Syntax. Methoden, die MicroPython nicht kennt (etwa
`str.isalnum()`), fallen erst beim Ausführen auf. Deshalb laufen Timerlogik,
HTTP-Austausch, Konfigurationsprüfung von `main.py` und Display-Rendering zusätzlich
auf dem Unix-Port derselben MicroPython-Version wie auf dem ESP32. Hardwaremodule
(`machine`, `network`, `bluetooth`, `aioble`) sind dabei durch kleine Ersatzmodule
in `tests/micropython/stubs/` ersetzt. Einmalig bauen (Linux/macOS, C-Compiler und
`make` nötig, dauert wenige Minuten):

```sh
git clone --depth 1 --branch v1.28.0 https://github.com/micropython/micropython.git ~/micropython-unix
make -C ~/micropython-unix/mpy-cross -j4
make -C ~/micropython-unix/ports/unix submodules
make -C ~/micropython-unix/ports/unix -j4 MICROPY_PY_FFI=0
```

Im Projektverzeichnis ausführen:

```sh
~/micropython-unix/ports/unix/build-standard/micropython tests/micropython/run.py
```

Erwartet: jede Zeile `ok`, zuletzt `0 failure(s)`. Der Test verwendet lokal TCP-Port
18765. Die CI führt ihn als eigenen Job aus und speichert das gebaute Binary im Cache.

**Diese Prüfungen erzeugen kein flashbares `.bin` und führen keine Hardware aus.**
Die `.pyc`-Dateien von CPython gehören nicht auf den ESP32. Der Syntax-Compiler
1.29.0.post2 ist das Werkzeug der CI und keine Festlegung der ESP32-Laufzeitversion.

Die native Pi-App wird ebenfalls direkt als Python-Quelltext ausgeführt.
Auf dem Pi zusätzlich `sudo apt install python3-tk fonts-dejavu-core` installieren;
keine Browser-Engine und kein separater App-Compiler nötig. Linux-GUI-Prüfung auf
einem Entwicklungsrechner (nicht in einer bereits laufenden Touch-Sitzung nötig):

```sh
sudo apt install python3-tk fonts-dejavu-core xvfb
xvfb-run -a -s '-screen 0 1024x600x24' /usr/bin/python3 tests/ui_smoke.py
```

Diese Prüfung läuft auch als eigener GitHub-CI-Job und kontrolliert Layout,
Touch-Zielgrößen und Tastenfunktionen. Sie ersetzt keinen Test auf dem Pi-Display.

## B. Fertige ESP32-C6-Basisfirmware verwenden — empfohlen

Die [offizielle ESP32_GENERIC_C6-Downloadseite](https://micropython.org/download/ESP32_GENERIC_C6/)
stellt kombinierte Images bereit. Der dokumentierte Ausgangspunkt dieses Projekts
ist v1.28.0 aus dem bisherigen Timer; zum Recherchezeitpunkt ist auch v1.29.0
verfügbar. Eine neuere Version erst nach erneutem Hardwaretest übernehmen.

Die richtige Datei ist die kombinierte **`.bin` für ESP32_GENERIC_C6**. Diese wird
ab Adresse `0x0` geschrieben. Die Einzeldatei `.app-bin` ist dafür nicht austauschbar.
Konkrete Flash-/Sicherungsbefehle stehen in [Installation, Schritt 5](INSTALLATION.md#5-esp32-basisfirmware-und-werkzeuge--rechner).

## C. MicroPython-Basisfirmware selbst kompilieren — optional

Dieser Weg ist nur nötig, wenn du die Laufzeit selbst bauen oder später anpassen
möchtest. Er kompiliert **MicroPython**, nicht ein Arduino-/ESP-IDF-Timerprojekt.
Unser Timer-Code und aioble werden anschließend genauso wie beim fertigen Image
über USB installiert.

### Festgelegte Kombination

| Komponente | Version / Ziel |
|---|---|
| MicroPython | Git-Tag `v1.28.0` |
| ESP-IDF | Git-Tag `v5.5.1` |
| Board | `ESP32_GENERIC_C6` |
| Chip | `esp32c6` |
| Ergebnis | `ports/esp32/build-ESP32_GENERIC_C6/firmware.bin` |

ESP-IDF v5.5.1 ist die im [MicroPython-v1.28.0-Buildleitfaden](https://github.com/micropython/micropython/blob/v1.28.0/ports/esp32/README.md)
empfohlene Version. Nicht ohne Prüfung `latest` oder beliebige ESP-IDF-Versionen
mischen. Die [Boarddefinition](https://github.com/micropython/micropython/blob/v1.28.0/ports/esp32/boards/ESP32_GENERIC_C6/mpconfigboard.cmake)
setzt das C6-Ziel und die BLE-Konfiguration.

### 1. Build-Rechner vorbereiten

Die folgenden vollständigen Shell-Schritte sind für **Ubuntu 24.04 LTS** auf
einem Rechner/VM/WSL mit mehreren GB freiem Speicher gedacht. Den Build nicht
auf dem Pi Zero 2 W durchführen; dort fehlen dafür komfortable CPU-/RAM-Reserven.
Unter macOS zuerst die Abhängigkeiten nach dem
[Espressif-Leitfaden für Linux/macOS](https://docs.espressif.com/projects/esp-idf/en/v5.5.1/esp32c6/get-started/linux-macos-setup.html)
installieren; die nachfolgenden Git-/Make-Schritte sind entsprechend anwendbar.

```sh
sudo apt update
sudo apt install -y git wget flex bison gperf python3 python3-pip python3-venv \
  cmake ninja-build ccache libffi-dev libssl-dev dfu-util libusb-1.0-0 build-essential
```

Ein frisches Build-Verzeichnis wählen. Vorhandene Checkouts mit eigenen Änderungen
nicht durch diese Befehle ersetzen:

```sh
TIMER_BUILD_DIR="$HOME/pi-timer-build-v1.28.0"
mkdir -p "$TIMER_BUILD_DIR"
cd "$TIMER_BUILD_DIR"
git clone --branch v5.5.1 --depth 1 --recursive https://github.com/espressif/esp-idf.git
git clone --branch v1.28.0 --depth 1 https://github.com/micropython/micropython.git
```

### 2. ESP-IDF-Toolchain und Cross-Compiler

```sh
cd "$TIMER_BUILD_DIR/esp-idf"
./install.sh esp32c6
. ./export.sh
cd "$TIMER_BUILD_DIR/micropython"
make -C mpy-cross -j2
```

`export.sh` aktiviert die ESP-IDF-Umgebung für dieses Terminal. In einem neuen
Terminal `TIMER_BUILD_DIR` erneut setzen und `export.sh` erneut laden. Diesen Build
außerhalb der Projekt-venv ausführen, damit die ESP-IDF-Python-Umgebung maßgeblich ist.

### 3. ESP32-C6-Laufzeit bauen

```sh
cd "$TIMER_BUILD_DIR/micropython"
make -C ports/esp32 BOARD=ESP32_GENERIC_C6 submodules
make -C ports/esp32 BOARD=ESP32_GENERIC_C6 -j2
ls -lh ports/esp32/build-ESP32_GENERIC_C6/firmware.bin
sha256sum ports/esp32/build-ESP32_GENERIC_C6/firmware.bin
```

Erwartet: erfolgreiche Build-Zusammenfassung und die kombinierte `firmware.bin`.
Den SHA256-Wert zusammen mit MicroPython-/ESP-IDF-Commit speichern. Unter macOS
statt `sha256sum` den Befehl `shasum -a 256` verwenden.

Die Datei zum USB-Rechner übertragen, dort z. B. als
`~/Downloads/micropython-c6.bin` speichern und nach
[INSTALLATION.md, Schritt 5](INSTALLATION.md#5-esp32-basisfirmware-und-werkzeuge--rechner)
flashen. `bootloader.bin`, `partitions.bin` und `micropython.bin` nicht einzeln
mit einer geratenen Adresse flashen. Nach dem Flashen weiterhin **aioble und
die sieben Timerdateien** installieren; sie sind nicht in diesem Image enthalten.

### Prüfung und Grenzen dieses Eigenbaus

Die Befehle wurden anhand des genannten MicroPython-Tags und der Espressif-
Dokumentation zusammengestellt. Ein vollständiger ESP-IDF-Eigenbau und dessen
Flash-Test wurden im Rahmen dieser Dokumentation **nicht ausgeführt**. Die CI
testet den Anwendungscode, dessen MicroPython-Syntax und die Ausführung auf dem
MicroPython-Unix-Port, nicht den ESP32-Firmwarebuild.

## D. `.mpy`-Dateien und Bibliotheken

Der Standardweg dieses Projekts überträgt `.py` und lässt `main.py` als Startdatei.
Das vermeidet eine zusätzliche manuelle Bytecode-Versionsabhängigkeit. Selbst
erzeugte `.mpy`-Module benötigen einen zur Gerätefirmware passenden Cross-Compiler;
bei nativen Modulen muss zusätzlich die CPU-Architektur passen. Das Ergebnis des
CI-Syntaxchecks nicht als Deployment-Paket behandeln.

Version des Geräts und dessen `.mpy`-Kennung abfragen:

```sh
.venv-board/bin/mpremote connect "$ESP_PORT" exec 'import sys; print(sys.version); print(sys.implementation)'
```

Bei `ValueError: incompatible .mpy file` Bibliotheks-/Compiler-Version prüfen.
aioble bei Bedarf als Quelltext installieren:

```sh
.venv-board/bin/mpremote connect "$ESP_PORT" mip install --no-mpy aioble
.venv-board/bin/mpremote connect "$ESP_PORT" reset
```

Bei bereits gemischten alten `.py`-/`.mpy`-Bibliotheksständen zuerst `lib/` sichern
und den betroffenen Bibliotheksstand bereinigen bzw. eine saubere Geräteinstallation
verwenden. Nicht wahllos `.mpy`- und `.py`-Versionen übereinander kopieren.
Hintergrund: [MicroPython .mpy-Kompatibilität](https://docs.micropython.org/en/latest/reference/mpyfiles.html).

## Versionen für die Abnahme notieren

- Projekt-Commit: `git rev-parse HEAD`.
- Pi-Pakete: `.venv/bin/python -m pip freeze`.
- USB-Werkzeuge: `.venv-board/bin/python -m pip freeze`.
- MicroPython-Version auf dem Gerät und Herkunft/SHA256 der verwendeten `.bin`.
- aioble-Version bzw. Installationsquelle und Datum; bei reproduzierbarer Abnahme
  den installierten Bibliotheksstand zusätzlich außerhalb des Repositories sichern.
- Pi-OS, Luxafor-Firmware und AP-Kanal im [Abnahmeprotokoll](acceptance.md).
