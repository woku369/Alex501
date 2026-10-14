"""
Unit-Tests für die SQLite-Persistenz (db.py): Anlegen, Migration einer alten Datenbank, Speichern, Laborwerte.

Ausführen mit:
    python -m unittest discover -s tests
"""

import glob
import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import measurement as m
from db import MeasurementDB

NOW = datetime(2026, 10, 14, 12, 0, 0)


def sample_result(**fields):
    raw = {"mode": m.MODE_DILUTED, "room_temp": "21", "probe_volume": "30", "water_value": "9,2",
           "water_mode": m.WATER_BY_MASS, "measured_alcohol": "40", "measured_density": "0.9500",
           "measured_extract": "2", "sample_name": "Salbei", "batch": "26-01"}
    raw.update(fields)
    return m.evaluate_measurement(raw, now=NOW)


class TestMeasurementDB(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "messungen.db")

    def tearDown(self):
        self.tmp.cleanup()

    def test_new_database_has_all_columns(self):
        db = MeasurementDB(self.path)
        with sqlite3.connect(self.path) as conn:
            columns = {row[1] for row in conn.execute("PRAGMA table_info(messungen)")}
        self.assertTrue({"mode", "lab_alcohol", "probe_volume_input", "water_input", "water_mode",
                         "effective_dilution_factor", "lab_note"} <= columns)
        self.assertEqual(db.fetch_all(), [])

    def test_insert_and_fetch_roundtrip(self):
        db = MeasurementDB(self.path)
        result = sample_result()
        new_id = db.insert_measurement(result)
        row = db.fetch_all()[0]
        self.assertEqual(row["id"], new_id)
        self.assertEqual(row["sample_name"], "Salbei")
        self.assertEqual(row["mode"], m.MODE_DILUTED)
        self.assertEqual(row["water_mode"], m.WATER_BY_MASS)
        self.assertAlmostEqual(row["water_input"], 9.2)
        self.assertAlmostEqual(row["probe_volume_input"], 30.0)
        self.assertAlmostEqual(row["actual_alcohol"], result["output"]["actual_alcohol"])
        self.assertAlmostEqual(row["effective_dilution_factor"], result["output"]["effective_dilution_factor"])
        self.assertEqual(row["calibration_applied"], 0)

    def test_fetch_all_newest_first(self):
        db = MeasurementDB(self.path)
        first = db.insert_measurement(sample_result(sample_name="A"))
        second = db.insert_measurement(sample_result(sample_name="B"))
        self.assertEqual([row["id"] for row in db.fetch_all()], [second, first])

    def test_direct_measurement_is_stored_without_dilution_values(self):
        db = MeasurementDB(self.path)
        result = m.evaluate_measurement({"mode": m.MODE_DIRECT, "room_temp": "20", "measured_alcohol": "27",
                                         "measured_density": "1.0123", "measured_extract": "31,5"}, now=NOW)
        db.insert_measurement(result)
        row = db.fetch_all()[0]
        self.assertEqual(row["mode"], m.MODE_DIRECT)
        self.assertIsNone(row["dilution_factor"])
        self.assertIsNone(row["probe_volume_input"])
        self.assertAlmostEqual(row["actual_extract"], 31.5)

    def test_update_lab_reference(self):
        db = MeasurementDB(self.path)
        new_id = db.insert_measurement(sample_result())
        self.assertTrue(db.update_lab_reference(new_id, lab_alcohol=51.2, lab_density=0.93, lab_extract=2.5,
                                                lab_note="Labor X, 20.10."))
        row = db.fetch_all()[0]
        self.assertAlmostEqual(row["lab_alcohol"], 51.2)
        self.assertEqual(row["lab_note"], "Labor X, 20.10.")
        self.assertFalse(db.update_lab_reference(9999, lab_alcohol=1))

    def test_migration_of_old_database_keeps_rows_and_backs_up_old_state(self):
        # Datenbank im ältesten Schema (ohne spätere Spalten) mit einer vorhandenen Messung
        with sqlite3.connect(self.path) as conn:
            conn.execute("""CREATE TABLE messungen (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp TEXT,
                            sample_name TEXT, batch TEXT, probe_volume REAL, water_volume REAL,
                            measured_alcohol REAL, measured_density REAL, measured_extract REAL,
                            dilution_factor REAL, spindle_alcohol REAL, actual_alcohol REAL,
                            actual_density REAL, actual_extract REAL)""")
            conn.execute("INSERT INTO messungen (timestamp, sample_name, measured_alcohol, actual_alcohol) "
                         "VALUES ('2026-01-05T10:00:00', 'Altprobe', 40.0, 78.0)")
        db = MeasurementDB(self.path)
        rows = db.fetch_all()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["sample_name"], "Altprobe")
        self.assertAlmostEqual(rows[0]["actual_alcohol"], 78.0)
        self.assertIsNone(rows[0]["mode"])
        # Sicherung enthält noch das alte Schema (Backup vor Migration)
        backups = glob.glob(os.path.join(self.tmp.name, "backups", "messungen_backup_*.db"))
        self.assertEqual(len(backups), 1)
        with sqlite3.connect(backups[0]) as conn:
            old_columns = {row[1] for row in conn.execute("PRAGMA table_info(messungen)")}
        self.assertNotIn("mode", old_columns)
        # und neue Messungen funktionieren neben der alten
        db.insert_measurement(sample_result())
        self.assertEqual(len(db.fetch_all()), 2)

    def test_backups_are_limited(self):
        MeasurementDB(self.path)
        backup_dir = os.path.join(self.tmp.name, "backups")
        os.makedirs(backup_dir, exist_ok=True)
        for index in range(MeasurementDB.MAX_BACKUPS + 5):
            open(os.path.join(backup_dir, f"messungen_backup_2025010{index:03d}.db"), "w").close()
        MeasurementDB(self.path)
        self.assertLessEqual(len(glob.glob(os.path.join(backup_dir, "messungen_backup_*.db"))),
                             MeasurementDB.MAX_BACKUPS)


if __name__ == "__main__":
    unittest.main()
