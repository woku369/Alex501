// Prüft die Auslieferung der Tablet-PWA (docs/): Versionen, Offline-Dateiliste, Manifest, Icons.
// Ausführen mit:  node --test tests-js/parity.test.js tests-js/pwa.test.js

import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync, statSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const docs = join(dirname(fileURLToPath(import.meta.url)), '..', 'docs');
const read = (name) => readFileSync(join(docs, name), 'utf8');

test('Version in app.js und sw.js stimmt überein', () => {
  const app = /APP_VERSION = '([^']+)'/.exec(read('app.js'))?.[1];
  const sw = /const VERSION = '([^']+)'/.exec(read('sw.js'))?.[1];
  assert.ok(app && sw, 'Versionen nicht gefunden');
  assert.equal(app, sw);
});

test('Alle Dateien der Offline-Liste existieren', () => {
  const list = /const ASSETS = \[([\s\S]*?)\];/.exec(read('sw.js'))[1];
  const files = [...list.matchAll(/'\.\/([^']*)'/g)].map((m) => m[1]).filter(Boolean);
  assert.ok(files.length >= 10);
  for (const file of files) assert.ok(existsSync(join(docs, file)), `fehlt: ${file}`);
});

test('Jede importierte Moduldatei steht in der Offline-Liste', () => {
  const list = read('sw.js');
  const imports = new Set();
  for (const file of ['app.js', 'db.js', 'measurement.js', 'calc.js']) {
    for (const m of read(file).matchAll(/from '\.\/([^']+)'/g)) imports.add(m[1]);
  }
  assert.ok(imports.size >= 5);
  for (const file of imports) assert.ok(list.includes(`'./${file}'`), `nicht im Cache: ${file}`);
});

test('Manifest ist vollständig und die Icons existieren', () => {
  const manifest = JSON.parse(read('manifest.webmanifest'));
  assert.equal(manifest.display, 'standalone');
  assert.equal(manifest.lang, 'de');
  assert.ok(manifest.name && manifest.short_name && manifest.start_url && manifest.theme_color);
  assert.ok(existsSync(join(docs, manifest.start_url.replace('./', ''))));
  const sizes = manifest.icons.map((i) => i.sizes);
  assert.ok(sizes.includes('192x192') && sizes.includes('512x512'));
  assert.ok(manifest.icons.some((i) => i.purpose === 'maskable'));
  for (const icon of manifest.icons) assert.ok(statSync(join(docs, icon.src)).size > 1000, icon.src);
});

test('Seite verweist auf Manifest und Skript', () => {
  const html = read('index.html');
  assert.ok(html.includes('rel="manifest" href="manifest.webmanifest"'));
  assert.ok(html.includes('src="app.js"'));
  assert.ok(html.includes('lang="de"'));
});

test('Keine externen Abhängigkeiten (läuft ohne Netz)', () => {
  for (const file of ['index.html', 'app.js', 'styles.css', 'db.js', 'calc.js', 'measurement.js']) {
    assert.doesNotMatch(read(file), /https?:\/\/(?!localhost)/, `externe Adresse in ${file}`);
  }
});
