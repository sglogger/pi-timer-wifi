# Änderungen

## Native Pi-Oberfläche (28.09.2026)

- Tkinter-Touch-App als Standard für den Pi Zero 2 W, direkt auf X11 ohne Browser.
- Lokaler Schlüssel wird aus `.env` geladen; keine Eingabe nach dem Einschalten.
- Separater Timer-Dienst erhält den Countdown beim Neustart der Oberfläche.
- Serieller HTTP-Worker, begrenzte Warteschlangen und keine automatischen Start-Wiederholungen.
- Tests für Offline-Anzeige, veraltete Antworten, verlorene Start-Antworten und
  nativen HTTP-Transport; eigener Linux-CI-Test für 1024×600-Layout und Touch-Tasten.
- Installations-/Betriebsanleitungen auf native App umgestellt; Desktop und Web optional.

## Aufbau- und Betriebsanleitungen (28.09.2026)

- Durchgehende Erstinstallation: Pi OS Lite, Touch-Display/Kiosk, Server-Dienst,
  ESP32-Sicherung/Flashen, Konfiguration und Offline-Inbetriebnahme.
- Build-Anleitung mit Syntaxprüfung und optionalem MicroPython-Eigenbau
  (`v1.28.0`, ESP-IDF `v5.5.1`, Board `ESP32_GENERIC_C6`).
- Betriebshandbuch für Statusanzeigen, Diagnose, Updates, Sicherungen und Rollback.
- X11-Kiosk-Startdatei für frische Pi-OS-Lite-Installationen.

## Direktes WLAN (28.09.2026)

- Standardaufbau für Veranstaltungen ohne Infrastruktur: Pi Zero 2 W stellt das
  WLAN `SwiNOG-Timer` bereit, ESP32 verbindet sich direkt; kein Router/Internet nötig.
- NetworkManager-Einrichtung mit WPA2, individuellem Passwort, DHCP und fester
  Pi-Adresse `10.42.0.1`. Aktivierung und Autostart werden separat eingeschaltet.
- Gemeinsames WLAN bleibt als alternative Konfiguration dokumentiert.
- Vorbereitung mit Internet und anschließender vollständig offline erfolgender
  Kaltstart-/Reichweitentest beschrieben. Hardware-Abnahme weiterhin offen.

## Erste Version (28.09.2026)

- Pi-Headend, WLAN-Synchronisation, ESP32-Display und direkte Luxafor-Pro-BLE-Steuerung.
- Monotoner Offline-Countdown, Wiederverbindung und Übernahmebestätigung.
