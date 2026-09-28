# Architekturentscheidung

## Strecke und Zuständigkeit

Der Pi besitzt den Sollzustand. Auf dem ESP32 werden Zeit und Farbe aus einer
lokalen Replik berechnet. Der Pi arbeitet standardmäßig selbst als Access Point;
der ESP32 verbindet sich direkt mit ihm. Ein zusätzlicher Router oder Internet
ist nicht nötig. Pi-Adresse: `10.42.0.1`; der ESP32 erhält seine Adresse per DHCP.
BLE wird auf die kurze Strecke zum Luxafor begrenzt. Der ESP32-C6 unterstützt BLE,
kein Bluetooth Classic. Die Bluetooth-Pro-Referenz verwendet BLE-GATT.

Die Rollen sind Pi = AP/Server und ESP32 = Station/BLE-Central. Es handelt sich
um einen normalen WLAN-Hotspot, nicht IBSS-Ad-hoc oder Wi-Fi Direct. Die
NetworkManager-Konfiguration ist in [Direktes WLAN](../deploy/direct-wifi.md)
beschrieben. Gemeinsames WLAN ist eine alternative Konfiguration mit anderen
Zugangsdaten und anderer Pi-IP; ein automatischer Wechsel wird nicht vorgenommen.

Der AP am Pi macht die Konferenz unabhängig vom Veranstaltungsnetz.
WLAN verbessert die Architektur, garantiert aber keine Reichweite. Bei stark
gestörter Funkumgebung ist eine kabelgebundene Bühnenanbindung die weitere Option.

## Luxafor Orb am Headend

Der Timer-Server steuert eine per USB angeschlossene Luxafor Orb direkt (`orb.py`,
pyusb, Gerät `04d8:f372`). Ein Hintergrundthread leitet alle 200 ms die Phase aus
demselben Timerzustand ab, den auch der ESP32 erhält, und sendet nur bei einem
Phasenwechsel. Die USB-Befehle entsprechen `luxafor-linux.py` aus dem ursprünglichen
Projekt (Farbe `[1, 255, r, g, b, 0, 0]`, Überzeit als Strobe `[3, 255, 255, 0, 0, 15, 0, 30]`).
Statt einzeln geplanter Befehle folgt die Orb so jedem Start, Stop und Ersatz-Start.
Alle 2 s wird geprüft, ob sich die angeschlossenen Lampen geändert haben; nach
erneutem Einstecken erhält die Orb die aktuelle Farbe. Fehlen pyusb, libusb oder
die Orb, läuft der Timer unverändert weiter. `/api/state`, `/api/start` und
`/api/stop` enthalten `"orb": {"connected": …, "status": …}`; `PI_TIMER_ORB=0` schaltet
die Ansteuerung ab. Die Orb meldet keine sichtbare LED-Farbe zurück.

## Warum HTTP-Polling

Am Headend läuft standardmäßig eine native Tkinter-Touch-App direkt auf X11.
Sie verwendet dieselbe API wie die optionale Weboberfläche. Der einzelne
Timer-Server läuft unabhängig als Dienst; ein Fensterneustart ändert seinen
Zustand nicht. HTTP läuft in einem Hintergrundthread, Tk ausschließlich im
GUI-Thread. Details: [Native Oberfläche](NATIVE_UI.md).

Ein Pi und ein ESP32 benötigen keinen Broker. Eine kleine JSON-Abfrage alle
500 ms genügt für Start/Stop eines Vortragstimers. Der normale Übertragungsweg
braucht bis zu einem Pollintervall plus Netzwerklaufzeit. Bei Verbindungsfehlern
steigt der Wiederholungsabstand bis 5 s. BLE-Reconnect wartet bis 15 s zwischen
Versuchen und scannt zusätzlich bis 5 s. Dies ist kein Echtzeitsystem.

Ein WebSocket/MQTT-Push kann später die Latenz reduzieren; die Zustandsreplikation
muss dabei erhalten bleiben. Ein einzelner verlorener Start darf keinen Timer verlieren.

## Protokoll v1

Alle `/api/*`-Routen benötigen `Authorization: Bearer <PI_TIMER_TOKEN>`.
POST verlangt `Content-Type: application/json`. Keine CORS-Freigabe. Fehler
(auch ungültiges JSON) werden als `{"error": "..."}` mit passendem Statuscode beantwortet.

| Route | Bedeutung |
|---|---|
| `GET /api/state` | Timer + zuletzt gemeldeter Gerätestatus |
| `POST /api/start` mit `{"minutes": 25}` | Neuen Countdown starten/ersetzen; Antwort wie `GET /api/state` |
| `POST /api/stop` mit `{}` | Sollzustand Stop; Antwort wie `GET /api/state` |
| `POST /api/device/sync` | Vorher übernommene Revision melden, aktuellen Sollzustand holen |

Gerätemeldung:

```json
{"session":null,"revision":-1,"ble_connected":false,"ble_status":"Suche Luxafor"}
```

Antwort an den ESP32 (Beispiel; ohne den Gerätestatus der Bedien-Antworten):

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
kann trotzdem bedeuten, dass der Server den Befehl übernommen hat; die Bedienoberfläche
fragt danach den Zustand ab, statt einen Start blind zu wiederholen.

## Grenzen

- Ein Headend, ein ESP32 und ein Luxafor; mehrere Nodes benötigen eigene IDs und
  separate Statusverwaltung.
- Timer überlebt WLAN-Ausfall, aber keinen Neustart des ESP32 ohne erreichbaren Pi.
- Serverzustand liegt im RAM und wird bei Prozess-Neustart auf Stop gesetzt.
- BLE Write-without-response bestätigt nur das lokale Absenden, keine LED-Farbe.
- Kein garantierter Stop bei vollständigem Netzwerkausfall.
- Pakete und Firmware werden vorab mit Internet vorbereitet; der Veranstaltungsbetrieb
  und der Countdown benötigen kein Internet. Ein Pi-Neustart unterbricht im
  Direktbetrieb sowohl den Server als auch dessen WLAN; der ESP32 verbindet sich erneut.
