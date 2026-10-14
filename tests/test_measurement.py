"""
Unit-Tests für den Messvorgang (Eingabeprüfung, Berechnung, Bericht) in measurement.py.

Ausführen mit:
    python -m unittest discover -s tests
"""

import os
import sys
import unittest
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import calculations as calc
import measurement as m

NOW = datetime(2026, 10, 14, 12, 0, 0)


def run(**fields):
    """Verdünnungsmessung mit sinnvollen Standardwerten, einzelne Felder überschreibbar."""
    raw = {"mode": m.MODE_DILUTED, "room_temp": "20", "probe_volume": "10", "water_value": "10",
           "water_mode": m.WATER_BY_VOLUME, "measured_alcohol": "40"}
    raw.update(fields)
    calib = raw.pop("calib_data", None)
    use = raw.pop("use_calibration", False)
    return m.evaluate_measurement(raw, calib_data=calib, use_calibration=use, now=NOW)


def levels(result):
    return [level for level, _ in result["messages"]]


class TestPlanDilution(unittest.TestCase):
    def test_roundtrip_hits_target_alcohol_and_volume(self):
        for probe_alc in (50, 53, 78, 80):
            plan = calc.plan_dilution(probe_alc, 45.0, 40.0)
            actual = calc.compute_actual_alcohol(40.0, plan["probe_volume"], plan["water_volume"])
            self.assertAlmostEqual(actual, probe_alc, places=4)
            real_volume = calc.compute_effective_dilution_factor(40.0, plan["probe_volume"], plan["water_volume"]) \
                * plan["probe_volume"]
            self.assertAlmostEqual(real_volume, 45.0, places=4)

    def test_water_mass_matches_volume_times_density(self):
        plan = calc.plan_dilution(78, 45.0, 40.0)
        self.assertAlmostEqual(plan["water_mass"], plan["water_volume"] * calc.water_density_temp(20.0), places=9)

    def test_summed_volume_exceeds_real_volume_by_contraction(self):
        plan = calc.plan_dilution(78, 45.0, 40.0)
        self.assertGreater(plan["summed_volume"], 45.0)

    def test_probe_at_or_below_target_raises(self):
        with self.assertRaises(ValueError):
            calc.plan_dilution(40, 45.0, 40.0)

    def test_invalid_target_or_volume_raises(self):
        with self.assertRaises(ValueError):
            calc.plan_dilution(78, 0, 40.0)
        with self.assertRaises(ValueError):
            calc.plan_dilution(78, 45.0, 100.0)


class TestInputValidation(unittest.TestCase):
    def test_room_temperature_is_required(self):
        result = run(room_temp="")
        self.assertFalse(result["ok"])
        self.assertIn("Raumtemperatur", result["messages"][0][1])

    def test_decimal_comma_is_accepted(self):
        result = run(room_temp="20,0", probe_volume="10,0", water_value="10,0", measured_alcohol="40,0")
        self.assertTrue(result["ok"])

    def test_invalid_optional_field_is_ignored_with_warning(self):
        result = run(measured_density="abc")
        self.assertTrue(result["ok"])
        self.assertIsNone(result["input"]["measured_density"])
        self.assertIn(m.LEVEL_WARNING, levels(result))

    def test_nothing_to_calculate_is_error(self):
        result = run(measured_alcohol="")
        self.assertFalse(result["ok"])

    def test_spindle_density_needs_spindle_alcohol(self):
        result = run(spindle_density="0.95")
        self.assertFalse(result["ok"])
        self.assertIn("Spindelwert Alkohol", result["messages"][-1][1])

    def test_out_of_range_value_warns_but_is_used(self):
        result = run(measured_density="2.5")
        self.assertTrue(result["ok"])
        self.assertAlmostEqual(result["input"]["measured_density"], 2.5)
        self.assertIn(m.LEVEL_WARNING, levels(result))

    def test_measured_alcohol_above_device_range_warns(self):
        result = run(measured_alcohol="52", water_value="2")
        self.assertTrue(result["ok"])
        self.assertTrue(any("Messbereich" in text for _, text in result["messages"]))

    def test_value_too_high_for_dilution_is_error(self):
        result = run(measured_alcohol="80", water_value="30")
        self.assertFalse(result["ok"])
        self.assertIn("100 %vol", result["messages"][-1][1])

    def test_zero_probe_volume_is_error_not_a_crash(self):
        result = run(probe_volume="0")
        self.assertFalse(result["ok"])
        self.assertIn("Probevolumen", result["messages"][-1][1])

    def test_negative_water_is_error(self):
        result = run(water_value="-1")
        self.assertFalse(result["ok"])

    def test_water_zero_is_allowed(self):
        result = run(water_value="0")
        self.assertTrue(result["ok"])
        self.assertAlmostEqual(result["output"]["actual_alcohol"], 40.0, places=6)

    def test_small_diluted_volume_gives_info(self):
        result = run(probe_volume="10", water_value="10")
        self.assertIn(m.LEVEL_INFO, levels(result))
        big = run(probe_volume="25", water_value="25")
        self.assertNotIn(m.LEVEL_INFO, levels(big))


