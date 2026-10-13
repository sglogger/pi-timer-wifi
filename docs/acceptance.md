# Abnahme vor Konferenzeinsatz

## Bereits automatisiert prüfbar

`python -m unittest discover -s tests -v` prüft Timergrenzen, kurze Presets,
Start/Stop-Ersetzung, Gerätemeldungen, API-Eingaben, Zugriffsschlüssel,
Offline-Countdown, Reconnect, Server-Neustart, Tick-Wrap und HTTP-Transport.
Diese Tests ersetzen keinen Funk-/Hardwaretest.

Entwicklungsprüfung am 28.09.2026: **46 Tests erfolgreich** unter Python 3.14,
einschließlich eines simulierten GATT-Geräts, echter lokaler TCP-Verbindungen und
Hotspot-Vorbereitung mit simuliertem NetworkManager. Der Hotspot-Test prüft auch,
dass bestehende Profile erhalten bleiben und das Setup keine Verbindung aktiviert.
Zusätzlich geprüft: native Statusanzeige, abgelaufene Bedienanfragen, alte
Antworten sowie ein verlorenes Start-Ergebnis ohne erneuten Startversuch.
Alle acht Firmware-Quelldateien wurden mit mpy-cross 1.29.0.post2 kompiliert.
Auf dem MicroPython-Unix-Port v1.28.0 laufen zusätzlich 13 Prüfungen
(`tests/micropython/run.py`): Timerlogik, Tick-Wrap, HTTP-Austausch über echte
Sockets einschließlich Größengrenzen, Konfigurationsprüfung beim Start von `main.py`
und Display-Rendering in den Framebuffer. Funk und SPI-Display sind dabei nachgebildet.
Browserprüfung mit simuliertem Knoten: Anmeldung, Start, Ein-Minuten-Preset,
Neuladen mit laufendem Timer, bestätigter Stop und getrennte BLE-Statusanzeige.
Eine Ausführung auf ESP32-C6 und Luxafor wurde dabei nicht durchgeführt.

Luxafor Orb am Headend (28.09.2026, **53 Tests erfolgreich**): `tests/test_orb.py`
prüft die USB-Befehle gegen `luxafor-linux.py`, Phasenwechsel, Senden nur bei
Änderung, Abziehen/Einstecken, mehrere Lampen, fehlendes pyusb/libusb und den
Orb-Status in der API. USB ist dabei nachgebildet; eine echte Orb wurde nicht angesteuert.

Ein zusätzlicher nativer GUI-Test (`tests/ui_smoke.py`) prüft die 1024×600-
Darstellung einschließlich negativer dreistelliger Minutenanzeige, alle acht
Touch-Tasten, deren Mindesthöhe und das Schließen ohne STOP. Er läuft separat
unter Linux/Xvfb in der CI und wurde auch lokal mit Tk ausgeführt. Die native
App benötigt weiterhin eine Prüfung auf dem echten Pi auf Startzeit, CPU/RAM
und Touch-Bedienung.

## Hardwareprotokoll – noch offen

Datum, MicroPython-Version, aioble-Version/Commit, Luxafor-Firmware, AP/gewählter Kanal, Anzahl ESP32,
Abstand und Hindernisse für den Test notieren. Bis alle Punkte geprüft sind,
diese Version als Prototyp behandeln.

- [ ] ESP32-Display: lesbarer Countdown im Querformat, Farben stimmen.
- [ ] Pi-Hotspot aktiv: `SwiNOG-Timer`, WPA2, Pi-IP `10.42.0.1`, ESP32 erhält DHCP-Adresse.
- [ ] Kaltstart ohne Router/Internet: erst Pi, dann ESP32; Verbindung entsteht automatisch.
- [ ] Umgekehrte Einschaltreihenfolge: ESP32 zuerst, Pi später; automatische Verbindung.
- [ ] Pi-Neustart: Hotspot und Timer-Dienst starten erneut, ESP32 übernimmt neue Sitzung/Stop.
- [ ] Kanalwahl: `journalctl -u pi-timer-hotspot-channel -b` zeigt Belegung und gewählten
      Kanal; nach Neustart mit anderem Kanal verbinden sich alle ESP32 wieder.
