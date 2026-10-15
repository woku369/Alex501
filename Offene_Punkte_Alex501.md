# Offene Punkte Alex501 (Warteschleife)

Stand: 15.10.2026. Hier stehen Themen, die besprochen, aber bewusst **noch nicht umgesetzt** sind, mit allen
Entscheidungen und Hintergründen. Zum Wiederaufnehmen genügt z. B.: „Nimm OP-2 wieder auf.“

Reihenfolge der Arbeit (Beschluss des Kräuter-Meisters): **zuerst** Abläufe der Probenvorbereitung und Messung im
Alltag erproben, Messwerte sammeln, Erfahrung und Routine aufbauen. Danach werden die Punkte unten aufgenommen;
dabei sind weitere Änderungen und Ergänzungen an Ablauf und App zu erwarten.

Kennzeichnung: **[Annahme]** = nicht belegt, **[Modell]** = Modellrechnung der App-Logik, **[Nutzerangabe]** = Angabe des
Kräuter-Meisters.

## Übersicht

| Nr. | Thema | Status | Aufnehmen, wenn |
|---|---|---|---|
| OP-1 | Einbindung in den MazerationsMeister (MM) | Konzept beschlossen, nichts gebaut | Ergebnisse als zuverlässig gelten |
| OP-2 | Korrekturanalyse Spindel ↔ Alex (Extrakt) | Idee, nichts gebaut | genug Messwerte je Sorte vorliegen |
| OP-3 | Spindel-Plausibilitätscheck (scheinbarer Alkohol aus der Dichte) | Idee, nichts gebaut | zusammen mit OP-2 |
| OP-4 | Messreihen / Wiederholmessungen in den Apps | Idee, nichts gebaut | vor oder mit OP-5 |
| OP-5 | Test der Spindelgenauigkeit (3 Mazerate, 3 Destillate, zwei Personen) | geplant, später | Routine in der Messung vorhanden |
| OP-6 | Kalibrierkurve: Ansatzpunkt der Korrektur | Frage offen | Kalibrierpunkte werden erhoben |
| OP-7 | Extraktkorrektur für Alkohol und Dichte | zurückgestellt | Extraktwerte der Mazerate liegen vor |
| OP-8 | Datenhaltung Tablet ↔ PC | offen | Tablet im Alltag in Gebrauch |
| OP-9 | Probenart-Feld und Übernahme-Zeile | nicht umgesetzt | bei Bedarf (manuelle Übernahme in MM) |
| OP-10 | Zoll: Methodenwechsel und Umgang mit korrigierten Werten | zu klären | bevor korrigierte Werte gebucht werden |
| OP-11 | Praxis: Probenvorbereitung, Messablauf, Routine | läuft (Kräuter-Meister) | laufend, Rückmeldungen einarbeiten |

---

## OP-1 Einbindung in den MazerationsMeister (MM)

**Beschlossen (Nutzerangaben, 15.10.2026)**
- MM läuft als portable exe am PC (Electron). Die PWA im MM ist nur Hilfe bei den Mazerationen (gleiche Gründe wie bei der Alex-PWA).
- Tank-Bezeichnungen sind einheitlich und richten sich nach MM.
- **Buchung nur per händischem Klick, nie automatisch.**
- Frische Mazerate: vorerst Spindelwerte (nicht Alex). Zunächst Spindelvergleich, danach der Alex-Output.
- Zu Beginn werden Alex-Werte **ausschließlich von Hand** in MM übernommen.

**Konzept (Vorschlag, mit dem Kräuter-Meister besprochen)**
- **Weg B: Übergabedatei.** Beide Alex-Apps schreiben dieselbe JSON-Datei (Format `alex501-messungen`, Version 1; die PWA liefert sie
  bereits, die Windows-App bräuchte einen JSON-Export). MM liest sie über einen Datei-Dialog (funktioniert in Electron, Browser und PWA).
- **MM bleibt die einzige Buchungsstelle.** Die Alex-Apps buchen nie in den Lagerbestand.
- **Messwerte-Liste je Tank in MM:** importierte Messungen stehen zuerst nur als Liste. Daneben: Buchwert, Spindelwert, Alex-Wert, Abweichung
  und Auswirkung auf die Liter Absolutalkohol. Erst ein Klick übernimmt den Wert als „Korrektur“ (in MM gibt es `recordCorrection` mit
  Vorher/Nachher von Menge, Alkohol, Liter Absolutalkohol und Grund). Die Herkunft (Messung Nr., Datum, Methode) steht im Grund/Journal.
