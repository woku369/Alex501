"""
Erzeugt die Datenmodule der Tablet-PWA (docs/) aus den Python-Quellen, damit es keine von Hand
gepflegte zweite Kopie gibt:
    docs/alkoholtabelle.js  <- alkoholtabelle.py
    docs/infotext.js        <- infotext.py

Aufruf (im Projektordner):  python tools/make_pwa_data.py
"""

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import alkoholtabelle  # noqa: E402
import infotext  # noqa: E402

HEADER = "// Automatisch erzeugt von tools/make_pwa_data.py - nicht von Hand ändern.\n"


def write(name, text):
    with open(os.path.join(ROOT, "docs", name), "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    print("geschrieben:", name)


def main():
    values = [str(v) for v in alkoholtabelle.VOL_PROZENT]
    rows = [",".join(values[i:i + 20]) + "," for i in range(0, len(values), 20)]
    write("alkoholtabelle.js",
          HEADER
          + "// Canadian Alcoholometric Laboratory Table 1996 (CRA), berechnet aus der OIML-R-22-Formel;\n"
          + "// Dichte in Luft, 20 °C. Quelle und Umrechnung siehe alkoholtabelle.py.\n"
          + f"export const DICHTE_START = {alkoholtabelle.DICHTE_START};\n"
          + f"export const DICHTE_SCHRITT = {alkoholtabelle.DICHTE_SCHRITT};\n"
          + "export const VOL_PROZENT = [\n" + "\n".join(rows) + "\n];\n")
    write("infotext.js",
          HEADER + "export const INFO_SECTIONS = "
          + json.dumps([[h, p] for h, p in infotext.INFO_SECTIONS], ensure_ascii=False, indent=2) + ";\n")


if __name__ == "__main__":
    main()
