// Alex 501 Mazerat-Interpolation – Tablet-Version (PWA). Oberfläche; die Rechnung liegt in calc.js und
// measurement.js (Portierung der Python-Berechnung, per Test gegen diese abgeglichen), die Messhistorie in db.js.

import { INFO_SECTIONS } from './infotext.js';
import * as calc from './calc.js';
import * as meas from './measurement.js';
import * as store from './db.js';
import { formatDe } from './calc.js';

export const APP_VERSION = '1.0.0'; // gleich zu VERSION in sw.js halten (wird von tests-js/pwa.test.js geprüft)

const PREF_KEY = 'alex501.prefs';
const CALIB_KEY = 'alex501.calib';
const EXPORT_KEY = 'alex501.lastExport';

// ---------------------------------------------------------------- Hilfsfunktionen

const $ = (selector, root = document) => root.querySelector(selector);

function h(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value === null || value === undefined || value === false) continue;
    if (key === 'class') node.className = value;
    else if (key === 'text') node.textContent = value;
    else if (key.startsWith('on')) node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value === true ? '' : value);
  }
  for (const child of children.flat(Infinity)) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child.nodeType ? child : document.createTextNode(String(child)));
  }
  return node;
}

function readStorage(key, fallback) {
  try {
    const raw = localStorage.getItem(key);
    return raw === null ? fallback : JSON.parse(raw);
  } catch {
    return fallback;
  }
}

function writeStorage(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* Speicher gesperrt oder voll: App läuft trotzdem, nur Einstellungen gehen verloren */
  }
}

const statusBar = $('#statusbar');
function setStatus(text, level = null) {
  statusBar.textContent = text;
  statusBar.className = 'statusbar' + (level === 'error' ? ' error' : level === 'warning' ? ' warning' : '');
}

function download(filename, content, type) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const link = h('a', { href: url, download: filename });
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

const stamp = (date = new Date()) => meas.isoLocal(date).replace(/[-:T]/g, '').slice(0, 14);

// ---------------------------------------------------------------- Zustand

let prefs = { mode: meas.MODE_DILUTED, room_temp: '', water_mode: meas.WATER_BY_MASS, ...readStorage(PREF_KEY, {}) };
let calibData = readStorage(CALIB_KEY, []);
let lastResult = null;
let lastReport = '';
let lastSavedKey = null;
let lastSavedId = null;
let historyRows = [];
let selectedId = null;

const inputs = {}; // Eingabefelder nach ID

// ---------------------------------------------------------------- Reiter

function selectTab(name) {
  for (const button of document.querySelectorAll('.tabs button')) button.setAttribute('aria-selected', String(button.dataset.tab === name));
  for (const section of document.querySelectorAll('.tab')) {
    const active = section.id === `tab-${name}`;
    section.classList.toggle('active', active);
    section.hidden = !active;
  }
  if (name === 'calib') drawCalibPlot();
  if (name === 'history') refreshHistory();
}

for (const button of document.querySelectorAll('.tabs button')) button.addEventListener('click', () => selectTab(button.dataset.tab));

// ---------------------------------------------------------------- Messung: Eingabekarten

function card(title, accent, ...children) {
  return h('div', { class: 'card' + (accent ? ` accent-${accent}` : '') }, h('h2', { class: 'card-title', text: title }), ...children);
}

function field(id, label, unit = '', options = {}) {
  const input = h('input', {
    id,
    type: 'text',
    inputmode: options.text ? 'text' : 'decimal',
    autocomplete: 'off',
    autocapitalize: 'none',
    spellcheck: 'false',
    enterkeyhint: 'done',
    'aria-label': label,
  });
  input.addEventListener('keydown', (event) => {
    if (event.key === 'Enter') {
      event.preventDefault();
      input.blur();
      calculate();
    }
  });
  inputs[id] = input;
  return h('label', { class: 'field' }, h('span', { text: label }), input, h('em', { text: unit }));
}

function segmented(name, options, value, onChange, extraClass = '') {
  const wrapper = h('div', { class: 'segmented ' + extraClass, role: 'radiogroup' });
  for (const [optionValue, text] of options) {
    const radio = h('input', { type: 'radio', name, value: optionValue, checked: optionValue === value });
    radio.addEventListener('change', () => onChange(optionValue));
    wrapper.append(h('label', {}, radio, h('span', { text })));
  }
  return wrapper;
}

function savePrefs() {
  prefs = { ...prefs, room_temp: inputs.room_temp.value, mode: currentMode(), water_mode: currentWaterMode() };
  writeStorage(PREF_KEY, prefs);
}

