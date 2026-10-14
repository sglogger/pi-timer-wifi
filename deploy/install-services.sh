#!/usr/bin/env bash
# Installs the systemd units and the Luxafor udev rule for the user who runs this
# script and for this checkout; no user name or path is hard-coded.
# Usage (as the timer user, not as root): deploy/install-services.sh [--hotspot]
set -euo pipefail

DIR="$(cd "$(dirname "$0")/.." && pwd)"
USER_NAME="${SUDO_USER:-$(id -un)}"
if [[ "$USER_NAME" == root ]]; then
  echo "Als Timer-Benutzer ausführen, nicht als root (sudo wird bei Bedarf selbst aufgerufen)." >&2
  exit 1
fi
if [[ ! -f "$DIR/.env" || ! -x "$DIR/.venv/bin/python" ]]; then
  echo "Zuerst ./install.sh ausführen (.env und .venv fehlen in $DIR)." >&2
  exit 1
fi

render() {
  sed -e "s#@USER@#$USER_NAME#g" -e "s#@DIR@#$DIR#g" "$DIR/deploy/$1" \
    | sudo tee "/etc/systemd/system/$1" >/dev/null
}

render pi-timer-wifi.service
render pi-timer-hotspot-channel.service

# Luxafor Orb per USB: write access for the group plugdev. Busy Tag (/dev/ttyACM*): dialout.
sudo install -m 644 "$DIR/deploy/99-luxafor.rules" /etc/udev/rules.d/99-luxafor.rules
sudo udevadm control --reload-rules
sudo udevadm trigger
for group in plugdev dialout; do
  id -nG "$USER_NAME" | grep -qw "$group" || sudo usermod -aG "$group" "$USER_NAME"
done

sudo systemctl daemon-reload
sudo systemctl enable pi-timer-wifi
sudo systemctl restart pi-timer-wifi
if [[ "${1:-}" == --hotspot ]]; then
  sudo systemctl enable pi-timer-hotspot-channel
fi

echo "Dienst pi-timer-wifi läuft als $USER_NAME aus $DIR: $(systemctl is-active pi-timer-wifi)"
