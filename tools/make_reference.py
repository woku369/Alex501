"""
Erzeugt tests-js/reference.json: Referenzergebnisse der Python-Berechnung für den Abgleich der
JavaScript-Portierung (docs/calc.js, docs/measurement.js) durch tests-js/parity.test.js.

Aufruf (im Projektordner):  python tools/make_reference.py
Nach jeder Änderung an calculations.py oder measurement.py neu erzeugen und die JS-Tests ausführen:
    node --test tests-js/parity.test.js tests-js/pwa.test.js
"""

import itertools
import json
import os
import sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import calculations as calc  # noqa: E402
import measurement as m  # noqa: E402

NOW = datetime(2026, 10, 14, 12, 0, 0)


def jsonable(value):
    """Tupel -> Liste, damit das Ergebnis dem JSON-Format der JS-Seite entspricht."""
    if isinstance(value, dict):
        return {k: jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    return value


def numeric_cases():
    out = {}
    alcs = [-1, 0, 0.01, 0.03, 0.5, 1, 5, 10, 20, 33.3, 40, 40.1, 45, 47, 50, 53, 60, 78, 80, 96, 99.98, 99.99, 100, 101]
    out["density"] = [[a, calc.interpolate_density_from_alcohol(a)] for a in alcs]
    out["mass_fraction"] = [[a, calc.alcohol_mass_fraction(a)] for a in alcs if 0 < a <= 100]
    out["water_density"] = [[t, calc.water_density_temp(t)] for t in (0, 4, 10, 15, 20, 21.3, 25, 30, 40)]
    out["volume_temp"] = [[v, t, w, calc.correct_volume_temp(v, t, w)]
                          for v in (10, 100) for t in (15, 20, 25.5) for w in (False, True)]
    out["density_temp"] = [[d, t, a, calc.correct_density_to_20C(d, t, a)]
                           for d in (0.95, 1.01) for t in (15, 20, 24.3) for a in (0, 40, 100)]
    out["calibration"] = [[[[10, 9], [20, 19]], 15, calc.apply_calibration_curve([(10, 9), (20, 19)], 15)],
                          [[[10, 9.7], [20, 19.8], [30, 30.3], [40, 40.5]], 52.3,
                           calc.apply_calibration_curve([(10, 9.7), (20, 19.8), (30, 30.3), (40, 40.5)], 52.3)]]
    actual = []
    for measured, probe, water in itertools.product((0, 5, 20, 40, 40.1, 47, 55), (10, 36, 100), (0, 9.2, 25.5, 98.4)):
        try:
            value = calc.compute_actual_alcohol(measured, probe, water)
            eff = calc.compute_effective_dilution_factor(measured, probe, water)
            actual.append([measured, probe, water, {"alcohol": value, "effective": eff}])
        except ValueError as error:
            actual.append([measured, probe, water, {"error": str(error)}])
    out["actual_alcohol"] = actual
    plans = []
    for probe_alc, volume, target in itertools.product((30, 41, 50, 53, 78, 80, 96), (25, 100), (40, 45)):
        try:
            plans.append([probe_alc, volume, target, calc.plan_dilution(probe_alc, volume, target)])
        except ValueError as error:
            plans.append([probe_alc, volume, target, {"error": str(error)}])
    out["plan"] = plans
    out["plan_errors"] = [[50, 0, 40], [50, 100, 0], [50, 100, 100], [40, 100, 40]]
    return out


def evaluation_cases():
    base = {"mode": "diluted", "room_temp": "21,3", "probe_volume": "100", "water_value": "25,5", "water_mode": "mass",
            "measured_alcohol": "40,1", "measured_density": "0,9505", "measured_extract": "1,6"}
    cases = []

    def add(name, **changes):
        calib = changes.pop("calib", None)
        use = changes.pop("use", False)
        raw = dict(base)
        raw.update(changes)
        cases.append({"name": name, "raw": raw, "calib": calib, "use": use})

    add("standard")
    add("mit Spindel", spindle_alcohol="49,6", spindle_density="0,935")
    add("Spindel nur Alkohol", spindle_alcohol="52")
    add("mit Labor", lab_alcohol="55,4", lab_density="0,93", lab_extract="2,1", lab_note="Labor X")
    add("Tank und Charge", sample_name="  Salbei ", batch="26-014", tank_nr="T-12")
    for temp in ("18", "20", "20,0", "24,9", "41"):
        add(f"Temperatur {temp}", room_temp=temp)
    for water_mode, water in (("vol", "25,5"), ("mass", "98,4"), ("vol", "0"), ("mass", "0")):
        add(f"Wasser {water_mode} {water}", water_mode=water_mode, water_value=water)
    for probe in ("10", "36", "100", "0", "-5", "12000"):
        add(f"Probe {probe}", probe_volume=probe)
    add("Wasser negativ", water_value="-1")
    for alc in ("0", "20", "40", "45", "47", "52", "80", "abc", ""):
        add(f"Alkohol {alc!r}", measured_alcohol=alc)
    add("zu hoch für Verdünnung", measured_alcohol="80", water_value="10", probe_volume="10", water_mode="vol")
    add("nur Extrakt", measured_alcohol="", measured_density="", measured_extract="5")
    add("nur Dichte", measured_alcohol="", measured_density="0,95", measured_extract="")
    add("kein Messwert", measured_alcohol="", measured_density="", measured_extract="")
    add("keine Temperatur", room_temp="")
    add("Temperatur Unsinn", room_temp="warm")
    add("ungültige Dichte", measured_density="abc")
    add("Dichte außerhalb", measured_density="2,5")
    add("Spindeldichte ohne Spindelalkohol", spindle_density="0,95")
    add("nur Spindeldichte", measured_alcohol="", measured_density="", measured_extract="", probe_volume="", water_value="",
        spindle_alcohol="40", spindle_density="0,95", room_temp="25")
    add("Kalibrierung", calib=[[10, 9.7], [20, 19.8], [30, 30.3], [40, 40.5]], use=True)
    add("Kalibrierung zu wenig Punkte", calib=[[10, 9]], use=True)
    add("Kalibrierung aus", calib=[[10, 9], [20, 19]], use=False, spindle_alcohol="50")
    add("kleines Volumen", probe_volume="10", water_value="2", water_mode="vol")
    add("Dezimalpunkt", room_temp="21.3", probe_volume="100.0", water_value="25.5", measured_alcohol="40.1")
    add("Leerzeichen", room_temp=" 21,3 ", probe_volume=" 100 ")
    for alc, water, probe in (("40", "98,4", "100"), ("39,6", "98,4", "100"), ("40,4", "98,4", "100"), ("40,0", "25,5", "100")):
        add(f"Destillat/Mazerat {alc} {water}", measured_alcohol=alc, water_value=water, probe_volume=probe,
            spindle_alcohol="77,2" if water == "98,4" else "49,6")
    direct = {"mode": "direct", "room_temp": "21", "measured_alcohol": "27,05", "measured_density": "1,0312",
              "measured_extract": "31,4"}
    for name, changes in (("direkt", {}), ("direkt über Messbereich", {"measured_alcohol": "60"}),
                          ("direkt mit Spindel", {"spindle_alcohol": "27", "spindle_density": "1,031"}),
                          ("direkt nur Extrakt", {"measured_alcohol": "", "measured_density": ""}),
                          ("direkt ohne Werte", {"measured_alcohol": "", "measured_density": "", "measured_extract": ""}),
                          ("direkt kalibriert", {"measured_alcohol": "15", "_calib": True})):
        raw = dict(direct)
        calib = None
        use = False
        if changes.pop("_calib", False):
            calib, use = [[10, 9], [20, 19]], True
        raw.update(changes)
        cases.append({"name": name, "raw": raw, "calib": calib, "use": use})
    for case in cases:
        calib = [tuple(p) for p in case["calib"]] if case["calib"] else None
        result = m.evaluate_measurement(case["raw"], calib_data=calib, use_calibration=case["use"], now=NOW)
        case["result"] = jsonable(result)
        case["report"] = m.format_report(result) if result["ok"] else None
    return cases


def history_cases():
    rows = []
    for index, case in enumerate(evaluation_cases()):
        result = case["result"]
        if not result["ok"]:
            continue
        inp, out = result["input"], result["output"]
        rows.append({
            "id": index + 1, "timestamp": result["timestamp"], "sample_name": result["sample_name"], "batch": result["batch"],
            "tank_nr": result["tank_nr"] or None, "mode": result["mode"], "room_temp": inp["room_temp"],
            "probe_volume": inp["probe_volume"], "water_volume": inp["water_volume"],
            "probe_volume_input": inp["probe_volume_input"], "water_input": inp["water_input"], "water_mode": inp["water_mode"],
            "measured_alcohol": inp["measured_alcohol"], "measured_density": inp["measured_density"],
            "measured_extract": inp["measured_extract"], "dilution_factor": inp["dilution_factor"],
            "effective_dilution_factor": out["effective_dilution_factor"], "spindle_alcohol": inp["spindle_alcohol"],
            "spindle_density_at_temp": inp["spindle_density_at_temp"], "spindle_density_20C": inp["spindle_density_20C"],
            "calibration_applied": int(inp["calibration_applied"]), "lab_alcohol": inp["lab_alcohol"],
            "lab_density": inp["lab_density"], "lab_extract": inp["lab_extract"], "lab_note": inp["lab_note"] or None,
            "actual_alcohol": out["actual_alcohol"], "actual_density": out["actual_density"], "actual_extract": out["actual_extract"],
        })
    rows.append({"id": 999, "timestamp": "2026-01-05T10:00:00", "sample_name": "Altprobe", "actual_alcohol": 78.0})
    return {
        "rows": rows,
        "table": [list(m.history_table_values(r)) for r in rows],
        "details": [jsonable(m.history_detail_lines(r)) for r in rows],
    }


def main():
    data = {"numeric": numeric_cases(), "evaluations": evaluation_cases(), "history": history_cases(),
            "columns": [[k, t] for k, t, _w in m.HISTORY_COLUMNS]}
    path = os.path.join(ROOT, "tests-js", "reference.json")
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(data, handle, ensure_ascii=False, allow_nan=False, indent=1)
    print("geschrieben:", path, f"({len(data['evaluations'])} Auswertungen, {len(data['history']['rows'])} Historienzeilen)")


if __name__ == "__main__":
    main()
