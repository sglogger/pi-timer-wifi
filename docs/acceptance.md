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

Busy Tag am Headend (14.10.2026, **108 Tests erfolgreich**): `tests/test_busytag.py`
prüft die serielle Ansteuerung gegen ein simuliertes Gerät an einem Pseudo-Terminal:
Erkennung (`AT+GDN`), Hochladen nur fehlender oder geänderter Bilder, Ersetzen des
gerade angezeigten Bildes, Phasenfarben und -bilder, Blinken im 0,5-s-Takt über die
Serverschleife, Fehlerantworten, Zeitüberschreitung und den zusammengefassten Status
beider Lampen. Zusätzlich am Mac mit einer echten Busy Tag (Firmware 1.0): Hochladen,
alle Phasen einschließlich Blinken ohne Fehlermeldung. Darstellung am Gerät und
Betrieb am Pi sind noch abzunehmen (Checkliste unten).

Ein zusätzlicher nativer GUI-Test (`tests/ui_smoke.py`) prüft die 1024×600-
Darstellung einschließlich negativer dreistelliger Minutenanzeige, alle acht
Touch-Tasten, deren Mindesthöhe und das Schließen ohne STOP. Er läuft separat
unter Linux/Xvfb in der CI und wurde auch lokal mit Tk ausgeführt. Die native
App benötigt weiterhin eine Prüfung auf dem echten Pi auf Startzeit, CPU/RAM
und Touch-Bedienung.

## Hardwareprotokoll

Datum, MicroPython-Version, aioble-Version/Commit, Luxafor-Firmware, AP/gewählter Kanal, Anzahl ESP32,
Abstand und Hindernisse für den Test notieren. Bis alle Punkte geprüft sind,
diese Version als Prototyp behandeln.

Stand 13.10.2026 (Pi-Software 1.5.0, ESP32-Firmware 1.4.0): Grundbetrieb, Mesh mit
zwei ESP32, Ausfälle und native App auf der Hardware geprüft. Offen sind Mesh über
zwei Hops, fremder `API_TOKEN`, Statusanzeige mit drei ESP32, die Luxafor Orb,
CPU/RAM-Messung auf dem Pi und der Reichweitentest im Saal.

- [x] ESP32-Display: lesbarer Countdown im Querformat, Farben stimmen.
- [x] Pi-Hotspot aktiv: `SwiNOG-Timer`, WPA2, Pi-IP `10.42.0.1`, ESP32 erhält DHCP-Adresse.
- [x] Kaltstart ohne Router/Internet: erst Pi, dann ESP32; Verbindung entsteht automatisch.
- [x] Umgekehrte Einschaltreihenfolge: ESP32 zuerst, Pi später; automatische Verbindung.
- [x] Pi-Neustart: Hotspot und Timer-Dienst starten erneut, ESP32 übernimmt neue Sitzung/Stop.
- [x] Kanalwahl: `journalctl -u pi-timer-hotspot-channel -b` zeigt Belegung und gewählten
      Kanal; nach Neustart mit anderem Kanal verbinden sich alle ESP32 wieder.
- [x] Mesh (`MESH = True` auf allen Geräten): WLAN-Abgleich und BLE bleiben bei aktivem
      ESP-NOW stabil (im ersten Test nicht der Fall, siehe Architektur).
- [x] Mesh: zweiten ESP32 mit `WIFI = False` (oder außerhalb der Hotspot-Reichweite)
      betreiben: Display `MESH OK`, Start/Stop kommen innerhalb von 2 s an.
- [x] Mesh: Gerät mit WLAN behält währenddessen seine BLE-Verbindung zur Luxafor.
- [ ] Mesh über zwei Hops: drei ESP32 in Kette, nur der erste mit WLAN.
- [ ] Mesh: ESP32 mit anderem `API_TOKEN` übernimmt keine Zustände.
- [x] Mesh: Pi ausschalten: alle zählen weiter, keiner springt, Displays zeigen `WIFI OFFLINE`.
- [ ] Statusanzeige: drei ESP32 mit `HOSTNAME`, einer nur über Mesh: alle drei getrennt
      sichtbar, der Mesh-Teilnehmer als „Mesh über …“, STOP für jedes Gerät bestätigt.
- [x] Einen ESP32 ausschalten: nach 5 s (WLAN) bzw. 10 s (Mesh) rot/offline, die
      Meldung unter STOP nennt ihn.
