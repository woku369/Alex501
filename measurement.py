"""
Messvorgang der Alex 501 Mazerat-Interpolation: Eingaben prüfen, berechnen, Bericht erzeugen.

Dieses Modul hat keine Abhängigkeit von tkinter oder der GUI und ist dadurch unabhängig
testbar (siehe tests/test_measurement.py). Die GUI liefert die Eingaben als Text und stellt
das zurückgegebene Ergebnis dar.
"""

from datetime import datetime

import calculations as calc
from calculations import format_de

MODE_DILUTED = "diluted"  # verdünnte Probe, Umrechnung auf die Originalprobe
MODE_DIRECT = "direct"    # Probe liegt im Messbereich, Alex-Werte werden direkt übernommen

WATER_BY_VOLUME = "vol"
WATER_BY_MASS = "mass"

DEVICE_MAX_ALCOHOL = 47.0   # %vol, Messbereich des Alex 501 (Angabe des Nutzers)
MIN_MEASURING_VOLUME = 40.0  # ml verdünnte Probe je Messung (Angabe des Nutzers)

LEVEL_ERROR = "error"      # Berechnung nicht möglich
LEVEL_WARNING = "warning"  # Berechnung läuft, Wert bitte prüfen
LEVEL_INFO = "info"


def parse_decimal(text):
    """Wandelt Text mit Komma oder Punkt in eine Zahl; leerer Text ergibt None, Unsinn ValueError."""
    text = (text or "").strip()
    if not text:
        return None
    return float(text.replace(",", "."))


def _signed(value, decimals):
    """Zahl mit Vorzeichen im deutschen Format (immer + oder -)."""
    text = format_de(abs(value), decimals)
    return ("+" if value > 0 else "-") + text