class TestDilutedMeasurement(unittest.TestCase):
    def test_actual_alcohol_uses_mass_balance(self):
        result = run()
        self.assertAlmostEqual(result["output"]["actual_alcohol"], calc.compute_actual_alcohol(40, 10, 10), places=9)
        self.assertLess(result["output"]["actual_alcohol"], 80.0)

    def test_water_by_mass_converts_with_density_at_20_degrees(self):
        mass = 10.0 * calc.water_density_temp(20.0)
        for temp in ("18", "20", "24"):
            result = run(room_temp=temp, water_value=str(mass), water_mode=m.WATER_BY_MASS)
            self.assertAlmostEqual(result["input"]["water_volume"], 10.0, places=6)

    def test_probe_volume_is_corrected_to_20_degrees(self):
        warm = run(room_temp="25", probe_volume="10")
        self.assertLess(warm["input"]["probe_volume"], 10.0)
        self.assertAlmostEqual(warm["input"]["probe_volume_input"], 10.0)

    def test_extract_uses_effective_factor(self):
        result = run(measured_extract="5")
        factor = result["output"]["effective_dilution_factor"]
        self.assertAlmostEqual(result["output"]["actual_extract"], 5 * factor, places=9)
        self.assertLess(factor, 2.0)

    def test_density_without_extract_equals_table_density(self):
        measured = calc.interpolate_density_from_alcohol(40)
        result = run(measured_density=str(measured))
        self.assertAlmostEqual(result["output"]["actual_density"],
                               calc.interpolate_density_from_alcohol(result["output"]["actual_alcohol"]), places=7)

    def test_extract_only_measurement_uses_volume_ratio(self):
        result = run(measured_alcohol="", measured_extract="5")
        self.assertTrue(result["ok"])
        self.assertAlmostEqual(result["output"]["actual_extract"], 10.0, places=9)
        self.assertIsNone(result["output"]["actual_alcohol"])

    def test_calibration_applied_to_calculated_alcohol(self):
        calib = [(10, 9), (20, 19)]
        plain = run()["output"]["actual_alcohol"]
        calibrated = run(calib_data=calib, use_calibration=True)
        self.assertTrue(calibrated["input"]["calibration_applied"])
        self.assertAlmostEqual(calibrated["output"]["actual_alcohol"], plain + 1.0, places=6)

    def test_calibration_ignored_with_fewer_than_two_points(self):
        result = run(calib_data=[(10, 9)], use_calibration=True)
        self.assertFalse(result["input"]["calibration_applied"])


