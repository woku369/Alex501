// Messvorgang der Alex 501 Mazerat-Interpolation (Portierung von measurement.py):
// Eingaben prüfen, berechnen, Bericht erzeugen, Messhistorie darstellen.
// Keine Abhängigkeit von Browser oder Oberfläche; wird in tests-js/ gegen die Python-Ergebnisse geprüft.

import * as calc from './calc.js';
import { formatDe, CalcError } from './calc.js';

export const MODE_DILUTED = 'diluted'; // verdünnte Probe, Umrechnung auf die Originalprobe
export const MODE_DIRECT = 'direct'; // Probe liegt im Messbereich, Alex-Werte werden direkt übernommen
export const WATER_BY_VOLUME = 'vol';
export const WATER_BY_MASS = 'mass';

export const DEVICE_MAX_ALCOHOL = 47.0; // %vol, Messbereich des Alex 501 (Angabe des Nutzers)
export const MIN_MEASURING_VOLUME = 40.0; // ml verdünnte Probe je Messung (Angabe des Nutzers)

// Genauigkeit des Alex 501 (±%vol bei 40 %vol) und der Spindelung (±%vol, schon auf 20 °C korrigiert),
// beides Angaben des Nutzers. Die Gerätegrenze wird für alle Messwerte als gleich angenommen.
export const DEVICE_ALCOHOL_TOLERANCE = 0.4;
export const SPINDLE_ALCOHOL_TOLERANCE = 0.3;

export const LEVEL_ERROR = 'error'; // Berechnung nicht möglich
export const LEVEL_WARNING = 'warning'; // Berechnung läuft, Wert bitte prüfen
export const LEVEL_INFO = 'info';

const NUMBER_PATTERN = /^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$/;

/** Text mit Komma oder Punkt in eine Zahl; leerer Text ergibt null, Unsinn wirft einen Fehler. */
export function parseDecimal(text) {
  const trimmed = String(text ?? '').trim();
  if (!trimmed) return null;
  const normalized = trimmed.replace(',', '.');
  if (!NUMBER_PATTERN.test(normalized)) throw new TypeError(`keine Zahl: ${text}`);
  return Number(normalized);
}

/** Zahl mit Vorzeichen im deutschen Format (immer + oder -). */
export function signed(value, decimals) {
  return (value > 0 ? '+' : '-') + formatDe(Math.abs(value), decimals);
}

/** Entspricht Python-Format "{:g}" (6 signifikante Stellen, ohne überflüssige Nullen). */
export function formatG(value) {
  if (value === 0) return '0';
  const exponent = Number(value.toExponential(5).split('e')[1]);
  if (exponent < -4 || exponent >= 6) {
    const [mantissa, exp] = value.toExponential(5).split('e');
    const trimmed = mantissa.includes('.') ? mantissa.replace(/0+$/, '').replace(/\.$/, '') : mantissa;
    const sign = Number(exp) < 0 ? '-' : '+';
    return `${trimmed}e${sign}${String(Math.abs(Number(exp))).padStart(2, '0')}`;
  }
  const fixed = value.toFixed(Math.max(0, 5 - exponent));
  return fixed.includes('.') ? fixed.replace(/0+$/, '').replace(/\.$/, '') : fixed;
}

/** Lokaler ISO-Zeitstempel ohne Zeitzone (wie Python datetime.isoformat). */
export function isoLocal(date) {
  const p = (n, w = 2) => String(n).padStart(w, '0');
  const base = `${date.getFullYear()}-${p(date.getMonth() + 1)}-${p(date.getDate())}T${p(date.getHours())}:${p(date.getMinutes())}:${p(date.getSeconds())}`;
  return date.getMilliseconds() ? `${base}.${p(date.getMilliseconds(), 3)}` : base;
}

function parseIso(timestamp) {
  const m = /^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})/.exec(timestamp ?? '');
  return m ? { y: m[1], mo: m[2], d: m[3], h: m[4], mi: m[5], s: m[6] } : null;
}

function formatTimestamp(timestamp, withSeconds) {
  const t = parseIso(timestamp);
  if (!t) return null;
  return `${t.d}.${t.mo}.${t.y} ${t.h}:${t.mi}${withSeconds ? ':' + t.s : ''}`;
}

/**
 * Wie stark sich ein Fehler des gemessenen Alkohols der Verdünnung auf den berechneten Alkohol der
 * Originalprobe auswirkt (numerische Ableitung der Massenbilanz). null, wenn nicht berechenbar.
 */
