"""
Alex 501 Mazerat-Interpolations-App
Berechnet tatsächliche Alkoholstärke, Dichte und Extraktgehalt aus verdünnten Messwerten
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
from datetime import datetime
import numpy as np
from scipy import interpolate
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import os
import sqlite3

# Deutsche Zahlenformatierung
def format_de(value, decimals=2):
    """Formatiert Zahlen mit deutschem Komma"""
    formatted = f"{value:.{decimals}f}".replace('.', ',')
    return formatted


class Alex501App:
    def correct_volume_temp(self, volume, temp, is_water=False):
        """Korrigiert das Volumen auf 20°C (Standardbedingungen) für Ethanol/Wasser oder Wasser."""
        # Näherungsformel für Volumenausdehnung (in % pro °C)
        # Ethanol: ca. 0,11%/K, Wasser: ca. 0,025%/K
        coeff = 0.00025 if is_water else 0.0011
        delta_t = temp - 20.0
        return volume / (1 + coeff * delta_t)

    def water_density_temp(self, temp):
        """Berechnet die Dichte von Wasser in g/cm³ in Abhängigkeit von der Temperatur (°C)."""
        # Näherungsformel für 0-40°C
        return 0.99987 - 0.00007 * (temp - 4) - 0.0000002 * (temp - 4) ** 2

    def interpolate_density_from_alcohol(self, alc):
        """Interpoliert die Dichte einer Ethanol-Wasser-Mischung bei 20°C anhand des Alkoholgehalts."""
        # Werte aus OIML R 22 Tabelle (stark vereinfacht, für Demo)
        # alc in %vol, density in g/cm³
        alc_tab = np.array([0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100])
        dens_tab = np.array([0.9982, 0.9920, 0.9837, 0.9742, 0.9636, 0.9518, 0.9389, 0.9248, 0.9096, 0.8932, 0.8757])
        return float(np.interp(alc, alc_tab, dens_tab))

    def correct_density_to_20C(self, density_at_temp, temp, alc_percent):
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
    def __init__(self, root):
        self.root = root
        self.measurement_db = MeasurementDB()  # Datenbank direkt nach root initialisieren
        self.root.title("Alex 501 Mazerat-Interpolation")
        self.root.configure(bg="#f4f4f7")

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background="#f4f4f7")
        style.configure("TLabel", background="#f4f4f7", font=("Helvetica", 12))
        style.configure("TButton", font=("Helvetica", 12, "bold"), padding=6)
        style.configure("Header.TLabel", font=("Helvetica", 16, "bold"), background="#e0e7ef")
        style.configure("Card.TLabelframe", background="#e0e7ef", borderwidth=2, relief="groove")
        style.configure("Card.TLabelframe.Label", font=("Helvetica", 13, "bold"), background="#e0e7ef")
        style.configure("Card.TLabelframe.Label", foreground="#2a3a5e")

        # Header
        header = ttk.Label(self.root, text="Alex 501 Mazerat-Interpolation", style="Header.TLabel", anchor="center")
        header.grid(row=0, column=0, sticky="ew", padx=0, pady=(0, 10))

        # Notebook mit Tabs
        notebook = ttk.Notebook(self.root)
        notebook.grid(row=1, column=0, sticky="nsew")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        # Tab 1: Hauptfunktion
        tab_main = ttk.Frame(notebook, style="TFrame")
        notebook.add(tab_main, text="Interpolation & Analyse")

        # Tab 2: Kalibrierkurvenerstellung
        tab_calib = ttk.Frame(notebook, style="TFrame")
        notebook.add(tab_calib, text="Kalibrierkurve")

        # Tab 3: Information & Berechnungslogik
        tab_info = ttk.Frame(notebook, style="TFrame")
        notebook.add(tab_info, text="Information & Berechnungslogik")
        # --- Info-Text ---
        info_text = (
            "Alex 501 Mazerat-Interpolations-App\n"
            "Version 1.0\n\n"
            "Diese Anwendung berechnet die tatsächlichen Messwerte (Alkoholgehalt, Dichte, Extraktgehalt) von alkoholischen Mazeraten aus verdünnten Proben.\n\n"
            "Hintergrund:\n"
            "Das Alex 501 Gerät kann nur bis max. 47 %vol. messen. Proben mit höherem Alkoholgehalt müssen verdünnt werden. Diese App rechnet die Messwerte der verdünnten Probe auf die tatsächlichen Werte der Originalprobe um.\n\n"
            "Verwendete Daten:\n"
            "- Ethanol-Wasser-Dichte-Tabellen nach OIML R 22 / DIN 12354\n"
            "- Berücksichtigung der Volumenkontraktion bei Ethanol-Wasser-Mischungen\n\n"
            "Wichtig:\n"
            "Die Berechnung berücksichtigt die nicht-linearen Beziehungen zwischen Alkoholgehalt, Dichte und Volumen. Für höchste Präzision wird eine Kalibrierung mit Ihrer spezifischen Probematrix empfohlen.\n\n"
            "Entwickelt: Januar 2026\n"
        )
        info_label = tk.Label(tab_info, text=info_text, font=("Helvetica", 12), justify="left", anchor="nw", bg="#f4f4f7")
        info_label.pack(fill="x", padx=24, pady=(24,8), anchor="nw")

        # --- Berechnungslogik ---
        berechnungslogik_text = (
            "Berechnungslogik:\n\n"
            "1. Verdünnungsfaktor:\n  Verdünnungsfaktor = (Probevolumen + Wasservolumen) / Probevolumen\n\n"
            "2. Tatsächlicher Alkoholgehalt der Originalprobe:\n  Alkohol_in_Verdünnung = (Gemessener Alkoholgehalt / 100) * (Probevolumen + Wasservolumen)\n  Tatsächlicher_Alkoholgehalt = (Alkohol_in_Verdünnung / Probevolumen) * 100\n  Falls >50 %vol: Korrektur = 1 + 0,001 * (Tatsächlicher_Alkoholgehalt - 50)\n  Optional: Kalibrierfunktion(Tatsächlicher_Alkoholgehalt)\n\n"
            "3. Tatsächliche Dichte:\n  Dichte_erwartet_verdünnt = Interpolation(Gemessener Alkoholgehalt)\n  Dichte_erwartet_original = Interpolation(Tatsächlicher_Alkoholgehalt)\n  Tatsächliche_Dichte = Dichte_erwartet_original + (Gemessene Dichte - Dichte_erwartet_verdünnt) * Verdünnungsfaktor\n\n"
            "4. Tatsächlicher Extraktgehalt:\n  Tatsächlicher_Extrakt = Gemessener Extrakt * Verdünnungsfaktor\n\n"
            "5. Kalibrierkurve:\n  Lineare Regression zwischen Messwerten und Referenzwerten, wird nur auf den berechneten Alkoholgehalt angewendet.\n\n"
            "6. Spindelvergleich:\n  Abweichung = Tatsächlicher_Alkoholgehalt - Spindelwert\n  Abweichung_% = (Abweichung / Spindelwert) * 100\n"
        )
        logik_label = tk.Label(tab_info, text=berechnungslogik_text, font=("Helvetica", 11), justify="left", anchor="nw", bg="#f4f4f7")
        logik_label.pack(fill="both", expand=True, padx=24, pady=(0,24), anchor="nw")

        # --- Hauptfunktion-Tab: bisherige GUI ---
        frm = ttk.Frame(tab_main, padding=18, style="TFrame")
        frm.grid(row=0, column=0, sticky="nsew")
        tab_main.columnconfigure(0, weight=1)
        tab_main.rowconfigure(0, weight=1)

        # Eingabefelder in einem Card-Frame
        input_frame = ttk.LabelFrame(frm, text="Eingabedaten", style="Card.TLabelframe", padding=(18, 12))
        input_frame.grid(row=0, column=0, sticky="nsew", padx=0, pady=(0, 16))
        frm.rowconfigure(0, weight=0)
        frm.columnconfigure(0, weight=1)

        # Probenbezeichnung
        ttk.Label(input_frame, text="Probenbezeichnung:").grid(row=0, column=0, sticky="w", pady=4, padx=(0,8))
        self.sample_name = tk.StringVar()
        ttk.Entry(input_frame, textvariable=self.sample_name, width=30, font=("Helvetica", 12)).grid(row=0, column=1, sticky="ew", pady=4)

        # Charge
        ttk.Label(input_frame, text="Charge:").grid(row=1, column=0, sticky="w", pady=4, padx=(0,8))
        self.batch_field = tk.StringVar()
        ttk.Entry(input_frame, textvariable=self.batch_field, width=20, font=("Helvetica", 12)).grid(row=1, column=1, sticky="ew", pady=4)

        # Raumtemperatur
        ttk.Label(input_frame, text="Raumtemperatur [°C]:").grid(row=2, column=0, sticky="w", pady=4, padx=(0,8))
        self.room_temp = tk.StringVar()
        ttk.Entry(input_frame, textvariable=self.room_temp, width=10, font=("Helvetica", 12)).grid(row=2, column=1, sticky="ew", pady=4)

        # Probevolumen
        ttk.Label(input_frame, text="Probevolumen [ml]:").grid(row=3, column=0, sticky="w", pady=4, padx=(0,8))
        self.probe_volume = tk.StringVar()
        ttk.Entry(input_frame, textvariable=self.probe_volume, width=10, font=("Helvetica", 12)).grid(row=3, column=1, sticky="ew", pady=4)

        # Wasserzugabe: Radiobuttons für Volumen/Gewicht
        ttk.Label(input_frame, text="Wasserzugabe:").grid(row=4, column=0, sticky="w", pady=4, padx=(0,8))
        self.water_value = tk.StringVar()
        ttk.Entry(input_frame, textvariable=self.water_value, width=10, font=("Helvetica", 12)).grid(row=4, column=1, sticky="ew", pady=4)
        self.water_mode = tk.StringVar(value="vol")
        water_frame = ttk.Frame(input_frame)
        water_frame.grid(row=4, column=2, sticky="w", padx=(8,0))
        ttk.Radiobutton(water_frame, text="Volumen [ml]", variable=self.water_mode, value="vol").pack(side="top", anchor="w", pady=2)
        ttk.Radiobutton(water_frame, text="Gewicht [g]", variable=self.water_mode, value="mass").pack(side="top", anchor="w", pady=2)

        # Messwerte
        ttk.Label(input_frame, text="Gemessener Alkohol [%vol]:").grid(row=5, column=0, sticky="w", pady=4, padx=(0,8))
        self.measured_alcohol = tk.StringVar()
        ttk.Entry(input_frame, textvariable=self.measured_alcohol, width=10, font=("Helvetica", 12)).grid(row=5, column=1, sticky="ew", pady=4)

        ttk.Label(input_frame, text="Gemessene Dichte [g/cm³]:").grid(row=6, column=0, sticky="w", pady=4, padx=(0,8))
        self.measured_density = tk.StringVar()
        ttk.Entry(input_frame, textvariable=self.measured_density, width=10, font=("Helvetica", 12)).grid(row=6, column=1, sticky="ew", pady=4)

        ttk.Label(input_frame, text="Gemessener Extrakt [g/100ml]:").grid(row=7, column=0, sticky="w", pady=4, padx=(0,8))
        self.measured_extract = tk.StringVar()
        ttk.Entry(input_frame, textvariable=self.measured_extract, width=10, font=("Helvetica", 12)).grid(row=7, column=1, sticky="ew", pady=4)

        ttk.Label(input_frame, text="Spindelwert Alkohol [%vol] (opt.):").grid(row=8, column=0, sticky="w", pady=4, padx=(0,8))
        self.spindle_alcohol = tk.StringVar()
        ttk.Entry(input_frame, textvariable=self.spindle_alcohol, width=10, font=("Helvetica", 12)).grid(row=8, column=1, sticky="ew", pady=4)

        ttk.Label(input_frame, text="Spindelwert Dichte [g/cm³] (opt.):").grid(row=9, column=0, sticky="w", pady=4, padx=(0,8))
        self.spindle_density = tk.StringVar()
        ttk.Entry(input_frame, textvariable=self.spindle_density, width=10, font=("Helvetica", 12)).grid(row=9, column=1, sticky="ew", pady=4)

        # Buttons und Checkbox für Kalibrierkurve
        btn_frame = ttk.Frame(frm, style="TFrame")
        btn_frame.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        btn_frame.columnconfigure(0, weight=1)
        ttk.Button(btn_frame, text="Berechnen", command=self.calculate_results, style="TButton").grid(row=0, column=0, padx=6, ipadx=8)
        ttk.Button(btn_frame, text="Exportieren", command=self.export_results, style="TButton").grid(row=0, column=1, padx=6, ipadx=8)
        ttk.Button(btn_frame, text="Drucken", command=self.print_results, style="TButton").grid(row=0, column=2, padx=6, ipadx=8)
        self.use_calib_curve = tk.BooleanVar(value=False)
        chk_calib = ttk.Checkbutton(btn_frame, text="Kalibrierkurve anwenden", variable=self.use_calib_curve)
        chk_calib.grid(row=0, column=3, padx=6, ipadx=8)

        # Button für Messhistorie im Haupt-Tab
        btn_history = ttk.Button(btn_frame, text="Messhistorie anzeigen", command=self.show_measurement_history)
        btn_history.grid(row=0, column=4, padx=6, ipadx=8)

        # Ergebnisfeld auf gesamte Fensterbreite, skalierbar
        result_frame = ttk.LabelFrame(frm, text="Ergebnisse", style="Card.TLabelframe", padding=(12, 8))
        result_frame.grid(row=2, column=0, sticky="nsew", padx=0, pady=(0, 0))
        frm.rowconfigure(2, weight=1)
        frm.columnconfigure(0, weight=1)

        self.result_text = tk.Text(result_frame, width=80, height=18, wrap="word", font=("Consolas", 12))
        self.result_text.pack(fill="both", expand=True)
        result_frame.rowconfigure(0, weight=1)
        result_frame.columnconfigure(0, weight=1)

        # --- Tab 2: Kalibrierkurve (Messwert-Eingabe, Plot) ---
        self.calib_data = []  # Liste für Kalibrierpunkte

        calib_input_frame = ttk.LabelFrame(tab_calib, text="Messwerte für Kalibrierkurve", padding=(18, 12))
        calib_input_frame.pack(fill="x", padx=20, pady=(20, 10))

        ttk.Label(calib_input_frame, text="Referenzwert:").grid(row=0, column=0, sticky="w", padx=(0,8), pady=4)
        self.calib_ref = tk.StringVar()
        ttk.Entry(calib_input_frame, textvariable=self.calib_ref, width=10).grid(row=0, column=1, sticky="ew", pady=4)

        ttk.Label(calib_input_frame, text="Messwert:").grid(row=0, column=2, sticky="w", padx=(16,8), pady=4)
        self.calib_meas = tk.StringVar()
        ttk.Entry(calib_input_frame, textvariable=self.calib_meas, width=10).grid(row=0, column=3, sticky="ew", pady=4)

        ttk.Button(calib_input_frame, text="Punkt hinzufügen", command=self.add_calib_point).grid(row=0, column=4, padx=(16,0), pady=4)

        # Tabelle für Kalibrierpunkte
        self.calib_tree = ttk.Treeview(tab_calib, columns=("ref", "meas"), show="headings", height=6)
        self.calib_tree.heading("ref", text="Referenzwert")
        self.calib_tree.heading("meas", text="Messwert")
        self.calib_tree.pack(fill="x", padx=20, pady=(0,10))

        # Plot-Bereich
        from matplotlib.figure import Figure
        self.calib_fig = Figure(figsize=(5,2.5), dpi=100)
        self.calib_ax = self.calib_fig.add_subplot(111)
        self.calib_canvas = FigureCanvasTkAgg(self.calib_fig, master=tab_calib)
        self.calib_canvas.get_tk_widget().pack(fill="both", expand=True, padx=20, pady=(0,20))

        # Button zum Löschen von Kalibrierpunkten
        btn_delete_calib = ttk.Button(tab_calib, text="Ausgewählten Punkt löschen", command=self.delete_selected_calib_point)
        btn_delete_calib.pack(pady=(0, 10))

        # Button zum Speichern der Kalibrierkurve
        btn_save_calib = ttk.Button(tab_calib, text="Kalibrierkurve speichern", command=self.save_calib_curve)
        btn_save_calib.pack(pady=(0, 10))

    def add_calib_point(self):
        try:
            ref = float(self.calib_ref.get().replace(',', '.'))
            meas = float(self.calib_meas.get().replace(',', '.'))
            self.calib_data.append((ref, meas))
            self.calib_tree.insert("", "end", values=(ref, meas))
            self.update_calib_plot()
            self.calib_ref.set("")
            self.calib_meas.set("")
        except ValueError:
            messagebox.showerror("Fehler", "Bitte gültige Zahlen eingeben!")

    def update_calib_plot(self):
        self.calib_ax.clear()
        # Skala der x- und y-Achse immer 0–50 %vol
        self.calib_ax.set_xlim(0, 50)
        self.calib_ax.set_ylim(0, 50)
        if len(self.calib_data) >= 2:
            sorted_data = sorted(self.calib_data, key=lambda x: x[0])
            refs, meas = zip(*sorted_data)
            self.calib_ax.plot(refs, meas, "o-", label="Messpunkte")
            # Trendlinie (lineare Regression)
            coeffs = np.polyfit(refs, meas, 1)
            trend_x = np.linspace(0, 50, 100)
            trend_y = np.polyval(coeffs, trend_x)
            self.calib_ax.plot(trend_x, trend_y, "r--", label="Trendlinie")
            self.calib_ax.set_xlabel("Referenzwert [%vol]")
            self.calib_ax.set_ylabel("Messwert [%vol]")
            self.calib_ax.set_title("Kalibrierkurve")
            self.calib_ax.legend()
        else:
            self.calib_ax.set_xlabel("Referenzwert [%vol]")
            self.calib_ax.set_ylabel("Messwert [%vol]")
            self.calib_ax.set_title("Kalibrierkurve")
        self.calib_canvas.draw()


        # ...entfernt: doppelte Felder außerhalb input_frame...
        # ...entfernt: Buttons mit .pack() und doppeltes Ergebnisfeld...

    def print_results(self):
        # Druckt die aktuellen Ergebnisse (Textbereich) über das Standarddrucksystem
        import tempfile
        import os
        import platform
        if not self.result_text.get('1.0', tk.END).strip():
            messagebox.showwarning("Warnung", "Keine Ergebnisse zum Drucken vorhanden!")
            return
        # Text temporär speichern
        with tempfile.NamedTemporaryFile(delete=False, suffix='.txt', mode='w', encoding='utf-8') as tmp:
            tmp.write(self.result_text.get('1.0', tk.END))
            tmp_path = tmp.name
        # Hier ggf. Druckfunktionalität einfügen

    def calculate_results(self):
        try:
            sample_name = self.sample_name.get().strip()
            batch = self.batch_field.get().strip()
            
            # Raumtemperatur ist Pflicht
            try:
                room_temp = float(self.room_temp.get().replace(',', '.'))
            except ValueError:
                messagebox.showerror("Fehler", "Raumtemperatur ist erforderlich!")
                return
            
            # Alle anderen Felder optional einlesen
            probe_vol_raw = None
            water_val = None
            measured_alc = None
            measured_alc_original = None
            measured_dens = None
            measured_ext = None
            
            try:
                if self.probe_volume.get().strip():
                    probe_vol_raw = float(self.probe_volume.get().replace(',', '.'))
            except ValueError:
                pass
            
            try:
                if self.water_value.get().strip():
                    water_val = float(self.water_value.get().replace(',', '.'))
            except ValueError:
                pass
            
            try:
                if self.measured_alcohol.get().strip():
                    measured_alc = float(self.measured_alcohol.get().replace(',', '.'))
                    measured_alc_original = measured_alc
            except ValueError:
                pass
            
            try:
                if self.measured_density.get().strip():
                    measured_dens = float(self.measured_density.get().replace(',', '.'))
            except ValueError:
                pass
            
            try:
                if self.measured_extract.get().strip():
                    measured_ext = float(self.measured_extract.get().replace(',', '.'))
            except ValueError:
                pass
            
            # Kalibrierkurve auf gemessenen Alkoholwert anwenden (falls vorhanden)
            if measured_alc is not None:
                use_curve = getattr(self, 'use_calib_curve', None)
                has_curve = hasattr(self, 'calib_data') and isinstance(self.calib_data, list) and len(self.calib_data) >= 2
                if use_curve and use_curve.get() and has_curve:
                    refs, meas = zip(*self.calib_data)
                    coeffs = np.polyfit(meas, refs, 1)
                    measured_alc = float(np.polyval(coeffs, measured_alc))

            # Temperaturkorrektur und Verdünnung nur wenn Werte vorhanden
            probe_vol = None
            water_vol = None
            
            if probe_vol_raw is not None:
                probe_vol = self.correct_volume_temp(probe_vol_raw, room_temp, is_water=False)
            
            if water_val is not None:
                if self.water_mode.get() == "vol":
                    water_vol = self.correct_volume_temp(water_val, room_temp, is_water=True)
                else:
                    # Gewicht -> Volumen
                    water_density = self.water_density_temp(room_temp)
                    if water_density > 0:
                        water_vol = self.correct_volume_temp(water_val / water_density, room_temp, is_water=True)

            # Optional: Gespindelter Alkoholwert
            spindle_alc = None
            spindle_text = self.spindle_alcohol.get().strip()
            if spindle_text:
                spindle_alc = float(spindle_text.replace(',', '.'))

            # Optional: Gespindelte Dichte (gemessen bei Raumtemperatur)
            spindle_dens_at_temp = None
            spindle_dens_20C = None
            spindle_dens_text = self.spindle_density.get().strip()
            if spindle_dens_text:
                try:
                    spindle_dens_at_temp = float(spindle_dens_text.replace(',', '.'))
                    # Korrigiere auf 20°C (Referenztemperatur)
                    # Verwende Spindelwert Alkohol (unverdünnt) für Korrekturkoeffizient
                    if spindle_alc is None:
                        messagebox.showwarning("Warnung", 
                            "Für die Temperaturkorrektur der Spindeldichte wird der Spindelwert Alkohol benötigt.\n"
                            "Bitte 'Gespindelter Alkohol' eingeben.")
                        return
                    spindle_dens_20C = self.correct_density_to_20C(spindle_dens_at_temp, room_temp, spindle_alc)
                except ValueError:
                    pass

            # Prüfe, ob mindestens eine sinnvolle Berechnung möglich ist
            can_calculate_dilution = (probe_vol is not None and water_vol is not None and 
                                     (measured_alc is not None or measured_dens is not None or measured_ext is not None))
            can_show_spindle_density = (spindle_dens_at_temp is not None)
            
            if not can_calculate_dilution and not can_show_spindle_density:
                messagebox.showwarning("Warnung", 
                    "Bitte mindestens folgende Werte eingeben:\n"
                    "- Für Verdünnungsberechnung: Probevolumen, Wasservolumen und mindestens einen Messwert\n"
                    "- Oder: Gespindelte Dichte für Temperaturkorrektur")
                return
            
            # Berechnung nur wenn Verdünnung möglich
            actual_alcohol_percent = None
            actual_density = None
            actual_extract = None
            dilution_factor = None
            expected_density_original = None
            
            if can_calculate_dilution:
                # Berechnung des Verdünnungsfaktors
                # probe_vol und water_vol sind hier garantiert nicht None
                assert probe_vol is not None and water_vol is not None
                total_diluted_volume = probe_vol + water_vol
                dilution_factor = total_diluted_volume / probe_vol
                
                # Alkoholgehalt berechnen (falls vorhanden)
                if measured_alc is not None:
                    alcohol_volume_in_dilution = (measured_alc / 100) * total_diluted_volume
                    actual_alcohol_percent = (alcohol_volume_in_dilution / probe_vol) * 100
                    
                    # Korrektur für Volumenkontraktion
                    if actual_alcohol_percent > 50:
                        contraction_correction = 1 + (0.001 * (actual_alcohol_percent - 50))
                        actual_alcohol_percent *= contraction_correction
                
                # Dichte berechnen (falls Alkohol und Dichte vorhanden)
                if measured_alc is not None and measured_dens is not None and actual_alcohol_percent is not None:
                    expected_density_diluted = self.interpolate_density_from_alcohol(measured_alc)
                    expected_density_original = self.interpolate_density_from_alcohol(actual_alcohol_percent)
                    density_difference = measured_dens - expected_density_diluted
                    actual_density = expected_density_original + density_difference * dilution_factor
                
                # Extrakt berechnen (falls vorhanden)
                if measured_ext is not None:
                    actual_extract = measured_ext * dilution_factor

            # Ergebnisse anzeigen
            self.result_text.delete('1.0', tk.END)

            # Vergleich mit Spindelung vorbereiten
            spindle_comparison = ""
            spindle_warning = ""

            if spindle_alc is not None and actual_alcohol_percent is not None:
                deviation = actual_alcohol_percent - spindle_alc
                deviation_percent = (deviation / spindle_alc) * 100 if spindle_alc > 0 else 0

                # Format mit Vorzeichen für Abweichung
                dev_str = format_de(abs(deviation), 2)
                if deviation > 0:
                    dev_str = '+' + dev_str
                else:
                    dev_str = '-' + dev_str

                dev_pct_str = format_de(abs(deviation_percent), 1)
                if deviation_percent > 0:
                    dev_pct_str = '+' + dev_pct_str
                else:
                    dev_pct_str = '-' + dev_pct_str

                spindle_comparison = f"""
{'='*60}

