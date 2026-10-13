"use strict";
const $ = id => document.getElementById(id);
const ui = JSON.parse($('ui-config').textContent);
class Unauthorized extends Error {}
let token = "";
try { token = sessionStorage.getItem("pi-timer-token") || ""; } catch (error) {}
let snapshot = null;
let sampledAt = 0;
let lastSuccess = 0;
let commandBusy = false;
let generation = 0;
let polling = false;

async function api(path, body, key = token) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 2500);
  try {
    const response = await fetch(path, {
      method: body === undefined ? "GET" : "POST",
      headers: {Authorization: `Bearer ${key}`, "Content-Type": "application/json"},
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: controller.signal, cache: "no-store"
    });
    if (response.status === 401) throw new Unauthorized("Zugriffsschlüssel fehlt oder ist ungültig.");
    if (!response.ok) throw new Error(`Serverfehler (${response.status})`);
    return await response.json();
  } finally { clearTimeout(timeout); }
}

// Stop polling with a rejected key, so a dismissed dialog stays closed.
function rejectToken() {
  token = "";
  try { sessionStorage.removeItem('pi-timer-token'); } catch (error) {}
  if (!$('login').open) $('login').showModal();
}

function accept(data, started) {
  snapshot = data;
  sampledAt = (started + performance.now()) / 2;
  lastSuccess = performance.now();
  render();
}

async function poll() {
  if (!token || polling || commandBusy) return;
  polling = true;
  const version = generation;
  const started = performance.now();
  try {
    const data = await api('/api/state');
    if (version === generation) accept(data, started);
  } catch (error) {
    if (error instanceof Unauthorized) rejectToken();
    else $('connection').textContent = "Server nicht erreichbar";
    $('feedback').textContent = error.message;
  } finally { polling = false; }
}

async function command(path, body) {
  if (commandBusy) return;
  commandBusy = true;
  ++generation; // Ignore a GET response that started before this command.
  document.querySelectorAll('.preset, #stop').forEach(el => el.disabled = true);
  try {
    const started = performance.now();
    accept(await api(path, body), started);
    $('feedback').textContent = "Gespeichert – warte auf ESP32-Bestätigung …";
  } catch (error) {
    if (error instanceof Unauthorized) rejectToken();
    $('feedback').textContent = `Befehl unbestätigt: ${error.message} Status wird neu abgefragt.`;
  } finally {
    commandBusy = false;
    document.querySelectorAll('.preset, #stop').forEach(el => el.disabled = false);
    poll();
  }
}

function render() {
  if (!snapshot) return;
  const now = performance.now();
  const fresh = now - lastSuccess < 4000;
  const remaining = snapshot.remaining_ms === null ? null : snapshot.remaining_ms - (now - sampledAt);
  const hit = remaining === null ? ['off'] : ui.thresholds.find(([, limit]) => remaining <= limit);
  const phase = hit ? hit[0] : 'green';
  const seconds = remaining === null ? 0 : Math.ceil(remaining / 1000);
  const abs = Math.abs(seconds);
  $('countdown').textContent = `${seconds < 0 ? '-' : ''}${String(Math.floor(abs/60)).padStart(2,'0')}:${String(abs%60).padStart(2,'0')}`;
  $('countdown').style.color = ui.colors[phase];
  $('countdown').classList.toggle('overdue', phase === 'overdue');
  $('phase').textContent = ui.labels[phase];
  $('connection').textContent = fresh ? 'Headend verbunden' : 'Server offline · lokale Anzeige';
  const elapsed = (now - sampledAt) / 1000;
  const devices = snapshot.devices || [];
  const online = devices.filter(d => fresh && d.online && d.age_s + elapsed < d.timeout_s);
  renderDevices(devices, online, elapsed);
  const pending = online.filter(d => !d.applied);
  const offline = devices.filter(d => !online.includes(d));
  const noBle = online.filter(d => !d.ble_connected);
  const names = list => list.map(d => d.name).join(', ');
  const orb = snapshot.orb;
  $('orb-dot').className = fresh && orb?.connected ? 'ok' : 'bad';
  $('orb-state').textContent = !fresh ? 'Status unbekannt' : orb ? orb.status : 'Deaktiviert';
  if (!commandBusy) {
    $('feedback').textContent = !fresh ? 'Serververbindung unterbrochen. Bedienung und Zustand sind unbestätigt.' :
      !online.length ? 'Kein ESP32 online. Start/Stop wird erst beim Wiederverbinden übernommen.' :
      pending.length ? `Warte auf Bestätigung: ${names(pending)} …` :
      offline.length ? `Synchronisiert · offline: ${names(offline)}` :
      noBle.length ? `Synchronisiert · Luxafor fehlt: ${names(noBle)}` :
      online.length > 1 ? `Alle ${online.length} ESP32 synchronisiert · BLE verbunden` : 'ESP32 synchronisiert · BLE verbunden';
  }
}

