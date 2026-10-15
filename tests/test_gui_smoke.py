"""
Rauchtest der Oberfläche (gui.py): baut das Fenster auf und spielt die wichtigsten Abläufe durch.
Wird übersprungen, wenn tkinter oder matplotlib fehlen oder kein Bildschirm verfügbar ist.

Ausführen mit:
    python -m unittest discover -s tests
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import tkinter as tk
    import matplotlib  # noqa: F401
    import gui
    import measurement as meas
    GUI_IMPORT_ERROR = None
except Exception as error:  # fehlende Pakete
    GUI_IMPORT_ERROR = error


@unittest.skipIf(GUI_IMPORT_ERROR is not None, f"GUI-Abhängigkeiten fehlen: {GUI_IMPORT_ERROR}")
class TestGuiSmoke(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_cwd = os.getcwd()
        os.chdir(self.tmp.name)  # messungen.db und kalibrierkurve.json landen im Temp-Ordner
        try:
            self.root = tk.Tk()
        except tk.TclError as error:
            os.chdir(self.old_cwd)
            self.tmp.cleanup()
            self.skipTest(f"kein Bildschirm verfügbar: {error}")
        self.root.geometry("1340x880+0+0")
        self.app = gui.Alex501App(self.root)
        self.root.update()

    def tearDown(self):
        self.root.destroy()
        os.chdir(self.old_cwd)
        self.tmp.cleanup()

    def fill_diluted(self):
        app = self.app
        app.sample_name.set("Salbei")
        app.batch_field.set("26-01")
        app.tank_nr.set("T-12")
        app.room_temp.set("21")
        app.probe_volume.set("36")
        app.water_value.set("9,2")
        app.measured_alcohol.set("40,1")
        app.measured_density.set("0,9505")
        app.measured_extract.set("1,6")

    def test_calculation_fills_tiles_and_report(self):
        self.fill_diluted()
        self.app.calculate_results()
        self.assertEqual(self.app.tile_alcohol.value.cget("text"), "50,16")
        self.assertIn("Salbei", self.app.last_report)
        self.assertIsNotNone(self.app.last_results)

    def test_repeated_calculation_is_saved_only_once(self):
        self.fill_diluted()
        self.app.calculate_results()
        self.app.calculate_results()
        self.assertEqual(len(self.app.measurement_db.fetch_all()), 1)
        self.app.measured_alcohol.set("40,2")
        self.app.calculate_results()
        self.assertEqual(len(self.app.measurement_db.fetch_all()), 2)

    def test_missing_temperature_shows_error_and_does_not_save(self):
        self.fill_diluted()
        self.app.room_temp.set("")
        self.app.calculate_results()
        self.assertEqual(self.app.measurement_db.fetch_all(), [])
        self.assertEqual(self.app.tile_alcohol.value.cget("text"), "–")
        texts = [child.cget("text") for child in self.app.message_frame.winfo_children()]
        self.assertTrue(any("Raumtemperatur" in text for text in texts))

    def test_direct_mode_disables_dilution_fields_and_takes_values_over(self):
        app = self.app
        app.mode.set(meas.MODE_DIRECT)
        app._on_mode_change()
        self.assertEqual(str(app.probe_entry.cget("state")), "disabled")
        self.assertEqual(str(app.planner_button.cget("state")), "disabled")
        app.room_temp.set("21")
        app.measured_alcohol.set("27,05")
        app.calculate_results()
        self.assertEqual(app.tile_alcohol.value.cget("text"), "27,05")
        app.mode.set(meas.MODE_DILUTED)
        app._on_mode_change()
        self.assertEqual(str(app.probe_entry.cget("state")), "normal")

    def test_new_measurement_clears_inputs_but_keeps_temperature_and_mode(self):
        self.fill_diluted()
        self.app.calculate_results()
        self.app.clear_inputs()
        self.assertEqual(self.app.sample_name.get(), "")
        self.assertEqual(self.app.tank_nr.get(), "")
        self.assertEqual(self.app.measured_alcohol.get(), "")
        self.assertEqual(self.app.room_temp.get(), "21")
        self.assertEqual(self.app.tile_alcohol.value.cget("text"), "–")

    def test_history_shows_saved_rows_and_filter(self):
        self.fill_diluted()
        self.app.calculate_results()
        self.app.sample_name.set("Thymian")
        self.app.calculate_results()
        tree = self.app.history_tree
        self.assertEqual(len(tree.get_children()), 2)
        self.app.history_filter.set("thym")
        self.root.update()
        self.assertEqual(len(tree.get_children()), 1)
        self.app.history_filter.set("t-12")  # Suche nach Tank-Nr.
        self.root.update()
        self.assertEqual(len(tree.get_children()), 2)
        self.app.history_filter.set("thym")
        self.root.update()
        tree.selection_set(tree.get_children()[0])
        self.root.update()
        self.assertTrue(self.app.history_detail.winfo_children())

    def test_lab_reference_can_be_added_later(self):
        self.fill_diluted()
        self.app.calculate_results()
        row_id = self.app.measurement_db.fetch_all()[0]["id"]
        self.app.measurement_db.update_lab_reference(row_id, 51.2, None, None, "Labor X")
        self.app.refresh_history()
        values = self.app.history_tree.item(str(row_id), "values")
        self.assertEqual(values[10], "51,20")

    def test_calibration_points_add_and_delete(self):
        app = self.app
        for ref, measured in (("10", "9,7"), ("20", "19,8")):
            app.calib_ref.set(ref)
            app.calib_meas.set(measured)
            app.add_calib_point()
        self.assertEqual(len(app.calib_data), 2)
        self.assertTrue(os.path.exists("kalibrierkurve.json"))
        first = app.calib_tree.get_children()[0]
        app.calib_tree.selection_set(first)
        app.delete_selected_calib_point()
        self.assertEqual(app.calib_data, [(20.0, 19.8)])

    def test_planner_dialog_opens(self):
        self.app.open_planner()
        self.root.update()
        dialogs = [w for w in self.root.winfo_children() if isinstance(w, tk.Toplevel)]
        self.assertEqual(len(dialogs), 1)


if __name__ == "__main__":
    unittest.main()