VERGLEICH MIT SPINDELUNG (Aräometer) - Alkohol:

  Gespindelter Wert:        {format_de(spindle_alc, 2)} %vol.
  Alex 501 (berechnet):     {format_de(actual_alcohol_percent, 2)} %vol.

  Abweichung:               {dev_str} %vol. ({dev_pct_str}%)
"""

            # Vergleich mit gespindelter Dichte vorbereiten
            density_comparison = ""
            if spindle_dens_at_temp is not None and spindle_dens_20C is not None:
                # Vergleich nur wenn auch berechnete Dichte vorhanden
                if expected_density_original is not None:
                    dens_deviation = spindle_dens_20C - expected_density_original
                    dens_deviation_percent = (dens_deviation / expected_density_original) * 100 if expected_density_original > 0 else 0

                    dens_dev_str = format_de(abs(dens_deviation), 5)
                    if dens_deviation > 0:
                        dens_dev_str = '+' + dens_dev_str
                    else:
                        dens_dev_str = '-' + dens_dev_str

                    dens_dev_pct_str = format_de(abs(dens_deviation_percent), 2)
                    if dens_deviation_percent > 0:
                        dens_dev_pct_str = '+' + dens_dev_pct_str
                    else:
                        dens_dev_pct_str = '-' + dens_dev_pct_str

                    density_comparison = f"""
{'='*60}