const currentMode = () => $('input[name="mode"]:checked')?.value ?? meas.MODE_DILUTED;
const currentWaterMode = () => $('input[name="water_mode"]:checked')?.value ?? meas.WATER_BY_MASS;

function applyMode() {
  const direct = currentMode() === meas.MODE_DIRECT;
  for (const id of ['probe_volume', 'water_value']) inputs[id].disabled = direct;
  for (const radio of document.querySelectorAll('input[name="water_mode"]')) radio.disabled = direct;
  $('#planner-button').disabled = direct;
  $('#ansatz-hint').textContent = direct
    ? 'Proben im Messbereich des Alex 501 (bis 47 %vol), z. B. Fertigprodukte: die gemessenen Werte werden unverändert übernommen.'
    : 'Verdünnung auf etwa 40 %vol; für eine Messung mindestens 40 ml verdünnte Probe. Eingeben, was tatsächlich eingewogen wurde.';
}

function buildMeasureTab() {
  const left = $('#col-left');
  const mid = $('#col-mid');

  left.append(card('Probe', null,
    field('sample_name', 'Bezeichnung', '', { text: true }),
    field('batch', 'Charge', '', { text: true }),
    field('tank_nr', 'Tank-Nr.', '', { text: true })));

  const waterToggle = segmented('water_mode', [[meas.WATER_BY_MASS, 'g'], [meas.WATER_BY_VOLUME, 'ml']], prefs.water_mode,
    () => savePrefs(), 'small unit-toggle');
  const waterField = field('water_value', 'Wasserzugabe', '');
  waterField.lastElementChild.replaceWith(waterToggle);
  left.append(card('Ansatz', null,
    segmented('mode', [[meas.MODE_DILUTED, 'Verdünnt gemessen'], [meas.MODE_DIRECT, 'Direkt gemessen']], prefs.mode,
      () => { savePrefs(); applyMode(); }),
    field('room_temp', 'Raumtemperatur', '°C'),
    field('probe_volume', 'Probevolumen', 'ml'),
    waterField,
    h('button', { type: 'button', class: 'btn secondary', id: 'planner-button', text: 'Verdünnungsplaner …', onclick: openPlanner,
      style: 'width:100%;margin-top:10px' }),
    h('p', { class: 'hint', id: 'ansatz-hint' })));

  mid.append(card('Alex 501 – gemessene Werte', 'alcohol',
    field('measured_alcohol', 'Alkohol', '%vol'),
    field('measured_density', 'Dichte', 'g/cm³'),
    field('measured_extract', 'Extrakt', 'g/100ml')));
  mid.append(card('Spindelung (optional)', 'density',
    field('spindle_alcohol', 'Alkohol', '%vol'),
    field('spindle_density', 'Dichte', 'g/cm³')));
  mid.append(card('Laboranalyse (optional)', 'extract',
    field('lab_alcohol', 'Alkohol', '%vol'),
    field('lab_density', 'Dichte', 'g/cm³'),
    field('lab_extract', 'Extrakt', 'g/100ml'),
    field('lab_note', 'Bemerkung', '', { text: true })));

  const useCalib = h('input', { type: 'checkbox', id: 'use-calib' });
  $('#actions').append(
    h('button', { type: 'button', class: 'btn primary', id: 'calculate', text: 'Berechnen', onclick: calculate }),
    h('button', { type: 'button', class: 'btn secondary', text: 'Neue Messung', onclick: clearInputs }),
    h('label', { class: 'check' }, useCalib, 'Kalibrierkurve anwenden'));

  // Tiles
  const tiles = $('#tiles');
  for (const [id, title, unit, color] of [['alcohol', 'Alkohol', '%vol', 'var(--alcohol)'],
    ['density', 'Dichte', 'g/cm³ bei 20 °C', 'var(--density)'], ['extract', 'Extrakt', 'g/100 ml', 'var(--extract)']]) {
    tiles.append(h('div', { class: 'tile', id: `tile-${id}`, style: `--c:${color}` },
      h('p', { class: 't-title', text: title }), h('p', { class: 't-value', text: '–' }),
      h('p', { class: 't-unit', text: unit }), h('p', { class: 't-caption' })));
  }

  inputs.room_temp.value = prefs.room_temp ?? '';
  inputs.room_temp.addEventListener('input', savePrefs);
  applyMode();
}

// ---------------------------------------------------------------- Messung: Berechnung und Ergebnisse

