"use strict";
const $ = id => document.getElementById(id);
let token = sessionStorage.getItem("pi-timer-token") || "";
let snapshot = null;
let sampledAt = 0;
let lastSuccess = 0;
let commandBusy = false;
let generation = 0;
let polling = false;

async function api(path, body) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 2500);
  try {
    const response = await fetch(path, {
      method: body === undefined ? "GET" : "POST",
      headers: {Authorization: `Bearer ${token}`, "Content-Type": "application/json"},
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: controller.signal, cache: "no-store"
    });
    if (response.status === 401) {
      if (!$('login').open) $('login').showModal();
      throw new Error("Zugriffsschlüssel fehlt oder ist ungültig.");
    }
    if (!response.ok) throw new Error(`Serverfehler (${response.status})`);
    return await response.json();
  } finally { clearTimeout(timeout); }
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
    $('connection').textContent = "Server nicht erreichbar";
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
  let phase = 'off';
  if (remaining !== null) phase = remaining <= -30000 ? 'overdue' : remaining <= 0 ? 'red' : remaining <= 60000 ? 'orange' : remaining <= 300000 ? 'yellow' : 'green';
  const colors = {off:'#eaf0f3',green:'#4ce7a0',yellow:'#f9dd69',orange:'#ffad60',red:'#ff6e79',overdue:'#ff6e79'};
  const labels = {off:'BEREIT',green:'REDEZEIT',yellow:'LETZTE 5 MINUTEN',orange:'LETZTE MINUTE',red:'ZEIT ABGELAUFEN',overdue:'ÜBERZOGEN'};
  const seconds = remaining === null ? 0 : Math.ceil(remaining / 1000);
  const abs = Math.abs(seconds);
  $('countdown').textContent = `${seconds < 0 ? '-' : ''}${String(Math.floor(abs/60)).padStart(2,'0')}:${String(abs%60).padStart(2,'0')}`;
  $('countdown').style.color = colors[phase];
  $('countdown').classList.toggle('overdue', phase === 'overdue');
  $('phase').textContent = labels[phase];
  $('connection').textContent = fresh ? 'Headend verbunden' : 'Server offline · lokale Anzeige';
  // A command response has no node report; only a fresh GET can confirm delivery.
  const node = snapshot.node;
  const online = fresh && node?.online && node.age_s + (now - lastSuccess)/1000 < 5;
  $('node-dot').className = online ? 'ok' : 'bad';
  $('node-state').textContent = online ? (node.applied ? 'Timer synchronisiert' : 'Übertragung ausstehend') : 'Offline / noch keine Meldung';
  const ble = online && node.report?.ble_connected;
  $('ble-dot').className = ble ? 'ok' : 'bad';
  $('ble-state').textContent = online ? node.report.ble_status : 'Status unbekannt';
  if (node && !commandBusy) {
    $('feedback').textContent = !fresh ? 'Serververbindung unterbrochen. Bedienung und Zustand sind unbestätigt.' :
      !online ? 'ESP32 offline. Start/Stop wird erst beim Wiederverbinden übernommen.' :
      !node.applied ? 'Warte auf ESP32-Bestätigung …' :
      !ble ? 'Timer synchronisiert. Luxafor-Verbindung fehlt.' :
      'ESP32 synchronisiert · BLE verbunden';
  }
}

document.querySelectorAll('.preset').forEach(button => button.onclick = () => command('/api/start', {minutes:Number(button.dataset.minutes)}));
$('stop').onclick = () => command('/api/stop', {});
$('settings').onclick = () => $('login').showModal();
$('login-form').onsubmit = async event => {
  event.preventDefault();
  token = $('token').value.trim();
  try {
    const started = performance.now();
    const data = await api('/api/state');
    sessionStorage.setItem('pi-timer-token', token);
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