VERGLEICH MIT SPINDELUNG (Aräometer) - Dichte:

  Gespindelter Wert ({format_de(room_temp, 1)}°C): {format_de(spindle_dens_at_temp, 5)} g/cm³
  Korrigiert auf 20°C:            {format_de(spindle_dens_20C, 5)} g/cm³
  Alex 501 (berechnet, 20°C):     {format_de(expected_density_original, 5)} g/cm³

  Abweichung:                     {dens_dev_str} g/cm³ ({dens_dev_pct_str}%)
"""
                else:
                    # Nur Temperaturkorrektur anzeigen
                    density_comparison = f"""
{'='*60}

TEMPERATURKORREKTUR SPINDELDICHTE:

  Gespindelter Wert ({format_de(room_temp, 1)}°C): {format_de(spindle_dens_at_temp, 5)} g/cm³
  Korrigiert auf 20°C:            {format_de(spindle_dens_20C, 5)} g/cm³
"""

            # Info, ob Kalibrierkurve angewendet wurde
            use_curve = getattr(self, 'use_calib_curve', None)
            has_curve = hasattr(self, 'calib_data') and isinstance(self.calib_data, list) and len(self.calib_data) >= 2
            if use_curve and use_curve.get() and has_curve:
                calib_info = "Kalibrierkurve: angewendet\n"
            else:
                calib_info = "Kalibrierkurve: nicht angewendet\n"

            results = f"""