function collectRaw() {
  const raw = Object.fromEntries(Object.entries(inputs).map(([id, input]) => [id, input.value]));
  return { ...raw, mode: currentMode(), water_mode: currentWaterMode() };
}

const LEVEL_TITLES = { [meas.LEVEL_ERROR]: 'Fehler', [meas.LEVEL_WARNING]: 'Achtung', [meas.LEVEL_INFO]: 'Hinweis' };

function showMessages(messages) {
  const box = $('#messages');
  box.replaceChildren(...messages.map(([level, text]) => h('div', { class: `message ${level}`, role: level === meas.LEVEL_ERROR ? 'alert' : null, text: `${LEVEL_TITLES[level]}: ${text}` })));
}

function setTile(id, value, decimals, caption) {
  const tile = $(`#tile-${id}`);
  $('.t-value', tile).textContent = value === null || value === undefined ? '–' : formatDe(value, decimals);
  $('.t-caption', tile).textContent = value === null || value === undefined ? '' : caption;
}

function setReport(text) {
  $('#report').textContent = text;
}

function clearResults() {
  for (const id of ['alcohol', 'density', 'extract']) setTile(id, null);
  const summary = $('#summary');
  summary.textContent = 'Noch keine Berechnung.';
  summary.className = 'summary muted';
  $('#comparison').replaceChildren();
  setReport('');
  lastResult = null;
  lastReport = '';
}

function clearInputs() {
  for (const [id, input] of Object.entries(inputs)) {
    if (id !== 'room_temp') input.value = '';
  }
  clearResults();
  $('#messages').replaceChildren();
  setStatus('Bereit für die nächste Messung.');
  inputs.sample_name.focus();
}

function showResult(result) {
  const inp = result.input;
  const out = result.output;
  const diluted = result.mode === meas.MODE_DILUTED;
  const calibrated = inp.calibration_applied ? ' (kalibriert)' : '';
  const origin = diluted ? 'Originalprobe' : 'direkt gemessen';

  let alcoholCaption = '';
  if (inp.measured_alcohol !== null) {
    alcoholCaption = (diluted ? `gemessen ${formatDe(inp.measured_alcohol, 2)} %vol in der Verdünnung` : 'direkt gemessen') + calibrated;
    if (out.alcohol_tolerance !== null) alcoholCaption += `; Gerätegrenze ±${formatDe(out.alcohol_tolerance, 2)} %vol`;
  }
  setTile('alcohol', out.actual_alcohol, 2, alcoholCaption);
  setTile('density', out.actual_density, 5, inp.measured_density !== null ? `${origin}; gemessen ${formatDe(inp.measured_density, 5)}` : '');
  setTile('extract', out.actual_extract, 2, inp.measured_extract !== null ? `${origin}; gemessen ${formatDe(inp.measured_extract, 2)}` : '');

  const summary = $('#summary');
  summary.className = 'summary set';
  if (result.has_calculation && diluted) {
    const unit = inp.water_mode === meas.WATER_BY_MASS ? 'g' : 'ml';
    let text = `Ansatz: ${formatDe(inp.probe_volume_input, 1)} ml Probe + ${formatDe(inp.water_input, 1)} ${unit} Wasser · Verdünnungsfaktor 1:${formatDe(inp.dilution_factor, 2)}`;
    if (inp.measured_alcohol !== null) text += ` · wirksam 1:${formatDe(out.effective_dilution_factor, 2)} (mit Volumenkontraktion)`;
    summary.textContent = text;
  } else if (result.has_calculation) {
    summary.textContent = 'Direkte Messung ohne Verdünnung – Werte unverändert übernommen.';
  } else {
    summary.textContent = 'Nur Temperaturkorrektur der Spindeldichte.';
  }

  showComparisons(result);
  lastReport = meas.formatReport(result);
  lastResult = result;
  setReport(lastReport);
}

