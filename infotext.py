"""
Texte des Info-Tabs der Alex 501 Mazerat-Interpolation.

Inhaltlich gleich zu Berechnungslogik_Alex501.txt (Beschreibung der Rechenschritte); bei Änderungen
an der Rechnung beide Stellen anpassen.
"""

INFO_SECTIONS = [
    ("Zweck", [
        "Das Alex 501 misst Alkohol, Dichte und Extrakt, gibt aber über etwa 47 %vol keine Werte aus. "
        "Mazerate (ca. 50 %vol) und Destillate (ca. 75-80 %vol) müssen deshalb verdünnt werden. Die App rechnet "
        "die Messwerte der verdünnten Probe auf die Originalprobe zurück und speichert jede Messung in der "
        "Messhistorie.",
    ]),
    ("Ablauf", [
        "0. Probenvorbereitung: Kohlensäurehaltige Proben werden entgast, Trübungen durch Kieselgurbehandlung "
        "entfernt (trübe Proben sind nicht messbar).",
        "1. Verdünnung ansetzen: Probe nach Volumen (Messkolben), Wasser nach Gewicht. Auf etwa 40 %vol "
        "verdünnen, damit keine Trübung (Louche-Effekt) entsteht. Für eine Messung werden mindestens 40 ml "
        "verdünnte Probe benötigt. Vorgesehen sind 100 ml Probe im Messkolben und Wasser nach Gewicht; der "
        "Verdünnungsplaner nennt die dazu nötige Wassermenge und wie viele Messungen die Verdünnung ergibt.",
        "2. Verdünnte Probe am Alex 501 messen: Alkohol, Dichte, Extrakt.",
        "3. Werte, Raumtemperatur und die tatsächlich angesetzten Mengen eingeben, 'Berechnen' klicken.",
        "4. Proben unter 47 %vol (z. B. Fertigprodukte) werden direkt gemessen: Modus 'Direkt gemessen', "
        "die Alex-Werte werden unverändert übernommen.",
        "5. Tank-Nr. und Charge eintragen: Die Inventur der Mazerat-Tanks am Jahresende ordnet jede Messung "
        "einem Tank zu; die Messhistorie lässt sich danach durchsuchen.",
    ]),
    ("Berechnungslogik", [
        "1. Volumen auf 20 °C: Das Probevolumen wird mit dem Ausdehnungskoeffizienten von Ethanol, Wasser nach "
        "Gewicht mit der Dichte bei 20 °C in ein Volumen bei 20 °C umgerechnet.",
        "2. Alkoholgehalt der Originalprobe (Massenbilanz): Volumina von Ethanol und Wasser sind nicht additiv "
        "(Volumenkontraktion), Massen schon. Aus dem gemessenen %vol der Verdünnung folgt der Massenanteil Ethanol "
        "w = (%vol / 100) * Dichte_Ethanol / Dichte_Gemisch. Die Ethanolmasse der Probe "
        "(V_Probe * %vol_Probe / 100 * Dichte_Ethanol) muss gleich w * Gesamtmasse der Verdünnung sein; daraus "
        "wird %vol_Probe bestimmt.",
        "3. Wirksamer Verdünnungsfaktor = reales Volumen der Verdünnung / Probevolumen. Das reale Volumen "
        "folgt aus Gesamtmasse und Dichte der Verdünnung und ist wegen der Kontraktion kleiner als die Summe "
        "der Volumina.",
        "4. Extrakt der Originalprobe = gemessener Extrakt * wirksamer Faktor (g/100 ml bezieht sich auf das "
        "reale Volumen).",
        "5. Dichte der Originalprobe = Tabellendichte bei berechnetem %vol + (gemessene Dichte - Tabellendichte "
        "bei gemessenem %vol) * wirksamer Faktor. Die Differenz stammt von den Extraktstoffen (Näherung erster "
        "Ordnung).",
        "6. Kalibrierkurve (optional): lineare Regression Messwert -> Referenzwert, angewendet auf den berechneten "
        "Alkoholgehalt.",
        "7. Spindelvergleich: Abweichung = berechneter Alkohol - Spindelwert. Die Messgrenzen sind die Summe aus "
        "Spindelgenauigkeit (±0,3 %vol) und Gerätegenauigkeit des Alex 501 (±0,4 %vol) mal Verstärkung durch die "
        "Verdünnung. Die Spindeldichte wird mit der berechneten Dichte der Originalprobe verglichen. Laborwerte "
        "werden analog verglichen.",
    ]),
    ("Datengrundlage", [
        "Dichte-Tabelle: Canadian Alcoholometric Laboratory Table 1996 (Canada Revenue Agency), berechnet aus der "
        "Formel der OIML R 22. Die Tabelle gibt die Dichte in Luft an und wird mit dem Luftauftrieb auf die wahre "
        "Dichte (Vakuum) bei 20 °C umgerechnet. Wasserdichte nach Tanaka et al. (2001).",
    ]),
    ("Bekannte Grenzen", [
        "Extraktstoffe: Die Massenbilanz behandelt Probe und Verdünnung als reines Ethanol-Wasser-Gemisch. Der "
        "Extrakt nimmt Volumen ein; der berechnete Alkoholgehalt fällt dadurch tendenziell zu hoch aus. Eine "
        "Modellrechnung (Annahme: Extrakt wie Zucker, nicht an echten Mazeraten geprüft) ergab etwa +0,23 %vol "
        "je 1 g/100 ml Extrakt. Bis belegte Werte vorliegen, wird nicht korrigiert.",
        "Geräteungenauigkeit: Die Genauigkeit des Alex 501 (±0,4 %vol bei 40 %vol, für alle Messwerte so "
        "angesetzt) wird durch die Verdünnung verstärkt: etwa Faktor 1,2 bei Mazeraten, etwa Faktor 1,9 bei "
        "Destillaten. Messkolben (100 ml), Waage und Raumtemperatur (±0,1 K) tragen dagegen weniger als 0,1 %vol bei.",
        "Kalibrierkurve: Sie wird auf den berechneten Alkoholgehalt der Originalprobe angewendet, auch wenn "
        "dieser über dem Bereich der Kalibrierpunkte liegt.",
    ]),
]
