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
| `GET /api/state` | Timer + Status aller ESP32 (`devices`) |
| `POST /api/start` mit `{"minutes": 25}` | Neuen Countdown starten/ersetzen; Antwort wie `GET /api/state` |
| `POST /api/stop` mit `{}` | Sollzustand Stop; Antwort wie `GET /api/state` |
| `POST /api/device/sync` | Vorher übernommene Revision melden, aktuellen Sollzustand holen |

Gerätemeldung (`id` = MAC, `name` = `HOSTNAME`, `peers` = per Mesh gehörte Geräte
ohne WLAN mit Alter der Meldung):

```json
{"id":"a1b2c3d4e5f6","name":"saal-1","session":null,"revision":-1,"ble_connected":false,
 "ble_status":"Suche Luxafor","firmware":"1.2.0",
 "peers":[{"id":"0a1b2c3d4e5f","name":"saal-2","session":null,"revision":-1,"ble_connected":true,
           "ble_status":"BLE verbunden; Befehl gesendet","firmware":"1.2.0","age_ms":2300}]}
```

Firmware vor 1.2.0 sendet weder `id` noch `peers`; der Server führt sie pro
IP-Adresse (`ip-10.42.0.23`). Ungültige `peers`-Einträge werden einzeln verworfen.

`devices` in `GET /api/state` (eine Zeile pro Gerät, nach Name sortiert):

```json
{"id":"0a1b2c3d4e5f","name":"saal-2","via":"mesh","relay":"saal-1","online":true,
 "age_s":2.3,"timeout_s":10,"applied":true,"ble_connected":true,
 "ble_status":"BLE verbunden; Befehl gesendet",
 "firmware":{"version":"1.2.0","expected":"1.2.0","current":true}}
```

`via` ist `wifi` (direkte Meldung, offline nach 5 s) oder `mesh` (weitergeleitet,
offline nach 10 s). Pro Gerät gilt die neueste Meldung; eine direkte Meldung ersetzt
immer eine weitergeleitete. Höchstens 16 Geräte; ohne Meldung für 30 Minuten
verschwindet ein Gerät aus der Liste.

Antwort an den ESP32 (Beispiel; ohne den Gerätestatus der Bedien-Antworten):

```json
{"protocol":1,"session":"a-server-boot-uuid","revision":3,"remaining_ms":1423500,"phase":"green","stamp":[214000000,81500]}
```