function showComparisons(result) {
  const box = $('#comparison');
  box.replaceChildren();
  const c = result.comparison;
  const lines = [];
  if (c.alcohol) {
    let text = `Abweichung ${meas.signed(c.alcohol.deviation, 2)} %vol (${meas.signed(c.alcohol.deviation_percent, 1)} %)`;
    let outside = false;
    if ('limit' in c.alcohol) {
      outside = !c.alcohol.within_limit;
      text += ` – ${outside ? 'außerhalb' : 'innerhalb'} der Messgrenzen (±${formatDe(c.alcohol.limit, 2)} %vol)`;
    }
    lines.push(['Spindel Alkohol', `${formatDe(c.alcohol.spindle_value, 2)} %vol`, text, outside]);
  }
  if (c.density && 'deviation' in c.density) {
    lines.push(['Spindel Dichte (20 °C)', `${formatDe(c.density.spindle_value_20C, 5)} g/cm³`,
      `Abweichung ${meas.signed(c.density.deviation, 5)} g/cm³ (${meas.signed(c.density.deviation_percent, 2)} %)`, false]);
  }
  const labNames = { alcohol: ['Labor Alkohol', '%vol', 2], density: ['Labor Dichte', 'g/cm³', 5], extract: ['Labor Extrakt', 'g/100ml', 2] };
  for (const [key, [label, unit, decimals]] of Object.entries(labNames)) {
    const lab = c.lab?.[key];
    if (lab) {
      lines.push([label, `${formatDe(lab.lab_value, decimals)} ${unit}`,
        `Abweichung ${meas.signed(lab.deviation, decimals)} ${unit} (${meas.signed(lab.deviation_percent, 1)} %)`, false]);
    }
  }
  if (!lines.length) return;
  box.append(card('Vergleich mit Referenzwerten', 'density', ...lines.map(([label, value, deviation, outside]) =>
    h('div', { class: 'cmp-line' }, h('span', { class: 'label', text: label }), h('span', { class: 'value', text: value }),
      h('span', { class: 'dev' + (outside ? ' out' : ''), text: deviation })))));
}

let calculating = false;
async function calculate() {
  if (calculating) return;
  calculating = true;
  try {
    let result;
    try {
      result = meas.evaluateMeasurement(collectRaw(), calibData, $('#use-calib').checked, new Date());
    } catch (error) {
      setStatus(`Fehler bei der Berechnung: ${error.message}`, 'error');
      return;
    }
    showMessages(result.messages);
    if (!result.ok) {
      clearResults();
      setStatus('Berechnung nicht möglich – siehe Meldung.', 'error');
      return;
    }
    showResult(result);
    await saveResult(result);
  } finally {
    calculating = false;
  }
}

/** Speichert die Messung in der Messhistorie; unveränderte Wiederholungen werden nicht doppelt abgelegt. */
async function saveResult(result) {
  const key = JSON.stringify({ input: result.input, output: result.output, mode: result.mode, sample: result.sample_name,
    batch: result.batch, tank: result.tank_nr });
  if (key === lastSavedKey) {
    setStatus(`Berechnet. Unveränderte Messung, bereits in der Messhistorie (Nr. ${lastSavedId}).`);
    return;
  }
  try {
    const id = await store.insertMeasurement(result);
    lastSavedKey = key;
    lastSavedId = id;
    setStatus(`Berechnet und in der Messhistorie gespeichert (Nr. ${id}).`);
    requestPersistentStorage();
    await refreshHistory();
  } catch (error) {
    setStatus(`Berechnet, aber nicht gespeichert: ${error.message}`, 'error');
  }
}

let persistRequested = false;
async function requestPersistentStorage() {
  if (persistRequested) return;
  persistRequested = true;
  try {
    await navigator.storage?.persist?.();
  } catch {
    /* nicht kritisch */
  }
}

$('#copy-report').addEventListener('click', async () => {
  if (!lastReport) return setStatus('Kein Protokoll vorhanden.', 'warning');
  try {
    await navigator.clipboard.writeText(lastReport);
    setStatus('Protokoll in die Zwischenablage kopiert.');
  } catch {
    setStatus('Kopieren nicht möglich – bitte „Als Text speichern“ verwenden.', 'warning');
  }
});
$('#save-report-txt').addEventListener('click', () => {
  if (!lastReport) return setStatus('Kein Protokoll vorhanden.', 'warning');
  download(`Alex501_Ergebnis_${stamp()}.txt`, lastReport, 'text/plain;charset=utf-8');
});
$('#save-report-json').addEventListener('click', () => {
  if (!lastResult) return setStatus('Kein Ergebnis vorhanden.', 'warning');
  download(`Alex501_Ergebnis_${stamp()}.json`, JSON.stringify(lastResult, null, 2), 'application/json');
});

// ---------------------------------------------------------------- Verdünnungsplaner