def evaluate_measurement(raw, calib_data=None, use_calibration=False, now=None):
    """Prüft die Eingaben, berechnet die Werte der Originalprobe und liefert ein Ergebnis-Dict.

    raw: Dict mit den Feldern der Eingabemaske als Text (fehlende Schlüssel zählen als leer):
        mode, sample_name, batch, room_temp, probe_volume, water_value, water_mode,
        measured_alcohol, measured_density, measured_extract,
        spindle_alcohol, spindle_density, lab_alcohol, lab_density, lab_extract, lab_note
    Rückgabe: Dict mit 'ok' (bool), 'messages' (Liste aus (Stufe, Text)) und, wenn 'ok' wahr ist,
    'input', 'output', 'derived', 'comparison', 'mode', 'timestamp', 'sample_name', 'batch'.
    """
    now = now or datetime.now()
    messages = []

    def fail(text):
        messages.append((LEVEL_ERROR, text))
        return {"ok": False, "messages": messages}

    ignored = []   # Felder mit ungültiger Eingabe (keine Zahl), werden ignoriert
    ranges = []    # unplausible Werte, werden trotzdem verwendet

    def number(key, label):
        try:
            return parse_decimal(raw.get(key))
        except ValueError:
            ignored.append(label)
            return None

    def check_range(value, low, high, label, inclusive_low=True):
        if value is None:
            return
        below = value < low if inclusive_low else value <= low
        if below or value > high:
            ranges.append(f"{label} ({value:g}) liegt außerhalb des erwarteten Bereichs {low}–{high}")

    mode = raw.get("mode") or MODE_DILUTED
    diluted = mode == MODE_DILUTED
    sample_name = (raw.get("sample_name") or "").strip()
    batch = (raw.get("batch") or "").strip()

    # Raumtemperatur ist Pflicht
    try:
        room_temp = parse_decimal(raw.get("room_temp"))
    except ValueError:
        room_temp = None
    if room_temp is None:
        return fail("Raumtemperatur ist erforderlich.")
    check_range(room_temp, 0, 40, "Raumtemperatur [°C]")

    probe_input = number("probe_volume", "Probevolumen")
    water_input = number("water_value", "Wasserzugabe")
    measured_alc = number("measured_alcohol", "Gemessener Alkohol")
    measured_dens = number("measured_density", "Gemessene Dichte")
    measured_ext = number("measured_extract", "Gemessener Extrakt")
    spindle_alc = number("spindle_alcohol", "Spindelwert Alkohol")
    spindle_dens_at_temp = number("spindle_density", "Spindelwert Dichte")
    lab_alc = number("lab_alcohol", "Labor Alkohol")
    lab_dens = number("lab_density", "Labor Dichte")
    lab_ext = number("lab_extract", "Labor Extrakt")
    lab_note = (raw.get("lab_note") or "").strip()

    if diluted:
        check_range(probe_input, 0, 10000, "Probevolumen [ml]", inclusive_low=False)
        check_range(water_input, 0, 10000, "Wasserzugabe", inclusive_low=False)
    check_range(measured_alc, 0, 100, "Gemessener Alkohol [%vol]")
    # Bereich deckt reine Ethanol-Wasser-Proben und zuckerhaltige Liköre (bis ca. 1,35 g/cm³) ab
    check_range(measured_dens, 0.70, 1.40, "Gemessene Dichte [g/cm³]")
    check_range(measured_ext, 0, 100, "Gemessener Extrakt [g/100ml]")
    check_range(spindle_alc, 0, 100, "Spindelwert Alkohol [%vol]")
    check_range(spindle_dens_at_temp, 0.70, 1.40, "Spindelwert Dichte [g/cm³]")
    check_range(lab_alc, 0, 100, "Labor Alkohol [%vol]")
    check_range(lab_dens, 0.70, 1.40, "Labor Dichte [g/cm³]")
    check_range(lab_ext, 0, 100, "Labor Extrakt [g/100ml]")

    water_mode = raw.get("water_mode") or WATER_BY_VOLUME

    if diluted and probe_input is not None and probe_input <= 0:
        return fail("Das Probevolumen muss größer als 0 sein.")
    if diluted and water_input is not None and water_input < 0:
        return fail("Die Wasserzugabe darf nicht negativ sein.")

    # Volumina auf 20 °C bringen (nur im Verdünnungsmodus)
    probe_vol = None
    water_vol = None
    if diluted:
        if probe_input is not None:
            probe_vol = calc.correct_volume_temp(probe_input, room_temp, is_water=False)
        if water_input is not None:
            if water_mode == WATER_BY_MASS:
                # Masse ist temperaturunabhängig: Volumen bei 20 °C direkt aus der Dichte bei 20 °C
                water_vol = water_input / calc.water_density_temp(20.0)
            else:
                water_vol = calc.correct_volume_temp(water_input, room_temp, is_water=True)

    # Spindeldichte auf 20 °C (braucht den Spindelwert Alkohol für den Korrekturkoeffizienten)
    spindle_dens_20c = None
    if spindle_dens_at_temp is not None:
        if spindle_alc is None:
            return fail("Für die Temperaturkorrektur der Spindeldichte wird der Spindelwert "
                        "Alkohol benötigt. Bitte 'Spindelwert Alkohol' eingeben.")
        spindle_dens_20c = calc.correct_density_to_20C(spindle_dens_at_temp, room_temp, spindle_alc)

    if ignored:
        messages.append((LEVEL_WARNING, "Ungültige Eingaben (keine Zahl) wurden ignoriert: " + ", ".join(ignored)))
    if ranges:
        messages.append((LEVEL_WARNING, "Außerhalb des erwarteten Wertebereichs (werden trotzdem verwendet, "
                                        "bitte prüfen): " + "; ".join(ranges)))

    any_measured = any(v is not None for v in (measured_alc, measured_dens, measured_ext))
    if diluted:
        can_calculate = probe_vol is not None and water_vol is not None and any_measured
    else:
        can_calculate = any_measured
    can_show_spindle_density = spindle_dens_at_temp is not None
    if not can_calculate and not can_show_spindle_density:
        if diluted:
            return fail("Bitte mindestens eingeben: Probevolumen, Wasserzugabe und mindestens einen "
                        "Messwert, oder die Spindeldichte für die Temperaturkorrektur.")
        return fail("Bitte mindestens einen Messwert eingeben, oder die Spindeldichte für die "
                    "Temperaturkorrektur.")

    # Messbereich des Geräts
    if measured_alc is not None and measured_alc > DEVICE_MAX_ALCOHOL:
        messages.append((LEVEL_WARNING, f"Der gemessene Alkohol ({format_de(measured_alc, 2)} %vol) liegt über dem "
                                        f"Messbereich des Alex 501 (bis {format_de(DEVICE_MAX_ALCOHOL, 0)} %vol). "
                                        "Bitte die Probe verdünnen."))

    # Berechnung
    actual_alc = None
    actual_dens = None
    actual_ext = None
    dilution_factor = None
    effective_factor = None
    expected_density_original = None
    use_curve = bool(use_calibration) and isinstance(calib_data, (list, tuple)) and len(calib_data) >= 2

    if can_calculate and diluted:
        dilution_factor = calc.compute_dilution_factor(probe_vol, water_vol)
        effective_factor = dilution_factor
        if measured_alc is not None:
            try:
                actual_alc = calc.compute_actual_alcohol(measured_alc, probe_vol, water_vol)
            except ValueError as error:
                return fail(str(error))
            effective_factor = calc.compute_effective_dilution_factor(measured_alc, probe_vol, water_vol)
            # Kalibrierkurve auf den berechneten Alkoholgehalt (siehe Berechnungslogik_Alex501.txt, Punkt 5)
            if use_curve:
                actual_alc = calc.apply_calibration_curve(calib_data, actual_alc)
        if measured_alc is not None and measured_dens is not None:
            actual_dens, expected_density_original = calc.compute_actual_density(
                measured_alc, measured_dens, actual_alc, effective_factor)
        if measured_ext is not None:
            actual_ext = calc.compute_actual_extract(measured_ext, effective_factor)
        total_volume = effective_factor * probe_vol
        if total_volume < MIN_MEASURING_VOLUME:
            messages.append((LEVEL_INFO, f"Die verdünnte Probe hat etwa {format_de(total_volume, 1)} ml. Für eine "
                                         f"Messung am Alex 501 werden mindestens {format_de(MIN_MEASURING_VOLUME, 0)} ml benötigt."))
    elif can_calculate:
        # Direkte Messung: Werte werden unverändert übernommen (nur optional kalibriert)
        actual_alc = measured_alc
        if actual_alc is not None and use_curve:
            actual_alc = calc.apply_calibration_curve(calib_data, actual_alc)
        actual_dens = measured_dens
        actual_ext = measured_ext
        if actual_alc is not None:
            expected_density_original = calc.interpolate_density_from_alcohol(actual_alc)

    # Vergleiche
    comparison = {}
    if spindle_alc is not None and actual_alc is not None:
        deviation = actual_alc - spindle_alc
        comparison["alcohol"] = {
            "spindle_value": spindle_alc,
            "alex501_value": actual_alc,
            "deviation": deviation,
            "deviation_percent": (deviation / spindle_alc * 100) if spindle_alc > 0 else 0,
        }
    if spindle_dens_at_temp is not None and spindle_dens_20c is not None:
        density_comparison = {"spindle_value_at_temp": spindle_dens_at_temp, "spindle_value_20C": spindle_dens_20c}
        if actual_dens is not None:
            deviation = spindle_dens_20c - actual_dens
            density_comparison.update({
                "alex501_value_20C": actual_dens,
                "deviation": deviation,
                "deviation_percent": (deviation / actual_dens * 100) if actual_dens > 0 else 0,
            })
        comparison["density"] = density_comparison
    lab = {}
    for key, reference, calculated in (("alcohol", lab_alc, actual_alc), ("density", lab_dens, actual_dens),
                                       ("extract", lab_ext, actual_ext)):
        if reference is not None and calculated is not None:
            deviation = calculated - reference
            lab[key] = {"lab_value": reference, "alex501_value": calculated, "deviation": deviation,
                        "deviation_percent": (deviation / reference * 100) if reference > 0 else 0}
    if lab:
        comparison["lab"] = lab

    return {
        "ok": True,
        "messages": messages,
        "timestamp": now.isoformat(),
        "sample_name": sample_name,
        "batch": batch,
        "mode": mode,
        "input": {
            "room_temp": room_temp,
            "probe_volume": probe_vol,
            "water_volume": water_vol,
            "probe_volume_input": probe_input if diluted else None,
            "water_input": water_input if diluted else None,
            "water_mode": water_mode if diluted else None,
            "measured_alcohol": measured_alc,
            "measured_density": measured_dens,
            "measured_extract": measured_ext,
            "dilution_factor": dilution_factor,
            "spindle_alcohol": spindle_alc,
            "spindle_density_at_temp": spindle_dens_at_temp,
            "spindle_density_20C": spindle_dens_20c,
            "calibration_applied": use_curve,
            "lab_alcohol": lab_alc,
            "lab_density": lab_dens,
            "lab_extract": lab_ext,
            "lab_note": lab_note,
        },
        "output": {
            "actual_alcohol": actual_alc,
            "actual_density": actual_dens,
            "actual_extract": actual_ext,
            "effective_dilution_factor": effective_factor,
        },
        "derived": {"expected_density_original": expected_density_original},
        "comparison": comparison,
        "has_calculation": can_calculate,
    }


