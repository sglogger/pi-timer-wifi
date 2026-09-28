# Abnahme vor Konferenzeinsatz

## Bereits automatisiert prüfbar

`python -m unittest discover -s tests -v` prüft Timergrenzen, kurze Presets,
Start/Stop-Ersetzung, Gerätemeldungen, API-Eingaben, Zugriffsschlüssel,
Offline-Countdown, Reconnect, Server-Neustart, Tick-Wrap und HTTP-Transport.
Diese Tests ersetzen keinen Funk-/Hardwaretest.

Entwicklungsprüfung am 28.09.2026: **32 Tests erfolgreich** unter Python 3.14,
einschließlich eines simulierten GATT-Geräts, echter lokaler TCP-Verbindungen und
Hotspot-Vorbereitung mit simuliertem NetworkManager. Der Hotspot-Test prüft auch,
dass bestehende Profile erhalten bleiben und das Setup keine Verbindung aktiviert.
Alle acht Firmware-Quelldateien wurden mit mpy-cross 1.29.0.post2 kompiliert.
Browserprüfung mit simuliertem Knoten: Anmeldung, Start, Ein-Minuten-Preset,
Neuladen mit laufendem Timer, bestätigter Stop und getrennte BLE-Statusanzeige.
Eine Ausführung auf ESP32-C6 und Luxafor wurde dabei nicht durchgeführt.

## Hardwareprotokoll – noch offen

Datum, MicroPython-Version, aioble-Version/Commit, Luxafor-Firmware, AP/Kanal,
Abstand und Hindernisse für den Test notieren. Bis alle Punkte geprüft sind,
diese Version als Prototyp behandeln.

- [ ] ESP32-Display: lesbarer Countdown im Querformat, Farben stimmen.
- [ ] Pi-Hotspot aktiv: `SwiNOG-Timer`, WPA2, Pi-IP `10.42.0.1`, ESP32 erhält DHCP-Adresse.
- [ ] Kaltstart ohne Router/Internet: erst Pi, dann ESP32; Verbindung entsteht automatisch.
- [ ] Umgekehrte Einschaltreihenfolge: ESP32 zuerst, Pi später; automatische Verbindung.
- [ ] Pi-Neustart: Hotspot und Timer-Dienst starten erneut, ESP32 übernimmt neue Sitzung/Stop.
- [ ] Luxafor ohne Dongle gefunden, GATT verbunden, Aus funktioniert.
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
- [ ] Browser neu laden: aktueller Timer wird übernommen.
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
