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
    def test_literature_values(self):
        # Wasser: 20 °C ca. 0,99820, 25 °C ca. 0,99705, 4 °C ca. 1,00000 g/cm³
        self.assertAlmostEqual(calc.water_density_temp(20), 0.99820, delta=1e-4)
        self.assertAlmostEqual(calc.water_density_temp(25), 0.99705, delta=1e-4)
        self.assertAlmostEqual(calc.water_density_temp(4), 1.00000, delta=1e-4)


class TestDensityInterpolation(unittest.TestCase):
    def test_pure_water_and_pure_ethanol(self):
        # Literaturwerte bei 20 °C (wahre Dichte): Wasser 0,998203, Ethanol 0,789239 g/cm³
        # (Ethanol: Canadian Alcoholometric Tables 1980, 789,2391233 kg/m³)
        self.assertAlmostEqual(calc.interpolate_density_from_alcohol(0), 0.998203, delta=1e-4)
        self.assertAlmostEqual(calc.interpolate_density_from_alcohol(100), 0.789239, delta=1e-4)

    def test_table_row_is_reproduced(self):
        # Tabellenzeile der CRA-Tabelle: 0,9725 g/cm³ (Dichte in Luft) entsprechen 20,00 %vol
        self.assertAlmostEqual(calc.interpolate_density_from_alcohol(20.0),
                               calc.density_in_air_to_true(0.9725), places=4)

    def test_air_to_true_density_conversion_for_ethanol(self):
        # Dichte in Luft von absolutem Ethanol laut CRA-Tabelle 1996: 0,7881589894 g/cm³
        self.assertAlmostEqual(calc.density_in_air_to_true(0.7881589894), 0.789239, delta=1e-5)

    def test_density_decreases_strictly_with_alcohol(self):
        values = [calc.interpolate_density_from_alcohol(a / 10) for a in range(0, 1001)]
        self.assertTrue(all(x > y for x, y in zip(values, values[1:])))

    def test_values_outside_range_are_clamped(self):
        self.assertEqual(calc.interpolate_density_from_alcohol(-5), calc.interpolate_density_from_alcohol(0))
        self.assertEqual(calc.interpolate_density_from_alcohol(120), calc.interpolate_density_from_alcohol(100))


class TestDensityTemperatureCorrection(unittest.TestCase):
    def test_no_correction_at_reference_temperature(self):
        self.assertAlmostEqual(calc.correct_density_to_20C(0.95, 20.0, 40), 0.95)

    def test_correction_direction_above_reference_temperature(self):
        # Bei höherer Temperatur ist die gemessene Dichte niedriger als bei 20 C,
        # die Korrektur auf 20 C muss die Dichte daher erhöhen.
        corrected = calc.correct_density_to_20C(0.95, 25.0, 40)
        self.assertGreater(corrected, 0.95)


class TestCalibrationCurve(unittest.TestCase):
    def test_linear_fit_applied_to_value(self):
        # refs = meas + 1 (siehe Herleitung: Steigung 1, Achsenabschnitt 1)
        calib_data = [(10, 9), (20, 19)]
        self.assertAlmostEqual(calc.apply_calibration_curve(calib_data, 15), 16.0)


class TestDilutionCalculations(unittest.TestCase):
    def test_dilution_factor(self):
        self.assertAlmostEqual(calc.compute_dilution_factor(10, 10), 2.0)
        self.assertAlmostEqual(calc.compute_dilution_factor(25, 75), 4.0)

    def test_actual_alcohol_without_water_is_unchanged(self):
        self.assertAlmostEqual(calc.compute_actual_alcohol(63.2, 10, 0), 63.2, places=6)

    def test_actual_alcohol_zero(self):
        self.assertEqual(calc.compute_actual_alcohol(0, 10, 10), 0.0)

    @staticmethod
    def _forward_diluted_alcohol(phi_probe, probe_vol, water_vol):
        """Vorwärtsrechnung: %vol der Verdünnung aus Probe und Wasser (Massenerhaltung)."""
        ethanol_mass = probe_vol * phi_probe / 100 * calc._ETHANOL_DENSITY_20
        total_mass = (calc.interpolate_density_from_alcohol(phi_probe) * probe_vol
                      + calc._WATER_DENSITY_20 * water_vol)
        target = ethanol_mass / total_mass
        low, high = 0.0, 100.0
        for _ in range(80):
            middle = (low + high) / 2
            if calc.alcohol_mass_fraction(middle) < target:
                low = middle
            else:
                high = middle
        return (low + high) / 2

    def test_actual_alcohol_roundtrip(self):
        for phi, probe, water in [(60, 10, 10), (75, 5, 20), (45, 10, 5), (96, 1, 1)]:
            diluted = self._forward_diluted_alcohol(phi, probe, water)
            self.assertAlmostEqual(calc.compute_actual_alcohol(diluted, probe, water), phi, places=4)

    def test_contraction_makes_result_lower_than_additive_volumes(self):
        measured, probe, water = 40, 10, 10
        additive = measured / 100 * (probe + water) / probe * 100  # 80 %vol bei additiven Volumina
        actual = calc.compute_actual_alcohol(measured, probe, water)
        self.assertLess(actual, additive)
        self.assertGreater(actual, measured)

    def test_equal_volumes_of_ethanol_and_water_contract_by_3_to_4_percent(self):
        # 50 ml Ethanol + 50 ml Wasser: README nennt ca. 3-4 % Volumenreduktion
        diluted = self._forward_diluted_alcohol(100, 50, 50)
        self.assertAlmostEqual(diluted, 51.8, delta=0.3)
        factor = calc.compute_effective_dilution_factor(diluted, 50, 50)
        contraction_percent = (2.0 - factor) / 2.0 * 100
        self.assertGreater(contraction_percent, 3.0)
        self.assertLess(contraction_percent, 4.0)

    def test_measured_value_too_high_for_dilution_raises(self):
        with self.assertRaises(ValueError):
            calc.compute_actual_alcohol(80, 10, 30)

    def test_mass_fraction_matches_cra_table_rows(self):
        # %vol -> %mass laut CRA-Tabelle 1996 (Dichte in Luft 0,9725 / 0,8845 / 0,8582 / 0,8281)
        for vol, mass in [(20.0, 16.22), (70.0, 62.38), (80.0, 73.48), (90.0, 85.67)]:
            self.assertAlmostEqual(calc.alcohol_mass_fraction(vol) * 100, mass, delta=0.01)

    def test_actual_density(self):
        actual_density, expected_density_original = calc.compute_actual_density(
            measured_alc=40, measured_dens=0.97, actual_alcohol_percent=60, dilution_factor=2.0)
        self.assertAlmostEqual(expected_density_original, 0.9091, places=4)
        self.assertAlmostEqual(actual_density, 0.9530, places=4)

    def test_actual_extract(self):
        self.assertAlmostEqual(calc.compute_actual_extract(5, 2), 10.0)


if __name__ == "__main__":
    unittest.main()
