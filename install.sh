#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
if [[ ! -f .env ]]; then
  (umask 077; .venv/bin/python -c 'import secrets; print("PI_TIMER_TOKEN=" + secrets.token_hex(24)); print("PI_TIMER_HOST=0.0.0.0"); print("PI_TIMER_PORT=8000")' > .env)
fi
printf '%s\n' 'Installation fertig. Token in .env ansehen und in firmware/config.py eintragen.' 'Server: ./run.sh' 'Touch-App (X11 + python3-tk): ./run-native.sh' 'Autostart: siehe deploy/README.md'