export function amplificationFactor(measuredAlc, probeVol, waterVol) {
  const step = 0.2;
  const low = Math.max(measuredAlc - step, 0.0);
  const high = measuredAlc + step;
  try {
    return (calc.computeActualAlcohol(high, probeVol, waterVol) - calc.computeActualAlcohol(low, probeVol, waterVol)) / (high - low);
  } catch (error) {
    if (error instanceof CalcError) return null;
    throw error;
  }
}

/**
 * Prüft die Eingaben, berechnet die Werte der Originalprobe und liefert ein Ergebnis-Objekt.
 * raw: Felder der Eingabemaske als Text (fehlende Schlüssel zählen als leer):
 *   mode, sample_name, batch, tank_nr, room_temp, probe_volume, water_value, water_mode,
 *   measured_alcohol, measured_density, measured_extract, spindle_alcohol, spindle_density,
 *   lab_alcohol, lab_density, lab_extract, lab_note
 * Rückgabe: { ok, messages: [[Stufe, Text]], ... } und, wenn ok, input/output/derived/comparison usw.
 */
export function evaluateMeasurement(raw, calibData = null, useCalibration = false, now = new Date()) {
  const messages = [];
  const fail = (text) => {
    messages.push([LEVEL_ERROR, text]);
    return { ok: false, messages };
  };

  const ignored = []; // Felder mit ungültiger Eingabe (keine Zahl), werden ignoriert
  const ranges = []; // unplausible Werte, werden trotzdem verwendet

  const number = (key, label) => {
    try {
      return parseDecimal(raw[key]);
    } catch (error) {
      if (error instanceof TypeError) {
        ignored.push(label);
        return null;
      }
      throw error;
    }
  };

  const checkRange = (value, low, high, label, inclusiveLow = true) => {
    if (value === null) return;
    const below = inclusiveLow ? value < low : value <= low;
    if (below || value > high) {
      ranges.push(`${label} (${formatG(value)}) liegt außerhalb des erwarteten Bereichs ${formatG(low)}–${formatG(high)}`);
    }
  };

  const mode = raw.mode || MODE_DILUTED;
  const diluted = mode === MODE_DILUTED;
  const sampleName = (raw.sample_name || '').trim();
  const batch = (raw.batch || '').trim();
  const tankNr = (raw.tank_nr || '').trim();

  // Raumtemperatur ist Pflicht
  let roomTemp = null;
  try {
    roomTemp = parseDecimal(raw.room_temp);
  } catch (error) {
    if (!(error instanceof TypeError)) throw error;
  }
  if (roomTemp === null) return fail('Raumtemperatur ist erforderlich.');
  checkRange(roomTemp, 0, 40, 'Raumtemperatur [°C]');

  const probeInput = number('probe_volume', 'Probevolumen');
  const waterInput = number('water_value', 'Wasserzugabe');
  const measuredAlc = number('measured_alcohol', 'Gemessener Alkohol');
  const measuredDens = number('measured_density', 'Gemessene Dichte');
  const measuredExt = number('measured_extract', 'Gemessener Extrakt');
  const spindleAlc = number('spindle_alcohol', 'Spindelwert Alkohol');
  const spindleDensAtTemp = number('spindle_density', 'Spindelwert Dichte');
  const labAlc = number('lab_alcohol', 'Labor Alkohol');
  const labDens = number('lab_density', 'Labor Dichte');
  const labExt = number('lab_extract', 'Labor Extrakt');
  const labNote = (raw.lab_note || '').trim();

  if (diluted) {
    checkRange(probeInput, 0, 10000, 'Probevolumen [ml]', false);
    checkRange(waterInput, 0, 10000, 'Wasserzugabe', false);
  }
  checkRange(measuredAlc, 0, 100, 'Gemessener Alkohol [%vol]');
  // Bereich deckt reine Ethanol-Wasser-Proben und zuckerhaltige Liköre (bis ca. 1,35 g/cm³) ab
  checkRange(measuredDens, 0.70, 1.40, 'Gemessene Dichte [g/cm³]');
  checkRange(measuredExt, 0, 100, 'Gemessener Extrakt [g/100ml]');
  checkRange(spindleAlc, 0, 100, 'Spindelwert Alkohol [%vol]');
  checkRange(spindleDensAtTemp, 0.70, 1.40, 'Spindelwert Dichte [g/cm³]');
  checkRange(labAlc, 0, 100, 'Labor Alkohol [%vol]');
  checkRange(labDens, 0.70, 1.40, 'Labor Dichte [g/cm³]');
  checkRange(labExt, 0, 100, 'Labor Extrakt [g/100ml]');

  const waterMode = raw.water_mode || WATER_BY_VOLUME;

  if (diluted && probeInput !== null && probeInput <= 0) return fail('Das Probevolumen muss größer als 0 sein.');
  if (diluted && waterInput !== null && waterInput < 0) return fail('Die Wasserzugabe darf nicht negativ sein.');

  // Volumina auf 20 °C bringen (nur im Verdünnungsmodus)
  let probeVol = null;
  let waterVol = null;
  if (diluted) {
    if (probeInput !== null) probeVol = calc.correctVolumeTemp(probeInput, roomTemp, false);
    if (waterInput !== null) {
      if (waterMode === WATER_BY_MASS) {
        // Masse ist temperaturunabhängig: Volumen bei 20 °C direkt aus der Dichte bei 20 °C
        waterVol = waterInput / calc.waterDensityTemp(20.0);
      } else {
        waterVol = calc.correctVolumeTemp(waterInput, roomTemp, true);
      }
    }
  }

  // Spindeldichte auf 20 °C (braucht den Spindelwert Alkohol für den Korrekturkoeffizienten)
  let spindleDens20c = null;
  if (spindleDensAtTemp !== null) {
    if (spindleAlc === null) {
      return fail('Für die Temperaturkorrektur der Spindeldichte wird der Spindelwert Alkohol benötigt. '
        + "Bitte 'Spindelwert Alkohol' eingeben.");
    }
    spindleDens20c = calc.correctDensityTo20C(spindleDensAtTemp, roomTemp, spindleAlc);
  }

  if (ignored.length) messages.push([LEVEL_WARNING, 'Ungültige Eingaben (keine Zahl) wurden ignoriert: ' + ignored.join(', ')]);
  if (ranges.length) {
    messages.push([LEVEL_WARNING, 'Außerhalb des erwarteten Wertebereichs (werden trotzdem verwendet, bitte prüfen): ' + ranges.join('; ')]);
  }

  const anyMeasured = [measuredAlc, measuredDens, measuredExt].some((v) => v !== null);
  const canCalculate = diluted ? probeVol !== null && waterVol !== null && anyMeasured : anyMeasured;
  const canShowSpindleDensity = spindleDensAtTemp !== null;
  if (!canCalculate && !canShowSpindleDensity) {
    if (diluted) {
      return fail('Bitte mindestens eingeben: Probevolumen, Wasserzugabe und mindestens einen Messwert, '
        + 'oder die Spindeldichte für die Temperaturkorrektur.');
    }
    return fail('Bitte mindestens einen Messwert eingeben, oder die Spindeldichte für die Temperaturkorrektur.');
  }

  // Messbereich des Geräts
  if (measuredAlc !== null && measuredAlc > DEVICE_MAX_ALCOHOL) {
    messages.push([LEVEL_WARNING, `Der gemessene Alkohol (${formatDe(measuredAlc, 2)} %vol) liegt über dem `
      + `Messbereich des Alex 501 (bis ${formatDe(DEVICE_MAX_ALCOHOL, 0)} %vol). Bitte die Probe verdünnen.`]);
  }

  // Berechnung
  let actualAlc = null;
  let actualDens = null;
  let actualExt = null;
  let amplification = null;
  let dilutionFactor = null;
  let effectiveFactor = null;
  let expectedDensityOriginal = null;
  const useCurve = Boolean(useCalibration) && Array.isArray(calibData) && calibData.length >= 2;

  if (canCalculate && diluted) {
    dilutionFactor = calc.computeDilutionFactor(probeVol, waterVol);
    effectiveFactor = dilutionFactor;
    if (measuredAlc !== null) {
      try {
        actualAlc = calc.computeActualAlcohol(measuredAlc, probeVol, waterVol);
      } catch (error) {
        if (error instanceof CalcError) return fail(error.message);
        throw error;
      }
      effectiveFactor = calc.computeEffectiveDilutionFactor(measuredAlc, probeVol, waterVol);
      amplification = amplificationFactor(measuredAlc, probeVol, waterVol);
      // Kalibrierkurve auf den berechneten Alkoholgehalt (siehe Berechnungslogik_Alex501.txt, Punkt 5)
      if (useCurve) actualAlc = calc.applyCalibrationCurve(calibData, actualAlc);
    }
    if (measuredAlc !== null && measuredDens !== null) {
      [actualDens, expectedDensityOriginal] = calc.computeActualDensity(measuredAlc, measuredDens, actualAlc, effectiveFactor);
    }
    if (measuredExt !== null) actualExt = calc.computeActualExtract(measuredExt, effectiveFactor);
    const totalVolume = effectiveFactor * probeVol;
    if (totalVolume < MIN_MEASURING_VOLUME) {
      messages.push([LEVEL_INFO, `Die verdünnte Probe hat etwa ${formatDe(totalVolume, 1)} ml. Für eine `
        + `Messung am Alex 501 werden mindestens ${formatDe(MIN_MEASURING_VOLUME, 0)} ml benötigt.`]);
    }
  } else if (canCalculate) {
    // Direkte Messung: Werte werden unverändert übernommen (nur optional kalibriert)
    actualAlc = measuredAlc;
    amplification = measuredAlc !== null ? 1.0 : null;
    if (actualAlc !== null && useCurve) actualAlc = calc.applyCalibrationCurve(calibData, actualAlc);
    actualDens = measuredDens;
    actualExt = measuredExt;
    if (actualAlc !== null) expectedDensityOriginal = calc.interpolateDensityFromAlcohol(actualAlc);
  }

  // Vergleiche
  const comparison = {};
  if (spindleAlc !== null && actualAlc !== null) {
    const deviation = actualAlc - spindleAlc;
    comparison.alcohol = {
      spindle_value: spindleAlc,
      alex501_value: actualAlc,
      deviation,
      deviation_percent: spindleAlc > 0 ? (deviation / spindleAlc) * 100 : 0,
    };
    if (amplification !== null) {
      const limit = SPINDLE_ALCOHOL_TOLERANCE + DEVICE_ALCOHOL_TOLERANCE * amplification;
      Object.assign(comparison.alcohol, {
        limit,
        within_limit: Math.abs(deviation) <= limit,
        spindle_tolerance: SPINDLE_ALCOHOL_TOLERANCE,
        alex_tolerance: DEVICE_ALCOHOL_TOLERANCE * amplification,
      });
    }
  }
  if (spindleDensAtTemp !== null && spindleDens20c !== null) {
    const densityComparison = { spindle_value_at_temp: spindleDensAtTemp, spindle_value_20C: spindleDens20c };
    if (actualDens !== null) {
      const deviation = spindleDens20c - actualDens;
      Object.assign(densityComparison, {
        alex501_value_20C: actualDens,
        deviation,
        deviation_percent: actualDens > 0 ? (deviation / actualDens) * 100 : 0,
      });
    }
    comparison.density = densityComparison;
  }
  const lab = {};
  for (const [key, reference, calculated] of [['alcohol', labAlc, actualAlc], ['density', labDens, actualDens], ['extract', labExt, actualExt]]) {
    if (reference !== null && calculated !== null) {
      const deviation = calculated - reference;
      lab[key] = {
        lab_value: reference,
        alex501_value: calculated,
        deviation,
        deviation_percent: reference > 0 ? (deviation / reference) * 100 : 0,
      };
    }
  }
  if (Object.keys(lab).length) comparison.lab = lab;

  return {
    ok: true,
    messages,
    timestamp: isoLocal(now),
    sample_name: sampleName,
    batch,
    tank_nr: tankNr,
    mode,
    input: {
      room_temp: roomTemp,
      probe_volume: probeVol,
      water_volume: waterVol,
      probe_volume_input: diluted ? probeInput : null,
      water_input: diluted ? waterInput : null,
      water_mode: diluted ? waterMode : null,
      measured_alcohol: measuredAlc,
      measured_density: measuredDens,
      measured_extract: measuredExt,
      dilution_factor: dilutionFactor,
      spindle_alcohol: spindleAlc,
      spindle_density_at_temp: spindleDensAtTemp,
      spindle_density_20C: spindleDens20c,
      calibration_applied: useCurve,
      lab_alcohol: labAlc,
      lab_density: labDens,
      lab_extract: labExt,
      lab_note: labNote,
    },
    output: {
      actual_alcohol: actualAlc,
      actual_density: actualDens,
      actual_extract: actualExt,
      effective_dilution_factor: effectiveFactor,
      amplification,
      alcohol_tolerance: amplification === null ? null : DEVICE_ALCOHOL_TOLERANCE * amplification,
    },
    derived: { expected_density_original: expectedDensityOriginal },
    comparison,
    has_calculation: canCalculate,
  };
}

