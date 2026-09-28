# Änderungen

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