ALEX 501 Mazeratinterpolation
Messung einer verdünnten Probe und Umrechnung auf Endwerte
{'='*60}

BERECHNUNGSERGEBNISSE
{'='*60}
{calib_info if can_calculate_dilution else ''}
Probenbezeichnung: {sample_name if sample_name else '-'}
Charge: {batch if batch else '-'}
"""
            
            # Eingabewerte nur wenn Verdünnung berechnet wurde
            if can_calculate_dilution and probe_vol is not None and water_vol is not None and dilution_factor is not None:
                results += f"""
Eingabewerte:
  Verdünnung: {format_de(probe_vol, 1)} ml Probe + {format_de(water_vol, 1)} ml Wasser
  Verdünnungsfaktor: 1:{format_de(dilution_factor, 2)}
"""
                if measured_alc_original is not None:
                    results += f"\n  Gemessener Alkoholgehalt: {format_de(measured_alc_original, 2)} %vol."
                if measured_dens is not None:
                    results += f"\n  Gemessene Dichte: {format_de(measured_dens, 5)} g/cm³"
                if measured_ext is not None:
                    results += f"\n  Gemessener Extrakt: {format_de(measured_ext, 2)} g/100ml"
                
                results += f"\n\n{'='*60}\n\nBerechnete tatsächliche Werte der Originalprobe:\n"
                
                if actual_alcohol_percent is not None:
                    results += f"\n  Alkoholgehalt: {format_de(actual_alcohol_percent, 2)} %vol."
                if actual_density is not None:
                    results += f"\n  Dichte: {format_de(actual_density, 5)} g/cm³"
                if actual_extract is not None:
                    results += f"\n  Extraktgehalt: {format_de(actual_extract, 2)} g/100ml"
            
            results += f"{spindle_comparison}{density_comparison}{spindle_warning if can_calculate_dilution else ''}\n{'='*60}\n"
            
            if can_calculate_dilution:
                results += f"""\nHinweise:
- Die Berechnung berücksichtigt Volumenkontraktion
- Dichte-Werte basieren auf OIML R 22 Standardtabellen
- Für höchste Präzision wird eine Kalibrierung empfohlen
{f'- Spindelung (Aräometer) ist die Referenzmethode für Zollamt' if spindle_alc else ''}
"""
            
            results += f"\nZeitstempel: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n"
            self.result_text.insert('1.0', results)

            # Ergebnisse für Export speichern
            self.last_results = {
                'timestamp': datetime.now().isoformat(),
                'sample_name': sample_name,
                'batch': batch,
                'input': {
                    'probe_volume': probe_vol,
                    'water_volume': water_vol,
                    'measured_alcohol': measured_alc_original,
                    'measured_density': measured_dens,
                    'measured_extract': measured_ext,
                    'dilution_factor': dilution_factor,
                    'spindle_alcohol': spindle_alc,
                    'spindle_density_at_temp': spindle_dens_at_temp,
                    'spindle_density_20C': spindle_dens_20C,
                    'calibration_applied': use_curve.get() if use_curve else False
                },
                'output': {
                    'actual_alcohol': actual_alcohol_percent,
                    'actual_density': actual_density,
                    'actual_extract': actual_extract
                }
            }

            # Messung automatisch in die Datenbank speichern
            try:
                self.measurement_db.insert_measurement(self.last_results)
            except Exception as e:
                print(f"Fehler beim Speichern der Messung in die Datenbank: {e}")

            # Vergleichsdaten hinzufügen
            if spindle_alc is not None or spindle_dens_at_temp is not None:
                self.last_results['comparison'] = {}
                if spindle_alc is not None and actual_alcohol_percent is not None:
                    self.last_results['comparison']['alcohol'] = {
                        'spindle_value': spindle_alc,
                        'alex501_value': actual_alcohol_percent,
                        'deviation': actual_alcohol_percent - spindle_alc,
                        'deviation_percent': ((actual_alcohol_percent - spindle_alc) / spindle_alc * 100) if spindle_alc > 0 else 0
                    }
                if spindle_dens_at_temp is not None and spindle_dens_20C is not None:
                    comparison_density = {
                        'spindle_value_at_temp': spindle_dens_at_temp,
                        'spindle_value_20C': spindle_dens_20C
                    }
                    if expected_density_original is not None:
                        comparison_density.update({
                            'alex501_value_20C': expected_density_original,
                            'deviation': spindle_dens_20C - expected_density_original,
                            'deviation_percent': ((spindle_dens_20C - expected_density_original) / expected_density_original * 100) if expected_density_original > 0 else 0
                        })
                    self.last_results['comparison']['density'] = comparison_density
        except ValueError:
            messagebox.showerror("Fehler", "Bitte geben Sie gültige numerische Werte ein!")
        except Exception as e:
            messagebox.showerror("Fehler", f"Fehler bei der Berechnung: {str(e)}")
    
    def export_results(self):
        if not hasattr(self, 'last_results'):
            messagebox.showwarning("Warnung", "Keine Ergebnisse zum Exportieren vorhanden!")
            return

        filename = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON Dateien", "*.json"), ("Text Dateien", "*.txt"), ("Alle Dateien", "*.*")],
            initialfile=f"Alex501_Ergebnis_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )

        if filename:
            try:
                if filename.endswith('.json'):
                    with open(filename, 'w', encoding='utf-8') as f:
                        json.dump(self.last_results, f, indent=2, ensure_ascii=False)
                else:
                    # Überschrift für Text-Export ergänzen
                    header = "ALEX 501 Mazeratinterpolation\nMessung einer verdünnten Probe und Umrechnung auf Endwerte\n" + ("="*60) + "\n\n"
                    with open(filename, 'w', encoding='utf-8') as f:
                        f.write(header)
                        f.write(self.result_text.get('1.0', tk.END))

                messagebox.showinfo("Erfolg", f"Ergebnisse wurden gespeichert:\n{filename}")
            except Exception as e:
                messagebox.showerror("Fehler", f"Fehler beim Speichern: {str(e)}")


    def save_calib_curve(self):
        """Speichert die aktuelle Kalibrierkurve als JSON-Datei."""
        if not hasattr(self, 'calib_data') or len(self.calib_data) < 2:
            messagebox.showwarning("Warnung", "Mindestens zwei Kalibrierpunkte erforderlich!")
            return
        filename = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON Dateien", "*.json"), ("Alle Dateien", "*.*")],
            initialfile=f"Kalibrierkurve_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(self.calib_data, f, indent=2, ensure_ascii=False)
                messagebox.showinfo("Erfolg", f"Kalibrierkurve gespeichert: {filename}")
            except Exception as e:
                messagebox.showerror("Fehler", f"Fehler beim Speichern: {str(e)}")


    def load_calib_curve(self, filename="kalibrierkurve.json"):
        """Lädt die Kalibrierkurve aus einer JSON-Datei, falls vorhanden."""
        import os
        if os.path.exists(filename):
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                if isinstance(data, list) and all(isinstance(pair, list) or isinstance(pair, tuple) for pair in data):
                    self.calib_data = [tuple(pair) for pair in data]
                    self.calib_tree.delete(*self.calib_tree.get_children())
                    for ref, meas in self.calib_data:
                        self.calib_tree.insert("", "end", values=(ref, meas))
                    self.update_calib_plot()
            except Exception as e:
                messagebox.showerror("Fehler", f"Kalibrierkurve konnte nicht geladen werden: {str(e)}")

    def autosave_calib_curve(self):
        """Speichert die aktuelle Kalibrierkurve automatisch als JSON-Datei."""
        if hasattr(self, 'calib_data') and len(self.calib_data) >= 2:
            try:
                with open("kalibrierkurve.json", 'w', encoding='utf-8') as f:
                    json.dump(self.calib_data, f, indent=2, ensure_ascii=False)
            except Exception:
                pass
        elif hasattr(self, 'calib_data') and len(self.calib_data) == 0:
            # Wenn alle Punkte gelöscht wurden, Datei entfernen
            import os
            if os.path.exists("kalibrierkurve.json"):
                try:
                    os.remove("kalibrierkurve.json")
                except Exception:
                    pass


    def delete_selected_calib_point(self):
        """Löscht den ausgewählten Kalibrierpunkt."""
        selected = self.calib_tree.selection()
        if not selected:
            messagebox.showwarning("Warnung", "Bitte einen Kalibrierpunkt auswählen!")
            return
        for item in selected:
            values = self.calib_tree.item(item, "values")
            try:
                self.calib_data.remove((float(values[0]), float(values[1])))
            except Exception:
                pass
            self.calib_tree.delete(item)
        self.update_calib_plot()
        self.autosave_calib_curve()


    def show_measurement_history(self):
        hist_win = tk.Toplevel(self.root)
        hist_win.title("Messhistorie")
        hist_win.geometry("1200x500")
        columns = ("id", "timestamp", "sample_name", "batch", "measured_alcohol", "measured_density", "measured_extract", "spindle_alcohol", "dilution_factor", "actual_alcohol", "actual_density", "actual_extract")
        tree = ttk.Treeview(hist_win, columns=columns, show="headings")
        tree.heading("id", text="ID")
        tree.heading("timestamp", text="Zeitstempel")
        tree.heading("sample_name", text="Probe")
        tree.heading("batch", text="Charge")
        tree.heading("measured_alcohol", text="Messwert %vol.")
        tree.heading("measured_density", text="Messwert Dichte")
        tree.heading("measured_extract", text="Messwert Extrakt")
        tree.heading("spindle_alcohol", text="Spindelwert")
        tree.heading("dilution_factor", text="Verdünnungsfaktor")
        tree.heading("actual_alcohol", text="berechnet %vol.")
        tree.heading("actual_density", text="berechnet Dichte")
        tree.heading("actual_extract", text="berechnet Extrakt")
        tree.column("id", width=40)
        tree.column("timestamp", width=160)
        tree.column("sample_name", width=120)
        tree.column("batch", width=80)
        tree.column("measured_alcohol", width=100)
        tree.column("measured_density", width=100)
        tree.column("measured_extract", width=100)
        tree.column("spindle_alcohol", width=100)
        tree.column("dilution_factor", width=100)
        tree.column("actual_alcohol", width=120)
        tree.column("actual_density", width=120)
        tree.column("actual_extract", width=120)
        tree.pack(fill="both", expand=True)
        # Daten aus DB laden
        import sqlite3
        with sqlite3.connect(self.measurement_db.db_path) as conn:
            c = conn.cursor()
            c.execute("SELECT id, timestamp, sample_name, batch, measured_alcohol, measured_density, measured_extract, spindle_alcohol, dilution_factor, actual_alcohol, actual_density, actual_extract FROM messungen ORDER BY id DESC")
            for row in c.fetchall():
                # Formatierung
                row = list(row)
                if row[4] is not None:
                    row[4] = f"{row[4]:.2f}"
                if row[5] is not None:
                    row[5] = f"{row[5]:.4f}"
                if row[6] is not None:
                    row[6] = f"{row[6]:.2f}"
                if row[7] is not None:
                    row[7] = f"{row[7]:.2f}"
                if row[8] is not None:
                    row[8] = f"{row[8]:.2f}"
                if row[9] is not None:
                    row[9] = f"{row[9]:.2f}"
                if row[10] is not None:
                    row[10] = f"{row[10]:.4f}"
                if row[11] is not None:
                    row[11] = f"{row[11]:.2f}"
                tree.insert("", "end", values=row)
        # Button zum Schließen
        btn_close = ttk.Button(hist_win, text="Schließen", command=hist_win.destroy)
        btn_close.pack(pady=8)


class MeasurementDB:
    def __init__(self, db_path="messungen.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('''
                CREATE TABLE IF NOT EXISTS messungen (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    sample_name TEXT,
                    batch TEXT,
                    probe_volume REAL,
                    water_volume REAL,
                    measured_alcohol REAL,
                    measured_density REAL,
                    measured_extract REAL,
                    dilution_factor REAL,
                    spindle_alcohol REAL,
                    actual_alcohol REAL,
                    actual_density REAL,
                    actual_extract REAL
                )
            ''')
            conn.commit()

    def insert_measurement(self, data):
        with sqlite3.connect(self.db_path) as conn:
            c = conn.cursor()
            c.execute('''
                INSERT INTO messungen (
                    timestamp, sample_name, batch, probe_volume, water_volume, measured_alcohol, measured_density, measured_extract, dilution_factor, spindle_alcohol, actual_alcohol, actual_density, actual_extract
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                data['timestamp'],
                data['sample_name'],
                data['batch'],
                data['input']['probe_volume'],
                data['input']['water_volume'],
                data['input']['measured_alcohol'],
                data['input']['measured_density'],
                data['input']['measured_extract'],
                data['input']['dilution_factor'],
                data['input']['spindle_alcohol'],
                data['output']['actual_alcohol'],
                data['output']['actual_density'],
                data['output']['actual_extract']
            ))
            conn.commit()

def main():
    root = tk.Tk()
    app = Alex501App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