function openPlanner() {
  const dialog = $('#planner-dialog');
  const probeAlc = h('input', { type: 'text', inputmode: 'decimal', value: '50', autocomplete: 'off' });
  const targetAlc = h('input', { type: 'text', inputmode: 'decimal', value: '40', autocomplete: 'off' });
  const probeVolume = h('input', { type: 'text', inputmode: 'decimal', value: '100', autocomplete: 'off' });
  const row = (label, input, unit) => h('label', { class: 'field' }, h('span', { text: label }), input, h('em', { text: unit }));
  const probeLine = h('p', { class: 'planner-result' });
  const waterLine = h('p', { class: 'planner-result' });
  const detailLine = h('p', { class: 'planner-detail' });

  const update = () => {
    let plan;
    let volume;
    try {
      volume = meas.parseDecimal(probeVolume.value);
      const alc = meas.parseDecimal(probeAlc.value);
      const target = meas.parseDecimal(targetAlc.value);
      if (volume === null || alc === null || target === null) throw new TypeError('leer');
      plan = calc.planDilution(alc, volume, target);
    } catch (error) {
      probeLine.textContent = '–';
      waterLine.textContent = '';
      detailLine.textContent = error instanceof calc.CalcError ? error.message : 'Bitte gültige Zahlen eingeben.';
      return;
    }
    const measurements = Math.floor(plan.total_volume / meas.MIN_MEASURING_VOLUME);
    probeLine.textContent = `Probe:  ${formatDe(volume, 1)} ml`;
    waterLine.textContent = `Wasser: ${formatDe(plan.water_mass, 1)} g`;
    detailLine.textContent = `Verdünnung gesamt etwa ${formatDe(plan.total_volume, 1)} ml nach der Kontraktion (Summe der Volumina `
      + `${formatDe(plan.summed_volume, 1)} ml). Reicht für ${measurements} Messung${measurements !== 1 ? 'en' : ''} zu je `
      + `${formatDe(meas.MIN_MEASURING_VOLUME, 0)} ml.` + (measurements < 1 ? ' Achtung: für eine Messung werden mindestens 40 ml benötigt.' : '');
  };
  for (const input of [probeAlc, targetAlc, probeVolume]) input.addEventListener('input', update);
  const preset = (alcohol) => { probeAlc.value = String(alcohol); update(); };

  dialog.replaceChildren(h('div', { class: 'dialog-body' },
    h('h2', { class: 'dialog-title', text: 'Verdünnungsplaner' }),
    card('Vorgaben', null,
      row('Alkohol der Probe (geschätzt)', probeAlc, '%vol'),
      row('Ziel-Alkohol der Verdünnung', targetAlc, '%vol'),
      row('Probevolumen (Messkolben)', probeVolume, 'ml'),
      h('div', { class: 'row' },
        h('button', { type: 'button', class: 'btn secondary', text: 'Mazerat 50', onclick: () => preset(50) }),
        h('button', { type: 'button', class: 'btn secondary', text: 'Destillat 78', onclick: () => preset(78) }))),
    card('Ansatz', 'extract', probeLine, waterLine, detailLine),
    h('p', { class: 'hint', text: 'Richtwert zum Ansetzen: Probe im Messkolben abmessen, Wasser wiegen. Im Hauptfenster die tatsächlich abgemessenen und eingewogenen Werte eingeben.' }),
    h('div', { class: 'row' }, h('button', { type: 'button', class: 'btn secondary', text: 'Schließen', onclick: () => dialog.close() }))));
  update();
  dialog.showModal();
}

// ---------------------------------------------------------------- Messhistorie

async function refreshHistory() {
  try {
    historyRows = await store.fetchAll();
  } catch (error) {
    setStatus(`Messhistorie nicht lesbar: ${error.message}`, 'error');
    historyRows = [];
  }
  renderHistory();
  renderExportHint();
}

function renderHistory() {
  const needle = $('#history-search').value.trim().toLowerCase();
  const rows = historyRows.filter((row) => !needle
    || `${row.sample_name || ''} ${row.batch || ''} ${row.tank_nr || ''}`.toLowerCase().includes(needle));
  const table = $('#history-table');
  const head = h('thead', {}, h('tr', {}, meas.HISTORY_COLUMNS.map(([, title], index) => h('th', { class: index >= 5 ? 'num' : '', text: title }))));
  const body = h('tbody');
  for (const row of rows) {
    const tr = h('tr', { 'data-id': row.id, class: row.id === selectedId ? 'selected' : '' },
      meas.historyTableValues(row).map((value, index) => h('td', { class: index >= 5 ? 'num' : '', text: value })));
    tr.addEventListener('click', () => selectHistoryRow(row.id));
    body.append(tr);
  }
  table.replaceChildren(head, body);
  $('#history-count').textContent = `${rows.length} von ${historyRows.length} Messungen`;
  if (selectedId !== null) showHistoryDetail();
}

