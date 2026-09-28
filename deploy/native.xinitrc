#!/bin/sh
# Default local touch frontend: X11 + native Tk, no browser or desktop shell.
xset s off || true
xset -dpms || true
xset s noblank || true

# Adapt this path when using a different repository location/user.
cd /home/pitimer/pi-timer-wifi || exit 1
# Restart only the frontend after a crash; the systemd timer service stays alive.
while true; do
    ./run-native.sh
    result=$?
    [ "$result" -eq 0 ] && exit 0
    sleep 3
done
