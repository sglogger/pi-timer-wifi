#!/bin/sh
# X11 session for a fresh Raspberry Pi OS Lite install; run as the normal user.
xset s off || true
xset -dpms || true
xset s noblank || true

# Try the local timer service 30 times (at most about 60 seconds).
attempt=0
while [ "$attempt" -lt 30 ]; do
    if curl --silent --fail --max-time 1 http://127.0.0.1:8000/ >/dev/null; then
        break
    fi
    attempt=$((attempt + 1))
    sleep 1
done

exec dbus-run-session -- sh -c 'openbox & exec falkon --fullscreen http://localhost:8000'
