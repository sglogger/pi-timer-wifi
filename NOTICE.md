# Herkunft

Dieses Projekt ist eine Neufassung des Konferenztimers von
[Steven / sglogger](https://github.com/sglogger/pi-timer).

`firmware/st7789.py` wurde aus `ESP32-C6/st7789.py` dieses ursprünglichen Projekts
übernommen. Display-Pinbelegung und Farbwerte stammen ebenfalls aus der dort
vorhandenen, auf das Waveshare ESP32-C6-LCD-1.47 abgestimmten Implementierung.
Das ursprüngliche Repository enthielt zum Zeitpunkt der Übernahme keine
separate Lizenzdatei. Hier wird keine neue Lizenz für fremde Bestandteile erklärt.

Die BLE-Protokollreferenzen sind in [docs/ble-protocol.md](docs/ble-protocol.md)
verlinkt. Diese wurden zur Interoperabilität ausgewertet; ihre Implementierungen
wurden nicht kopiert. Flask, Waitress, MicroPython und aioble werden getrennt
installiert und behalten ihre jeweiligen Lizenzen.
