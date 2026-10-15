# Alex 501 Mazerat-Interpolations-App

Desktop-Anwendung zur Berechnung tatsächlicher Messwerte von alkoholischen Mazeraten aus verdünnten Proben.

## Hintergrund

Das Alex 501 Gerät von Anton Paar kann nur bis maximal 47 %vol. Alkoholgehalt messen. Proben mit höherem Alkoholgehalt (z.B. Kräutermazerate mit >50 %vol.) müssen verdünnt werden. Diese Anwendung rechnet die Messwerte der verdünnten Probe auf die tatsächlichen Werte der Originalprobe um.

## Features

- ✅ Berechnung des tatsächlichen Alkoholgehalts unter Berücksichtigung der Volumenkontraktion
- ✅ Berechnung der tatsächlichen Dichte basierend auf der Alkoholtabelle (Canadian Alcoholometric Laboratory Table 1996, berechnet aus der OIML-R-22-Formel)
- ✅ Berechnung des tatsächlichen Extraktgehalts
- ✅ Grafische Oberfläche mit Eingabe-Karten, Ergebnis-Kacheln und Meldungen direkt im Fenster
- ✅ Verdünnungsplaner: nötige Wassermenge für eine vorgegebene Probemenge (z. B. 100 ml im Messkolben) und den Zielalkohol, mit Anzahl möglicher Messungen
- ✅ Gerätegrenze des Alkohols (Verstärkung durch die Verdünnung) und Messgrenzen für den Spindelvergleich
- ✅ Modus „Direkt gemessen“ für Proben im Messbereich (z. B. Fertigprodukte): Alex-Werte werden unverändert übernommen
- ✅ Vergleich mit Spindelung und optionalen Laborwerten (auch nachträglich ergänzbar)
- ✅ Export der Ergebnisse (JSON/TXT) und der Messhistorie (CSV)
- ✅ Lineare Kalibrierkurve (Referenz-/Messwert-Paare, Diagramm, Speichern/Laden)
- ✅ Temperaturkorrektur für Probe-/Wasservolumen und Spindeldichte (Referenz 20 °C)
- ✅ Messhistorie in SQLite (eigener Tab mit Suche und Details) mit automatischem Backup vor jeder Schema-Änderung
- 🔄 Erweiterte Kalibrierung (Verdünnungsreihen, Polynom/Spline) – in Entwicklung

## Einsatz im Betrieb

Die App unterstützt die Qualitätssicherung der Frischkräuter-Mazerate, -Destillate und Fertigprodukte:

- **Mazerate (ca. 50 %vol):** Frisch hergestellte Mazerate werden gespindelt (Alkohol, Dichte) und in das Lager gebucht, ggf. in einen bereits belegten Tank gepoolt. Am Jahresende werden alle Tanks gespindelt und zusätzlich mit dem Alex 501 gemessen. Die App rechnet die verdünnte Probe auf den Tank zurück und vergleicht mit der Spindelung. Dafür gibt es die Tank-Nr.
- **Destillate (ca. 75-80 %vol):** chargenrein gelagert, für die Inventur reicht eine Messung.
- **Fertigprodukte (4-27 %vol, zuckerhaltig):** werden im Jahresverlauf gemessen, direkt am Alex 501 (Modus „Direkt gemessen“); Spindelung ist hier nicht sinnvoll.
- **Probenvorbereitung:** Kohlensäurehaltige Proben werden entgast, Trübungen durch Kieselgurbehandlung entfernt.
- **Reihenfolge der Einführung:** Zunächst dient der Spindelvergleich zur Prüfung der Ergebnisse, danach der Alex-Output. Sind die Ergebnisse zuverlässig, soll die App in den MazerationsMeister eingebunden werden (siehe Roadmap).

## Tablet-Version (PWA, Android)

Für den Mazerationsraum ohne PC und Netzwerk gibt es eine Tablet-Version im Ordner `docs/`. Sie läuft im Browser (Chrome), nach einmaligem Laden **auch ohne Netz**, und rechnet wie die Windows-App (die JavaScript-Rechnung wird in `tests-js/` gegen die Python-Ergebnisse geprüft).

