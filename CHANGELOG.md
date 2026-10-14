# Änderungen

Versionsnummern nach [Semantic Versioning](https://semver.org/lang/de/): Fehlerkorrektur
→ dritte Stelle, neue Funktion → zweite Stelle, inkompatible Änderung (z. B. neue
ESP32-Firmware zwingend) → erste Stelle. Die aktuelle Version steht in `version.py`
und wird in der Touch-App (WLAN / IP) und der Weboberfläche angezeigt. Mit 0.7.1 lief
die Grundfunktion erstmals auf der Hardware (Hotspot, ESP32-WLAN, BLE-Verbindung);
1.0.0 ist die erste Version danach. Die ESP32-Firmware hat eine eigene Version
(`FIRMWARE_VERSION` in `firmware/timer_logic.py`); sie wird nur erhöht, wenn sich
Dateien ändern, die auf den ESP32 kopiert werden.

## 1.6.0 – Busy Tag am Headend, Dienste für beliebigen Benutzer (14.10.2026)

Pi-Software 1.6.0, ESP32-Firmware unverändert.

Busy Tag:
- Eine [Busy Tag](docs/INSTALLATION.md#busy-tag-am-headend) per USB am Pi wird wie die
  Orb angesteuert, allein oder zusammen mit ihr: LEDs in der Phasenfarbe, rotes
  Blinken bei Überzeit, Display mit „SwiNOG“ bei Stop und Phasentext im Vortrag.
  Fehlende Bilder (`static/busytag/`) lädt der Server beim Anschließen hoch.
- Das Blinken schaltet der Server selbst: Die Musterbefehle der Firmware 1.0
  speicherten im Test fehlerhafte Muster und starteten das Gerät neu.
- Touch-App und Weboberfläche heißen den Status jetzt „LED Light“ statt „Luxafor · USB“;
  er fasst beide Lampen zusammen, die Meldungen nennen das Gerät
  („Luxafor USB verbunden“, „Busy Tag nicht gefunden“).
- Zugriff über die Gruppe `dialout`. Die Bilder erzeugt `tools/make_busytag_images.py`
  aus den UI-Farben und -Texten, samt Übersicht `images/busytag-display.png` für die Doku.

Installation:
- Neues `deploy/install-services.sh` installiert `pi-timer-wifi.service`,
  `pi-timer-hotspot-channel.service` und die udev-Regel der Luxafor Orb für den
  aufrufenden Benutzer und den Ort des Repositories. Der feste Benutzer `pitimer`
  und `/home/pitimer` entfallen; die Unit-Dateien unter `deploy/` sind jetzt
  Vorlagen mit `@USER@`/`@DIR@`. `--hotspot` aktiviert zusätzlich die Kanalwahl.
- Anleitungen verwenden einen frei wählbaren Timer-Benutzer.
- Fehlersuche Orb: Bleibt `sudo dmesg -w` beim Einstecken leer, kommt kein
  USB-Signal an (Ladekabel ohne Daten, Buchse oder Orb defekt).

Bestehende Installation: `git pull`, dann `deploy/install-services.sh` als
Timer-Benutzer ausführen (`--hotspot`, falls die Kanalwahl aktiv ist).

## 1.5.0 – ESP32-C6-Touch-LCD-1.47 als drittes Board (13.10.2026)

Pi-Software 1.5.0, ESP32-Firmware 1.4.0. Auf die ESP32 `firmware/boards.py`,
`firmware/st7789.py`, `firmware/display.py` und `firmware/timer_logic.py` kopieren.
Die Dateien gehören zusammen; auf allen Boards aktualisieren.

ESP32-Firmware:
- Dieselben Dateien laufen auch auf dem
  [ESP32-C6-Touch-LCD-1.47](firmware/README.md#esp32-c6-touch-lcd-147). Das Board
  hat einen JD9853-Display-Controller statt des ST7789 und andere Pins; mit der
  bisherigen Firmware blieb sein Display schwarz. Die Touch-Funktion wird nicht
  genutzt.
- Die Firmware erkennt das Touch-Board am Touch-Controller bzw. Lagesensor auf dem
  I2C-Bus (GPIO18/19) und wählt das neue Profil `c6-touch-147`; `BOARD` in
  `config.py` bleibt leer. Die erste REPL-Zeile nennt es, z. B.
  `Pi Timer Firmware 1.4.0 c6-touch-147`.
- Auf dem Touch-Board hält die Firmware die Chip-Select-Leitung des TF-Slots
  (GPIO4) auf High; er teilt sich SCK und MOSI mit dem Display.
- Der SPI-Bus des Touch-Boards bekommt GPIO3 als MISO. Ohne Angabe belegt
  MicroPython auf dem C6 GPIO2 als MISO-Eingang; das ist hier die Datenleitung zum
  Display, das dann trotz Beleuchtung schwarz blieb.
- Auf der Hardware geprüft: Erkennung, Anzeige, Phasenfarben und Drehung mit
  `FLIP` auf dem ESP32-C6-Touch-LCD-1.47.

Abnahme: Grundbetrieb, Mesh mit zwei ESP32, Ausfälle und native App auf der
Hardware geprüft ([Hardwareprotokoll](docs/acceptance.md#hardwareprotokoll)).

## 1.4.2 – BLE im reinen Mesh-Betrieb (13.10.2026)

Pi-Software 1.4.2, ESP32-Firmware 1.3.2. Auf die ESP32 `firmware/main.py`,
`firmware/luxafor.py` und `firmware/timer_logic.py` kopieren.

ESP32-Firmware:
- Ohne WLAN-Verbindung und mit Mesh fand der ESP32 die Luxafor nie (`BLE OFFLINE`):
  mit `WIFI = False` und ebenso im Fallback, wenn bei `WIFI = True` der Hotspot
  nicht erreichbar ist. Messung mit
  `ble_test.py`: Mit WLAN und ESP-NOW an, aber ohne WLAN-Verbindung, sah der
  BLE-Scan kein einziges Gerät (0 von 3 Runden); ohne diese Last fand er die Lampe
  jedes Mal nach 0,3–2,3 s. Eine bestehende Verbindung lief unter der Last weiter.
- Ohne WLAN-Verbindung schaltet der ESP32 ESP-NOW und WLAN deshalb nur für Suche
  und Verbindungsaufbau zur Luxafor ab (im Test 1–3 s) und stellt danach den
  Mesh-Kanal wieder her. Ein laufender WLAN-Verbindungsversuch zum Hotspot hat
  Vorrang: Währenddessen sucht der ESP32 ohne Pause, die Suche wird bei Misserfolg
  wiederholt. WLAN-Verbindungsversuche warten, solange die Pause läuft.
- Neue Konsolenzeile bei jeder WLAN-Verbindung, z. B. `WLAN verbunden nach 95 s ohne
  WLAN, 6 Versuch(e), Kanal 11`. Nach einem Headend-Neustart zeigt sie, ob die
  Zeit beim Pi (Booten, Hotspot) oder beim ESP32 liegt. Der Countdown läuft in der Zeit lokal weiter. Ist die Lampe aus,
  wiederholt sich das alle paar Sekunden bis 15 s; das Display kann dann kurz
  `MESH OFFLINE` zeigen.
- Mit WLAN-Verbindung bleibt alles an, wie bisher. Ohne `MESH` gibt es keine Pause.
- `ble_test.py`: neue Option `PAUSE_FOR_SCAN` für diesen Ablauf.

## 1.4.1 – Display um 180° drehbar (13.10.2026)

Pi-Software 1.4.1, ESP32-Firmware 1.3.1. Auf die ESP32 `firmware/main.py`,
`firmware/display.py`, `firmware/st7789.py`, `firmware/boards.py`,
`firmware/luxafor.py` und `firmware/timer_logic.py` kopieren; neue Option aus `config.example.py` bei Bedarf
übernehmen.

ESP32-Firmware:
- Neue Option `FLIP = True` in `config.py`: Die Anzeige steht um 180° gedreht,
  auf beiden Boards (auf C6 und S3 geprüft).
- Die S3-Erkennung akzeptiert auch die Schreibweise `ESP32-S3` im Chipnamen.
- ESP32-S3-LCD-1.69 auf der Hardware geprüft: läuft mit Firmware 1.3.1.
- Die Luxafor bestätigt jeden Schreibbefehl mit der Meldung `1\r`. Die Firmware hielt
  sie für eine Ready-Meldung und sendete die Farbe sofort erneut: etwa zehn Befehle
  pro Sekunde statt einem bei Phasenwechsel bzw. alle 5 s. Das belastete die
  Funkzeit, die sich BLE mit WLAN und ESP-NOW teilt.
- `ble_test.py`: Die GATT-Liste in Runde 1 brach mit `ValueError: Discovery in
  progress` ab.
- Fehlt `LUXAFOR_PAIR` in `config.py`, gilt jetzt `False`. Bisher brach jede
  BLE-Verbindung direkt nach dem Aufbau mit `BLE: AttributeError` ab.
- Neues Diagnoseskript `firmware/ble_test.py` (nur ausführen, nicht kopieren): prüft
  Scan, Verbindung, GATT und Farbbefehle zur Luxafor ohne den restlichen Timer,
  optional unter ESP-NOW-Last ([BLE-Test](firmware/README.md#ble-test-ohne-timer)).

## 1.4.0 – ESP32-S3-LCD-1.69 als zweites Board (13.10.2026)

Pi-Software 1.4.0, ESP32-Firmware 1.3.0. Auf die ESP32 die neue Datei
`firmware/boards.py` sowie `firmware/st7789.py`, `firmware/display.py`,
`firmware/main.py` und `firmware/timer_logic.py` kopieren. Die Dateien gehören
zusammen; nur ein Teil davon startet nicht.

ESP32-Firmware:
- Dieselben Dateien laufen auf dem ESP32-C6-LCD-1.47 und dem
  [ESP32-S3-LCD-1.69](firmware/README.md#esp32-s3-lcd-169). Die Firmware erkennt
  den Chip und wählt Pins, Display-Offset und Layout aus `boards.py`. Die erste
  REPL-Zeile nennt das Profil, z. B. `Pi Timer Firmware 1.3.0 s3-169`.
- Neue Option `BOARD` in `config.py`, nur für die erste Revision des S3-Boards
  nötig (`"s3-169-v1"`, anderer Haltepin für den Akkubetrieb).
- Auf dem S3 hält die Firmware die Stromversorgung im Akkubetrieb (SYS_EN) und
  schaltet den Buzzer stumm. Layout mit breiterem Rand für die runden Ecken.
- Display-Initialisierung mit den Wartezeiten aus dem ST7789-Datenblatt nach Reset
  und Sleep Out; vermutliche Ursache des schwarzen Displays auf dem S3-Board.
- Auf dem C6 bleibt die Anzeige unverändert. Das S3 ist noch nicht auf der
  Hardware abgenommen.

## 1.3.7 – Reiner Mesh-Empfänger (13.10.2026)

Pi-Software 1.3.7, ESP32-Firmware 1.2.7. Auf die ESP32 `firmware/main.py` und
`firmware/timer_logic.py` kopieren; neue Option aus `config.example.py` bei Bedarf
übernehmen.

ESP32-Firmware:
- Neue Option `WIFI = False` in `config.py`: Das Gerät nutzt nur das ESP-NOW-Mesh,
  verbindet sich nie mit dem Hotspot und sucht die Kanäle 1, 6 und 11 nach Nachbarn
  ab. `MESH` ist dann automatisch an. Display `MESH OK` bzw. `MESH OFFLINE`.
  Praktisch auch zum Testen des Mesh mit zwei Geräten nebeneinander.

## 1.3.6 – Mesh sendet nur bei Bedarf (13.10.2026)

Pi-Software 1.3.6, ESP32-Firmware 1.2.6. Auf die ESP32 `firmware/main.py` und
`firmware/timer_logic.py` kopieren.

ESP32-Firmware:
- Mit `MESH = True` sendet ein ESP32 den Timer-Zustand nur noch, wenn in den letzten
  15 s ein Gerät ohne WLAN nach ihm gefragt hat (dessen Statuspaket), und dann
  jede Sekunde statt alle 500 ms. Haben alle Geräte WLAN, ist das Mesh still. Im
  Test mit 1.2.5 und Mesh lief der BLE-Verbindungsaufbau zur Luxafor mehrfach in
  den Timeout (`BLE: TimeoutError`), ohne Mesh nicht.
- Der Speicher blieb mit 1.2.5 und Mesh stabil (Tiefststand über 110 KB).

## 1.3.5 – Verständliche BLE-Fehlermeldung (13.10.2026)

Pi-Software 1.3.5, ESP32-Firmware 1.2.5. Auf die ESP32 `firmware/luxafor.py` und
`firmware/timer_logic.py` kopieren.

ESP32-Firmware:
- BLE-Fehler nennen den Typ, z. B. `BLE: DeviceDisconnectedError` nach dem
  Ausschalten der Lampe statt eines leeren `BLE:`; so auch im Luxafor-Status am Headend.

Auf der Hardware geprüft (1.2.4, ohne Mesh): 20 Minuten ohne `Sync`-Fehler oder
`ENOMEM`, Luxafor aus- und wieder eingeschaltet ohne Störung des WLAN-Abgleichs.

## 1.3.4 – Speicher für WLAN und BLE freigegeben (13.10.2026)

Pi-Software 1.3.4, ESP32-Firmware 1.2.4. Auf **alle ESP32** `firmware/st7789.py`,
`firmware/display.py`, `firmware/main.py` und `firmware/timer_logic.py` kopieren und
mit Reset-Knopf oder `mpremote … reset` neu starten.

ESP32-Firmware:
- Behoben: Das Display hielt ein komplettes Bild im RAM (320×172 RGB565 =
  110 KB am Stück). Auf dem ESP32-C6 blieb damit für WLAN und BLE zeitweise kein
  Speicher (gemessen: Tiefststand 4 bzw. 792 Bytes freier IDF-Speicher). Folgen:
  `Sync: TimeoutError`, BLE `ENOMEM`, mit Mesh ein Absturz (Guru Meditation), nach
  einem Soft-Reset `MemoryError … 110080 bytes`. Jetzt zeichnet die Firmware
  Kopfzeile, Countdown und Statuszeile einzeln über einen Streifenpuffer von 30 KB
  und überträgt nur geänderte Bereiche.
- Das Mesh bleibt bis zu einem Hardwaretest mit 1.2.4 aus.

## 1.3.3 – Socket-Leck im ESP32-Abgleich behoben (13.10.2026)

Pi-Software 1.3.3, ESP32-Firmware 1.2.3. Auf dem Pi Dienst und App neu starten,
auf **alle ESP32** `firmware/http_sync.py`, `firmware/main.py` und
`firmware/timer_logic.py` kopieren.

ESP32-Firmware:
- Behoben: Jeder Abgleich ließ einen Socket offen. In MicroPython schließt
  `Stream.close()` den Socket nicht (nur `wait_closed()`), und ein Timeout während
  `open_connection()` verlor ihn ganz. Nach einiger Zeit waren Sockets und
  Netzwerkspeicher erschöpft: Jeder Abgleich endete mit `Sync: TimeoutError` trotz
  gutem Signal, der Pi sah keine Pakete mehr, BLE meldete `ENOMEM`. Ein Reset half
  nur vorübergehend. Der Socket wird jetzt in jedem Fall direkt geschlossen; ein
  Test auf dem MicroPython-Unix-Port prüft das auch nach Timeouts.
- Der in 1.2.2 ESP-NOW zugeschriebene Ausfall hatte dieselbe Ursache; ESP-NOW löste
  ihn nur schneller aus. Das Mesh bleibt aus, bis ein Hardwaretest mit 1.2.3 es
  bestätigt (`MESH = True` schaltet es ein).

## 1.3.2 – ESP-NOW-Mesh standardmäßig aus (13.10.2026)

Pi-Software 1.3.2, ESP32-Firmware 1.2.2. Auf dem Pi Dienst und App neu starten,
auf den ESP32 `firmware/main.py` und `firmware/timer_logic.py` kopieren.

ESP32-Firmware:
- Das Mesh ist ohne `MESH`-Eintrag in `config.py` jetzt aus. Im Hardwaretest legte
  aktives ESP-NOW auf dem ESP32-C6 den WLAN-Abgleich lahm (`Sync: TimeoutError`
  bei Kanal 6 und −70 dBm) und BLE meldete `ENOMEM`; ohne ESP-NOW lief beides.
  `MESH = True` schaltet es für Tests wieder ein. Wer `MESH = True` aus der alten
  Vorlage in seiner `config.py` hat, sollte es auf `False` setzen.

Headend:
- Meldet ein ESP32 eine neuere Firmware, als der Pi kennt, zeigt **WLAN / IP**
  `FW 1.2.1 (Pi kennt 1.2.0)` statt eines irreführenden `FW 1.2.1 → 1.2.0`: Dann ist
  die Pi-Software zu aktualisieren (`git pull`, Dienst und App neu starten).

## 1.3.1 – Diagnose für WLAN-Abgleich (13.10.2026)

Pi-Software 1.3.1, ESP32-Firmware 1.2.1. Nur die ESP32-Firmware hat sich geändert
(`firmware/main.py`, `firmware/timer_logic.py`).

ESP32-Firmware:
- Fehler beim Abgleich nennen auf der Konsole den Typ (bisher erschien ein Timeout
  als leeres `Sync:`) und bei bestehender WLAN-Verbindung Signalstärke, Kanal und
  IP, z. B. `Sync: TimeoutError (RSSI -71 dBm, Kanal 6, IP 10.42.0.23)`.

## 1.3.0 – Status pro ESP32 (13.10.2026)

Pi-Software 1.3.0, ESP32-Firmware 1.2.0. Nach dem Update auf dem Pi den Dienst neu
starten und die native App neu starten; die systemd-Units sind unverändert. Alle
ESP32 aktualisieren (`docs/BETRIEB.md`, „ESP32-Firmware aktualisieren“) und bei
mehreren Geräten je einen eigenen `HOSTNAME` setzen. Firmware vor 1.2.0 erscheint
weiterhin, aber pro IP-Adresse und ohne Mesh-Status.

Headend:
- Statusanzeige pro ESP32 statt nur des zuletzt meldenden Geräts: Name, Weg
  (WLAN oder „Mesh über …“), Übernahme von Start/STOP und Luxafor-Verbindung.
  `GET /api/state` liefert `devices` statt `node`.
- Touch-App: `ESP32 · 2/3 OK`, ein Gerät ausführlich, ab zwei Geräten je eine
  Zeile (höchstens fünf); grün/orange/rot. Weboberfläche listet alle Geräte.
- Meldung unter STOP nennt betroffene Geräte („Warte auf Bestätigung: saal-2“).
- **WLAN / IP**: ESP32 im Hotspot (an der MAC erkannt) mit Name und Firmware-Version,
  Mesh-Geräte mit ihrem Weg. Die Firmware-Angaben stehen nicht mehr in der Statusspalte.
- Geräte gelten direkt nach 5 s, über das Mesh nach 10 s ohne Meldung als offline
  und verschwinden nach 30 Minuten aus der Liste; höchstens 16 Geräte.
- `tools/simulate_node.py` meldet sich mit Namen (`PI_TIMER_NODE`), mehrere
  Simulationen erscheinen getrennt.

ESP32-Firmware:
- Meldet MAC-Adresse als `id` und `HOSTNAME` als `name`.
- Geräte ohne WLAN senden alle 2 s ein signiertes Statuspaket per ESP-NOW; Geräte
  ohne WLAN leiten es weiter, ein Gerät mit WLAN meldet es als `peers` an den Pi.

Noch nicht auf der Hardware geprüft: Statusweiterleitung über das Mesh und die
Zuordnung von DHCP-Einträgen zu ESP32 über die MAC.

## 1.2.0 – ESP-NOW-Mesh zwischen den ESP32 (13.10.2026)

Pi-Software 1.2.0, ESP32-Firmware 1.1.0. Nach dem Update auf dem Pi die Unit
`pi-timer-wifi.service` neu kopieren (neu: `StateDirectory`) und
`sudo systemctl daemon-reload`. Auf jeden ESP32 zusätzlich `firmware/mesh.py`
kopieren (`docs/BETRIEB.md`, „ESP32-Firmware aktualisieren“). Firmware 1.0.0 läuft
mit dem neuen Server weiter, nimmt aber nicht am Mesh teil.

Headend:
- Server-Antworten tragen einen Stempel `stamp: [Generation, ms]`. Die Generation
  steigt bei jedem Serverstart und liegt in `/var/lib/pi-timer-wifi/generation`.

ESP32-Firmware:
- ESP-NOW-Mesh zwischen gleichberechtigten ESP32: Jedes Gerät sendet seinen
  Zustand zweimal pro Sekunde, jedes übernimmt nur einen neueren Server-Stempel.
  Wer zuletzt den Pi erreicht hat, ist damit automatisch die Quelle; Geräte ohne
  WLAN erhalten Start/Stop über Nachbarn, auch über mehrere Hops.
- Pakete mit HMAC-SHA256 (`API_TOKEN`) signiert; alte Pakete verlieren gegen neuere.
- Ohne WLAN bleibt das Gerät auf dem Hotspot-Kanal bzw. sucht 1/6/11 ab und
  versucht das WLAN nur alle 30 s, solange das Mesh frische Zustände liefert.
- Display zeigt `MESH OK`, wenn der Timer über einen anderen ESP32 kommt.
- Optional `MESH = False` in `config.py`.

Noch nicht auf der Hardware geprüft: ESP-NOW neben WLAN und BLE auf dem ESP32-C6,
Kanalsuche ohne WLAN und Mesh über mehrere Hops. Geräte, die nur über das Mesh
synchronisieren, erscheinen nicht in der Statusanzeige des Pi.

## 1.1.0 – Automatische Kanalwahl (13.10.2026)

Pi-Software 1.1.0, ESP32-Firmware unverändert (1.0.0). Nach dem Update den neuen
Dienst einmalig installieren (`deploy/direct-wifi.md`, „Automatische Kanalwahl“).

Headend:
- Neuer Dienst `pi-timer-hotspot-channel`: scannt bei jedem Booten das 2.4-GHz-Band
  und startet den Hotspot auf dem am wenigsten belegten Kanal (1, 6 oder 11), für
  maximale Reichweite. Bei fehlgeschlagenem Scan bleibt der bisherige Kanal.
- `sudo python3 deploy/hotspot_channel.py` wiederholt die Kanalwahl vor Ort.

Noch nicht auf der Hardware geprüft: Scan nach dem Trennen des Hotspots auf dem
Pi Zero 2 W und Reichweitengewinn.

## 1.0.0 – WLAN / IP-Übersicht und Versionen (13.10.2026)

Pi-Software 1.0.0, ESP32-Firmware 1.0.0. Nach dem Update auf dem Pi `./install.sh`
ausführen (neue Abhängigkeit) und die ESP32-Firmware aktualisieren
(`docs/BETRIEB.md`, „ESP32-Firmware aktualisieren“). Ältere Firmware läuft weiter,
wird aber als veraltet angezeigt.

Headend:
- Touch-App: Knopf „WLAN / IP“ unten rechts öffnet ein schließbares Overlay mit
  WLAN-QR-Code (inkl. Passwort), Headend-Adressen und den Geräten im Hotspot
  (DHCP-Leases und ARP-Tabelle, mit Hostname). Aktualisiert alle 5 Sekunden.
- Overlay zeigt die Adressen der Weboberfläche für Handys/Laptops im Hotspot
  (`http://pi-timer.local:8000/` und `http://10.42.0.1:8000/`).
- Versionsnummer in `version.py` mit Git-Commit, angezeigt im Overlay und in der
  Weboberfläche; Changelog nummeriert.
- ESP32-Status zeigt die gemeldete Firmware-Version und markiert veraltete Firmware.
- Mauszeiger im Vollbild ausgeblendet statt X11-„X“; `PI_TIMER_CURSOR=dot` zeigt einen Punkt.
- Farblegende mit kleinem Farbquadrat je Phase (Touch-App und Weboberfläche);
  „Blinkend“ als statisches dunkleres Rot.
- Neue Abhängigkeit `qrcode` (reines Python).

ESP32-Firmware:
- Eigene Version `FIRMWARE_VERSION` in `firmware/timer_logic.py`, wird bei jedem
  Abgleich gemeldet und beim Start auf der seriellen Konsole ausgegeben.
- Optionaler `HOSTNAME` in `config.py`, damit mehrere Geräte im Overlay unterscheidbar sind.
- Display zeigt die Firmware-Version unten rechts und den `HOSTNAME` (falls gesetzt) oben rechts.

Noch nicht auf der Hardware geprüft: Overlay (insbesondere Lesen des WLAN-Passworts
per `nmcli` als normaler Benutzer), `HOSTNAME`, Versionsmeldung und Display-Anzeige des ESP32.

## 0.7.1 – Hotspot und Installation korrigiert (12.10.2026)

- Hotspot: PMF im Profil abgeschaltet; macOS konnte sich trotz korrektem Passwort
  nicht verbinden. Bestehende Profile: siehe `deploy/direct-wifi.md`.
- Hotspot: Autoconnect-Priorität 999 statt 1000 (NetworkManager erlaubt höchstens 999);
  `setup_hotspot.py` brach bisher mit nmcli-Exit-Code 2 ab.
- `setup_hotspot.py` zeigt die nmcli-Fehlermeldung an (Passwort maskiert).
- `native.xinitrc` verwendet `$HOME/pi-timer-wifi` statt fest `/home/pitimer`.
- Anleitung: systemd-Unit für andere Benutzernamen, Console Autologin je nach
  raspi-config-Version, Hotspot-Umschaltung nur über SSH mit Rückfall-Timer.

## 0.7.0 – Luxafor Orb am Headend (28.09.2026)

- Luxafor Orb per USB am Pi funktioniert wie im ursprünglichen Projekt: gleiche Farben
  und USB-Befehle wie `luxafor-linux.py`, jetzt direkt im Timer-Server (`orb.py`).
- Orb folgt jedem Start, Stop und Ersatz-Start; nach erneutem Einstecken erhält sie
  die aktuelle Farbe. Ohne Orb, pyusb oder libusb läuft der Timer normal weiter.
- Touch-App und Weboberfläche zeigen den Status „Luxafor · USB“; `PI_TIMER_ORB=0` schaltet ab.
- udev-Regel `deploy/99-luxafor.rules` (Gruppe `plugdev` statt Vollzugriff für alle).
- Hardwarefotos aus dem ursprünglichen Projekt in README und Anleitungen übernommen.

## 0.6.0 – MicroPython-Laufzeittest (28.09.2026)

- Neuer CI-Job führt die Firmware auf dem MicroPython-Unix-Port v1.28.0 aus
  (`tests/micropython/run.py`); findet Methoden, die nur CPython kennt.
- ESP32 liest HTTP-Antworten in Blöcken statt byteweise; Größengrenzen bleiben.
- Legende und Weboberflächen-Farben werden aus `ui_config.py` bzw. den Phasen-Schwellen erzeugt.
- Weboberfläche startet auch, wenn der Browser `sessionStorage` blockiert.
- `age_s` in der API auf Millisekunden gerundet.

## 0.5.0 – Review-Korrekturen (28.09.2026)

- ESP32-Start repariert: MicroPython kennt `str.isalnum()` nicht; die Token-Prüfung
  in `firmware/main.py` brach dadurch beim Booten ab.
- Display-Framebuffer wird vor WLAN/BLE belegt, damit der Speicher noch nicht zerstückelt ist.
- Weboberfläche: Ein falsch eingegebener Schlüssel ersetzt einen gültigen nicht mehr.
  Ein abgelehnter Schlüssel beendet die Abfragen, damit sich der Anmeldedialog nicht ständig neu öffnet.
- Start/Stop-Antworten enthalten den ESP32-Status; die Anzeige springt nicht mehr kurz auf «offline».
- Ungültiges JSON ergibt eine JSON-Fehlerantwort statt Flasks HTML-Seite.
- Phasen-Schwellen, Presets, Farben und Beschriftungen an einer Stelle
  (`firmware/timer_logic.py`, `ui_config.py`); die Weboberfläche übernimmt sie vom Server.
- Hinweis zur Token-Sicherheit im gemeinsamen WLAN.

## 0.4.0 – Native Pi-Oberfläche (28.09.2026)

- Tkinter-Touch-App als Standard für den Pi Zero 2 W, direkt auf X11 ohne Browser.
- Lokaler Schlüssel wird aus `.env` geladen; keine Eingabe nach dem Einschalten.
- Separater Timer-Dienst erhält den Countdown beim Neustart der Oberfläche.
- Serieller HTTP-Worker, begrenzte Warteschlangen und keine automatischen Start-Wiederholungen.
- Tests für Offline-Anzeige, veraltete Antworten, verlorene Start-Antworten und
  nativen HTTP-Transport; eigener Linux-CI-Test für 1024×600-Layout und Touch-Tasten.
- Installations-/Betriebsanleitungen auf native App umgestellt; Desktop und Web optional.

## 0.3.0 – Aufbau- und Betriebsanleitungen (28.09.2026)

- Durchgehende Erstinstallation: Pi OS Lite, Touch-Display/Kiosk, Server-Dienst,
  ESP32-Sicherung/Flashen, Konfiguration und Offline-Inbetriebnahme.
- Build-Anleitung mit Syntaxprüfung und optionalem MicroPython-Eigenbau
  (`v1.28.0`, ESP-IDF `v5.5.1`, Board `ESP32_GENERIC_C6`).
- Betriebshandbuch für Statusanzeigen, Diagnose, Updates, Sicherungen und Rollback.
- X11-Kiosk-Startdatei für frische Pi-OS-Lite-Installationen.

## 0.2.0 – Direktes WLAN (28.09.2026)

- Standardaufbau für Veranstaltungen ohne Infrastruktur: Pi Zero 2 W stellt das
  WLAN `SwiNOG-Timer` bereit, ESP32 verbindet sich direkt; kein Router/Internet nötig.
- NetworkManager-Einrichtung mit WPA2, individuellem Passwort, DHCP und fester
  Pi-Adresse `10.42.0.1`. Aktivierung und Autostart werden separat eingeschaltet.
- Gemeinsames WLAN bleibt als alternative Konfiguration dokumentiert.
- Vorbereitung mit Internet und anschließender vollständig offline erfolgender
  Kaltstart-/Reichweitentest beschrieben. Hardware-Abnahme weiterhin offen.

## 0.1.0 – Erste Version (28.09.2026)

- Pi-Headend, WLAN-Synchronisation, ESP32-Display und direkte Luxafor-Pro-BLE-Steuerung.
- Monotoner Offline-Countdown, Wiederverbindung und Übernahmebestätigung.