- [x] **WLAN / IP**: ESP32 im Hotspot mit Name und Firmware, Mesh-Geräte mit `Mesh/…`.
- [x] Luxafor ohne Dongle gefunden, GATT verbunden, Aus funktioniert (13.10.2026,
      `firmware/ble_test.py`: rot, grün, aus sichtbar, drei Runden `OK`).
- [x] ESP32-S3-LCD-1.69: Display, Drehung mit `FLIP` (13.10.2026, Firmware 1.3.1).
- [x] `FLIP = True` auf ESP32-C6-LCD-1.47 (13.10.2026).
- [x] ESP32-C6-Touch-LCD-1.47: Profil `c6-touch-147` automatisch erkannt, Display
      lesbar, Farben richtig, Drehung mit `FLIP` (13.10.2026, Firmware 1.4.0).
- [x] Reiner Mesh-Empfänger (`WIFI = False`, Firmware 1.3.2): verbindet die Luxafor
      nach dem Einschalten und nach Aus-/Einschalten der Lampe, Display `BLE OK` und
      `MESH OK`.
- [x] Fallback (`WIFI = True`, `MESH = True`, Hotspot aus): Luxafor verbindet nach
      dem Einschalten des ESP32 und nach Aus-/Einschalten der Lampe; nach Rückkehr
      des Hotspots wieder `WIFI OK`.
- [ ] Luxafor Orb per USB am Headend: Farben wie Bluetooth Pro, Blinken bei Überzeit, Aus bei Stop.
- [ ] Orb bei laufendem Timer abziehen und wieder einstecken: aktuelle Farbe kehrt zurück.
- [ ] Orb nach Kaltstart ohne Anmeldung/Root-Rechte angesteuert (udev-Regel, `plugdev`).
- [ ] Busy Tag am Headend: LED-Farben wie Orb, rotes Blinken bei Überzeit, Display
      „SwiNOG“ bei Stop und Phasentext während des Vortrags (am Mac geprüft, am Pi offen).
- [ ] Busy Tag bei laufendem Timer abziehen und wieder einstecken: Farbe und Bild kehren zurück.
- [x] Start 10 min: grün; Start 5 min: gelb; Start 1 min: orange.
- [x] 1-min-Timer ablaufen lassen: rot bei 0, blinkend nach weiteren 30 s.
- [x] Stop während Blinken: Licht aus, Display READY, Übernahme bestätigt.
- [x] Schnell Start 30 → Start 1 → Stop: zuletzt gewünschter Zustand bleibt.
- [x] Luxafor kurz ausschalten: BLE offline erkennbar, Countdown läuft weiter.
- [x] Luxafor wieder einschalten: aktuelle Farbe wird wiederhergestellt.
- [x] WLAN für 60 s ausschalten: Display zählt ohne Sprung/Stillstand weiter;
      Farbe wechselt lokal, Headend meldet ESP32 offline.
- [x] Während Ausfall Stop am Pi: als unbestätigt/offline angezeigt; nach
      WLAN-Rückkehr wird Stop angewendet, kein alter Start nachgeliefert.
- [x] Native App: sieben Zeitknöpfe und STOP bei 1024×600 vollständig sichtbar und bedienbar.
- [x] Native App nach Kaltstart ohne Tastatur/Schlüsseleingabe bereit.
- [x] App bei laufendem Timer schließen und neu starten: aktueller Countdown bleibt erhalten.
- [ ] CPU/RAM/Swap und Startzeit auf dem Pi erfassen; nach einer Stunde erneut messen.
- [x] Optionale Weboberfläche neu laden: aktueller Timer wird übernommen.
- [x] Pi-Server neu starten: neue Sitzung/Stop wird übernommen.
- [x] ESP32 neu starten: bei Verbindung aktueller Countdown, ohne Verbindung READY.
- [ ] 20–30 m mit Personen im Raum: mindestens 1 h laufen lassen, Start-/Stop-
      Latenzen und Abbrüche protokollieren. Ziel im verbundenen Betrieb < 2 s.
- [x] Mehrstündiger Dauertest: keine wachsenden Reconnect-Zeiten oder Speicherfehler.

Bei unzuverlässigem BLE zunächst exklusiven Zugriff, Ladestand und Pairing prüfen.
Bei unzuverlässigem WLAN Pi/Antennenposition und Kanalbelegung prüfen; alternativ
kann ein separater Access Point als gemeinsame WLAN-Infrastruktur verwendet werden.
Vor der Veranstaltung einen vollständigen Durchlauf und eine manuelle
Ersatzsignalisierung einplanen.
