"""
Reine Berechnungsfunktionen für die Alex 501 Mazerat-Interpolation.

Diese Funktionen haben keine Abhängigkeit von tkinter oder der GUI und
sind dadurch unabhängig testbar (siehe tests/test_calculations.py).
"""

import numpy as np

from alkoholtabelle import DICHTE_SCHRITT, DICHTE_START, VOL_PROZENT


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


# Alkoholtabelle (Canadian Alcoholometric Laboratory Table 1996, berechnet aus der
# OIML-R-22-Formel), siehe alkoholtabelle.py. Dort steht die Dichte in Luft.
# Umrechnung auf die wahre Dichte (Vakuum, wie sie ein Biegeschwinger-Dichtemessgerät
# anzeigt) mit den konventionellen Werten: Luft 0,0012 g/cm³, Gewichte 8,0 g/cm³.
_AIR_DENSITY = 0.0012
_WEIGHT_DENSITY = 8.0
_EXTRAPOLATION_POINTS = 50  # Tabellenzeilen für die lineare Extrapolation an den Rändern

# Aufsteigend nach Alkoholgehalt sortiert (Tabelle läuft nach Dichte aufsteigend).
_ALCOHOL_TABLE = np.array(VOL_PROZENT[::-1])
_DENSITY_AIR_TABLE = (DICHTE_START + DICHTE_SCHRITT * np.arange(len(VOL_PROZENT)))[::-1]


def density_in_air_to_true(density_air):
    """Rechnet die scheinbare Dichte in Luft (gegen 8,0-g/cm³-Gewichte) in die wahre
    Dichte (Vakuum) um: rho = (rho_Luft + rho_a) / (1 + rho_a / rho_Gewicht)."""
    return (density_air + _AIR_DENSITY) / (1 + _AIR_DENSITY / _WEIGHT_DENSITY)


def _edge_fit(x, y):
    """Geradenanpassung (Steigung, Achsenabschnitt) über die Randzeilen der Tabelle."""
    return np.polyfit(x, y, 1)


_LOW_FIT = _edge_fit(_ALCOHOL_TABLE[:_EXTRAPOLATION_POINTS], _DENSITY_AIR_TABLE[:_EXTRAPOLATION_POINTS])
_HIGH_FIT = _edge_fit(_ALCOHOL_TABLE[-_EXTRAPOLATION_POINTS:], _DENSITY_AIR_TABLE[-_EXTRAPOLATION_POINTS:])


def interpolate_density_from_alcohol(alc):
    """Interpoliert die wahre Dichte (g/cm³) einer Ethanol-Wasser-Mischung bei 20°C anhand des
    Alkoholgehalts (%vol). Zwischen 0,03 und 99,99 %vol linear aus der Tabelle, an den
    Rändern (0 bis 0,03 und 99,99 bis 100 %vol) linear extrapoliert. Werte außerhalb
    0 bis 100 %vol werden auf diesen Bereich begrenzt."""
    alc = min(max(float(alc), 0.0), 100.0)
    if alc < _ALCOHOL_TABLE[0]:
        density_air = np.polyval(_LOW_FIT, alc)
    elif alc > _ALCOHOL_TABLE[-1]:
        density_air = np.polyval(_HIGH_FIT, alc)
    else:
        density_air = np.interp(alc, _ALCOHOL_TABLE, _DENSITY_AIR_TABLE)
    return float(density_in_air_to_true(density_air))


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