/** Textbericht (Anzeige, Teilen, Text-Export) aus einem Ergebnis von evaluateMeasurement. */
export function formatReport(result) {
  const line = '='.repeat(60);
  const inp = result.input;
  const out = result.output;
  const comparison = result.comparison;
  const diluted = result.mode === MODE_DILUTED;
  const parts = [
    'ALEX 501 Mazeratinterpolation',
    diluted ? 'Messung einer verdünnten Probe und Umrechnung auf Endwerte' : 'Direkte Messung (ohne Verdünnung)',
    line, '', 'BERECHNUNGSERGEBNISSE', line, '',
    `Probenbezeichnung: ${result.sample_name || '-'}`,
    `Charge: ${result.batch || '-'}`,
    `Tank: ${result.tank_nr || '-'}`,
  ];
  if (result.has_calculation) parts.push('Kalibrierkurve: ' + (inp.calibration_applied ? 'angewendet' : 'nicht angewendet'));

  if (result.has_calculation) {
    parts.push('', 'Eingabewerte:');
    if (diluted) {
      parts.push(`  Verdünnung: ${formatDe(inp.probe_volume, 1)} ml Probe + ${formatDe(inp.water_volume, 1)} ml Wasser (bei 20 °C)`);
      parts.push(`  Verdünnungsfaktor: 1:${formatDe(inp.dilution_factor, 2)}`);
      if (inp.measured_alcohol !== null) {
        parts.push(`  Wirksamer Faktor (mit Volumenkontraktion): 1:${formatDe(out.effective_dilution_factor, 2)}`);
      }
    }
    if (inp.measured_alcohol !== null) parts.push(`  Gemessener Alkoholgehalt: ${formatDe(inp.measured_alcohol, 2)} %vol.`);
    if (inp.measured_density !== null) parts.push(`  Gemessene Dichte: ${formatDe(inp.measured_density, 5)} g/cm³`);
    if (inp.measured_extract !== null) parts.push(`  Gemessener Extrakt: ${formatDe(inp.measured_extract, 2)} g/100ml`);
    parts.push('', line, '', diluted ? 'Berechnete tatsächliche Werte der Originalprobe:' : 'Werte der Probe (direkt gemessen):', '');
    if (out.actual_alcohol !== null) {
      const tolerance = out.alcohol_tolerance;
      parts.push(`  Alkoholgehalt: ${formatDe(out.actual_alcohol, 2)} %vol.`
        + (tolerance !== null ? ` (Gerätegrenze ±${formatDe(tolerance, 2)})` : ''));
    }
    if (out.actual_density !== null) parts.push(`  Dichte: ${formatDe(out.actual_density, 5)} g/cm³`);
    if (out.actual_extract !== null) parts.push(`  Extraktgehalt: ${formatDe(out.actual_extract, 2)} g/100ml`);
  }

  if (comparison.alcohol) {
    const c = comparison.alcohol;
    parts.push('', line, '', 'VERGLEICH MIT SPINDELUNG (Aräometer) - Alkohol:', '',
      `  Gespindelter Wert:        ${formatDe(c.spindle_value, 2)} %vol.`,
      `  Alex 501 (berechnet):     ${formatDe(c.alex501_value, 2)} %vol.`, '',
      `  Abweichung:               ${signed(c.deviation, 2)} %vol. (${signed(c.deviation_percent, 1)}%)`);
    if ('limit' in c) {
      parts.push(`  Messgrenzen:              ±${formatDe(c.limit, 2)} %vol (Spindel ±${formatDe(c.spindle_tolerance, 2)} `
        + `+ Alex ±${formatDe(c.alex_tolerance, 2)}): Abweichung ${c.within_limit ? 'innerhalb' : 'außerhalb'} der Grenzen`);
    }
  }
  if (comparison.density) {
    const c = comparison.density;
    const temp = formatDe(inp.room_temp, 1);
    parts.push('', line, '');
    if ('deviation' in c) {
      parts.push('VERGLEICH MIT SPINDELUNG (Aräometer) - Dichte:', '',
        `  Gespindelter Wert (${temp}°C): ${formatDe(c.spindle_value_at_temp, 5)} g/cm³`,
        `  Korrigiert auf 20°C:            ${formatDe(c.spindle_value_20C, 5)} g/cm³`,
        `  Alex 501 (berechnet, 20°C):     ${formatDe(c.alex501_value_20C, 5)} g/cm³`, '',
        `  Abweichung:                     ${signed(c.deviation, 5)} g/cm³ (${signed(c.deviation_percent, 2)}%)`);
    } else {
      parts.push('TEMPERATURKORREKTUR SPINDELDICHTE:', '',
        `  Gespindelter Wert (${temp}°C): ${formatDe(c.spindle_value_at_temp, 5)} g/cm³`,
        `  Korrigiert auf 20°C:            ${formatDe(c.spindle_value_20C, 5)} g/cm³`);
    }
  }
  if (comparison.lab) {
    parts.push('', line, '', 'VERGLEICH MIT LABORANALYSE:', '');
    const names = { alcohol: ['Alkohol', '%vol.', 2], density: ['Dichte', 'g/cm³', 5], extract: ['Extrakt', 'g/100ml', 2] };
    for (const [key, [label, unit, decimals]] of Object.entries(names)) {
      const c = comparison.lab[key];
      if (c) {
        parts.push(`  ${label}: Labor ${formatDe(c.lab_value, decimals)} ${unit}, Alex 501 ${formatDe(c.alex501_value, decimals)} ${unit}, `
          + `Abweichung ${signed(c.deviation, decimals)} (${signed(c.deviation_percent, 1)}%)`);
      }
    }
    if (inp.lab_note) parts.push(`  Bemerkung: ${inp.lab_note}`);
  }

  parts.push('', line);
  if (result.has_calculation) {
    parts.push('', 'Hinweise:');
    if (diluted) parts.push('- Die Berechnung berücksichtigt Volumenkontraktion (Massenbilanz)');
    parts.push('- Dichte-Werte basieren auf der Alkoholtabelle CRA 1996 (nach OIML R 22)',
      '- Für höchste Präzision wird eine Kalibrierung empfohlen');
    if (diluted) {
      parts.push('- Extraktstoffe werden bei der Alkoholberechnung nicht berücksichtigt (Abweichung steigt mit dem Extraktgehalt)');
    }
    if (inp.spindle_alcohol !== null) parts.push('- Spindelung (Aräometer) ist die Referenzmethode für Zollamt');
  }
  for (const [level, text] of result.messages) {
    if (level !== LEVEL_ERROR) parts.push((level === LEVEL_WARNING ? '! ' : 'i ') + text);
  }
  parts.push('', `Zeitstempel: ${formatTimestamp(result.timestamp, true)}`, '');
  return parts.join('\n');
}

