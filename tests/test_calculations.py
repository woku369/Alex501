"""
Unit-Tests für die reinen Berechnungsfunktionen in calculations.py.

Ausführen mit:
    python -m unittest discover -s tests
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import calculations as calc


class TestFormatDe(unittest.TestCase):
    def test_formats_with_german_comma(self):
        self.assertEqual(calc.format_de(3.14159, 2), "3,14")

    def test_zero_decimals(self):
        self.assertEqual(calc.format_de(5, 0), "5")


class TestVolumeTemperatureCorrection(unittest.TestCase):
    def test_no_correction_at_reference_temperature(self):
        self.assertAlmostEqual(calc.correct_volume_temp(100, 20.0, is_water=False), 100.0)
        self.assertAlmostEqual(calc.correct_volume_temp(100, 20.0, is_water=True), 100.0)

    def test_volume_shrinks_when_correcting_down_from_warmer_temperature(self):
        # Bei einer Probe, die wärmer als 20 C war, nimmt das Volumen bei
        # Korrektur auf 20 C ab (das warme Volumen war ausgedehnt).
        corrected = calc.correct_volume_temp(100, 30, is_water=False)
        self.assertLess(corrected, 100)
        self.assertAlmostEqual(corrected, 100 / 1.011, places=6)


class TestWaterDensity(unittest.TestCase):
    def test_density_at_4_degrees(self):
        # Bei 4 C fällt der quadratische/lineare Korrekturterm weg
        self.assertAlmostEqual(calc.water_density_temp(4), 0.99987)


class TestDensityInterpolation(unittest.TestCase):
    def test_table_endpoints(self):
        self.assertAlmostEqual(calc.interpolate_density_from_alcohol(0), 0.9982)
        self.assertAlmostEqual(calc.interpolate_density_from_alcohol(100), 0.8757)

    def test_table_midpoint(self):
        self.assertAlmostEqual(calc.interpolate_density_from_alcohol(50), 0.9518)

    def test_linear_interpolation_between_points(self):
        # Zwischen 0 %vol (0,9982) und 10 %vol (0,9920) linear interpoliert
        self.assertAlmostEqual(calc.interpolate_density_from_alcohol(5), 0.9951, places=4)


class TestDensityTemperatureCorrection(unittest.TestCase):
    def test_no_correction_at_reference_temperature(self):
        self.assertAlmostEqual(calc.correct_density_to_20C(0.95, 20.0, 40), 0.95)

    def test_correction_direction_above_reference_temperature(self):
        # Bei höherer Temperatur ist die gemessene Dichte niedriger als bei 20 C,
        # die Korrektur auf 20 C muss die Dichte daher erhöhen.
        corrected = calc.correct_density_to_20C(0.95, 25.0, 40)
        self.assertGreater(corrected, 0.95)


class TestContractionCorrection(unittest.TestCase):
    def test_no_correction_at_or_below_50_percent(self):
        self.assertEqual(calc.apply_contraction_correction(40), 40)
        self.assertEqual(calc.apply_contraction_correction(50), 50)

    def test_correction_above_50_percent(self):
        # Korrektur = 1 + 0,001 * (60-50) = 1,01 -> 60 * 1,01 = 60,6
        self.assertAlmostEqual(calc.apply_contraction_correction(60), 60.6)


class TestCalibrationCurve(unittest.TestCase):
    def test_linear_fit_applied_to_value(self):
        # refs = meas + 1 (siehe Herleitung: Steigung 1, Achsenabschnitt 1)
        calib_data = [(10, 9), (20, 19)]
        self.assertAlmostEqual(calc.apply_calibration_curve(calib_data, 15), 16.0)


class TestDilutionCalculations(unittest.TestCase):
    def test_dilution_factor(self):
        self.assertAlmostEqual(calc.compute_dilution_factor(10, 10), 2.0)
        self.assertAlmostEqual(calc.compute_dilution_factor(25, 75), 4.0)

    def test_actual_alcohol(self):
        # 40 %vol in 20 ml Gesamtvolumen (10 ml Probe + 10 ml Wasser) zurückgerechnet
        # auf 10 ml Probevolumen ergibt 80 %vol (vor Kontraktionskorrektur).
        self.assertAlmostEqual(calc.compute_actual_alcohol(40, 10, 20), 80.0)

    def test_actual_density(self):
        actual_density, expected_density_original = calc.compute_actual_density(
            measured_alc=40, measured_dens=0.97, actual_alcohol_percent=60, dilution_factor=2.0)
        self.assertAlmostEqual(expected_density_original, 0.9389)
        self.assertAlmostEqual(actual_density, 0.9517, places=4)

    def test_actual_extract(self):
        self.assertAlmostEqual(calc.compute_actual_extract(5, 2), 10.0)


if __name__ == "__main__":
    unittest.main()