def format_report(result):
    """Erzeugt den Textbericht (Anzeige, Druck, Text-Export) aus einem Ergebnis von evaluate_measurement."""
    line = "=" * 60
    inp, out = result["input"], result["output"]
    comparison = result["comparison"]
    diluted = result["mode"] == MODE_DILUTED
    parts = [
        "ALEX 501 Mazeratinterpolation",
        "Messung einer verdünnten Probe und Umrechnung auf Endwerte" if diluted
        else "Direkte Messung (ohne Verdünnung)",
        line, "", "BERECHNUNGSERGEBNISSE", line, "",
        f"Probenbezeichnung: {result['sample_name'] or '-'}",
        f"Charge: {result['batch'] or '-'}",
    ]
    if result["has_calculation"]:
        parts.append("Kalibrierkurve: " + ("angewendet" if inp["calibration_applied"] else "nicht angewendet"))

    if result["has_calculation"]:
        parts += ["", "Eingabewerte:"]
        if diluted:
            parts.append(f"  Verdünnung: {format_de(inp['probe_volume'], 1)} ml Probe + "
                         f"{format_de(inp['water_volume'], 1)} ml Wasser (bei 20 °C)")
            parts.append(f"  Verdünnungsfaktor: 1:{format_de(inp['dilution_factor'], 2)}")
            if inp["measured_alcohol"] is not None:
                parts.append(f"  Wirksamer Faktor (mit Volumenkontraktion): "
                             f"1:{format_de(out['effective_dilution_factor'], 2)}")
        if inp["measured_alcohol"] is not None:
            parts.append(f"  Gemessener Alkoholgehalt: {format_de(inp['measured_alcohol'], 2)} %vol.")
        if inp["measured_density"] is not None:
            parts.append(f"  Gemessene Dichte: {format_de(inp['measured_density'], 5)} g/cm³")
        if inp["measured_extract"] is not None:
            parts.append(f"  Gemessener Extrakt: {format_de(inp['measured_extract'], 2)} g/100ml")
        parts += ["", line, "",
                  "Berechnete tatsächliche Werte der Originalprobe:" if diluted else "Werte der Probe (direkt gemessen):", ""]
        if out["actual_alcohol"] is not None:
            parts.append(f"  Alkoholgehalt: {format_de(out['actual_alcohol'], 2)} %vol.")
        if out["actual_density"] is not None:
            parts.append(f"  Dichte: {format_de(out['actual_density'], 5)} g/cm³")
        if out["actual_extract"] is not None:
            parts.append(f"  Extraktgehalt: {format_de(out['actual_extract'], 2)} g/100ml")

    if "alcohol" in comparison:
        c = comparison["alcohol"]
        parts += ["", line, "", "VERGLEICH MIT SPINDELUNG (Aräometer) - Alkohol:", "",
                  f"  Gespindelter Wert:        {format_de(c['spindle_value'], 2)} %vol.",
                  f"  Alex 501 (berechnet):     {format_de(c['alex501_value'], 2)} %vol.", "",
                  f"  Abweichung:               {_signed(c['deviation'], 2)} %vol. ({_signed(c['deviation_percent'], 1)}%)"]
    if "density" in comparison:
        c = comparison["density"]
        temp = format_de(inp["room_temp"], 1)
        parts += ["", line, ""]
        if "deviation" in c:
            parts += ["VERGLEICH MIT SPINDELUNG (Aräometer) - Dichte:", "",
                      f"  Gespindelter Wert ({temp}°C): {format_de(c['spindle_value_at_temp'], 5)} g/cm³",
                      f"  Korrigiert auf 20°C:            {format_de(c['spindle_value_20C'], 5)} g/cm³",
                      f"  Alex 501 (berechnet, 20°C):     {format_de(c['alex501_value_20C'], 5)} g/cm³", "",
                      f"  Abweichung:                     {_signed(c['deviation'], 5)} g/cm³ ({_signed(c['deviation_percent'], 2)}%)"]
        else:
            parts += ["TEMPERATURKORREKTUR SPINDELDICHTE:", "",
                      f"  Gespindelter Wert ({temp}°C): {format_de(c['spindle_value_at_temp'], 5)} g/cm³",
                      f"  Korrigiert auf 20°C:            {format_de(c['spindle_value_20C'], 5)} g/cm³"]
    if "lab" in comparison:
        parts += ["", line, "", "VERGLEICH MIT LABORANALYSE:", ""]
        names = {"alcohol": ("Alkohol", "%vol.", 2), "density": ("Dichte", "g/cm³", 5), "extract": ("Extrakt", "g/100ml", 2)}
        for key, (label, unit, decimals) in names.items():
            if key in comparison["lab"]:
                c = comparison["lab"][key]
                parts.append(f"  {label}: Labor {format_de(c['lab_value'], decimals)} {unit}, "
                             f"Alex 501 {format_de(c['alex501_value'], decimals)} {unit}, "
                             f"Abweichung {_signed(c['deviation'], decimals)} ({_signed(c['deviation_percent'], 1)}%)")
        if inp["lab_note"]:
            parts.append(f"  Bemerkung: {inp['lab_note']}")

    parts += ["", line]
    if result["has_calculation"]:
        parts += ["", "Hinweise:"]
        if diluted:
            parts.append("- Die Berechnung berücksichtigt Volumenkontraktion (Massenbilanz)")
        parts += ["- Dichte-Werte basieren auf der Alkoholtabelle CRA 1996 (nach OIML R 22)",
                  "- Für höchste Präzision wird eine Kalibrierung empfohlen"]
        if diluted:
            parts.append("- Extraktstoffe werden bei der Alkoholberechnung nicht berücksichtigt "
                         "(Abweichung steigt mit dem Extraktgehalt)")
        if inp["spindle_alcohol"] is not None:
            parts.append("- Spindelung (Aräometer) ist die Referenzmethode für Zollamt")
    for level, text in result["messages"]:
        if level != LEVEL_ERROR:
            parts.append(("! " if level == LEVEL_WARNING else "i ") + text)
    parts += ["", f"Zeitstempel: {datetime.fromisoformat(result['timestamp']).strftime('%d.%m.%Y %H:%M:%S')}", ""]
    return "\n".join(parts)


