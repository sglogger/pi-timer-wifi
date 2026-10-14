# Herkunft

Dieses Projekt ist eine Neufassung des Konferenztimers von
[Steven / sglogger](https://github.com/sglogger/pi-timer).

`firmware/st7789.py` wurde aus `ESP32-C6/st7789.py` dieses ursprünglichen Projekts
übernommen. Display-Pinbelegung und Farbwerte stammen ebenfalls aus der dort
vorhandenen, auf das Waveshare ESP32-C6-LCD-1.47 abgestimmten Implementierung.
Die JD9853-Initialisierungssequenz für das ESP32-C6-Touch-LCD-1.47 in
`firmware/st7789.py` stammt aus Waveshares Democode zu diesem Board
(`esp_lcd_jd9853.c`, [Download](https://docs.waveshare.com/ESP32-C6-Touch-LCD-1.47/Resources-And-Documents)).
Das ursprüngliche Repository enthielt zum Zeitpunkt der Übernahme keine
separate Lizenzdatei. Hier wird keine neue Lizenz für fremde Bestandteile erklärt.

Die Busy-Tag-Ansteuerung in `orb.py` folgt der
[USB-CDC-Befehlsreferenz](https://luxafor.helpscoutdocs.com/article/47-busy-tag-usb-cdc-command-reference-guide)
von Luxafor; [busytag_tool](https://github.com/acoster/busytag_tool) und
[busytag-lib](https://github.com/busy-tag/busytag-lib) dienten als Referenz für den
Ablauf. Code daraus wurde nicht übernommen.

Die BLE-Protokollreferenzen sind in [docs/ble-protocol.md](docs/ble-protocol.md)
verlinkt. Diese wurden zur Interoperabilität ausgewertet; ihre Implementierungen
wurden nicht kopiert. Flask, Waitress, MicroPython und aioble werden getrennt
installiert und behalten ihre jeweiligen Lizenzen.
