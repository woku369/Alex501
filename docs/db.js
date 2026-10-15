// Messhistorie im Browser (IndexedDB). Die Zeilen haben dieselben Spaltennamen wie die SQLite-Datenbank
// der Windows-App (db.py), damit Exporte später dort importiert werden können.

const DB_NAME = 'alex501';
const STORE = 'messungen';
const DB_VERSION = 1;

export const EXPORT_FORMAT = 'alex501-messungen';

function openDb() {
  return new Promise((resolve, reject) => {
    if (!('indexedDB' in globalThis)) {
      reject(new Error('IndexedDB wird von diesem Browser nicht unterstützt.'));
      return;
    }
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains(STORE)) db.createObjectStore(STORE, { keyPath: 'id', autoIncrement: true });
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error ?? new Error('Datenbank konnte nicht geöffnet werden.'));
  });
}

function requestToPromise(request) {
  return new Promise((resolve, reject) => {
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

function transactionDone(transaction) {
  return new Promise((resolve, reject) => {
    transaction.oncomplete = () => resolve();
    transaction.onerror = () => reject(transaction.error);
    transaction.onabort = () => reject(transaction.error ?? new Error('Speichern abgebrochen.'));
  });
}

/** Wandelt ein Ergebnis von evaluateMeasurement in eine Zeile der Messhistorie (Spaltenreihenfolge wie in SQLite). */
export function resultToRow(result) {
  const inp = result.input;
  const out = result.output;
  return {
    timestamp: result.timestamp,
    sample_name: result.sample_name,
    batch: result.batch,
    room_temp: inp.room_temp,
    probe_volume: inp.probe_volume,
    water_volume: inp.water_volume,
    measured_alcohol: inp.measured_alcohol,
    measured_density: inp.measured_density,
    measured_extract: inp.measured_extract,
    dilution_factor: inp.dilution_factor,
    spindle_alcohol: inp.spindle_alcohol,
    spindle_density_at_temp: inp.spindle_density_at_temp,
    spindle_density_20C: inp.spindle_density_20C,
    calibration_applied: inp.calibration_applied ? 1 : 0,
    actual_alcohol: out.actual_alcohol,
    actual_density: out.actual_density,
    actual_extract: out.actual_extract,
    tank_nr: result.tank_nr || null,
    mode: result.mode,
    probe_volume_input: inp.probe_volume_input,
    water_input: inp.water_input,
    water_mode: inp.water_mode,
    effective_dilution_factor: out.effective_dilution_factor,
    lab_alcohol: inp.lab_alcohol,
    lab_density: inp.lab_density,
    lab_extract: inp.lab_extract,
    lab_note: inp.lab_note || null,
  };
}

/** Speichert eine Messung und gibt die ID zurück. */
export async function insertMeasurement(result) {
  const db = await openDb();
  try {
    const transaction = db.transaction(STORE, 'readwrite');
    const idRequest = transaction.objectStore(STORE).add(resultToRow(result));
    const id = await requestToPromise(idRequest);
    await transactionDone(transaction);
    return id;
  } finally {
    db.close();
  }
}

/** Alle Messungen, neueste zuerst. */
export async function fetchAll() {
  const db = await openDb();
  try {
    const rows = await requestToPromise(db.transaction(STORE, 'readonly').objectStore(STORE).getAll());
    // id zuerst, wie in der Windows-Datenbank (IndexedDB hängt den Schlüssel sonst hinten an)
    return rows.map((row) => ({ id: row.id, ...row })).sort((a, b) => b.id - a.id);
  } finally {
    db.close();
  }
}

/** Trägt Laborwerte nachträglich zu einer Messung ein. Gibt true zurück, wenn die Messung existiert. */
export async function updateLabReference(id, { lab_alcohol = null, lab_density = null, lab_extract = null, lab_note = '' } = {}) {
  const db = await openDb();
  try {
    const transaction = db.transaction(STORE, 'readwrite');
    const store = transaction.objectStore(STORE);
    const row = await requestToPromise(store.get(id));
    if (!row) return false;
    Object.assign(row, { lab_alcohol, lab_density, lab_extract, lab_note: lab_note || null });
    store.put(row);
    await transactionDone(transaction);
    return true;
  } finally {
    db.close();
  }
}

const duplicateKey = (row) => [row.timestamp, row.sample_name, row.batch, row.tank_nr, row.actual_alcohol].join('|');

/** Importiert Zeilen aus einem Export (JSON). Bereits vorhandene Messungen werden übersprungen. */
export async function importRows(rows) {
  const existing = new Set((await fetchAll()).map(duplicateKey));
  const db = await openDb();
  let added = 0;
  let skipped = 0;
  try {
    const transaction = db.transaction(STORE, 'readwrite');
    const store = transaction.objectStore(STORE);
    for (const source of rows) {
      if (!source || typeof source !== 'object' || !source.timestamp) {
        skipped += 1;
        continue;
      }
      const row = { ...source };
      delete row.id; // neue ID vergeben
      const key = duplicateKey(row);
      if (existing.has(key)) {
        skipped += 1;
        continue;
      }
      existing.add(key);
      store.add(row);
      added += 1;
    }
    await transactionDone(transaction);
  } finally {
    db.close();
  }
  return { added, skipped };
}

/** Export aller Messungen als Objekt (für JSON). */
export async function exportAll(now = new Date()) {
  return { format: EXPORT_FORMAT, version: 1, exported: now.toISOString(), rows: await fetchAll() };
}

/** Liest Zeilen aus einem Export (Objekt mit rows oder reine Liste). */
export function rowsFromExport(data) {
  if (Array.isArray(data)) return data;
  if (data && data.format === EXPORT_FORMAT && Array.isArray(data.rows)) return data.rows;
  throw new Error('Die Datei ist kein Export der Alex-501-Messhistorie.');
}