# --- Messhistorie: Darstellung der gespeicherten Messungen (Zeilen aus db.MeasurementDB.fetch_all) ---

MODE_LABELS = {MODE_DILUTED: "Verdünnt", MODE_DIRECT: "Direkt"}

# (Schlüssel, Spaltenüberschrift, Breite in Pixel)
HISTORY_COLUMNS = (
    ("timestamp", "Zeit", 135),
    ("sample_name", "Probe", 115),
    ("batch", "Charge", 80),
    ("mode", "Modus", 80),
    ("actual_alcohol", "Alkohol %vol", 125),
    ("actual_density", "Dichte g/cm³", 125),
    ("actual_extract", "Extrakt g/100ml", 150),
    ("spindle", "Spindel %vol", 125),
    ("spindle_dev", "Δ Spindel", 95),
    ("lab", "Labor %vol", 110),
    ("lab_dev", "Δ Labor", 90),
)


def _fmt(value, decimals):
    return "–" if value is None else format_de(value, decimals)


def _fmt_signed(value, decimals):
    return "–" if value is None else _signed(value, decimals)


def _fmt_time(timestamp):
    try:
        return datetime.fromisoformat(timestamp).strftime("%d.%m.%Y %H:%M")
    except (TypeError, ValueError):
        return timestamp or "–"