- [ ] Mesh (`MESH = True` auf allen Geräten): WLAN-Abgleich und BLE bleiben bei aktivem
      ESP-NOW stabil (im ersten Test nicht der Fall, siehe Architektur).
- [ ] Mesh: zweiten ESP32 außerhalb der Hotspot-Reichweite (oder mit falschem WLAN-Passwort)
      betreiben: Display `MESH OK`, Start/Stop kommen innerhalb von 2 s an.
- [ ] Mesh über zwei Hops: drei ESP32 in Kette, nur der erste mit WLAN.
- [ ] Mesh: ESP32 mit anderem `API_TOKEN` übernimmt keine Zustände.
- [ ] Mesh: Pi ausschalten: alle zählen weiter, keiner springt, Displays zeigen `WIFI OFFLINE`.
- [ ] Statusanzeige: drei ESP32 mit `HOSTNAME`, einer nur über Mesh: alle drei getrennt
      sichtbar, der Mesh-Teilnehmer als „Mesh über …“, STOP für jedes Gerät bestätigt.
- [ ] Einen ESP32 ausschalten: nach 5 s (WLAN) bzw. 10 s (Mesh) rot/offline, die
      Meldung unter STOP nennt ihn.
- [ ] **WLAN / IP**: ESP32 im Hotspot mit Name und Firmware, Mesh-Geräte mit `Mesh/…`.
- [ ] Luxafor ohne Dongle gefunden, GATT verbunden, Aus funktioniert.
- [ ] Luxafor Orb per USB am Headend: Farben wie Bluetooth Pro, Blinken bei Überzeit, Aus bei Stop.
- [ ] Orb bei laufendem Timer abziehen und wieder einstecken: aktuelle Farbe kehrt zurück.
- [ ] Orb nach Kaltstart ohne Anmeldung/Root-Rechte angesteuert (udev-Regel, `plugdev`).
- [ ] Start 10 min: grün; Start 5 min: gelb; Start 1 min: orange.
- [ ] 1-min-Timer ablaufen lassen: rot bei 0, blinkend nach weiteren 30 s.
- [ ] Stop während Blinken: Licht aus, Display READY, Übernahme bestätigt.
- [ ] Schnell Start 30 → Start 1 → Stop: zuletzt gewünschter Zustand bleibt.
- [ ] Luxafor kurz ausschalten: BLE offline erkennbar, Countdown läuft weiter.
- [ ] Luxafor wieder einschalten: aktuelle Farbe wird wiederhergestellt.
- [ ] WLAN für 60 s ausschalten: Display zählt ohne Sprung/Stillstand weiter;
      Farbe wechselt lokal, Headend meldet ESP32 offline.
- [ ] Während Ausfall Stop am Pi: als unbestätigt/offline angezeigt; nach
      WLAN-Rückkehr wird Stop angewendet, kein alter Start nachgeliefert.
- [ ] Native App: sieben Zeitknöpfe und STOP bei 1024×600 vollständig sichtbar und bedienbar.
- [ ] Native App nach Kaltstart ohne Tastatur/Schlüsseleingabe bereit.
- [ ] App bei laufendem Timer schließen und neu starten: aktueller Countdown bleibt erhalten.
- [ ] CPU/RAM/Swap und Startzeit auf dem Pi erfassen; nach einer Stunde erneut messen.
- [ ] Optionale Weboberfläche neu laden: aktueller Timer wird übernommen.
- [ ] Pi-Server neu starten: neue Sitzung/Stop wird übernommen.
- [ ] ESP32 neu starten: bei Verbindung aktueller Countdown, ohne Verbindung READY.
- [ ] 20–30 m mit Personen im Raum: mindestens 1 h laufen lassen, Start-/Stop-
      Latenzen und Abbrüche protokollieren. Ziel im verbundenen Betrieb < 2 s.
- [ ] Mehrstündiger Dauertest: keine wachsenden Reconnect-Zeiten oder Speicherfehler.

Bei unzuverlässigem BLE zunächst exklusiven Zugriff, Ladestand und Pairing prüfen.
Bei unzuverlässigem WLAN Pi/Antennenposition und Kanalbelegung prüfen; alternativ
kann ein separater Access Point als gemeinsame WLAN-Infrastruktur verwendet werden.
Vor der Veranstaltung einen vollständigen Durchlauf und eine manuelle
Ersatzsignalisierung einplanen.
