# Alex 501 Mazerat-Interpolations-App

## Git / GitHub

- Remote: https://github.com/woku369/Alex501 (Branch `main`).
- Standing permission: `git push` auf dieses Repo darf ohne vorherige Rückfrage ausgeführt werden.
  Gilt nur für `push` auf dieses eine Repo – andere riskante Git-Aktionen (force-push, reset --hard,
  Löschen von Branches etc.) weiterhin vorher bestätigen lassen.
- Das Projektverzeichnis liegt auf einem Netzlaufwerk (`//ds124-rockingk/...`); dafür ist
  `safe.directory` global in der Git-Konfiguration eingetragen.

## Entwicklung

- Python-Tests: `python -m unittest discover -s tests` (der GUI-Rauchtest braucht tkinter, matplotlib und einen Bildschirm, sonst wird er übersprungen).
- Tablet-Version (PWA) im Ordner `docs/` (JavaScript, ohne Build-Schritt). Der Rechenkern `docs/calc.js` und `docs/measurement.js` ist eine Portierung von `calculations.py` und `measurement.py`; Abgleich: `python tools/make_reference.py` und `node --test tests-js/parity.test.js tests-js/pwa.test.js`. Erzeugte Dateien: `docs/alkoholtabelle.js`, `docs/infotext.js` (per `python tools/make_pwa_data.py`).
- Bei Änderungen an der Rechnung beide Seiten (Python und JavaScript) anpassen und die Referenzwerte neu erzeugen.
- Bei Änderungen an der PWA `VERSION` in `docs/sw.js` und `APP_VERSION` in `docs/app.js` gemeinsam erhöhen.

## Offene Punkte

- Bewusst zurückgestellte Themen (Warteschleife) stehen in `Offene_Punkte_Alex501.md` (Nummern OP-1 bis OP-11). Bei „offene Punkte“, „Warteschleife“ oder einer OP-Nummer dort nachsehen und beim Erledigen oder Ändern eines Punktes die Datei aktualisieren.

