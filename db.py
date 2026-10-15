"""
SQLite-Persistenz für die Alex 501 Mazerat-Interpolation (Messhistorie).
"""

import sqlite3
import os
import shutil
import glob
from datetime import datetime

# Spalten, die nachträglich zur ersten Schema-Version dazugekommen sind (ALTER TABLE ADD COLUMN).
_ADDED_COLUMNS = {
    'room_temp': 'REAL',
    'spindle_density_at_temp': 'REAL',
    'spindle_density_20C': 'REAL',
    'calibration_applied': 'INTEGER',
    'tank_nr': 'TEXT',                    # Tank bzw. Lagerort (Inventur, Zuordnung zu MazerationsMeister)
    'mode': 'TEXT',                       # 'diluted' oder 'direct'
    'probe_volume_input': 'REAL',         # Probevolumen wie eingegeben (ml, bei Raumtemperatur)
    'water_input': 'REAL',                # Wasserzugabe wie eingegeben (ml oder g)
    'water_mode': 'TEXT',                 # 'vol' oder 'mass'
    'effective_dilution_factor': 'REAL',
    'lab_alcohol': 'REAL',
    'lab_density': 'REAL',
    'lab_extract': 'REAL',
    'lab_note': 'TEXT',
}


class MeasurementDB:
    MAX_BACKUPS = 20  # Anzahl der aufbewahrten Backup-Kopien

    def __init__(self, db_path="messungen.db"):
        self.db_path = db_path
        # Zuerst sichern, dann erst das Schema anpassen: so enthält die Sicherung den Stand vor einer Migration
        self._backup_db()
        self._init_db()

    def _backup_db(self):
        """Legt bei jedem Programmstart eine zeitgestempelte Sicherungskopie der
        Datenbank an und behält nur die letzten MAX_BACKUPS Kopien."""
        if not os.path.exists(self.db_path):
            return
        try:
            backup_dir = os.path.join(os.path.dirname(os.path.abspath(self.db_path)), "backups")
            os.makedirs(backup_dir, exist_ok=True)
            db_name = os.path.splitext(os.path.basename(self.db_path))[0]
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = os.path.join(backup_dir, f"{db_name}_backup_{timestamp}.db")
            shutil.copy2(self.db_path, backup_path)

            # Alte Backups über dem Limit entfernen (älteste zuerst)
            existing_backups = sorted(glob.glob(os.path.join(backup_dir, f"{db_name}_backup_*.db")))
            for old_backup in existing_backups[:-self.MAX_BACKUPS]:
                os.remove(old_backup)
        except OSError as e:
            print(f"Warnung: Backup der Datenbank konnte nicht erstellt werden: {e}")

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('''
                CREATE TABLE IF NOT EXISTS messungen (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    sample_name TEXT,
                    batch TEXT,
                    room_temp REAL,
                    probe_volume REAL,
                    water_volume REAL,
                    measured_alcohol REAL,
                    measured_density REAL,
                    measured_extract REAL,
                    dilution_factor REAL,
                    spindle_alcohol REAL,
                    spindle_density_at_temp REAL,
                    spindle_density_20C REAL,
                    calibration_applied INTEGER,
                    actual_alcohol REAL,
                    actual_density REAL,
                    actual_extract REAL
                )
            ''')
            conn.commit()
            self._migrate_schema(conn)

    def _migrate_schema(self, conn):
        """Ergänzt bei einer bereits bestehenden Datenbank (aus einer älteren
        Version vor einer Schema-Erweiterung) die fehlenden Spalten nachträglich.
        Bestehende Messungen bleiben unverändert (neue Spalten sind dort leer)."""
        c = conn.cursor()
        c.execute("PRAGMA table_info(messungen)")
        existing_columns = {row[1] for row in c.fetchall()}
        for column, col_type in _ADDED_COLUMNS.items():
            if column not in existing_columns:
                c.execute(f"ALTER TABLE messungen ADD COLUMN {column} {col_type}")
        conn.commit()

    def fetch_all(self):
        """Gibt alle Messungen (neueste zuerst) als Liste von Dicts mit allen Spalten zurück."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM messungen ORDER BY id DESC").fetchall()
            return [dict(row) for row in rows]

    def insert_measurement(self, data):
        """Speichert eine Messung (Ergebnis von measurement.evaluate_measurement) und gibt die ID zurück."""
        inp, out = data['input'], data['output']
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('''
                INSERT INTO messungen (
                    timestamp, sample_name, batch, tank_nr, mode, room_temp, probe_volume, water_volume,
                    probe_volume_input, water_input, water_mode,
                    measured_alcohol, measured_density, measured_extract, dilution_factor,
                    effective_dilution_factor,
                    spindle_alcohol, spindle_density_at_temp, spindle_density_20C, calibration_applied,
                    lab_alcohol, lab_density, lab_extract, lab_note,
                    actual_alcohol, actual_density, actual_extract
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                data['timestamp'],
                data['sample_name'],
                data['batch'],
                data.get('tank_nr') or None,
                data.get('mode'),
                inp['room_temp'],
                inp['probe_volume'],
                inp['water_volume'],
                inp.get('probe_volume_input'),
                inp.get('water_input'),
                inp.get('water_mode'),
                inp['measured_alcohol'],
                inp['measured_density'],
                inp['measured_extract'],
                inp['dilution_factor'],
                out.get('effective_dilution_factor'),
                inp['spindle_alcohol'],
                inp['spindle_density_at_temp'],
                inp['spindle_density_20C'],
                int(bool(inp['calibration_applied'])),
                inp.get('lab_alcohol'),
                inp.get('lab_density'),
                inp.get('lab_extract'),
                inp.get('lab_note') or None,
                out['actual_alcohol'],
                out['actual_density'],
                out['actual_extract'],
            ))
            conn.commit()
            return c.lastrowid

    def update_lab_reference(self, measurement_id, lab_alcohol=None, lab_density=None, lab_extract=None,
                             lab_note=None):
        """Trägt Laborwerte nachträglich zu einer vorhandenen Messung ein (Laborergebnisse kommen
        meist erst später). Gibt True zurück, wenn die Messung existiert."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "UPDATE messungen SET lab_alcohol = ?, lab_density = ?, lab_extract = ?, lab_note = ? WHERE id = ?",
                (lab_alcohol, lab_density, lab_extract, lab_note or None, measurement_id))
            conn.commit()
            return cursor.rowcount > 0

    @staticmethod
    def rows_from_export(data):
        """Liest die Zeilen aus einer Sicherung der Tablet-Version (JSON mit "rows") oder einer reinen Liste."""
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and data.get('format') == 'alex501-messungen' and isinstance(data.get('rows'), list):
            return data['rows']
        raise ValueError("Die Datei ist keine Sicherung der Alex-501-Messhistorie.")

    @staticmethod
    def _duplicate_key(row):
        parts = (row.get('timestamp'), row.get('sample_name'), row.get('batch'), row.get('tank_nr'),
                 row.get('actual_alcohol'))
        return '|'.join('' if part is None else str(part) for part in parts)

    def import_rows(self, rows):
        """Übernimmt Messungen aus einer Sicherung der Tablet-Version. Bereits vorhandene Messungen
        (gleicher Zeitstempel, Probe, Charge, Tank und Ergebnis) werden übersprungen, die ID wird neu
        vergeben, unbekannte Spalten werden ignoriert. Gibt (hinzugefügt, übersprungen) zurück."""
        existing = {self._duplicate_key(row) for row in self.fetch_all()}
        added = skipped = 0
        with sqlite3.connect(self.db_path) as conn:
            columns = [row[1] for row in conn.execute("PRAGMA table_info(messungen)") if row[1] != 'id']
            for source in rows:
                if not isinstance(source, dict) or not source.get('timestamp'):
                    skipped += 1
                    continue
                key = self._duplicate_key(source)
                if key in existing:
                    skipped += 1
                    continue
                existing.add(key)
                values = {column: source[column] for column in columns if column in source}
                names = ', '.join(values)
                marks = ', '.join('?' for _ in values)
                conn.execute(f"INSERT INTO messungen ({names}) VALUES ({marks})", tuple(values.values()))
                added += 1
            conn.commit()
        return added, skipped
