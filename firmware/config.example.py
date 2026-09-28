# Copy to config.py on the ESP32. Do not commit credentials.
WIFI_SSID = "YOUR-2.4-GHZ-WIFI"
WIFI_PASSWORD = "YOUR-WIFI-PASSWORD"
# Numeric IPv4 avoids blocking DNS lookups in MicroPython's event loop.
SERVER_IP = "192.168.10.10"
SERVER_PORT = 8000
API_TOKEN = "REPLACE-WITH-TOKEN-FROM-PI"
# Run scan.py, then enter the exact device name (or MAC below).
LUXAFOR_NAME = "LUX DOT YOUR-DEVICE"
LUXAFOR_MAC = ""
# Set True only if your firmware requires pairing before GATT access.
LUXAFOR_PAIR = False
