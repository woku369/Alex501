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
    """Berechnet die Dichte von luftfreiem Wasser in g/cm³ in Abhängigkeit von der Temperatur (°C)
    nach Tanaka et al. (2001), gültig für 0-40 °C."""
    a1, a2, a3, a4, a5 = -3.983035, 301.797, 522528.9, 69.34881, 999.974950  # a5 in kg/m³
    return a5 * (1 - ((temp + a1) ** 2 * (temp + a2)) / (a3 * (temp + a4))) / 1000


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


_ETHANOL_DENSITY_20 = interpolate_density_from_alcohol(100)  # g/cm³, reines Ethanol bei 20 °C
_WATER_DENSITY_20 = water_density_temp(20.0)  # g/cm³


def alcohol_mass_fraction(vol_percent):
    """Rechnet %vol in den Massenanteil Ethanol (0-1) um. Definition von %vol: Volumen des
    reinen Ethanols (20 °C) je Volumen der Mischung, daher w = phi * rho_Ethanol / rho_Mischung."""
    return vol_percent / 100 * _ETHANOL_DENSITY_20 / interpolate_density_from_alcohol(vol_percent)


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


def compute_actual_alcohol(measured_alc, probe_vol, water_vol):
    """Rechnet den gemessenen Alkoholgehalt (%vol, 20 °C) der verdünnten Probe auf die
    Originalprobe zurück (vor einer Kalibrierung).

    Die Volumina von Ethanol und Wasser sind nicht additiv (Volumenkontraktion), die Massen
    schon. Daher wird über die Ethanolmasse bilanziert:
        Ethanolmasse Probe = V_Probe * phi_Probe/100 * rho_Ethanol
        Ethanolmasse Verdünnung = w_Verdünnung * (rho(phi_Probe) * V_Probe + rho_Wasser * V_Wasser)
    und phi_Probe aus der Gleichheit beider Seiten bestimmt (Bisektion, die Bilanz ist in
    phi_Probe streng steigend). Annahme: Probe und Verdünnung verhalten sich wie ein reines
    Ethanol-Wasser-Gemisch; Extraktstoffe werden vernachlässigt.
    """
    if measured_alc <= 0:
        return 0.0
    ethanol_fraction_diluted = alcohol_mass_fraction(measured_alc)

    def balance(phi):
        ethanol_mass = probe_vol * phi / 100 * _ETHANOL_DENSITY_20
        total_mass = interpolate_density_from_alcohol(phi) * probe_vol + _WATER_DENSITY_20 * water_vol
        return ethanol_mass - ethanol_fraction_diluted * total_mass

    low, high = float(measured_alc), 100.0
    # kleine Toleranz gegen numerisches Rauschen bei genau 100 %vol in der Originalprobe
    if balance(high) < -1e-6 * probe_vol * _ETHANOL_DENSITY_20:
        raise ValueError(
            "Der gemessene Alkoholgehalt ist für diese Verdünnung zu hoch: "
            "die Originalprobe müsste mehr als 100 %vol enthalten.")
    for _ in range(60):
        middle = (low + high) / 2
        if balance(middle) < 0:
            low = middle
        else:
            high = middle
    return (low + high) / 2


def plan_dilution(probe_alc, total_volume, target_alc=40.0):
    """Ansatzplanung: Probe- und Wassermenge für eine Verdünnung auf den Zielalkohol.

    probe_alc: geschätzter Alkoholgehalt der Probe (%vol), total_volume: gewünschtes reales
    Volumen der verdünnten Probe (ml, 20 °C), target_alc: Ziel-Alkoholgehalt der Verdünnung (%vol).
    Gibt ein Dict mit Probevolumen (ml), Wasservolumen (ml, 20 °C) und Wassermasse (g) zurück.
    Grundlage ist dieselbe Massenbilanz wie in compute_actual_alcohol, hier in geschlossener Form;
    die Volumenkontraktion ist berücksichtigt, die Temperatur nicht (Richtwert zum Ansetzen,
    maßgeblich sind die tatsächlich eingewogenen Werte).
    """
    if not 0 < target_alc < 100:
        raise ValueError("Der Ziel-Alkoholgehalt muss zwischen 0 und 100 %vol liegen.")
    if probe_alc <= target_alc:
        raise ValueError("Die Probe liegt nicht über dem Ziel-Alkoholgehalt, eine Verdünnung ist nicht nötig.")
    if total_volume <= 0:
        raise ValueError("Das Zielvolumen muss größer als 0 ml sein.")
    ethanol_fraction_target = alcohol_mass_fraction(target_alc)
    probe_density = interpolate_density_from_alcohol(probe_alc)
    water_per_probe = (probe_alc / 100 * _ETHANOL_DENSITY_20 / ethanol_fraction_target
                       - probe_density) / _WATER_DENSITY_20
    diluted_per_probe = ((probe_density + _WATER_DENSITY_20 * water_per_probe)
                         / interpolate_density_from_alcohol(target_alc))
    probe_volume = total_volume / diluted_per_probe
    water_volume = probe_volume * water_per_probe
    return {
        "probe_volume": probe_volume,
        "water_volume": water_volume,
        "water_mass": water_volume * _WATER_DENSITY_20,
        "summed_volume": probe_volume + water_volume,
    }


def compute_effective_dilution_factor(measured_alc, probe_vol, water_vol):
    """Wirksamer Verdünnungsfaktor V_Verdünnung(real) / V_Probe unter Berücksichtigung der
    Volumenkontraktion; maßgeblich für Größen je Volumen (z. B. Extrakt in g/100 ml).
    Das reale Volumen folgt aus der Gesamtmasse und der Dichte der Verdünnung, beides als
    Ethanol-Wasser-Gemisch angenommen (Extraktanteil in Probe und Verdünnung kürzt sich
    näherungsweise heraus)."""
    actual_alc = compute_actual_alcohol(measured_alc, probe_vol, water_vol)
    total_mass = interpolate_density_from_alcohol(actual_alc) * probe_vol + _WATER_DENSITY_20 * water_vol
    diluted_volume = total_mass / interpolate_density_from_alcohol(measured_alc)
    return diluted_volume / probe_vol


def compute_actual_density(measured_alc, measured_dens, actual_alcohol_percent, dilution_factor):
    """Berechnet die tatsächliche Dichte der Originalprobe.

    Die Dichte der verdünnten Probe wird in den Anteil eines reinen Ethanol-Wasser-Gemisches
    (Alkoholtabelle) und einen Rest durch Extraktstoffe zerlegt. Der Rest ist näherungsweise
    proportional zur Extraktkonzentration je Volumen und wird deshalb mit dem wirksamen
    Verdünnungsfaktor (reales Volumen der Verdünnung / Probevolumen, siehe
    compute_effective_dilution_factor) auf die Originalprobe hochgerechnet.

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
