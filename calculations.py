"""
Reine Berechnungsfunktionen für die Alex 501 Mazerat-Interpolation.

Diese Funktionen haben keine Abhängigkeit von tkinter oder der GUI und
sind dadurch unabhängig testbar (siehe tests/test_calculations.py).
"""

import numpy as np


def format_de(value, decimals=2):
    """Formatiert Zahlen mit deutschem Komma."""
    formatted = f"{value:.{decimals}f}".replace('.', ',')
    return formatted


def correct_volume_temp(volume, temp, is_water=False):
    """Korrigiert das Volumen auf 20°C (Standardbedingungen) für Ethanol/Wasser oder Wasser."""
    # Näherungsformel für Volumenausdehnung (in % pro °C)
    # Ethanol: ca. 0,11%/K, Wasser: ca. 0,025%/K
    coeff = 0.00025 if is_water else 0.0011
    delta_t = temp - 20.0
    return volume / (1 + coeff * delta_t)


def water_density_temp(temp):
    """Berechnet die Dichte von Wasser in g/cm³ in Abhängigkeit von der Temperatur (°C)."""
    # Näherungsformel für 0-40°C
    return 0.99987 - 0.00007 * (temp - 4) - 0.0000002 * (temp - 4) ** 2


# Werte aus OIML R 22 Tabelle (stark vereinfacht, für Demo)
# alc in %vol, density in g/cm³
_ALCOHOL_TABLE = np.array([0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100])
_DENSITY_TABLE = np.array([0.9982, 0.9920, 0.9837, 0.9742, 0.9636, 0.9518, 0.9389, 0.9248, 0.9096, 0.8932, 0.8757])


def interpolate_density_from_alcohol(alc):
    """Interpoliert die Dichte einer Ethanol-Wasser-Mischung bei 20°C anhand des Alkoholgehalts."""
    return float(np.interp(alc, _ALCOHOL_TABLE, _DENSITY_TABLE))


def correct_density_to_20C(density_at_temp, temp, alc_percent):
    """Korrigiert die Dichte von der aktuellen Temperatur auf 20°C (Referenztemperatur)."""
    # Temperaturkoeffizient für Dichte in g/(cm³·°C)
    # Wasser: ca. -0.0002, Ethanol: ca. -0.0009
    # Lineare Interpolation basierend auf Alkoholgehalt
    coeff_water = -0.0002
    coeff_ethanol = -0.0009
    coeff = coeff_water + (coeff_ethanol - coeff_water) * (alc_percent / 100)
    delta_t = temp - 20.0
    # Bei höherer Temp ist Dichte niedriger, also bei Korrektur auf 20°C subtrahieren
    return density_at_temp - coeff * delta_t


def apply_contraction_correction(alcohol_percent):
    """Korrigiert den Alkoholgehalt für die Volumenkontraktion bei Ethanol-Wasser-
    Mischungen oberhalb von 50 %vol."""
    if alcohol_percent > 50:
        contraction_correction = 1 + (0.001 * (alcohol_percent - 50))
        return alcohol_percent * contraction_correction
    return alcohol_percent


def apply_calibration_curve(calib_data, value):
    """Wendet eine lineare Kalibrierkurve (Paare aus Referenzwert und Messwert) auf
    einen Wert an und gibt den korrigierten Wert zurück."""
    refs, meas = zip(*calib_data)
    coeffs = np.polyfit(meas, refs, 1)
    return float(np.polyval(coeffs, value))


def compute_dilution_factor(probe_vol, water_vol):
    """Berechnet den Verdünnungsfaktor aus Probe- und Wasservolumen."""
    total_diluted_volume = probe_vol + water_vol
    return total_diluted_volume / probe_vol


def compute_actual_alcohol(measured_alc, probe_vol, total_diluted_volume):
    """Rechnet den gemessenen Alkoholgehalt der verdünnten Probe auf die
    Originalprobe zurück (vor Volumenkontraktions-Korrektur und Kalibrierung)."""
    alcohol_volume_in_dilution = (measured_alc / 100) * total_diluted_volume
    return (alcohol_volume_in_dilution / probe_vol) * 100


def compute_actual_density(measured_alc, measured_dens, actual_alcohol_percent, dilution_factor):
    """Berechnet die tatsächliche Dichte der Originalprobe.

    Gibt ein Tupel (actual_density, expected_density_original) zurück, wobei
    expected_density_original der aus der OIML-Tabelle interpolierte Erwartungswert
    für den berechneten Alkoholgehalt ist (wird separat für den Spindelvergleich
    benötigt).
    """
    expected_density_diluted = interpolate_density_from_alcohol(measured_alc)
    expected_density_original = interpolate_density_from_alcohol(actual_alcohol_percent)
    density_difference = measured_dens - expected_density_diluted
    actual_density = expected_density_original + density_difference * dilution_factor
    return actual_density, expected_density_original


def compute_actual_extract(measured_ext, dilution_factor):
    """Berechnet den tatsächlichen Extraktgehalt der Originalprobe."""
    return measured_ext * dilution_factor