class TestDirectMeasurement(unittest.TestCase):
    def raw(self, **fields):
        base = {"mode": m.MODE_DIRECT, "room_temp": "20", "measured_alcohol": "27", "measured_density": "1.0123",
                "measured_extract": "31,5"}
        base.update(fields)
        return m.evaluate_measurement(base, now=NOW)

    def test_values_are_taken_over_unchanged(self):
        result = self.raw()
        self.assertTrue(result["ok"])
        self.assertAlmostEqual(result["output"]["actual_alcohol"], 27.0)
        self.assertAlmostEqual(result["output"]["actual_density"], 1.0123)
        self.assertAlmostEqual(result["output"]["actual_extract"], 31.5)
        self.assertIsNone(result["input"]["dilution_factor"])
        self.assertIsNone(result["output"]["effective_dilution_factor"])

    def test_no_dilution_inputs_needed(self):
        self.assertTrue(self.raw(probe_volume="", water_value="")["ok"])

    def test_above_device_range_warns(self):
        result = self.raw(measured_alcohol="60")
        self.assertTrue(any("Messbereich" in text for _, text in result["messages"]))

    def test_calibration_applies_to_measured_alcohol(self):
        result = m.evaluate_measurement({"mode": m.MODE_DIRECT, "room_temp": "20", "measured_alcohol": "15"},
                                        calib_data=[(10, 9), (20, 19)], use_calibration=True, now=NOW)
        self.assertAlmostEqual(result["output"]["actual_alcohol"], 16.0, places=6)


class TestComparisons(unittest.TestCase):
    def test_spindle_alcohol_deviation(self):
        result = run(spindle_alcohol="75")
        c = result["comparison"]["alcohol"]
        self.assertAlmostEqual(c["deviation"], result["output"]["actual_alcohol"] - 75.0)
        self.assertAlmostEqual(c["deviation_percent"], c["deviation"] / 75.0 * 100)

    def test_spindle_density_compares_with_actual_density(self):
        result = run(measured_density="0.9700", spindle_alcohol="75", spindle_density="0.9100")
        c = result["comparison"]["density"]
        self.assertAlmostEqual(c["alex501_value_20C"], result["output"]["actual_density"])
        self.assertAlmostEqual(c["deviation"], c["spindle_value_20C"] - result["output"]["actual_density"])

    def test_spindle_density_only_shows_temperature_correction(self):
        result = m.evaluate_measurement({"mode": m.MODE_DILUTED, "room_temp": "25", "spindle_alcohol": "40",
                                         "spindle_density": "0.9500"}, now=NOW)
        self.assertTrue(result["ok"])
        self.assertFalse(result["has_calculation"])
        self.assertNotIn("deviation", result["comparison"]["density"])
        self.assertGreater(result["input"]["spindle_density_20C"], 0.95)

    def test_lab_comparison_for_all_three_values(self):
        result = run(measured_density="0.9700", measured_extract="2", lab_alcohol="78", lab_density="0.86",
                     lab_extract="4,5", lab_note="Labor X")
        lab = result["comparison"]["lab"]
        self.assertEqual(set(lab), {"alcohol", "density", "extract"})
        self.assertAlmostEqual(lab["alcohol"]["deviation"], result["output"]["actual_alcohol"] - 78.0)
        self.assertEqual(result["input"]["lab_note"], "Labor X")

    def test_lab_value_without_calculation_is_not_compared(self):
        result = run(measured_alcohol="", measured_extract="5", lab_alcohol="78")
        self.assertNotIn("lab", result["comparison"])