`session` ändert sich bei Serverstart. `stamp` ordnet Zustände im
[ESP-NOW-Mesh](#esp-now-mesh-zwischen-den-esp32); ältere Firmware ignoriert ihn. `revision` steigt bei jedem Start/Stop;
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

## ESP-NOW-Mesh zwischen den ESP32

Mehrere ESP32 bilden nebenbei ein gleichberechtigtes Mesh über ESP-NOW. Es gibt
keinen festen Master: **Der aktuellste Zustand gewinnt.** Jede Server-Antwort trägt
einen Stempel `stamp: [Generation, ms]`. `ms` zählt seit dem Serverstart, die
Generation steigt bei jedem Serverstart und liegt in
`/var/lib/pi-timer-wifi/generation` (systemd `StateDirectory`). So bleibt sie auch
nach Stromausfall ohne Uhr monoton.

- Jeder ESP32 mit Zustand sendet alle 0,5–0,63 s einen Broadcast mit Session,
  Revision, aktueller Restzeit und dem Stempel seines Zustands.
- Ein Empfänger übernimmt nur einen **strikt neueren Stempel**. Geräte mit WLAN
  erhalten alle 500 ms einen frischen Stempel vom Server und sind dadurch automatisch
  die Quelle. Geräte ohne WLAN geben den übernommenen Stempel unverändert weiter;
  so erreicht der Zustand auch Geräte, die nur einen anderen ESP32 ohne WLAN hören
  (Multi-Hop, etwa eine Sendeperiode pro Hop).
- Fällt der Pi aus, haben alle denselben letzten Stempel; niemand übernimmt etwas,
  alle zählen lokal weiter und zeigen `WIFI OFFLINE`.
- **Status zurück zum Pi:** Ein Gerät ohne frische Server-Verbindung sendet alle 2 s
  ein Statuspaket (ID, Name, Revision, Luxafor, Firmware, Alter). Geräte ohne WLAN
  leiten fremde Statuspakete weiter (jüngstes pro Gerät, bis 10 s alt); ein Gerät
  mit WLAN sendet sie als `peers` mit seinem nächsten Abgleich an den Pi.
- Das Display zeigt `WIFI OK` (eigene Server-Verbindung), `MESH OK` (frischer
  Server-Zustand über einen anderen ESP32 innerhalb von 5 s) oder `WIFI OFFLINE`.

**Sicherheit:** Broadcasts lassen sich mit ESP-NOW nicht verschlüsseln. Jedes Paket
trägt deshalb ein HMAC-SHA256-Tag (16 Bytes) mit `API_TOKEN` als Schlüssel; fremde
oder veränderte Pakete werden verworfen. Ein mitgeschnittenes altes Paket verliert
gegen jeden neueren Stempel. Nur ein frisch gestartetes Gerät ohne jeden Zustand
könnte es kurz übernehmen, bis das nächste echte Paket eintrifft. Der Timerinhalt
selbst ist nicht vertraulich.

**Kanal:** ESP-NOW und WLAN teilen sich das Funkmodul. Geräte mit WLAN senden auf
dem Hotspot-Kanal. Ein Gerät ohne WLAN bleibt nach einem Fehlversuch auf dem
zuletzt bekannten Hotspot-Kanal oder sucht 1, 6 und 11 ab (je 1,5 s), bis es Pakete
hört. Solange das Mesh frische Server-Zustände liefert, versucht es das WLAN nur alle 30 s erneut, weil der
Verbindungsversuch (bis 10 s) die Kanäle wechselt und ESP-NOW-Pakete verpasst.
Wählt der Pi nach einem Neustart einen anderen Kanal, finden die Geräte ihn so wieder.

**Empfang mit WLAN:** Mit WLAN-Verbindung ist auf dem ESP32 wegen BLE der
WLAN-Energiesparmodus vorgeschrieben; Mesh-Pakete kommen dann unzuverlässig an.
Diese Geräte brauchen sie nicht, sie senden nur. Die Weiterleitung hängt an Geräten
ohne WLAN, die ständig empfangen.

**Experimentell, standardmäßig aus:** Im Hardwaretest (ESP32-C6, MicroPython 1.28,
WLAN + BLE + ESP-NOW auf einem Funkmodul) liefen mit aktivem ESP-NOW alle
HTTP-Abgleiche in den Timeout, obwohl Kanal (6) und Signal (−70 dBm) passten; der
Pi empfing keine Pakete des ESP32, BLE meldete `ENOMEM`. Dasselbe trat später auch
ohne ESP-NOW auf: Ursache war ein Socket-Leck im HTTP-Abgleich (in Firmware 1.2.3
behoben, siehe CHANGELOG), das ESP-NOW nur schneller auslöste. Bis ein erneuter
Hardwaretest das Mesh bestätigt, bleibt es aus. `MESH = True` in `config.py`
schaltet es pro Gerät ein. Server ohne Stempel
(vor Pi-Software 1.2.0) deaktivieren es automatisch.

## Grenzen

- Ein Headend; mehrere ESP32 zeigen denselben Timer. Statusmeldungen über das Mesh
  sind nur signiert, nicht gegen Wiedereinspielen geschützt; sie zeigen Zustand an,
  steuern aber nichts.
- Timer überlebt WLAN-Ausfall, aber keinen Neustart des ESP32 ohne erreichbaren Pi.
- Serverzustand liegt im RAM und wird bei Prozess-Neustart auf Stop gesetzt.
- BLE Write-without-response bestätigt nur das lokale Absenden, keine LED-Farbe.
- Kein garantierter Stop bei vollständigem Netzwerkausfall.
- Pakete und Firmware werden vorab mit Internet vorbereitet; der Veranstaltungsbetrieb
  und der Countdown benötigen kein Internet. Ein Pi-Neustart unterbricht im
  Direktbetrieb sowohl den Server als auch dessen WLAN; der ESP32 verbindet sich erneut.
