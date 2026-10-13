# Direkte Luxafor-Bluetooth-Pro-Anbindung

Luxafor beschreibt beim [Bluetooth Pro](https://luxafor.com/product/bluetooth-pro/)
eine direkte Bluetooth-Verbindung als Alternative zum Dongle. Das bisherige
`luxafor-linux.py` schreibt dagegen **USB-HID-Befehle an den Dongle**.
Die alten UUIDs `48593a1c-…` und `9f3c7b34-…` gehören zum eigenen ESP32-Timerdienst,
nicht zum Luxafor. Sie werden in der neuen Architektur nicht verwendet.

## Öffentlich nachvollziehbare Referenz

Die direkte BLE-Implementierung des Projekts
[AlixAbbasi/LuxaforStatusBar](https://github.com/AlixAbbasi/LuxaforStatusBar)
beschreibt einen Bluetooth-Pro-Client:

- [LuxaforBLEDevice.swift](https://github.com/AlixAbbasi/LuxaforStatusBar/blob/main/LuxaforStatusBar/LuxaforBLEDevice.swift):
  GATT-UUIDs, Notify-Abonnement, Initialisierung, Sleep-/Ready-Meldungen.
- [LuxaforColor.swift](https://github.com/AlixAbbasi/LuxaforStatusBar/blob/main/LuxaforStatusBar/LuxaforColor.swift):
  BLE-Befehle unterscheiden sich von USB-Befehlen.

Das ist eine Protokollreferenz aus einer Geräteimplementierung, keine hier
verifizierte Herstellerzusage für alle Firmwarestände. Die Firmware in diesem
Repository ist eigenständig geschrieben; kein Swift-Quellcode wurde übernommen.

| Zweck | UUID |
|---|---|
| Service | `00001234-0000-1000-8000-00805f9b34fb` |
| Schreiben | `00001235-0000-1000-8000-00805f9b34fb` |
| Notifications | `00001236-0000-1000-8000-00805f9b34fb` |

Verwendete 8-Byte-Befehle, hexadezimal:

```text
Farbe:   A1 FF RR GG BB 10 10 10
Aus:     A1 FF 00 00 00 10 10 10
Blinken: A3 FF FF 00 00 0F 00 00
```

Der ESP32 entdeckt Service und Characteristics neu, abonniert Notifications,
wartet bis zu 2 s auf eine Meldung, sendet Aus, wartet 400 ms und setzt den
aktuellen Zustand. Er aktualisiert bei Phasenwechsel und spätestens alle 5 s.
Ready-/Sleep-Meldungen lösen ebenfalls eine Aktualisierung aus. `1\r` ist keine
davon: Die Lampe (LUX DOT, Bluetooth Pro) bestätigt damit jeden Schreibbefehl, etwa
90 ms danach (gemessen mit `firmware/ble_test.py`); nach dem Abonnieren kam keine
Ready-Meldung.
aioble wählt Write-without-response, wenn die Characteristic dies unterstützt,
ansonsten Write-with-response. Auch eine GATT-Schreibbestätigung bestätigt nur
die Protokolloperation, nicht die sichtbare Lichtfarbe.

Der bisherige Dongle und Telefon-/Desktop-App dürfen die Lampe währenddessen
nicht exklusiv verbunden halten. Bei GATT-Authentifizierungsfehlern ist die
konfigurierbare Pairing-Variante vor Ort zu prüfen.

## Plattformquellen

- [Espressif: ESP32-C6 Bluetooth-Fähigkeiten](https://docs.espressif.com/projects/esp-idf/en/latest/esp32c6/api-guides/bt-architecture/overview.html)
- [MicroPython aioble API und Beispiele](https://github.com/micropython/micropython-lib/tree/master/micropython/bluetooth/aioble)
- [MicroPython asyncio](https://docs.micropython.org/en/latest/library/asyncio.html)

Recherche: 28.09.2026. **Auf der Hardware bestätigt (13.10.2026)** mit einer Luxafor
Bluetooth Pro (`LUX DOT …`) und `firmware/ble_test.py`: Service `1234`, Schreiben auf
`1235` ohne Pairing, Notifications auf `1236`; die Lampe zeigte die gesendeten Farben
(rot, grün, aus). Bei Abweichungen mit anderen Lampen- oder Firmwareständen zuerst
GATT und Firmwareversion dokumentieren und `luxafor.py` anpassen; nicht beliebige
Characteristics mit geratenen Paketen beschreiben.
