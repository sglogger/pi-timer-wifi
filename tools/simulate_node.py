"""CPython smoke test node (no hardware); loads PI_TIMER_TOKEN from environment.

PI_TIMER_NODE sets the device name (default sim-1); start several with different
names to see them listed separately on the headend.
"""
import json
import os
import time
from urllib.request import Request, urlopen

url = os.environ.get('PI_TIMER_URL', 'http://127.0.0.1:8000')
token = os.environ['PI_TIMER_TOKEN']
name = os.environ.get('PI_TIMER_NODE', 'sim-1')
report = dict(id=name, name=name, session=None, revision=-1, ble_connected=False,
              ble_status='Simulation: kein Luxafor', firmware='simulation')
while True:
    request = Request(url + '/api/device/sync', data=json.dumps(report).encode(),
                      headers={'Authorization':'Bearer ' + token, 'Content-Type':'application/json'})
    try:
        with urlopen(request, timeout=2) as response:
            state = json.load(response)
        if (state['session'], state['revision']) != (report['session'], report['revision']):
            print(state, flush=True)
        report.update(session=state['session'], revision=state['revision'])
    except Exception as exc:
        print(exc, flush=True)
    time.sleep(.5)