def _deviation(calculated, reference):
    return None if calculated is None or reference is None else calculated - reference


def history_table_values(row):
    """Werte einer Messung für die Übersichtstabelle (Reihenfolge wie HISTORY_COLUMNS)."""
    return (
        _fmt_time(row.get("timestamp")),
        row.get("sample_name") or "–",
        row.get("batch") or "–",
        MODE_LABELS.get(row.get("mode"), "–"),
        _fmt(row.get("actual_alcohol"), 2),
        _fmt(row.get("actual_density"), 5),
        _fmt(row.get("actual_extract"), 2),
        _fmt(row.get("spindle_alcohol"), 2),
        _fmt_signed(_deviation(row.get("actual_alcohol"), row.get("spindle_alcohol")), 2),
        _fmt(row.get("lab_alcohol"), 2),
        _fmt_signed(_deviation(row.get("actual_alcohol"), row.get("lab_alcohol")), 2),
    )


def history_detail_lines(row):
    """Detailansicht einer Messung als Liste aus ('head', Titel) und ('item', Bezeichnung, Wert)."""
    water_unit = "g" if row.get("water_mode") == WATER_BY_MASS else "ml"
    lines = [("head", "Ansatz")]
    lines += [
        ("item", "Modus", MODE_LABELS.get(row.get("mode"), "– (ältere Messung)")),
        ("item", "Raumtemperatur", _fmt(row.get("room_temp"), 1) + " °C"),
    ]
    if row.get("mode") != MODE_DIRECT:
        lines += [
            ("item", "Probe (eingegeben)", _fmt(row.get("probe_volume_input"), 2) + " ml"),
            ("item", "Wasser (eingegeben)", _fmt(row.get("water_input"), 2) + " " + water_unit),
            ("item", "Volumen bei 20 °C",
             f"{_fmt(row.get('probe_volume'), 2)} / {_fmt(row.get('water_volume'), 2)} ml"),
            ("item", "Verdünnungsfaktor", "1:" + _fmt(row.get("dilution_factor"), 3)),
            ("item", "Wirksamer Faktor", "1:" + _fmt(row.get("effective_dilution_factor"), 3)),
        ]
    lines += [("head", "Alex 501 gemessen"),
              ("item", "Alkohol", _fmt(row.get("measured_alcohol"), 2) + " %vol"),
              ("item", "Dichte", _fmt(row.get("measured_density"), 5) + " g/cm³"),
              ("item", "Extrakt", _fmt(row.get("measured_extract"), 2) + " g/100ml"),
              ("head", "Ergebnis" + (" (Originalprobe)" if row.get("mode") != MODE_DIRECT else "")),
              ("item", "Alkohol", _fmt(row.get("actual_alcohol"), 2) + " %vol"),
              ("item", "Dichte", _fmt(row.get("actual_density"), 5) + " g/cm³"),
              ("item", "Extrakt", _fmt(row.get("actual_extract"), 2) + " g/100ml"),
              ("item", "Kalibrierkurve", "angewendet" if row.get("calibration_applied") else "nicht angewendet")]
    if any(row.get(k) is not None for k in ("spindle_alcohol", "spindle_density_at_temp")):
        lines += [("head", "Spindelung"),
                  ("item", "Alkohol", _fmt(row.get("spindle_alcohol"), 2) + " %vol"),
                  ("item", "Dichte (T / 20 °C)",
                   f"{_fmt(row.get('spindle_density_at_temp'), 5)} / {_fmt(row.get('spindle_density_20C'), 5)}")]
    if any(row.get(k) is not None for k in ("lab_alcohol", "lab_density", "lab_extract")) or row.get("lab_note"):
        lines += [("head", "Laboranalyse"),
                  ("item", "Alkohol", _fmt(row.get("lab_alcohol"), 2) + " %vol"),
                  ("item", "Dichte", _fmt(row.get("lab_density"), 5) + " g/cm³"),
                  ("item", "Extrakt", _fmt(row.get("lab_extract"), 2) + " g/100ml")]
        if row.get("lab_note"):
            lines.append(("item", "Bemerkung", row["lab_note"]))
    return lines


def history_csv_table(rows):
    """Tabelle (Kopfzeile + Zeilen) aller gespeicherten Spalten für den CSV-Export; Zahlen mit Dezimalkomma."""
    if not rows:
        return []
    keys = list(rows[0].keys())
    table = [keys]
    for row in rows:
        table.append(["" if row.get(k) is None else (str(row[k]).replace(".", ",") if isinstance(row[k], float)
                                                    else str(row[k])) for k in keys])
    return table