// --- Messhistorie: Darstellung gespeicherter Messungen (Zeilen mit denselben Schlüsseln wie die Windows-Datenbank) ---

export const MODE_LABELS = { [MODE_DILUTED]: 'Verdünnt', [MODE_DIRECT]: 'Direkt' };

// [Schlüssel, Spaltenüberschrift]
export const HISTORY_COLUMNS = [
  ['timestamp', 'Zeit'], ['sample_name', 'Probe'], ['batch', 'Charge'], ['tank_nr', 'Tank'], ['mode', 'Modus'],
  ['actual_alcohol', 'Alkohol %vol'], ['actual_density', 'Dichte g/cm³'], ['actual_extract', 'Extrakt g/100ml'],
  ['spindle', 'Spindel %vol'], ['spindle_dev', 'Δ Spindel'], ['lab', 'Labor %vol'], ['lab_dev', 'Δ Labor'],
];

const fmt = (value, decimals) => (value === null || value === undefined ? '–' : formatDe(value, decimals));
const fmtSigned = (value, decimals) => (value === null || value === undefined ? '–' : signed(value, decimals));
const fmtTime = (timestamp) => formatTimestamp(timestamp, false) ?? (timestamp || '–');
const deviation = (calculated, reference) => (calculated == null || reference == null ? null : calculated - reference);