- Zuordnung bei Tank-Inventur über die **Tank-Nr.**, bei frischen Mazeraten über die **Charge**.
- **Warnung**, wenn nach der Probenahme Zu- oder Abgänge für den Tank gebucht wurden (Messwert kann veraltet sein).
- Inhalt je Messung: Tank-Nr., Charge, Datum, Alkohol (%vol) mit Gerätegrenze, Dichte bei 20 °C, Extrakt, Modus, Spindelwert, Messungs-ID.
- Alkohol mit **einer Nachkommastelle** übernehmen (Alex ±0,4 %vol, nach der Verdünnung etwa ±0,5 bei Mazerat; zwei Stellen täuschen Genauigkeit vor).
- Tank-Nr. prüfen (in MM gibt es `findAehnlichenWert` für Groß-/Kleinschreibung und Leerzeichen). Spätere Idee: Tankliste aus MM in die Alex-Apps
  exportieren, damit die Eingabe nicht vertippt wird.
- Optional später (nach Bewährung): Datei automatisch aus einem festen Ordner einlesen (in MM müsste dafür ein Lese-Zugriff in der Electron-Schnittstelle ergänzt werden).

**Bewusst nicht gewählt**
- **SQLite-Datei der Windows-App direkt aus MM lesen:** neuer nativer Zugriff in Electron nötig; die Datenbank liegt auf einem Netzlaufwerk,
  gleichzeitiger Zugriff mit der Alex-App ist heikel (allgemeines Wissen über SQLite im Netzwerk, hier nicht geprüft); schließt die
  Tablet-Daten aus.
- **Rechenkern in MM einbauen:** wäre eine dritte Kopie der Rechnung. Die Rechnung bleibt in den Alex-Apps (Python als Referenz, JavaScript für das Tablet).

**Stand der Prüfung von MM:** gelesen wurden `APP_DOCUMENTATION.md`, `src/lib/stock-service.ts`, `src/lib/mazeration-calc.ts`,
`src/schemas/inventorySchema.ts`, `src/lib/electron-bridge.ts` (Repo `woku369/MazerationsMeister`, Stand SHA 464cc55). Nicht gelesen wurden
die Dialoge (Einlagern, Bearbeiten) und die Tank-Verwaltung. Vor dem Bau die tatsächliche Bedienung dort ansehen.

**Offene Fragen**
- Soll der Alex-Wert bei frischen Mazeraten später doch die Alkoholangabe bei der Einlagerung bzw. das Protokollfeld „Endkonzentration“
  bestimmen? (Davon hängen die Liter Absolutalkohol der Ausbeute und damit der Verlust ab, siehe OP-10.)

---

## OP-2 Korrekturanalyse Spindel ↔ Alex (Extrakt)

**Idee des Kräuter-Meisters:** mit dem Alex einen Korrekturfaktor ermitteln, vermutlich je Mazeratsorte, um abzuschätzen, wie weit der
Spindelwert vom tatsächlichen abweicht. Größenordnung bisher unbekannt (2–3 %? bei extraktreicheren 5 %? mehr?).

**Fachlicher Hintergrund**
- Zwei Arten von Fehlern: **zufällig** (Alex ±0,4 %vol, Verdünnung, Spindelablesung) und **systematisch** (Extrakt erhöht die Dichte, die Spindel liest einen zu niedrigen Alkohol).
- **[Modell]** (Annahme: Extrakt mit 0,5 bis 0,8 ml/g partiellem spezifischem Volumen, zuckerähnlich; nicht an echten Mazeraten geprüft): bei 50 %vol liest die Spindel
  etwa **1,3 bis 2,8 %vol zu niedrig je g/100 ml Extrakt**; mit 0,63 ml/g sind es 2,15 (1 g/100 ml), 4,4 (2), 6,7 (3), 11,8 (5).
  Der Alex-Wert aus der Verdünnung liegt im selben Modell um etwa +0,23 %vol je g/100 ml zu hoch (siehe `Berechnungslogik_Alex501.txt`, Punkt 6).
- Damit hängt die Abweichung **am Extrakt der jeweiligen Charge**, nicht konstant an der Sorte. Der Alex misst diesen Extrakt mit.

**Umsetzungsskizze**
- Auswertung in der Messhistorie: je Sorte (Bezeichnung) die Paare *Alex-Alkohol minus Spindel-Alkohol* gegen *gemessenen Extrakt*; lineare Regression mit Steigung,
  Achsenabschnitt, Anzahl, Streuung. Sinnvoll ab etwa 5 bis 10 Messungen je Sorte über einen Extraktbereich.