function selectHistoryRow(id) {
  selectedId = id;
  for (const tr of document.querySelectorAll('#history-table tbody tr')) tr.classList.toggle('selected', Number(tr.dataset.id) === id);
  showHistoryDetail();
}

function showHistoryDetail() {
  const row = historyRows.find((r) => r.id === selectedId);
  const box = $('#history-detail');
  if (!row) {
    box.replaceChildren(h('p', { class: 'muted', text: 'Bitte eine Messung in der Tabelle auswählen.' }));
    return;
  }
  const sections = [];
  for (const line of meas.historyDetailLines(row)) {
    if (line[0] === 'head') sections.push({ title: line[1], items: [] });
    else sections.at(-1).items.push([line[1], line[2]]);
  }
  box.replaceChildren(...sections.map((section) => h('div', {}, h('h3', { text: section.title }),
    h('dl', {}, section.items.map(([label, value]) => [h('dt', { text: label }), h('dd', { text: value })])))));
}

function renderExportHint() {
  const last = readStorage(EXPORT_KEY, null);
  const text = historyRows.length === 0 ? ''
    : last ? `Letzte Sicherung: ${new Date(last).toLocaleString('de-AT')}. Die Messdaten liegen nur auf diesem Gerät.`
      : 'Noch keine Sicherung. Die Messdaten liegen nur auf diesem Gerät – bitte regelmäßig als JSON sichern.';
  $('#export-hint').textContent = text;
}

$('#history-search').addEventListener('input', renderHistory);

