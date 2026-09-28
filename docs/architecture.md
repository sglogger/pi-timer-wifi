# Architekturentscheidung

## Strecke und Zuständigkeit

Der Pi besitzt den Sollzustand. Auf dem ESP32 werden Zeit und Farbe aus einer
lokalen Replik berechnet. WLAN überbrückt die Entfernung über einen Access Point;
BLE wird auf die kurze Strecke zum Luxafor begrenzt. Der ESP32-C6 unterstützt BLE,
kein Bluetooth Classic. Die Bluetooth-Pro-Referenz verwendet BLE-GATT.

Ein dedizierter AP ist für eine Konferenz vorhersehbarer als ein offenes Gastnetz.
WLAN verbessert die Architektur, garantiert aber keine Reichweite. Bei stark
gestörter Funkumgebung ist eine kabelgebundene Bühnenanbindung die weitere Option.

## Warum HTTP-Polling

Ein Pi und ein ESP32 benötigen keinen Broker. Eine kleine JSON-Abfrage alle
500 ms genügt für Start/Stop eines Vortragstimers. Der normale Übertragungsweg
braucht bis zu einem Pollintervall plus Netzwerklaufzeit. Bei Verbindungsfehlern
steigt der Wiederholungsabstand bis 5 s. BLE-Reconnect wartet bis 15 s zwischen
Versuchen und scannt zusätzlich bis 5 s. Dies ist kein Echtzeitsystem.

Ein WebSocket/MQTT-Push kann später die Latenz reduzieren; die Zustandsreplikation
muss dabei erhalten bleiben. Ein einzelner verlorener Start darf keinen Timer verlieren.

## Protokoll v1

Alle `/api/*`-Routen benötigen `Authorization: Bearer <PI_TIMER_TOKEN>`.
POST verlangt `Content-Type: application/json`. Keine CORS-Freigabe.

| Route | Bedeutung |
|---|---|
| `GET /api/state` | Timer + zuletzt gemeldeter Gerätestatus |
| `POST /api/start` mit `{"minutes": 25}` | Neuen Countdown starten/ersetzen |
| `POST /api/stop` mit `{}` | Sollzustand Stop |
| `POST /api/device/sync` | Vorher übernommene Revision melden, aktuellen Sollzustand holen |

Gerätemeldung:

```json
{"session":null,"revision":-1,"ble_connected":false,"ble_status":"Suche Luxafor"}
```

Antwort (Beispiel):

```json
{"protocol":1,"session":"a-server-boot-uuid","revision":3,"remaining_ms":1423500,"phase":"green"}
```

`session` ändert sich bei Serverstart. `revision` steigt bei jedem Start/Stop;
periodische Snapshots derselben Revision korrigieren Zeitdrift. `remaining_ms: null`
bedeutet Stop, negative Werte Überzeit. Es gibt keine Warteschlange alter Befehle.
Ein Stop während eines Ausfalls wird beim nächsten Sync angewendet, sofern er
nicht durch einen späteren Start ersetzt wurde.

Der ESP32 korrigiert grob um die halbe Roundtrip-Zeit und verwirft Antworten über
2 s Laufzeit. Das ist eine Näherung bei asymmetrischem WLAN, keine präzise
Uhrensynchronisation. Beide Seiten benutzen monotone Uhren, kein Datum/NTP.
MicroPython-Tick-Wrap wird durch regelmäßiges `ticks_diff` berücksichtigt.

Die Übernahme erscheint erst in der folgenden Gerätemeldung als bestätigt.
Geräte gelten nach 5 s ohne Meldung als offline. Ein HTTP-Timeout nach Start/Stop
kann trotzdem bedeuten, dass der Server den Befehl übernommen hat; der Browser
fragt danach den Zustand ab, statt einen Start blind zu wiederholen.

## Grenzen

- Ein Headend, ein ESP32 und ein Luxafor; mehrere Nodes benötigen eigene IDs und
  separate Statusverwaltung.
- Timer überlebt WLAN-Ausfall, aber keinen Neustart des ESP32 ohne erreichbaren Pi.
- Serverzustand liegt im RAM und wird bei Prozess-Neustart auf Stop gesetzt.
- BLE Write-without-response bestätigt nur das lokale Absenden, keine LED-Farbe.
- Kein garantierter Stop bei vollständigem Netzwerkausfall.