- Prüfen: gibt es je Sorte eine saubere Gerade, haben alle Sorten dieselbe Steigung, wie groß ist der Rest?
- Später für frische Mazerate: Schätzung *Spindel + typischer Extrakt der Sorte × Steigung* mit Streubreite; Übergabe als kleine Korrekturtabelle an MM (OP-1).
- Voraussetzung für belastbare Zahlen: Kenntnis der Spindelgenauigkeit (OP-5).

---

## OP-3 Spindel-Plausibilitätscheck

- Aus der berechneten Dichte der Originalprobe (Alex) den **scheinbaren Alkohol** ausrechnen, den die Spindel anzeigen müsste (Umkehrung der Dichtetabelle), und mit dem Spindelwert vergleichen.
- Braucht die Annahme zum partiellen spezifischen Volumen nicht und zeigt, ob Spindel-Alkohol und Alex-Dichte zusammenpassen und wie viel der Abweichung zum Alex-Alkohol vom Extrakt stammt.
- Dazu passend: Spindeldichte (3 Nachkommastellen, ±0,0005) mit dem scheinbaren Alkohol und der Alex-Dichte vergleichen.

---

## OP-4 Messreihen / Wiederholmessungen

- Wiederholmessungen als Gruppe auswerten (Mittelwert, Standardabweichung), z. B. dieselbe Verdünnung mehrfach am Alex, mehrere unabhängige Verdünnungen derselben Probe, mehrere Spindelablesungen.
- Ziel: Gerät, Verdünnung und Ablesung voneinander trennen, damit die Unsicherheit aus den eigenen Daten kommt statt aus Annahmen.
- Voraussetzung: Gruppierung über Probe/Charge/Tank und Datum (eventuell neues Feld „Messreihe“).

---

## OP-5 Test der Spindelgenauigkeit (später)

**Plan (Nutzerangabe):** 3 Mazerate und 3 Destillate, jede Probe 5-mal gespindelt. Dieselbe Prozedur macht der Lohnbrenner. Wenn amtliche Messwerte vorliegen, umso besser.

**Hintergrund:** Die App rechnet bisher mit **±0,3 %vol für die Spindel** (Nutzerangabe, schon auf 20 °C korrigiert). Diese Zahl ist die gesetzliche Toleranz; die tatsächliche Ablesegenauigkeit
ist unbekannt. Weitere Angaben des Kräuter-Meisters: Gesetzgeber akzeptiert ±0,3 %vol, der Zoll misst mit ±0,2 %vol, der Alex hat ±0,4 %vol.

**Auswertung (geplant):** Standardabweichung der Ablesungen je Person und Probenart, Unterschied zwischen den beiden Personen, Unterschied zwischen Mazerat und Destillat, Vergleich mit den amtlichen Werten.
Ergebnis in die Messgrenzen der App übernehmen: `SPINDLE_ALCOHOL_TOLERANCE` in `measurement.py` und `docs/measurement.js` (beide Seiten), danach `python tools/make_reference.py`.

| Probe | Art | Person | Ablesung 1 | 2 | 3 | 4 | 5 | Temperatur | Amtlicher Wert |
|---|---|---|---|---|---|---|---|---|---|
| | | | | | | | | | |

---

## OP-6 Kalibrierkurve: Ansatzpunkt

- Stand: Die Kalibrierkurve wird auf den **berechneten** Alkohol der Originalprobe angewendet (bei Destillat etwa 78 %vol), obwohl die Kalibrierpunkte nur bis 50 %vol reichen (Extrapolation).
- Vermutung des Kräuter-Meisters: Kalibriert wird mit der **verdünnten** Probe. Dann wäre der richtige Ansatzpunkt die **gemessene Anzeige** der Verdünnung (im Gerätebereich), und erst danach wird zurückgerechnet.
- Zu klären: wie die Kalibrierpunkte gewonnen werden. Änderung wäre klein (`measurement.py` und `docs/measurement.js`, Doku `Berechnungslogik_Alex501.txt` Punkt 5, Tests).

---

## OP-7 Extraktkorrektur für Alkohol und Dichte

