# Copy to config.py on the ESP32. Do not commit credentials.
# Default: Pi hotspot; see deploy/direct-wifi.md.
# For an existing WLAN, replace SSID/password AND SERVER_IP with that network's values.
WIFI_SSID = "SwiNOG-Timer"
WIFI_PASSWORD = "PASSWORD-FROM-HOTSPOT-SETUP"
# Numeric IPv4 avoids blocking DNS lookups in MicroPython's event loop.
SERVER_IP = "10.42.0.1"
SERVER_PORT = 8000
API_TOKEN = "REPLACE-WITH-TOKEN-FROM-PI"
# Recommended with several devices: name in the headend's device list and
# "WLAN / IP" overlay and top right on the ESP32 display (first 25 characters),
# e.g. "saal-1". Letters, digits and "-" only. Empty: the headend shows the MAC.
HOSTNAME = ""
# ESP-NOW mesh (experimental): devices without Wi-Fi take the timer from peers
# that have it. All devices need the same API_TOKEN. Off by default: on the
# ESP32-C6 an active ESP-NOW stopped HTTP sync and BLE (ENOMEM) in a hardware test.
MESH = False
# False: this device never joins the hotspot and gets the timer only through the
# mesh from a nearby ESP32 that has Wi-Fi (MESH is then on automatically).
# WIFI_SSID/WIFI_PASSWORD/SERVER_IP are ignored; API_TOKEN must still match.
WIFI = True
# Board: empty = detected from the chip (ESP32-C6-LCD-1.47 or ESP32-S3-LCD-1.69 V2).
# "s3-169-v1" for the first S3 revision without the "V2QC" label (other power pin).
BOARD = ""
# Run scan.py, then enter the exact device name (or MAC below).
LUXAFOR_NAME = "LUX DOT YOUR-DEVICE"
LUXAFOR_MAC = ""
# Set True only if your firmware requires pairing before GATT access.
LUXAFOR_PAIR = False