/** Werte einer Messung für die Übersichtstabelle (Reihenfolge wie HISTORY_COLUMNS). */
export function historyTableValues(row) {
  return [
    fmtTime(row.timestamp),
    row.sample_name || '–',
    row.batch || '–',
    row.tank_nr || '–',
    MODE_LABELS[row.mode] ?? '–',
    fmt(row.actual_alcohol, 2),
    fmt(row.actual_density, 5),
    fmt(row.actual_extract, 2),
    fmt(row.spindle_alcohol, 2),
    fmtSigned(deviation(row.actual_alcohol, row.spindle_alcohol), 2),
    fmt(row.lab_alcohol, 2),
    fmtSigned(deviation(row.actual_alcohol, row.lab_alcohol), 2),
  ];
}

/** Detailansicht einer Messung als Liste aus ['head', Titel] und ['item', Bezeichnung, Wert]. */
export function historyDetailLines(row) {
  const waterUnit = row.water_mode === WATER_BY_MASS ? 'g' : 'ml';
  const has = (key) => row[key] !== null && row[key] !== undefined;
  const lines = [['head', 'Ansatz'],
    ['item', 'Tank', row.tank_nr || '–'],
    ['item', 'Modus', MODE_LABELS[row.mode] ?? '– (ältere Messung)'],
    ['item', 'Raumtemperatur', fmt(row.room_temp, 1) + ' °C']];
  if (row.mode !== MODE_DIRECT) {
    lines.push(
      ['item', 'Probe (eingegeben)', fmt(row.probe_volume_input, 2) + ' ml'],
      ['item', 'Wasser (eingegeben)', fmt(row.water_input, 2) + ' ' + waterUnit],
      ['item', 'Volumen bei 20 °C', `${fmt(row.probe_volume, 2)} / ${fmt(row.water_volume, 2)} ml`],
      ['item', 'Verdünnungsfaktor', '1:' + fmt(row.dilution_factor, 3)],
      ['item', 'Wirksamer Faktor', '1:' + fmt(row.effective_dilution_factor, 3)],
    );
  }
  lines.push(
    ['head', 'Alex 501 gemessen'],
    ['item', 'Alkohol', fmt(row.measured_alcohol, 2) + ' %vol'],
    ['item', 'Dichte', fmt(row.measured_density, 5) + ' g/cm³'],
    ['item', 'Extrakt', fmt(row.measured_extract, 2) + ' g/100ml'],
    ['head', 'Ergebnis' + (row.mode !== MODE_DIRECT ? ' (Originalprobe)' : '')],
    ['item', 'Alkohol', fmt(row.actual_alcohol, 2) + ' %vol'],
    ['item', 'Dichte', fmt(row.actual_density, 5) + ' g/cm³'],
    ['item', 'Extrakt', fmt(row.actual_extract, 2) + ' g/100ml'],
    ['item', 'Kalibrierkurve', row.calibration_applied ? 'angewendet' : 'nicht angewendet'],
  );
  if (has('spindle_alcohol') || has('spindle_density_at_temp')) {
    lines.push(['head', 'Spindelung'],
      ['item', 'Alkohol', fmt(row.spindle_alcohol, 2) + ' %vol'],
      ['item', 'Dichte (T / 20 °C)', `${fmt(row.spindle_density_at_temp, 5)} / ${fmt(row.spindle_density_20C, 5)}`]);
  }
  if (has('lab_alcohol') || has('lab_density') || has('lab_extract') || row.lab_note) {
    lines.push(['head', 'Laboranalyse'],
      ['item', 'Alkohol', fmt(row.lab_alcohol, 2) + ' %vol'],
      ['item', 'Dichte', fmt(row.lab_density, 5) + ' g/cm³'],
      ['item', 'Extrakt', fmt(row.lab_extract, 2) + ' g/100ml']);
    if (row.lab_note) lines.push(['item', 'Bemerkung', row.lab_note]);
  }
  return lines;
}

/** Tabelle (Kopfzeile + Zeilen) aller gespeicherten Spalten für den CSV-Export; Zahlen mit Dezimalkomma. */
export function historyCsvTable(rows) {
  if (!rows.length) return [];
  const keys = Object.keys(rows[0]);
  const table = [keys];
  for (const row of rows) {
    table.push(keys.map((k) => {
      const value = row[k];
      if (value === null || value === undefined) return '';
      // Python: Gleitkommazahlen mit Komma, ganze Zahlen und Text unverändert
      return typeof value === 'number' && !Number.isInteger(value) ? String(value).replace('.', ',') : String(value);
    }));
  }
  return table;
}
