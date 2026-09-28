# Copy to config.py on the ESP32. Do not commit credentials.
# Default: Pi hotspot; see deploy/direct-wifi.md.
# For an existing WLAN, replace SSID/password AND SERVER_IP with that network's values.
WIFI_SSID = "SwiNOG-Timer"
WIFI_PASSWORD = "PASSWORD-FROM-HOTSPOT-SETUP"
# Numeric IPv4 avoids blocking DNS lookups in MicroPython's event loop.
SERVER_IP = "10.42.0.1"
SERVER_PORT = 8000
API_TOKEN = "REPLACE-WITH-TOKEN-FROM-PI"
# Run scan.py, then enter the exact device name (or MAC below).
LUXAFOR_NAME = "LUX DOT YOUR-DEVICE"
LUXAFOR_MAC = ""
# Set True only if your firmware requires pairing before GATT access.
LUXAFOR_PAIR = False