- **Einrichten (einmalig):** Auf GitHub unter *Settings → Pages* den Ordner `/docs` des Branches `main` veröffentlichen. Die Adresse lautet dann vermutlich `https://woku369.github.io/Alex501/`. Am Tablet einmal mit mobilen Daten öffnen und in Chrome über das Menü *App installieren* bzw. *Zum Startbildschirm hinzufügen* wählen. Danach startet sie wie eine App und braucht kein Netz mehr.
- **Funktionen:** Eingabe, Berechnung, Ergebnis-Kacheln, Meldungen, Verdünnungsplaner, Spindel- und Laborvergleich, Messhistorie mit Suche, Kalibrierkurve, Tank-Nr. Rechnung und Texte entsprechen der Windows-App.
- **Daten:** Die Messungen liegen nur im Browser des Tablets (IndexedDB). Bitte regelmäßig über *Messhistorie → Sicherung (JSON)* sichern; die Datei lässt sich in der Windows-App über *Messhistorie → Import (Tablet)* übernehmen (Dubletten werden übersprungen). Wenn Browserdaten gelöscht werden, sind die Messungen weg.
- **Updates:** Bei bestehender Verbindung lädt die App neue Versionen im Hintergrund und weist auf den Neustart hin.
- **Öffentliches Repo:** Das Repository ist öffentlich, die Seite enthält nur den Programmcode. Messdaten gehören nicht ins Repo.

### Entwicklung der Tablet-Version
```powershell
python tools/make_pwa_data.py      # docs/alkoholtabelle.js und docs/infotext.js aus den Python-Quellen
python tools/make_reference.py     # Referenzwerte der Python-Rechnung für den Abgleich neu erzeugen
node --test tests-js/parity.test.js tests-js/pwa.test.js   # Abgleich JavaScript gegen Python, Auslieferung (Version, Offline-Dateiliste)
```
Ändert sich `calculations.py`, `measurement.py` oder die Tabelle, müssen `docs/calc.js` bzw. `docs/measurement.js` nachgezogen und die Referenzwerte neu erzeugt werden; der Abgleich schlägt sonst fehl. Bei Änderungen an der Oberfläche `VERSION` in `docs/sw.js` und `APP_VERSION` in `docs/app.js` erhöhen, damit die Tablets die neuen Dateien holen. Der Browser-Test `tests-js/e2e.mjs` (Offline-Betrieb, Export/Import) braucht `playwright-core` und Chromium (siehe Kopf der Datei).

## Installation

### Voraussetzungen
- Python 3.8 oder höher
- pip (Python Package Manager)

### Schritt-für-Schritt Installation

