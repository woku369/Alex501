// Abgleich der JavaScript-Portierung (docs/) mit den Python-Ergebnissen (tests-js/reference.json).
// Ausführen mit:  node --test tests-js/parity.test.js tests-js/pwa.test.js
// Referenz neu erzeugen:  python tools/make_reference.py

import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

import * as calc from '../docs/calc.js';
import * as m from '../docs/measurement.js';

const here = dirname(fileURLToPath(import.meta.url));
const ref = JSON.parse(readFileSync(join(here, 'reference.json'), 'utf8'));
const NOW = new Date(2026, 9, 14, 12, 0, 0);

/** Vergleicht verschachtelte Strukturen; Zahlen mit relativer Toleranz, alles andere exakt. */
function assertClose(actual, expected, path = '$') {
  if (typeof expected === 'number') {
    assert.equal(typeof actual, 'number', `${path}: Zahl erwartet, bekam ${actual}`);
    const tolerance = 1e-9 * Math.max(1, Math.abs(expected));
    assert.ok(Math.abs(actual - expected) <= tolerance, `${path}: ${actual} != ${expected}`);
  } else if (Array.isArray(expected)) {
    assert.ok(Array.isArray(actual), `${path}: Liste erwartet`);
    assert.equal(actual.length, expected.length, `${path}: Länge ${actual.length} != ${expected.length}`);
    expected.forEach((value, i) => assertClose(actual[i], value, `${path}[${i}]`));
  } else if (expected !== null && typeof expected === 'object') {
    assert.ok(actual !== null && typeof actual === 'object', `${path}: Objekt erwartet`);
    assert.deepEqual(Object.keys(actual).sort(), Object.keys(expected).sort(), `${path}: Schlüssel`);
    for (const key of Object.keys(expected)) assertClose(actual[key], expected[key], `${path}.${key}`);
  } else {
    assert.equal(actual, expected, `${path}`);
  }
}

test('Dichte und Massenanteil aus der Alkoholtabelle', () => {
  for (const [alc, expected] of ref.numeric.density) assertClose(calc.interpolateDensityFromAlcohol(alc), expected, `Dichte(${alc})`);
  for (const [alc, expected] of ref.numeric.mass_fraction) assertClose(calc.alcoholMassFraction(alc), expected, `w(${alc})`);
});

test('Wasserdichte und Temperaturkorrekturen', () => {
  for (const [t, expected] of ref.numeric.water_density) assertClose(calc.waterDensityTemp(t), expected, `Wasser(${t})`);
  for (const [v, t, w, expected] of ref.numeric.volume_temp) assertClose(calc.correctVolumeTemp(v, t, w), expected, `Vol(${v},${t},${w})`);
  for (const [d, t, a, expected] of ref.numeric.density_temp) assertClose(calc.correctDensityTo20C(d, t, a), expected, `Dichte20(${d},${t},${a})`);
});

test('Kalibrierkurve', () => {
  for (const [data, value, expected] of ref.numeric.calibration) assertClose(calc.applyCalibrationCurve(data, value), expected);
});

test('Massenbilanz: Alkohol der Originalprobe und wirksamer Faktor', () => {
  for (const [measured, probe, water, expected] of ref.numeric.actual_alcohol) {
    if ('error' in expected) {
      assert.throws(() => calc.computeActualAlcohol(measured, probe, water), (e) => e instanceof calc.CalcError && e.message === expected.error);
    } else {
      assertClose(calc.computeActualAlcohol(measured, probe, water), expected.alcohol, `Alkohol(${measured},${probe},${water})`);
      assertClose(calc.computeEffectiveDilutionFactor(measured, probe, water), expected.effective, `Faktor(${measured},${probe},${water})`);
    }
  }
});

test('Verdünnungsplaner', () => {
  for (const [probeAlc, volume, target, expected] of ref.numeric.plan) {
    if ('error' in expected) {
      assert.throws(() => calc.planDilution(probeAlc, volume, target), (e) => e instanceof calc.CalcError && e.message === expected.error);
    } else {
      assertClose(calc.planDilution(probeAlc, volume, target), expected, `Plan(${probeAlc},${volume},${target})`);
    }
  }
  for (const args of ref.numeric.plan_errors) assert.throws(() => calc.planDilution(...args), calc.CalcError);
});

test('Auswertung und Bericht stimmen mit Python überein', () => {
  for (const c of ref.evaluations) {
    const result = m.evaluateMeasurement(c.raw, c.calib, c.use, NOW);
    assertClose(result, c.result, c.name);
    if (c.report !== null) assert.equal(m.formatReport(result), c.report, `Bericht: ${c.name}`);
  }
});

test('Messhistorie: Tabelle und Details', () => {
  assert.deepEqual(m.HISTORY_COLUMNS.map(([k, t]) => [k, t]), ref.columns);
  ref.history.rows.forEach((row, i) => {
    assert.deepEqual(m.historyTableValues(row), ref.history.table[i], `Tabelle Zeile ${row.id}`);
    assert.deepEqual(m.historyDetailLines(row), ref.history.details[i], `Details Zeile ${row.id}`);
  });
});

test('Eingabe: Dezimalkomma, Leerzeichen, Unsinn', () => {
  assert.equal(m.parseDecimal(' 21,3 '), 21.3);
  assert.equal(m.parseDecimal('21.3'), 21.3);
  assert.equal(m.parseDecimal(''), null);
  assert.equal(m.parseDecimal(null), null);
  assert.throws(() => m.parseDecimal('abc'), TypeError);
  assert.throws(() => m.parseDecimal('1,2,3'), TypeError);
});

test('Format {:g} wie Python', () => {
  const cases = [[0, '0'], [100, '100'], [2.5, '2.5'], [0.7, '0.7'], [1.4, '1.4'], [10000, '10000'], [1e-5, '1e-05'],
    [123456, '123456'], [1234567, '1.23457e+06'], [0.0001, '0.0001'], [12000, '12000'], [-5, '-5']];
  for (const [value, expected] of cases) assert.equal(m.formatG(value), expected, String(value));
});
