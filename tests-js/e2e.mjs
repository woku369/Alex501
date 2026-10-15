// Ende-zu-Ende-Test der Tablet-PWA im echten Browser (Chromium): Berechnung, Speichern, Offline-Betrieb,
// Export/Import, Laborwerte, Kalibrierung. Benötigt playwright-core und einen Chromium:
//   npm install playwright-core
//   CHROMIUM_PATH=/pfad/zu/chrome node tests-js/e2e.mjs
// (Nicht Teil von "node --test", damit die Rechen-Tests ohne Browser laufen.)

import { chromium } from 'playwright-core';
import { createServer } from 'node:http';
import { readFile, writeFile, mkdtemp } from 'node:fs/promises';
import { extname, join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { tmpdir } from 'node:os';
import assert from 'node:assert/strict';

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..', 'docs');
const CHROMIUM = process.env.CHROMIUM_PATH;
const types = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.webmanifest': 'application/manifest+json', '.png': 'image/png' };

const server = createServer(async (req, res) => {
  try {
    const path = new URL(req.url, 'http://x').pathname;
    const file = join(ROOT, path === '/' ? 'index.html' : path);
    res.writeHead(200, { 'content-type': types[extname(file)] || 'application/octet-stream' });
    res.end(await readFile(file));
  } catch { res.writeHead(404); res.end('nf'); }
}).listen(0);
const url = `http://localhost:${server.address().port}/`;

const browser = await chromium.launch({ executablePath: CHROMIUM, args: ['--no-sandbox'] });
const errors = [];
let step = 0;
const ok = (text) => console.log(`ok ${++step} - ${text}`);

const newContext = async () => {
  const context = await browser.newContext({ viewport: { width: 1280, height: 800 }, locale: 'de-AT', acceptDownloads: true });
  const page = await context.newPage();
  page.on('pageerror', (e) => errors.push(`pageerror: ${e.message}`));
  page.on('console', (m) => { if (m.type() === 'error') errors.push(`console: ${m.text()}`); });
  await page.goto(url);
  await page.waitForSelector('#calculate');
  return { context, page };
};
const fill = async (page, values) => { for (const [id, v] of Object.entries(values)) await page.fill('#' + id, v); };
const calculate = async (page) => { await page.click('#calculate'); await page.waitForTimeout(150); };
const tile = (page, id) => page.textContent(`#tile-${id} .t-value`);
const status = (page) => page.textContent('#statusbar');
const SALBEI = { sample_name: 'Salbei Mazerat', batch: '26-014', tank_nr: 'T-12', room_temp: '21,3', probe_volume: '100', water_value: '25,5',
  measured_alcohol: '40,1', measured_density: '0,9505', measured_extract: '1,6', spindle_alcohol: '49,6', spindle_density: '0,935' };

try {
  const { context, page } = await newContext();

  await page.waitForFunction(() => document.querySelector('#net-status').textContent.includes('offline bereit'));
  ok('Service Worker aktiv, "offline bereit" angezeigt');

  await fill(page, SALBEI);
  await calculate(page);
  assert.equal(await tile(page, 'alcohol'), '50,14');
  assert.equal(await tile(page, 'density'), '0,93313');
  assert.equal(await tile(page, 'extract'), '2,00');
  assert.match(await status(page), /gespeichert \(Nr\. 1\)/);
  ok('Berechnung entspricht der Windows-App (50,14 / 0,93313 / 2,00) und wird gespeichert');

  await calculate(page);
  assert.match(await status(page), /bereits in der Messhistorie/);
  await page.click('[data-tab=history]');
  assert.equal((await page.textContent('#history-count')).trim(), '1 von 1 Messungen');
  ok('Wiederholter Klick speichert nicht doppelt');

  await page.reload();
  await page.waitForSelector('#calculate');
  await page.click('[data-tab=history]');
  assert.equal((await page.textContent('#history-count')).trim(), '1 von 1 Messungen');
  assert.equal(await page.inputValue('#room_temp'), '21,3');
  ok('Messung und Raumtemperatur bleiben nach Neustart erhalten (IndexedDB, Einstellungen)');

  await context.setOffline(true);
  await page.reload();
  await page.waitForSelector('#calculate');
  assert.match(await page.textContent('#net-status'), /Offline/);
  await fill(page, SALBEI);
  await page.fill('#sample_name', 'Offline-Probe');
  await calculate(page);
  assert.equal(await tile(page, 'alcohol'), '50,14');
  await page.click('[data-tab=history]');
  assert.equal((await page.textContent('#history-count')).trim(), '2 von 2 Messungen');
  ok('Ohne Netz: App lädt aus dem Cache, rechnet und speichert');
  await context.setOffline(false);

  await page.fill('#history-search', 'offline');
  await page.waitForTimeout(100);
  assert.equal((await page.textContent('#history-count')).trim(), '1 von 2 Messungen');
  await page.fill('#history-search', 't-12');
  await page.waitForTimeout(100);
  assert.equal((await page.textContent('#history-count')).trim(), '2 von 2 Messungen');
  await page.fill('#history-search', '');
  ok('Suche nach Probe und Tank-Nr.');

  await page.click('#history-table tbody tr');
  await page.click('#lab-edit');
  await page.waitForSelector('#lab-dialog[open]');
  const labInputs = await page.$$('#lab-dialog input');
  await labInputs[0].fill('51,2');
  await labInputs[3].fill('Labor X');
  await page.click('#lab-dialog .btn.primary');
  await page.waitForTimeout(200);
  assert.ok((await page.textContent('#history-table tbody tr.selected')).includes('51,20'));
  assert.ok((await page.textContent('#history-detail')).includes('Labor X'));
  ok('Laborwerte nachträglich eintragen');

  const [csv] = await Promise.all([page.waitForEvent('download'), page.click('#export-csv')]);
  const csvText = await readFile(await csv.path(), 'utf8');
  assert.ok(csvText.startsWith('﻿id;timestamp;sample_name;batch;room_temp'));
  assert.ok(csvText.includes('Salbei Mazerat') && csvText.includes('Offline-Probe') && csvText.includes('50,1'));
  ok('CSV-Export (Semikolon, UTF-8 mit BOM, Dezimalkomma)');

  const [json] = await Promise.all([page.waitForEvent('download'), page.click('#export-json')]);
  const jsonPath = join(await mkdtemp(join(tmpdir(), 'alex501-')), 'sicherung.json');
  await writeFile(jsonPath, await readFile(await json.path()));
  const exported = JSON.parse(await readFile(jsonPath, 'utf8'));
  assert.equal(exported.format, 'alex501-messungen');
  assert.equal(exported.rows.length, 2);
  assert.ok(exported.rows.some((r) => r.lab_alcohol === 51.2 && r.tank_nr === 'T-12'));
  assert.match(await page.textContent('#export-hint'), /Letzte Sicherung/);
  ok('JSON-Sicherung mit denselben Spaltennamen wie die Windows-Datenbank');

  const second = await newContext();
  await second.page.click('[data-tab=history]');
  assert.equal((await second.page.textContent('#history-count')).trim(), '0 von 0 Messungen');
  await second.page.setInputFiles('#import-file', jsonPath);
  await second.page.waitForTimeout(300);
  assert.equal((await second.page.textContent('#history-count')).trim(), '2 von 2 Messungen');
  await second.page.setInputFiles('#import-file', jsonPath);
  await second.page.waitForTimeout(300);
  assert.equal((await second.page.textContent('#history-count')).trim(), '2 von 2 Messungen');
  assert.match(await status(second.page), /0 Messungen hinzugefügt, 2 übersprungen/);
  ok('Import in ein leeres Gerät; erneuter Import erzeugt keine Dubletten');
  await second.context.close();

  await page.click('[data-tab=measure]');
  await page.click('#planner-button');
  await page.waitForSelector('#planner-dialog[open]');
  assert.ok((await page.textContent('#planner-dialog')).includes('Wasser: 25,5 g'));
  assert.ok((await page.textContent('#planner-dialog')).includes('125,0 ml'));
  await page.click('#planner-dialog >> text=Destillat 78');
  assert.ok((await page.textContent('#planner-dialog')).includes('Wasser: 98,4 g'));
  await page.click('#planner-dialog >> text=Schließen');
  ok('Verdünnungsplaner: 25,5 g (Mazerat 50) und 98,4 g (Destillat 78) auf 100 ml Probe');

  await page.click('.segmented label:has-text("Direkt gemessen")');
  assert.equal(await page.isDisabled('#probe_volume'), true);
  assert.equal(await page.isDisabled('#planner-button'), true);
  await page.click('[data-tab=measure]');
  await page.click('.actions .btn.secondary');
  await fill(page, { measured_alcohol: '27,05', measured_density: '1,0312', measured_extract: '31,4', sample_name: 'Gurktaler Mild' });
  await calculate(page);
  assert.equal(await tile(page, 'alcohol'), '27,05');
  assert.equal(await tile(page, 'extract'), '31,40');
  ok('Modus "Direkt gemessen": Alex-Werte unverändert, Verdünnungsfelder gesperrt');
  await page.click('.segmented label:has-text("Verdünnt gemessen")');

  await page.fill('#room_temp', '');
  await calculate(page);
  assert.ok((await page.textContent('#messages')).includes('Raumtemperatur ist erforderlich'));
  assert.equal(await tile(page, 'alcohol'), '–');
  await page.fill('#room_temp', '21,3');
  ok('Fehlende Raumtemperatur: Meldung, kein Ergebnis');

  await page.click('.actions .btn.secondary');
  await fill(page, SALBEI);
  await page.click('[data-tab=calib]');
  for (const [r, m] of [['10', '9'], ['20', '19']]) { await page.fill('#calib-ref', r); await page.fill('#calib-meas', m); await page.click('#calib-add'); }
  assert.equal((await page.$$('#calib-table tbody tr')).length, 2);
  await page.click('[data-tab=measure]');
  await page.check('#use-calib');
  await calculate(page);
  assert.equal(await tile(page, 'alcohol'), '51,14');
  await page.reload();
  await page.click('[data-tab=calib]');
  assert.equal((await page.$$('#calib-table tbody tr')).length, 2);
  ok('Kalibrierkurve (Messwert = Referenz - 1): +1,00 auf den berechneten Alkohol, bleibt nach Neustart gespeichert');

  await context.close();
  assert.deepEqual(errors, [], `Konsolenfehler: ${errors.join(' | ')}`);
  ok('keine Konsolen- oder Seitenfehler');
  console.log(`\n${step} Prüfungen bestanden`);
} finally {
  await browser.close();
  server.close();
}
