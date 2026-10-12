# Änderungen

Versionsnummern nach [Semantic Versioning](https://semver.org/lang/de/): Fehlerkorrektur
→ dritte Stelle, neue Funktion → zweite Stelle, inkompatible Änderung (z. B. neue
ESP32-Firmware zwingend) → erste Stelle. Die aktuelle Version steht in `version.py`
und wird in der Touch-App (WLAN / IP) und der Weboberfläche angezeigt. Mit 0.7.1 lief
die Grundfunktion erstmals auf der Hardware (Hotspot, ESP32-WLAN, BLE-Verbindung);
1.0.0 ist die erste Version danach. Die ESP32-Firmware hat eine eigene Version
(`FIRMWARE_VERSION` in `firmware/timer_logic.py`); sie wird nur erhöht, wenn sich
Dateien ändern, die auf den ESP32 kopiert werden.

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