class TestReport(unittest.TestCase):
    def test_diluted_report_contains_results_and_sections(self):
        text = m.format_report(run(sample_name="Salbei", batch="26-01", measured_density="0.9700",
                                   measured_extract="2", spindle_alcohol="75", lab_alcohol="78"))
        for expected in ("Salbei", "26-01", "Berechnete tatsächliche Werte der Originalprobe", "Alkoholgehalt:",
                         "VERGLEICH MIT SPINDELUNG", "VERGLEICH MIT LABORANALYSE", "Wirksamer Faktor",
                         "14.10.2026 12:00:00"):
            self.assertIn(expected, text)

    def test_report_uses_german_decimal_comma(self):
        text = m.format_report(run())
        self.assertIn("%vol.", text)
        self.assertNotIn("78.5", text)

    def test_direct_report_has_no_dilution_lines(self):
        result = m.evaluate_measurement({"mode": m.MODE_DIRECT, "room_temp": "20", "measured_alcohol": "27"}, now=NOW)
        text = m.format_report(result)
        self.assertIn("Direkte Messung", text)
        self.assertNotIn("Verdünnungsfaktor", text)
        self.assertIn("27,00 %vol.", text)

    def test_signed_deviation(self):
        self.assertEqual(m._signed(1.234, 2), "+1,23")
        self.assertEqual(m._signed(-1.234, 2), "-1,23")


if __name__ == "__main__":
    unittest.main()


class TestHistoryHelpers(unittest.TestCase):
    ROW = {"id": 3, "timestamp": "2026-10-14T12:00:00", "sample_name": "Salbei", "batch": "26-01",
           "mode": m.MODE_DILUTED, "room_temp": 21.0, "probe_volume": 29.9, "water_volume": 9.2,
           "probe_volume_input": 30.0, "water_input": 9.2, "water_mode": m.WATER_BY_MASS,
           "measured_alcohol": 40.0, "measured_density": 0.95, "measured_extract": 2.0,
           "dilution_factor": 1.31, "effective_dilution_factor": 1.29, "spindle_alcohol": 50.0,
           "spindle_density_at_temp": None, "spindle_density_20C": None, "calibration_applied": 0,
           "lab_alcohol": 51.0, "lab_density": None, "lab_extract": None, "lab_note": "Labor X",
           "actual_alcohol": 51.5, "actual_density": 0.93, "actual_extract": 2.6}

    def test_table_values_match_columns_and_deviations(self):
        values = m.history_table_values(self.ROW)
        self.assertEqual(len(values), len(m.HISTORY_COLUMNS))
        self.assertEqual(values[0], "14.10.2026 12:00")
        self.assertEqual(values[3], "Verdünnt")
        self.assertEqual(values[4], "51,50")
        self.assertEqual(values[8], "+1,50")   # Δ Spindel
        self.assertEqual(values[10], "+0,50")  # Δ Labor

    def test_legacy_row_without_new_values_renders(self):
        legacy = {"id": 1, "timestamp": "2026-01-05T10:00:00", "sample_name": "Alt", "actual_alcohol": 78.0}
        values = m.history_table_values(legacy)
        self.assertEqual(values[3], "–")
        self.assertEqual(values[7], "–")
        self.assertTrue(m.history_detail_lines(legacy))

    def test_detail_lines_have_sections_and_lab_note(self):
        lines = m.history_detail_lines(self.ROW)
        heads = [text for kind, *rest in lines if kind == "head" for text in rest]
        self.assertIn("Laboranalyse", heads)
        self.assertIn(("item", "Bemerkung", "Labor X"), lines)
        self.assertIn(("item", "Wasser (eingegeben)", "9,20 g"), lines)

    def test_direct_row_has_no_dilution_section(self):
        row = dict(self.ROW, mode=m.MODE_DIRECT)
        labels = [rest[0] for kind, *rest in m.history_detail_lines(row) if kind == "item"]
        self.assertNotIn("Verdünnungsfaktor", labels)

    def test_csv_table_uses_decimal_comma(self):
        table = m.history_csv_table([self.ROW])
        header, data = table
        self.assertEqual(data[header.index("actual_alcohol")], "51,5")
        self.assertEqual(data[header.index("id")], "3")
        self.assertEqual(data[header.index("spindle_density_20C")], "")
        self.assertEqual(m.history_csv_table([]), [])