function toCsv(table) {
  const quote = (cell) => (/[;"\n\r]/.test(cell) ? `"${cell.replaceAll('"', '""')}"` : cell);
  return '﻿' + table.map((row) => row.map(quote).join(';')).join('\r\n') + '\r\n';
}

$('#export-csv').addEventListener('click', () => {
  const table = meas.historyCsvTable(historyRows);
  if (!table.length) return setStatus('Die Messhistorie ist noch leer.', 'warning');
  download(`Alex501_Messhistorie_${stamp().slice(0, 8)}.csv`, toCsv(table), 'text/csv;charset=utf-8');
  setStatus('Messhistorie als CSV exportiert (Downloads).');
});

$('#export-json').addEventListener('click', async () => {
  if (!historyRows.length) return setStatus('Die Messhistorie ist noch leer.', 'warning');
  const data = await store.exportAll();
  download(`Alex501_Sicherung_${stamp()}.json`, JSON.stringify(data, null, 2), 'application/json');
  writeStorage(EXPORT_KEY, new Date().toISOString());
  renderExportHint();
  setStatus(`Sicherung mit ${data.rows.length} Messungen gespeichert (Downloads).`);
});

$('#import-json').addEventListener('click', () => $('#import-file').click());
$('#import-file').addEventListener('change', async (event) => {
  const file = event.target.files[0];
  event.target.value = '';
  if (!file) return;
  try {
    const rows = store.rowsFromExport(JSON.parse(await file.text()));
    const { added, skipped } = await store.importRows(rows);
    await refreshHistory();
    setStatus(`Import: ${added} Messungen hinzugefügt, ${skipped} übersprungen (bereits vorhanden oder ungültig).`);
  } catch (error) {
    setStatus(`Import fehlgeschlagen: ${error.message}`, 'error');
  }
});

$('#lab-edit').addEventListener('click', () => {
  const row = historyRows.find((r) => r.id === selectedId);
  if (!row) return setStatus('Bitte zuerst eine Messung in der Tabelle auswählen.', 'warning');
  const dialog = $('#lab-dialog');
  const variables = {};
  const fields = [['lab_alcohol', 'Alkohol', '%vol', 2], ['lab_density', 'Dichte', 'g/cm³', 5], ['lab_extract', 'Extrakt', 'g/100ml', 2]];
  const rows = fields.map(([key, label, unit, decimals]) => {
    variables[key] = h('input', { type: 'text', inputmode: 'decimal', autocomplete: 'off', value: row[key] == null ? '' : formatDe(row[key], decimals) });
    return h('label', { class: 'field' }, h('span', { text: label }), variables[key], h('em', { text: unit }));
  });
  const note = h('input', { type: 'text', autocomplete: 'off', value: row.lab_note || '' });
  const save = async () => {
    let values;
    try {
      values = Object.fromEntries(Object.entries(variables).map(([key, input]) => [key, meas.parseDecimal(input.value)]));
    } catch {
      return setStatus('Bitte gültige Zahlen eingeben.', 'error');
    }
    await store.updateLabReference(row.id, { ...values, lab_note: note.value.trim() });
    dialog.close();
    await refreshHistory();
    setStatus(`Laborwerte zu Messung Nr. ${row.id} gespeichert.`);
  };
  dialog.replaceChildren(h('div', { class: 'dialog-body' },
    h('h2', { class: 'dialog-title', text: `Laborwerte zu Messung Nr. ${row.id}` }),
    card(`${row.sample_name || 'Messung'} – ${meas.historyTableValues(row)[0]}`, 'extract', ...rows,
      h('label', { class: 'field' }, h('span', { text: 'Bemerkung' }), note, h('em'))),
    h('div', { class: 'row' },
      h('button', { type: 'button', class: 'btn primary', text: 'Speichern', onclick: save }),
      h('button', { type: 'button', class: 'btn secondary', text: 'Abbrechen', onclick: () => dialog.close() }))));
  dialog.showModal();
});

// ---------------------------------------------------------------- Kalibrierkurve

function renderCalib() {
  const table = $('#calib-table');
  const head = h('thead', {}, h('tr', {}, h('th', { class: 'num', text: 'Referenz' }), h('th', { class: 'num', text: 'Messwert' }), h('th')));
  const body = h('tbody');
  calibData.forEach(([ref, measured], index) => {
    body.append(h('tr', { style: 'cursor:default' },
      h('td', { class: 'num', text: formatDe(ref, 2) }), h('td', { class: 'num', text: formatDe(measured, 2) }),
      h('td', {}, h('button', { type: 'button', class: 'icon-btn', 'aria-label': 'Punkt löschen', text: '✕', onclick: () => {
        calibData.splice(index, 1);
        saveCalib();
      } }))));
  });
  table.replaceChildren(head, body);
  drawCalibPlot();
}

function saveCalib() {
  writeStorage(CALIB_KEY, calibData);
  renderCalib();
}

function addCalibPoint() {
  let ref;
  let measured;
  try {
    ref = meas.parseDecimal($('#calib-ref').value);
    measured = meas.parseDecimal($('#calib-meas').value);
  } catch {
    return setStatus('Bitte gültige Zahlen eingeben.', 'error');
  }
  if (ref === null || measured === null) return setStatus('Bitte Referenzwert und Messwert eingeben.', 'warning');
  calibData.push([ref, measured]);
  $('#calib-ref').value = '';
  $('#calib-meas').value = '';
  saveCalib();
  $('#calib-ref').focus();
}

$('#calib-add').addEventListener('click', addCalibPoint);
for (const id of ['calib-ref', 'calib-meas']) {
  $(`#${id}`).addEventListener('keydown', (event) => {
    if (event.key === 'Enter') {
      event.preventDefault();
      addCalibPoint();
    }
  });
}

function drawCalibPlot() {
  const canvas = $('#calib-plot');
  if (!canvas.offsetParent) return; // Reiter nicht sichtbar
  const ratio = window.devicePixelRatio || 1;
  const width = canvas.clientWidth || 640;
  const height = Math.round(width * 0.66);
  canvas.width = Math.round(width * ratio);
  canvas.height = Math.round(height * ratio);
  canvas.style.height = `${height}px`;
  const ctx = canvas.getContext('2d');
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
  ctx.clearRect(0, 0, width, height);
  const css = getComputedStyle(document.documentElement);
  const color = (name) => css.getPropertyValue(name).trim();
  const left = 52;
  const right = 16;
  const top = 34;
  const bottom = 46;
  const x = (value) => left + (value / 50) * (width - left - right);
  const y = (value) => height - bottom - (value / 50) * (height - top - bottom);
  ctx.font = '13px system-ui, sans-serif';
  ctx.textAlign = 'center';
  ctx.fillStyle = color('--primary-dark');
  ctx.font = 'bold 15px system-ui, sans-serif';
  ctx.fillText('Kalibrierkurve', width / 2, 20);
  ctx.font = '13px system-ui, sans-serif';
  ctx.strokeStyle = '#e3e9e0';
  ctx.fillStyle = color('--muted');
  ctx.lineWidth = 1;
  for (let v = 0; v <= 50; v += 10) {
    ctx.beginPath(); ctx.moveTo(x(v), y(0)); ctx.lineTo(x(v), y(50)); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(x(0), y(v)); ctx.lineTo(x(50), y(v)); ctx.stroke();
    ctx.textAlign = 'center'; ctx.fillText(String(v), x(v), height - bottom + 18);
    ctx.textAlign = 'right'; ctx.fillText(String(v), left - 8, y(v) + 4);
  }
  ctx.strokeStyle = color('--border');
  ctx.strokeRect(x(0), y(50), x(50) - x(0), y(0) - y(50));
  ctx.fillStyle = color('--text');
  ctx.textAlign = 'center';
  ctx.fillText('Referenzwert [%vol]', (left + width - right) / 2, height - 8);
  ctx.save();
  ctx.translate(14, (top + height - bottom) / 2);
  ctx.rotate(-Math.PI / 2);
  ctx.fillText('Messwert [%vol]', 0, 0);
  ctx.restore();
  if (calibData.length >= 2) {
    const { slope, intercept } = calc.linearFit(calibData.map((p) => p[0]), calibData.map((p) => p[1]));
    ctx.strokeStyle = color('--extract');
    ctx.lineWidth = 2;
    ctx.setLineDash([7, 5]);
    ctx.beginPath();
    ctx.moveTo(x(0), y(intercept));
    ctx.lineTo(x(50), y(slope * 50 + intercept));
    ctx.stroke();
    ctx.setLineDash([]);
  }
  ctx.fillStyle = color('--primary');
  for (const [ref, measured] of calibData) {
    ctx.beginPath(); ctx.arc(x(ref), y(measured), 6, 0, Math.PI * 2); ctx.fill();
  }
}
window.addEventListener('resize', drawCalibPlot);

// ---------------------------------------------------------------- Information und Offline-Status

function buildInfoTab() {
  const text = $('#info-text');
  text.append(h('h1', { text: 'Alex 501 Mazerat-Interpolations-App (Tablet-Version)' }));
  for (const [heading, paragraphs] of INFO_SECTIONS) {
    text.append(h('h2', { text: heading }), ...paragraphs.map((p) => h('p', { text: p })));
  }
  text.append(h('h2', { text: 'Tablet-Version' }),
    h('p', { text: 'Diese Version läuft im Browser und nach einmaligem Laden auch ohne Netz (Mazerationsraum). Die Messungen liegen nur auf diesem Gerät. Bitte regelmäßig über „Messhistorie → Sicherung (JSON)“ sichern; die Datei lässt sich in der Windows-App über „Messhistorie → Import (Tablet)“ übernehmen.' }));
}

let offlineReady = false;
function renderNetwork() {
  const chip = $('#net-status');
  const online = navigator.onLine;
  chip.textContent = `${online ? 'Online' : 'Offline'}${offlineReady ? ' · offline bereit' : ''}`;
  chip.className = 'chip ' + (online ? 'ok' : 'off');
}

async function renderAppInfo() {
  let persisted = 'unbekannt';
  try {
    if (navigator.storage?.persisted) persisted = (await navigator.storage.persisted()) ? 'dauerhaft' : 'nicht garantiert (Browser kann Daten bei Platzmangel löschen)';
  } catch { /* ignorieren */ }
  $('#app-info').replaceChildren(
    h('h2', { class: 'card-title', text: 'Diese Installation' }),
    h('p', { text: `Version ${APP_VERSION}` }),
    h('p', { text: `Offline nutzbar: ${offlineReady ? 'ja' : 'noch nicht (einmal mit Netz öffnen)'}` }),
    h('p', { text: `Speicher der Messdaten: ${persisted}` }));
}

function setupServiceWorker() {
  renderNetwork();
  window.addEventListener('online', renderNetwork);
  window.addEventListener('offline', renderNetwork);
  if (!('serviceWorker' in navigator)) return;
  const hadController = Boolean(navigator.serviceWorker.controller);
  navigator.serviceWorker.addEventListener('controllerchange', () => {
    if (hadController) $('#update-banner').hidden = false;
  });
  $('#update-reload').addEventListener('click', () => location.reload());
  navigator.serviceWorker.register('./sw.js').catch((error) => setStatus(`Offline-Betrieb nicht verfügbar: ${error.message}`, 'warning'));
  navigator.serviceWorker.ready.then(() => {
    offlineReady = true;
    renderNetwork();
    renderAppInfo();
  });
}

// ---------------------------------------------------------------- Start

buildMeasureTab();
buildInfoTab();
renderCalib();
renderAppInfo();
setupServiceWorker();
refreshHistory();
