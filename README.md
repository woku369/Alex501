# Alex 501 Mazerat-Interpolations-App

Desktop-Anwendung zur Berechnung tatsächlicher Messwerte von alkoholischen Mazeraten aus verdünnten Proben.

## Hintergrund

Das Alex 501 Gerät von Anton Paar kann nur bis maximal 47 %vol. Alkoholgehalt messen. Proben mit höherem Alkoholgehalt (z.B. Kräutermazerate mit >50 %vol.) müssen verdünnt werden. Diese Anwendung rechnet die Messwerte der verdünnten Probe auf die tatsächlichen Werte der Originalprobe um.

## Features

- ✅ Berechnung des tatsächlichen Alkoholgehalts unter Berücksichtigung der Volumenkontraktion
- ✅ Berechnung der tatsächlichen Dichte basierend auf der Alkoholtabelle (Canadian Alcoholometric Laboratory Table 1996, berechnet aus der OIML-R-22-Formel)
- ✅ Berechnung des tatsächlichen Extraktgehalts
- ✅ Intuitive grafische Benutzeroberfläche
- ✅ Export der Ergebnisse (JSON/TXT)
- ✅ Lineare Kalibrierkurve (Referenz-/Messwert-Paare, Diagramm, Speichern/Laden)
- ✅ Temperaturkorrektur für Probe-/Wasservolumen und Spindeldichte (Referenz 20 °C)
- ✅ Messhistorie in SQLite mit automatischem Backup
- 🔄 Erweiterte Kalibrierung (Verdünnungsreihen, Polynom/Spline) – in Entwicklung

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

### 1. Verdünnung durchführen
- Verdünnen Sie Ihre Probe auf 40-45 %vol.
- Notieren Sie das Verhältnis (z.B. 1ml Probe + 1ml Wasser)

### 2. Messung mit Alex 501
- Messen Sie die verdünnte Probe
- Notieren Sie:
  - Alkoholgehalt (%vol.)
  - Dichte (g/cm³)
  - Extraktgehalt (g/100ml)

### 3. Werte in App eingeben
- Öffnen Sie den Tab "Messung"
- Geben Sie das Verdünnungsverhältnis ein
- Geben Sie die drei Messwerte ein
- Klicken Sie auf "Berechnen"

### 4. Ergebnisse
- Die App zeigt die tatsächlichen Werte der Originalprobe an
- Optional: Exportieren Sie die Ergebnisse als JSON oder TXT

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