- Bekannte Grenze: Extraktstoffe werden bei der Alkoholberechnung nicht berücksichtigt. **[Modell]** ca. +0,23 %vol je g/100 ml Extrakt (Alkohol zu hoch), Dichte −0,0014 / −0,0036 / −0,0073 g/cm³ bei 2 / 5 / 10 g/100 ml.
- Entscheidung bisher: keine Korrektur, da keine belegten Extraktwerte der eigenen Mazerate vorliegen.
- Geplant: Korrektur je Messung aus dem gemessenen Extrakt mit einem Parameter (partielles spezifisches Volumen des Extrakts), festgelegt aus Referenzdaten (Laborwerte gibt es nur gelegentlich, vor allem für das GFKC);
  Gegenprobe der Messkette über das GFKC (aus den Einzelwerten der Rezeptur vorausberechnen, mit Laborwert vergleichen). Siehe auch OP-2 (liefert eine empirische Steigung).

---

## OP-8 Datenhaltung Tablet ↔ PC

- Stand: Messungen liegen in der PWA nur im Browser des Tablets. Transport über JSON-Sicherung und Import in die Windows-App (vorhanden).
- Offen: Sync über ein **privates** Repo wäre möglich (das Repo `Alex501` ist öffentlich, dorthin dürfen keine Messdaten).
- Offen: Praxistest der PWA auf einem echten Android-Tablet im Mazerationsraum (Installation, Start ohne Netz, Tastatur mit Dezimalkomma, Sicherung, Bedienung mit Handschuhen).

---

## OP-9 Probenart-Feld und Übernahme-Zeile

- **Probenart** (Mazerat, Destillat, Fertigprodukt): würde den Modus einstellen und den Planer anpassen. Nicht umgesetzt.
- **Übernahme-Zeile** für die manuelle Übernahme in MM: Tank, Alkohol (eine Nachkommastelle), Dichte bei 20 °C und fertiger Text für den Korrekturgrund zum Kopieren. Nicht umgesetzt; sinnvoll, solange die Übernahme von Hand geschieht.

---

## OP-10 Zoll: Methodenwechsel und korrigierte Werte (zu klären)

**Kontext (Nutzerangaben):** Der Kräuter-Meister ist dem Zoll gegenüber steuerpflichtig und muss eigentlich nur seine Verluste schlüssig erklären; das soll mit geräteunterstützter Dokumentation geschehen.
Die Spindelwerte der Mazerate stimmen nach seiner Einschätzung nicht; der Zoll akzeptiert die (nicht dokumentierte) Abweichung stillschweigend.

**Technische Beobachtung (keine rechtliche Bewertung):** In MM ist der Verlust die eingesetzte Liter Absolutalkohol minus Ausbeute; die Ausbeute hängt am Alkoholgehalt des Mazerats.
Liest die Spindel systematisch zu niedrig, erscheint die Ausbeute zu klein und der Verlust zu groß. 1 %vol Differenz auf 5000 L sind 50 L Liter Absolutalkohol.
Ein Methodenwechsel mitten im Jahr erzeugt einen Sprung in den Aufzeichnungen.

**Vorschlag:** Beide Werte (Spindel und Alex) mit Datum und Methode nebeneinander führen. Ob und wann korrigierte Werte gebucht werden, vorab mit dem Zoll bzw. der Steuerberatung klären.

---

## OP-11 Praxis: Probenvorbereitung, Messablauf, Routine

- Läuft beim Kräuter-Meister. Ablauf bisher: Probenvorbereitung (Kohlensäure entgasen, Trübungen mit Kieselgur entfernen), Probe im 100-ml-Messkolben, Wasser wiegen,
  Raumtemperatur über geeichten Logger, Messung am Alex 501 (mindestens 40 ml verdünnte Probe), Eingabe in der App.
- Erwartet: Änderungen und Ergänzungen an Ablauf und App aus den Erfahrungen. Rückmeldungen und Screenshots einarbeiten.

---

## Annahmen, die vor belastbaren Aussagen geprüft werden sollten

- Alex 501 ±0,4 %vol (Angabe für 40 %vol; in der App für alle Messwerte angesetzt) und Messbereich bis 47 %vol, Mindestmenge 40 ml (Nutzerangaben).
- Spindel ±0,3 %vol (siehe OP-5).
- Partielles spezifisches Volumen des Extrakts 0,5 bis 0,8 ml/g und die Annahme, dass die Spindel dem Alkohol aus der Dichte entspricht (Modellrechnungen in OP-2, OP-7).
- Wie das Alex 501 den Alkohol bei extrakthaltigen Proben bestimmt (hier nicht geprüft).
- Dichte des Alex als wahre Dichte (Vakuum) bei der Umrechnung der Alkoholtabelle (CRA 1996, Dichte in Luft).
- Reale Extraktgehalte der Mazerate (bisher unbekannt, der Alex liefert sie).
