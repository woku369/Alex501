"""
SQLite-Persistenz für die Alex 501 Mazerat-Interpolation (Messhistorie).
"""

import sqlite3
import os
import shutil
import glob
from datetime import datetime


class MeasurementDB:
    MAX_BACKUPS = 20  # Anzahl der aufbewahrten Backup-Kopien

    def __init__(self, db_path="messungen.db"):
        self.db_path = db_path
        self._init_db()
        self._backup_db()

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
        Version vor der Schema-Erweiterung) die fehlenden Spalten nachträglich."""
        c = conn.cursor()
        c.execute("PRAGMA table_info(messungen)")
        existing_columns = {row[1] for row in c.fetchall()}
        new_columns = {
            'room_temp': 'REAL',
            'spindle_density_at_temp': 'REAL',
            'spindle_density_20C': 'REAL',
            'calibration_applied': 'INTEGER'
        }
        for column, col_type in new_columns.items():
            if column not in existing_columns:
                c.execute(f"ALTER TABLE messungen ADD COLUMN {column} {col_type}")
        conn.commit()

    def fetch_all(self):
        """Gibt alle Messungen (neueste zuerst) mit allen gespeicherten Spalten zurück,
        in der gleichen Spaltenreihenfolge wie insert_measurement() + id/timestamp/sample_name/batch."""
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute("""SELECT id, timestamp, sample_name, batch, room_temp, measured_alcohol, measured_density,
                                measured_extract, spindle_alcohol, spindle_density_at_temp, spindle_density_20C,
                                dilution_factor, calibration_applied, actual_alcohol, actual_density, actual_extract
                         FROM messungen ORDER BY id DESC""")
            return c.fetchall()

    def insert_measurement(self, data):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('''
                INSERT INTO messungen (
                    timestamp, sample_name, batch, room_temp, probe_volume, water_volume,
                    measured_alcohol, measured_density, measured_extract, dilution_factor,
                    spindle_alcohol, spindle_density_at_temp, spindle_density_20C, calibration_applied,
                    actual_alcohol, actual_density, actual_extract
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                data['timestamp'],
                data['sample_name'],
                data['batch'],
                data['input']['room_temp'],
                data['input']['probe_volume'],
                data['input']['water_volume'],
                data['input']['measured_alcohol'],
                data['input']['measured_density'],
                data['input']['measured_extract'],
                data['input']['dilution_factor'],
                data['input']['spindle_alcohol'],
                data['input']['spindle_density_at_temp'],
                data['input']['spindle_density_20C'],
                int(bool(data['input']['calibration_applied'])),
                data['output']['actual_alcohol'],
                data['output']['actual_density'],
                data['output']['actual_extract']
            ))
            conn.commit()