function deviceText(d, isOnline, elapsed) {
  const fw = d.firmware;
  const outdated = fw.current ? '' : fw.newer ? ` · Firmware ${fw.version} neuer als Pi-Software (kennt ${fw.expected})`
    : ` · Firmware ${fw.version || '< 1.0.0'} veraltet – aktuell ${fw.expected}`;
  if (!isOnline) {
    const age = d.age_s + elapsed;
    return `Offline · letzte Meldung vor ${age < 120 ? Math.floor(age) + ' s' : Math.floor(age / 60) + ' min'}${outdated}`;
  }
  const link = d.via === 'wifi' ? 'WLAN' : `Mesh über ${d.relay}`;
  const ble = d.ble_connected ? 'Luxafor verbunden' : d.ble_status;
  return `${link} · ${d.applied ? 'synchronisiert' : 'Übertragung ausstehend'} · ${ble}${outdated}`;
}

// Rows are built with textContent only: device names come from the network.
function renderDevices(devices, online, elapsed) {
  const box = $('devices');
  if (box.children.length !== Math.max(1, devices.length)) {
    box.replaceChildren(...Array.from({length: Math.max(1, devices.length)}, () => {
      const row = document.createElement('div');
      row.className = 'status';
      row.append(document.createElement('i'), document.createElement('div'));
      row.lastChild.append(document.createElement('strong'), document.createElement('small'));
      return row;
    }));
  }
  if (!devices.length) {
    const [dot, text] = box.children[0].children;
    dot.className = 'bad';
    text.children[0].textContent = 'ESP32';
    text.children[1].textContent = 'Noch keine Meldung';
    return;
  }
  devices.forEach((d, index) => {
    const [dot, text] = box.children[index].children;
    const isOnline = online.includes(d);
    dot.className = !isOnline ? 'off' : d.applied && d.ble_connected && d.firmware.current ? 'ok' : 'bad';
    text.children[0].textContent = d.name;
    text.children[1].textContent = deviceText(d, isOnline, elapsed);
  });
}

document.querySelectorAll('.preset').forEach(button => button.onclick = () => command('/api/start', {minutes:Number(button.dataset.minutes)}));
$('stop').onclick = () => command('/api/stop', {});
$('settings').onclick = () => $('login').showModal();
$('login-form').onsubmit = async event => {
  event.preventDefault();
  // Keep the working key until the new one has been accepted.
  const candidate = $('token').value.trim();
  try {
    const started = performance.now();
    const data = await api('/api/state', undefined, candidate);
    token = candidate;
    try { sessionStorage.setItem('pi-timer-token', token); } catch (error) {}
    $('login-error').textContent = '';
    $('token').value = '';
    $('login').close();
    accept(data, started);
  } catch (error) { $('login-error').textContent = error.message; }
};
setInterval(poll, 750);
setInterval(render, 100);
if (!token) $('login').showModal();
else poll();