1. **Python installieren** (falls nicht vorhanden):
   - Download von [python.org](https://www.python.org/downloads/)
   - Bei Installation "Add Python to PATH" aktivieren

2. **Abhängigkeiten installieren**:
   ```powershell
   pip install -r requirements.txt
   ```

3. **Anwendung starten**:
   ```powershell
   python main.py
   ```

## Verwendung

### 1. Verdünnung ansetzen
- Verdünnen Sie die Probe auf etwa 40 %vol (so entsteht keine Trübung). Für eine Messung werden mindestens 40 ml verdünnte Probe benötigt.
- Der **Verdünnungsplaner** (Tab „Messung“) nennt die Wassermenge für die vorgegebene Probemenge (Standard: 100 ml im Messkolben). Vorgesehen: Probe nach Volumen im Messkolben, Wasser wiegen.
- Notieren Sie, was tatsächlich abgemessen und eingewogen wurde.

### 2. Messung mit Alex 501
- Messen Sie die verdünnte Probe
- Notieren Sie:
  - Alkoholgehalt (%vol.)
  - Dichte (g/cm³)
  - Extraktgehalt (g/100ml)
- Proben im Messbereich (bis 47 %vol, z. B. Fertigprodukte) brauchen keine Verdünnung.

### 3. Werte in App eingeben
- Öffnen Sie den Tab „Messung“
- Wählen Sie den Modus „Verdünnt gemessen“ oder „Direkt gemessen (ohne Verdünnung)“
- Geben Sie Raumtemperatur, Probevolumen und Wasserzugabe (g oder ml) sowie die gemessenen Werte ein
- Optional: Spindelwerte und Laborwerte zum Vergleich
- Klicken Sie auf „Berechnen“ (oder Enter in einem Feld)

### 4. Ergebnisse
- Die App zeigt die Werte der Originalprobe als Kacheln, dazu Hinweise und den Vergleich mit Referenzwerten
- Jede Messung wird in der Messhistorie gespeichert (eine unveränderte Wiederholung wird nicht doppelt abgelegt)
- Im Tab „Messhistorie“ lassen sich Messungen suchen, im Detail ansehen, Laborwerte nachtragen und alles als CSV exportieren
- Optional: Exportieren Sie das Ergebnis als JSON oder TXT

### Tests ausführen
```powershell
python -m unittest discover -s tests
```
Der GUI-Rauchtest wird übersprungen, wenn kein Bildschirm verfügbar ist.

## Wissenschaftlicher Hintergrund

### Volumenkontraktion
Beim Mischen von Ethanol und Wasser tritt eine Volumenkontraktion auf (die App bilanziert deshalb über die Ethanolmasse, nicht über Volumina):
- 50ml Ethanol + 50ml Wasser ≠ 100ml Mischung
- Bei 50:50 Mischung ca. 3-4% Volumenreduktion

### Dichte-Interpolation
Die App verwendet die Ethanol-Wasser-Alkoholtabelle bei 20 °C (Canadian Alcoholometric Laboratory Table 1996, 2090 Zeilen, berechnet aus der OIML-R-22-Formel; siehe `alkoholtabelle.py`) mit linearer Interpolation für Zwischenwerte. Die Tabelle gibt die Dichte in Luft an; die App rechnet sie mit dem Luftauftrieb (Luft 0,0012 g/cm³, Gewichte 8,0 g/cm³) auf die wahre Dichte um, wie sie ein Biegeschwinger-Dichtemessgerät anzeigt.

### Extraktberechnung
Extrakte (g/100 ml) verdünnen sich proportional zum realen Volumen der Verdünnung. Dieses ist durch die Volumenkontraktion kleiner als die Summe von Probe- und Wasservolumen; die App berechnet es aus Gesamtmasse und Dichte der Verdünnung.

## Wichtige Hinweise

⚠️ **Genauigkeit**: Die Berechnungen basieren auf Standardkurven für reine Ethanol-Wasser-Gemische. Mazerate enthalten zusätzliche Inhaltsstoffe (Kräuterextrakte), die die Eigenschaften beeinflussen können.

⚠️ **Bekannte Grenze – Extraktstoffe**: Die Massenbilanz für den Alkoholgehalt behandelt die Probe als reines Ethanol-Wasser-Gemisch. Der Extrakt nimmt aber Volumen ein, wodurch der berechnete Alkoholgehalt der Originalprobe tendenziell zu hoch ausfällt; die berechnete Dichte fällt dann entsprechend zu niedrig aus. Eine Modellrechnung (Annahme: Extrakt mit partiellem spezifischem Volumen 0,63 ml/g, zuckerähnlich; **nicht an echten Mazeraten geprüft**) ergab bei 60 %vol und 1:1-Verdünnung etwa +0,3 %vol bei 2 g/100 ml, +0,9 %vol bei 5 g/100 ml und +1,7 %vol bei 10 g/100 ml Extrakt. Der Extraktwert selbst wird dabei kaum beeinflusst (Abweichung unter 0,4 %). Bis belegte Extraktwerte der eigenen Mazerate vorliegen, wird bewusst keine Korrektur angewendet; die lineare Kalibrierkurve (Spindel gegen Alex 501) kann einen näherungsweise gleichbleibenden Rest-Bias auffangen. Geplante Korrektur aus Referenzdaten: siehe `Roadmap_Alex501.txt`, Version 1.1.

💡 **Empfehlung**: Für höchste Präzision führen Sie eine Verdünnungsreihe mit einer Referenzprobe bekannter Werte durch und nutzen Sie die Kalibrierkurve (linear; erweiterte Kalibrierung in Entwicklung).

## Zukünftige Erweiterungen

- [ ] Erweiterte Kalibrierung mit Verdünnungsreihen (Polynom/Spline, mehrere Profile)
- [ ] Datenbank für Messserien
- [ ] PDF-Export mit Grafiken
- [ ] Temperaturkorrektur für alle Messwerte (bisher nur Volumen und Spindeldichte)

## Support

Bei Fragen oder Problemen wenden Sie sich an den Entwickler.

## Lizenz

Diese Software wird bereitgestellt "wie sie ist" ohne jegliche Garantie.
