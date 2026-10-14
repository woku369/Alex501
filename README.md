# Alex 501 Mazerat-Interpolations-App

Desktop-Anwendung zur Berechnung tatsächlicher Messwerte von alkoholischen Mazeraten aus verdünnten Proben.

## Hintergrund

Das Alex 501 Gerät von Anton Paar kann nur bis maximal 47 %vol. Alkoholgehalt messen. Proben mit höherem Alkoholgehalt (z.B. Kräutermazerate mit >50 %vol.) müssen verdünnt werden. Diese Anwendung rechnet die Messwerte der verdünnten Probe auf die tatsächlichen Werte der Originalprobe um.

## Features

- ✅ Berechnung des tatsächlichen Alkoholgehalts unter Berücksichtigung der Volumenkontraktion
- ✅ Berechnung der tatsächlichen Dichte basierend auf OIML R 22 / DIN 12354 Standardtabellen
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
Beim Mischen von Ethanol und Wasser tritt eine Volumenkontraktion auf:
- 50ml Ethanol + 50ml Wasser ≠ 100ml Mischung
- Bei 50:50 Mischung ca. 3-4% Volumenreduktion

### Dichte-Interpolation
Die App verwendet standardisierte Ethanol-Wasser-Dichte-Tabellen (OIML R 22) mit linearer Interpolation für Zwischenwerte.

### Extraktberechnung
Extrakte verdünnen sich proportional zum Gesamtvolumen unter Berücksichtigung der Volumenkontraktion.

## Wichtige Hinweise

⚠️ **Genauigkeit**: Die Berechnungen basieren auf Standardkurven für reine Ethanol-Wasser-Gemische. Mazerate enthalten zusätzliche Inhaltsstoffe (Kräuterextrakte), die die Eigenschaften beeinflussen können.

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
