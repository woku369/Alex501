"""
Alex 501 Mazerat-Interpolations-App – Oberfläche (tkinter).

Berechnet tatsächliche Alkoholstärke, Dichte und Extraktgehalt aus verdünnten Messwerten.
Die Rechnung liegt in calculations.py und measurement.py (ohne GUI, mit Tests), die Messhistorie in db.py;
dieses Modul stellt nur die Eingabe, die Ergebnisse und den Verlauf dar.
"""

import csv
import json
import os
import platform
import tempfile
import tkinter as tk
from datetime import datetime
from tkinter import ttk, messagebox, filedialog, font as tkfont

import numpy as np
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

import calculations as calc
import measurement as meas
from calculations import format_de
from db import MeasurementDB
from infotext import INFO_SECTIONS

# Farbpalette (Kräuter-Grün mit warmen Akzenten)
C = {
    "bg": "#f1f4ef", "card": "#ffffff", "border": "#d3dcd0", "field_border": "#b9c5b6",
    "primary": "#2e6b3f", "primary_dark": "#245532", "primary_soft": "#e5efe5",
    "text": "#1e2b20", "muted": "#677668", "stripe": "#f7f9f6",
    "alcohol": "#2e6b3f", "density": "#2a6a88", "extract": "#9a6a1f",
    "error_bg": "#fde9e9", "error_fg": "#a02424",
    "warn_bg": "#fff3dc", "warn_fg": "#80550a",
    "info_bg": "#e7f0fa", "info_fg": "#1d5a96",
}

MESSAGE_COLORS = {
    meas.LEVEL_ERROR: (C["error_bg"], C["error_fg"], "Fehler"),
    meas.LEVEL_WARNING: (C["warn_bg"], C["warn_fg"], "Achtung"),
    meas.LEVEL_INFO: (C["info_bg"], C["info_fg"], "Hinweis"),
}


def _pick_font(root, candidates, fallback):
    available = set(tkfont.families(root))
    for name in candidates:
        if name in available:
            return name
    return fallback


class ResultTile(tk.Frame):
    """Kachel mit einer großen Kennzahl (Alkohol, Dichte oder Extrakt)."""

    def __init__(self, parent, title, unit, color, fonts):
        super().__init__(parent, bg=C["card"], highlightbackground=C["border"], highlightcolor=C["border"],
                         highlightthickness=1)
        self.unit_text = unit
        tk.Frame(self, bg=color, height=4).pack(fill="x")
        tk.Label(self, text=title.upper(), bg=C["card"], fg=C["muted"], font=fonts["small_bold"]).pack(
            anchor="w", padx=14, pady=(10, 0))
        self.value = tk.Label(self, text="–", bg=C["card"], fg=color, font=fonts["big"])
        self.value.pack(anchor="w", padx=14)
        self.unit = tk.Label(self, text=unit, bg=C["card"], fg=C["muted"], font=fonts["base"])
        self.unit.pack(anchor="w", padx=14)
        self.caption = tk.Label(self, text="", bg=C["card"], fg=C["muted"], font=fonts["small"],
                                justify="left", anchor="w", wraplength=190)
        self.caption.pack(anchor="w", padx=14, pady=(2, 10), fill="x")
        self.bind("<Configure>", lambda event: self.caption.config(wraplength=max(event.width - 30, 80)))

    def set(self, value_text, caption=""):
        self.value.config(text=value_text)
        self.caption.config(text=caption)


class Alex501App:
    def __init__(self, root):
        self.root = root
        self.measurement_db = MeasurementDB()
        self.root.title("Alex 501 Mazerat-Interpolation")
        self.root.configure(bg=C["bg"])
        self.root.minsize(1280, 780)

        self._setup_fonts()
        self._setup_style()

        self.last_results = None
        self.last_report = ""
        self._last_saved_key = None
        self._last_saved_id = None
        self._entries = []
        self._history_rows = {}
        self.calib_data = []  # Liste der Kalibrierpunkte (Referenzwert, Messwert)

        self._build_header()
        self.notebook = ttk.Notebook(self.root)
        self.notebook.grid(row=1, column=0, sticky="nsew")
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=1)

        tab_main = ttk.Frame(self.notebook)
        tab_history = ttk.Frame(self.notebook)
        tab_calib = ttk.Frame(self.notebook)
        tab_info = ttk.Frame(self.notebook)
        self.notebook.add(tab_main, text="Messung")
        self.notebook.add(tab_history, text="Messhistorie")
        self.notebook.add(tab_calib, text="Kalibrierkurve")
        self.notebook.add(tab_info, text="Information & Berechnungslogik")

        self._build_measure_tab(tab_main)
        self._build_history_tab(tab_history)
        self._build_calib_tab(tab_calib)
        self._build_info_tab(tab_info)

        self.status_var = tk.StringVar(value="Bereit.")
        self.status_label = tk.Label(self.root, textvariable=self.status_var, anchor="w", bg=C["primary_soft"],
                                     fg=C["primary_dark"], font=self.f_small, padx=16, pady=5)
        self.status_label.grid(row=2, column=0, sticky="ew")

        self.load_calib_curve()
        self.refresh_history()
        self._on_mode_change()
        self._entries[0].focus_set()

    # ------------------------------------------------------------------ Grundgerüst

    def _setup_fonts(self):
        family = _pick_font(self.root, ["Segoe UI", "Helvetica Neue", "Helvetica", "DejaVu Sans"], "TkDefaultFont")
        mono = _pick_font(self.root, ["Consolas", "DejaVu Sans Mono", "Courier New"], "TkFixedFont")
        self.f_base = (family, 10)
        self.f_small = (family, 9)
        self.f_small_bold = (family, 9, "bold")
        self.f_bold = (family, 10, "bold")
        self.f_head = (family, 11, "bold")
        self.f_title = (family, 18, "bold")
        self.f_big = (family, 24, "bold")
        self.f_mono = (mono, 10)
        self.tile_fonts = {"base": self.f_base, "small": self.f_small, "small_bold": self.f_small_bold,
                           "big": self.f_big}

    def _setup_style(self):
        s = ttk.Style()
        s.theme_use("clam")
        s.configure(".", background=C["bg"], foreground=C["text"], font=self.f_base)
        s.configure("TFrame", background=C["bg"])
        s.configure("TLabel", background=C["bg"], foreground=C["text"])
        s.configure("Card.TLabel", background=C["card"])
        s.configure("Muted.TLabel", background=C["card"], foreground=C["muted"], font=self.f_small)
        s.configure("TEntry", fieldbackground="white", bordercolor=C["field_border"], lightcolor=C["field_border"],
                    darkcolor=C["field_border"], padding=(6, 4))
        s.map("TEntry", bordercolor=[("focus", C["primary"])], lightcolor=[("focus", C["primary"])],
              darkcolor=[("focus", C["primary"])], fieldbackground=[("disabled", "#edf0eb")],
              foreground=[("disabled", C["muted"])])
        s.configure("Primary.TButton", background=C["primary"], foreground="white", font=self.f_bold,
                    padding=(22, 9), borderwidth=0, focusthickness=0)
        s.map("Primary.TButton", background=[("active", C["primary_dark"]), ("disabled", "#9db5a1")],
              foreground=[("disabled", "#eef3ee")])
        s.configure("Secondary.TButton", background="white", foreground=C["primary"], bordercolor=C["field_border"],
                    padding=(14, 8), font=self.f_bold, focusthickness=0)
        s.map("Secondary.TButton", background=[("active", C["primary_soft"]), ("disabled", "#f1f4ef")],
              foreground=[("disabled", C["muted"])])
        s.configure("Card.TRadiobutton", background=C["card"], font=self.f_base)
        s.map("Card.TRadiobutton", background=[("active", C["card"])])
        s.configure("Card.TCheckbutton", background=C["card"], font=self.f_base)
        s.map("Card.TCheckbutton", background=[("active", C["card"])])
        s.configure("Bar.TCheckbutton", background=C["bg"], font=self.f_base)
        s.map("Bar.TCheckbutton", background=[("active", C["bg"])])
        s.configure("TNotebook", background=C["bg"], borderwidth=0, tabmargins=(16, 8, 0, 0))
        s.configure("TNotebook.Tab", padding=(18, 9), font=self.f_bold, background="#dce5d9",
                    foreground=C["muted"], borderwidth=0)
        s.map("TNotebook.Tab", background=[("selected", C["bg"])], foreground=[("selected", C["primary"])])
        s.configure("Treeview", rowheight=27, background="white", fieldbackground="white",
                    bordercolor=C["border"], font=self.f_base)
        s.configure("Treeview.Heading", background=C["primary_soft"], foreground=C["primary_dark"],
                    font=self.f_bold, padding=(6, 7), relief="flat")
        s.map("Treeview", background=[("selected", C["primary"])], foreground=[("selected", "white")])
        s.map("Treeview.Heading", background=[("active", "#d5e5d6")])

    def _build_header(self):
        band = tk.Frame(self.root, bg=C["primary"])
        band.grid(row=0, column=0, sticky="ew")
        tk.Label(band, text="Alex 501 Mazerat-Interpolation", bg=C["primary"], fg="white",
                 font=self.f_title).pack(anchor="w", padx=20, pady=(12, 0))
        tk.Label(band, text="Kräuter-Meister  ·  Rückrechnung verdünnter Proben auf die Originalprobe",
                 bg=C["primary"], fg="#cfe3d2", font=self.f_small).pack(anchor="w", padx=20, pady=(0, 12))

    def _card(self, parent, title, accent=None):
        outer = tk.Frame(parent, bg=C["card"], highlightbackground=C["border"], highlightcolor=C["border"],
                         highlightthickness=1)
        head = tk.Frame(outer, bg=C["card"])
        head.pack(fill="x", padx=14, pady=(10, 4))
        tk.Frame(head, bg=accent or C["primary"], width=4, height=16).pack(side="left", padx=(0, 8))
        tk.Label(head, text=title, bg=C["card"], fg=C["text"], font=self.f_head).pack(side="left")
        body = tk.Frame(outer, bg=C["card"])
        body.pack(fill="both", expand=True, padx=14, pady=(0, 12))
        return outer, body

    def _field(self, body, row, label, var, unit="", width=11):
        ttk.Label(body, text=label, style="Card.TLabel").grid(row=row, column=0, sticky="w", pady=3, padx=(0, 10))
        entry = ttk.Entry(body, textvariable=var, width=width, font=self.f_base)
        entry.grid(row=row, column=1, sticky="ew", pady=3)
        if unit:
            ttk.Label(body, text=unit, style="Muted.TLabel").grid(row=row, column=2, sticky="w", padx=(6, 0))
        entry.bind("<Return>", lambda _event: self.calculate_results())
        self._entries.append(entry)
        return entry

    def set_status(self, text, level=None):
        colors = {None: (C["primary_soft"], C["primary_dark"]), meas.LEVEL_ERROR: (C["error_bg"], C["error_fg"]),
                  meas.LEVEL_WARNING: (C["warn_bg"], C["warn_fg"])}
        bg, fg = colors.get(level, colors[None])
        self.status_label.config(bg=bg, fg=fg)
        self.status_var.set(text)

    # ------------------------------------------------------------------ Tab Messung

    def _build_measure_tab(self, tab):
        tab.columnconfigure(2, weight=1)
        tab.rowconfigure(0, weight=1)
        left = ttk.Frame(tab)
        left.grid(row=0, column=0, sticky="ns", padx=(16, 8), pady=(8, 12))
        mid = ttk.Frame(tab)
        mid.grid(row=0, column=1, sticky="ns", padx=8, pady=(8, 12))
        right = ttk.Frame(tab)
        right.grid(row=0, column=2, sticky="nsew", padx=(8, 16), pady=(8, 12))

        self.sample_name = tk.StringVar()
        self.batch_field = tk.StringVar()
        self.mode = tk.StringVar(value=meas.MODE_DILUTED)
        self.room_temp = tk.StringVar()
        self.probe_volume = tk.StringVar()
        self.water_value = tk.StringVar()
        self.water_mode = tk.StringVar(value=meas.WATER_BY_MASS)
        self.measured_alcohol = tk.StringVar()
        self.measured_density = tk.StringVar()
        self.measured_extract = tk.StringVar()
        self.spindle_alcohol = tk.StringVar()
        self.spindle_density = tk.StringVar()
        self.lab_alcohol = tk.StringVar()
        self.lab_density = tk.StringVar()
        self.lab_extract = tk.StringVar()
        self.lab_note = tk.StringVar()
        self.use_calib_curve = tk.BooleanVar(value=False)

        # Spalte 1: Probe und Ansatz
        card, body = self._card(left, "Probe")
        card.pack(fill="x")
        body.columnconfigure(1, weight=1)
        self._field(body, 0, "Bezeichnung", self.sample_name, width=22)
        self._field(body, 1, "Charge", self.batch_field, width=22)

        card, body = self._card(left, "Ansatz")
        card.pack(fill="x", pady=(10, 0))
        body.columnconfigure(1, weight=1)
        ttk.Radiobutton(body, text="Verdünnt gemessen", variable=self.mode, value=meas.MODE_DILUTED,
                        style="Card.TRadiobutton", command=self._on_mode_change).grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 1))
        ttk.Radiobutton(body, text="Direkt gemessen (ohne Verdünnung)", variable=self.mode, value=meas.MODE_DIRECT,
                        style="Card.TRadiobutton", command=self._on_mode_change).grid(
            row=1, column=0, columnspan=3, sticky="w", pady=(0, 6))
        self._field(body, 2, "Raumtemperatur", self.room_temp, "°C")
        self.probe_entry = self._field(body, 3, "Probevolumen", self.probe_volume, "ml")
        self.water_entry = self._field(body, 4, "Wasserzugabe", self.water_value)
        unit_frame = tk.Frame(body, bg=C["card"])
        unit_frame.grid(row=4, column=2, sticky="w", padx=(6, 0))
        self.water_radios = [
            ttk.Radiobutton(unit_frame, text="g", variable=self.water_mode, value=meas.WATER_BY_MASS,
                            style="Card.TRadiobutton"),
            ttk.Radiobutton(unit_frame, text="ml", variable=self.water_mode, value=meas.WATER_BY_VOLUME,
                            style="Card.TRadiobutton"),
        ]
        for radio in self.water_radios:
            radio.pack(side="left", padx=(0, 6))
        self.planner_button = ttk.Button(body, text="Verdünnungsplaner …", style="Secondary.TButton",
                                         command=self.open_planner)
        self.planner_button.grid(row=5, column=0, columnspan=3, sticky="ew", pady=(10, 0))
        self.ansatz_hint = ttk.Label(body, text="", style="Muted.TLabel", wraplength=300, justify="left")
        self.ansatz_hint.grid(row=6, column=0, columnspan=3, sticky="w", pady=(8, 0))

        # Spalte 2: Messwerte und Referenzen
        card, body = self._card(mid, "Alex 501 – gemessene Werte", accent=C["alcohol"])
        card.pack(fill="x")
        body.columnconfigure(1, weight=1)
        self._field(body, 0, "Alkohol", self.measured_alcohol, "%vol")
        self._field(body, 1, "Dichte", self.measured_density, "g/cm³")
        self._field(body, 2, "Extrakt", self.measured_extract, "g/100ml")

        card, body = self._card(mid, "Spindelung (optional)", accent=C["density"])
        card.pack(fill="x", pady=(10, 0))
        body.columnconfigure(1, weight=1)
        self._field(body, 0, "Alkohol", self.spindle_alcohol, "%vol")
        self._field(body, 1, "Dichte", self.spindle_density, "g/cm³")

        card, body = self._card(mid, "Laboranalyse (optional)", accent=C["extract"])
        card.pack(fill="x", pady=(10, 0))
        body.columnconfigure(1, weight=1)
        self._field(body, 0, "Alkohol", self.lab_alcohol, "%vol")
        self._field(body, 1, "Dichte", self.lab_density, "g/cm³")
        self._field(body, 2, "Extrakt", self.lab_extract, "g/100ml")
        self._field(body, 3, "Bemerkung", self.lab_note, width=16)

        # Aktionsleiste unter den Eingaben
        bar = ttk.Frame(tab)
        bar.grid(row=1, column=0, columnspan=2, sticky="ew", padx=(16, 8), pady=(0, 14))
        ttk.Button(bar, text="Berechnen", style="Primary.TButton", command=self.calculate_results).pack(side="left")
        ttk.Button(bar, text="Neue Messung", style="Secondary.TButton", command=self.clear_inputs).pack(
            side="left", padx=(10, 0))
        ttk.Checkbutton(bar, text="Kalibrierkurve anwenden", variable=self.use_calib_curve,
                        style="Bar.TCheckbutton").pack(side="left", padx=(18, 0))

        # Spalte 3: Ergebnisse
        tiles = ttk.Frame(right)
        tiles.pack(fill="x")
        for column in range(3):
            tiles.columnconfigure(column, weight=1, uniform="tiles")
        self.tile_alcohol = ResultTile(tiles, "Alkohol", "%vol", C["alcohol"], self.tile_fonts)
        self.tile_density = ResultTile(tiles, "Dichte", "g/cm³ bei 20 °C", C["density"], self.tile_fonts)
        self.tile_extract = ResultTile(tiles, "Extrakt", "g/100 ml", C["extract"], self.tile_fonts)
        for column, tile in enumerate((self.tile_alcohol, self.tile_density, self.tile_extract)):
            tile.grid(row=0, column=column, sticky="nsew", padx=(0 if column == 0 else 8, 0))

        self.summary_label = ttk.Label(right, text="Noch keine Berechnung.", foreground=C["muted"], justify="left")
        self.summary_label.pack(anchor="w", pady=(10, 4))
        right.bind("<Configure>", lambda event: self.summary_label.config(wraplength=max(event.width - 8, 200)))

        self.message_frame = tk.Frame(right, bg=C["bg"])
        self.message_frame.pack(fill="x")
        self.message_frame.bind("<Configure>", self._on_message_resize)
        self.compare_frame = tk.Frame(right, bg=C["bg"])
        self.compare_frame.pack(fill="x")

        card, body = self._card(right, "Protokoll")
        card.pack(fill="both", expand=True, pady=(8, 0))
        text_frame = tk.Frame(body, bg=C["card"])
        text_frame.pack(fill="both", expand=True)
        self.result_text = tk.Text(text_frame, wrap="word", font=self.f_mono, height=8, relief="flat",
                                   bg=C["stripe"], fg=C["text"], padx=10, pady=8, state="disabled",
                                   highlightthickness=1, highlightbackground=C["border"])
        scroll = ttk.Scrollbar(text_frame, command=self.result_text.yview)
        self.result_text.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.result_text.pack(side="left", fill="both", expand=True)

        buttons = tk.Frame(body, bg=C["card"])
        buttons.pack(fill="x", pady=(8, 0))
        ttk.Button(buttons, text="Exportieren", style="Secondary.TButton", command=self.export_results).pack(side="left")
        ttk.Button(buttons, text="Drucken", style="Secondary.TButton", command=self.print_results).pack(
            side="left", padx=(8, 0))

    def _on_mode_change(self):
        direct = self.mode.get() == meas.MODE_DIRECT
        state = "disabled" if direct else "normal"
        self.probe_entry.config(state=state)
        self.water_entry.config(state=state)
        for radio in self.water_radios:
            radio.config(state=state)
        self.planner_button.config(state=state)
        if direct:
            self.ansatz_hint.config(text="Proben im Messbereich des Alex 501 (bis 47 %vol), z. B. Fertigprodukte: "
                                         "die gemessenen Werte werden unverändert übernommen.")
        else:
            self.ansatz_hint.config(text="Verdünnung auf etwa 40 %vol; für eine Messung mindestens 40 ml verdünnte "
                                         "Probe. Eingeben, was tatsächlich eingewogen wurde.")

    def _on_message_resize(self, event):
        for child in self.message_frame.winfo_children():
            child.config(wraplength=max(event.width - 40, 200))

    def clear_inputs(self):
        """Leert die Felder für die nächste Messung; Modus, Raumtemperatur und Wassereinheit bleiben."""
        for var in (self.sample_name, self.batch_field, self.probe_volume, self.water_value, self.measured_alcohol,
                    self.measured_density, self.measured_extract, self.spindle_alcohol, self.spindle_density,
                    self.lab_alcohol, self.lab_density, self.lab_extract, self.lab_note):
            var.set("")
        self._clear_results()
        self._clear_messages()
        self.set_status("Bereit für die nächste Messung.")
        self._entries[0].focus_set()

    def _place_dialog(self, win):
        """Positioniert einen Dialog oben mittig über dem Hauptfenster."""
        self.root.update_idletasks()
        x = self.root.winfo_rootx() + max((self.root.winfo_width() - 460) // 2, 20)
        y = self.root.winfo_rooty() + 120
        win.geometry(f"+{x}+{y}")

    # ------------------------------------------------------------------ Verdünnungsplaner

    def open_planner(self):
        win = tk.Toplevel(self.root)
        win.title("Verdünnungsplaner")
        win.configure(bg=C["bg"])
        win.transient(self.root)
        win.resizable(False, False)
        self._place_dialog(win)

        probe_alc = tk.StringVar(value="50")
        target_alc = tk.StringVar(value="40")
        total_volume = tk.StringVar(value="45")

        card, body = self._card(win, "Zielwerte")
        card.pack(fill="x", padx=16, pady=(16, 8))
        body.columnconfigure(1, weight=1)
        rows = (("Alkohol der Probe (geschätzt)", probe_alc, "%vol"),
                ("Ziel-Alkohol der Verdünnung", target_alc, "%vol"),
                ("Volumen der verdünnten Probe", total_volume, "ml"))
        entries = []
        for index, (label, var, unit) in enumerate(rows):
            ttk.Label(body, text=label, style="Card.TLabel").grid(row=index, column=0, sticky="w", pady=3, padx=(0, 10))
            entry = ttk.Entry(body, textvariable=var, width=9, font=self.f_base)
            entry.grid(row=index, column=1, sticky="ew", pady=3)
            ttk.Label(body, text=unit, style="Muted.TLabel").grid(row=index, column=2, sticky="w", padx=(6, 0))
            entries.append(entry)
        quick = tk.Frame(body, bg=C["card"])
        quick.grid(row=3, column=0, columnspan=3, sticky="w", pady=(8, 0))

        card, result_body = self._card(win, "Ansatz", accent=C["extract"])
        card.pack(fill="x", padx=16, pady=(0, 8))
        probe_line = tk.Label(result_body, text="", bg=C["card"], fg=C["text"], font=self.f_head, anchor="w")
        water_line = tk.Label(result_body, text="", bg=C["card"], fg=C["text"], font=self.f_head, anchor="w")
        detail_line = tk.Label(result_body, text="", bg=C["card"], fg=C["muted"], font=self.f_small, anchor="w",
                               justify="left", wraplength=360)
        for label in (probe_line, water_line, detail_line):
            label.pack(fill="x", pady=2)
        tk.Label(win, text="Richtwert zum Ansetzen (Messkolben für die Probe, Wasser wiegen). Im Hauptfenster die "
                           "tatsächlich abgemessenen und eingewogenen Werte eingeben.",
                 bg=C["bg"], fg=C["muted"], font=self.f_small, wraplength=392, justify="left").pack(
            padx=16, pady=(0, 8), anchor="w")

        def update(_event=None):
            try:
                plan = calc.plan_dilution(meas.parse_decimal(probe_alc.get()), meas.parse_decimal(total_volume.get()),
                                          meas.parse_decimal(target_alc.get()))
            except (TypeError, ValueError) as error:
                message = str(error) if isinstance(error, ValueError) and "float" not in str(error) else \
                    "Bitte gültige Zahlen eingeben."
                probe_line.config(text="–")
                water_line.config(text="")
                detail_line.config(text=message)
                return
            probe_line.config(text=f"Probe:  {format_de(plan['probe_volume'], 1)} ml")
            water_line.config(text=f"Wasser: {format_de(plan['water_mass'], 1)} g")
            detail = (f"Summe der Volumina {format_de(plan['summed_volume'], 1)} ml, reales Volumen nach der "
                      f"Kontraktion {format_de(meas.parse_decimal(total_volume.get()), 1)} ml.")
            if meas.parse_decimal(total_volume.get()) < meas.MIN_MEASURING_VOLUME:
                detail += f" Achtung: für eine Messung werden mindestens {format_de(meas.MIN_MEASURING_VOLUME, 0)} ml benötigt."
            detail_line.config(text=detail)

        def preset(alcohol):
            probe_alc.set(str(alcohol))
            update()

        ttk.Button(quick, text="Mazerat 50", style="Secondary.TButton", command=lambda: preset(50)).pack(side="left")
        ttk.Button(quick, text="Destillat 78", style="Secondary.TButton", command=lambda: preset(78)).pack(
            side="left", padx=(8, 0))
        for entry in entries:
            entry.bind("<KeyRelease>", update)
        ttk.Button(win, text="Schließen", style="Secondary.TButton", command=win.destroy).pack(pady=(0, 16))
        update()
        entries[0].focus_set()

    # ------------------------------------------------------------------ Berechnung und Ergebnisse

    def _collect_raw(self):
        return {
            "mode": self.mode.get(), "sample_name": self.sample_name.get(), "batch": self.batch_field.get(),
            "room_temp": self.room_temp.get(), "probe_volume": self.probe_volume.get(),
            "water_value": self.water_value.get(), "water_mode": self.water_mode.get(),
            "measured_alcohol": self.measured_alcohol.get(), "measured_density": self.measured_density.get(),
            "measured_extract": self.measured_extract.get(), "spindle_alcohol": self.spindle_alcohol.get(),
            "spindle_density": self.spindle_density.get(), "lab_alcohol": self.lab_alcohol.get(),
            "lab_density": self.lab_density.get(), "lab_extract": self.lab_extract.get(),
            "lab_note": self.lab_note.get(),
        }

    def calculate_results(self):
        try:
            result = meas.evaluate_measurement(self._collect_raw(), calib_data=self.calib_data,
                                               use_calibration=self.use_calib_curve.get())
        except Exception as error:  # unerwartete Fehler nicht lautlos verschlucken
            messagebox.showerror("Fehler", f"Fehler bei der Berechnung: {error}")
            return
        self._show_messages(result["messages"])
        if not result["ok"]:
            self._clear_results()
            self.last_results = None
            self.set_status("Berechnung nicht möglich – siehe Meldung.", meas.LEVEL_ERROR)
            return
        self._show_result(result)
        self._save_result(result)

    def _clear_results(self):
        for tile in (self.tile_alcohol, self.tile_density, self.tile_extract):
            tile.set("–")
        self.summary_label.config(text="Noch keine Berechnung.", foreground=C["muted"])
        for child in self.compare_frame.winfo_children():
            child.destroy()
        self._set_report("")
        self.last_results = None
        self.last_report = ""

    def _clear_messages(self):
        for child in self.message_frame.winfo_children():
            child.destroy()

    def _show_messages(self, messages):
        self._clear_messages()
        for level, text in messages:
            bg, fg, title = MESSAGE_COLORS[level]
            label = tk.Label(self.message_frame, text=f"{title}: {text}", bg=bg, fg=fg, font=self.f_base,
                             justify="left", anchor="w", padx=12, pady=7,
                             wraplength=max(self.message_frame.winfo_width() - 40, 420))
            label.pack(fill="x", pady=(0, 4))

    def _set_report(self, text):
        self.result_text.config(state="normal")
        self.result_text.delete("1.0", tk.END)
        self.result_text.insert("1.0", text)
        self.result_text.config(state="disabled")

    def _show_result(self, result):
        inp, out = result["input"], result["output"]
        diluted = result["mode"] == meas.MODE_DILUTED
        calibrated = " (kalibriert)" if inp["calibration_applied"] else ""

        def tile(widget, value, decimals, caption):
            widget.set("–" if value is None else format_de(value, decimals), caption if value is not None else "")

        origin = "Originalprobe" if diluted else "direkt gemessen"
        tile(self.tile_alcohol, out["actual_alcohol"], 2,
             (f"gemessen {format_de(inp['measured_alcohol'], 2)} %vol in der Verdünnung" if diluted
              else "direkt gemessen") + calibrated if inp["measured_alcohol"] is not None else "")
        tile(self.tile_density, out["actual_density"], 5,
             f"{origin}; gemessen {format_de(inp['measured_density'], 5)}" if inp["measured_density"] is not None else "")
        tile(self.tile_extract, out["actual_extract"], 2,
             f"{origin}; gemessen {format_de(inp['measured_extract'], 2)}" if inp["measured_extract"] is not None else "")

        if result["has_calculation"] and diluted:
            unit = "g" if inp["water_mode"] == meas.WATER_BY_MASS else "ml"
            text = (f"Ansatz: {format_de(inp['probe_volume_input'], 1)} ml Probe + "
                    f"{format_de(inp['water_input'], 1)} {unit} Wasser  ·  Verdünnungsfaktor "
                    f"1:{format_de(inp['dilution_factor'], 2)}")
            if inp["measured_alcohol"] is not None:
                text += f"  ·  wirksam 1:{format_de(out['effective_dilution_factor'], 2)} (mit Volumenkontraktion)"
            self.summary_label.config(text=text, foreground=C["text"])
        elif result["has_calculation"]:
            self.summary_label.config(text="Direkte Messung ohne Verdünnung – Werte unverändert übernommen.",
                                      foreground=C["text"])
        else:
            self.summary_label.config(text="Nur Temperaturkorrektur der Spindeldichte.", foreground=C["text"])

        self._show_comparisons(result)
        self.last_report = meas.format_report(result)
        self.last_results = result
        self._set_report(self.last_report)

    def _show_comparisons(self, result):
        for child in self.compare_frame.winfo_children():
            child.destroy()
        comparison = result["comparison"]
        lines = []
        if "alcohol" in comparison:
            c = comparison["alcohol"]
            lines.append(("Spindel Alkohol", f"{format_de(c['spindle_value'], 2)} %vol",
                          f"Abweichung {meas._signed(c['deviation'], 2)} %vol ({meas._signed(c['deviation_percent'], 1)} %)"))
        if "density" in comparison and "deviation" in comparison["density"]:
            c = comparison["density"]
            lines.append(("Spindel Dichte (20 °C)", f"{format_de(c['spindle_value_20C'], 5)} g/cm³",
                          f"Abweichung {meas._signed(c['deviation'], 5)} g/cm³ ({meas._signed(c['deviation_percent'], 2)} %)"))
        names = {"alcohol": ("Labor Alkohol", "%vol", 2), "density": ("Labor Dichte", "g/cm³", 5),
                 "extract": ("Labor Extrakt", "g/100ml", 2)}
        for key, (label, unit, decimals) in names.items():
            c = comparison.get("lab", {}).get(key)
            if c:
                lines.append((label, f"{format_de(c['lab_value'], decimals)} {unit}",
                              f"Abweichung {meas._signed(c['deviation'], decimals)} {unit} ({meas._signed(c['deviation_percent'], 1)} %)"))
        if not lines:
            return
        card, body = self._card(self.compare_frame, "Vergleich mit Referenzwerten", accent=C["density"])
        card.pack(fill="x", pady=(4, 0))
        for index, (label, value, deviation) in enumerate(lines):
            ttk.Label(body, text=label, style="Card.TLabel").grid(row=index, column=0, sticky="w", padx=(0, 16), pady=2)
            ttk.Label(body, text=value, style="Card.TLabel").grid(row=index, column=1, sticky="w", padx=(0, 16), pady=2)
            tk.Label(body, text=deviation, bg=C["card"], fg=C["primary_dark"], font=self.f_bold).grid(
                row=index, column=2, sticky="w", pady=2)

    def _save_result(self, result):
        """Speichert die Messung in der Messhistorie; unveränderte Wiederholungen werden nicht doppelt abgelegt."""
        key = json.dumps({"input": result["input"], "output": result["output"], "mode": result["mode"],
                          "sample": result["sample_name"], "batch": result["batch"]}, sort_keys=True, default=str)
        if key == self._last_saved_key:
            self.set_status(f"Berechnet. Unveränderte Messung, bereits in der Messhistorie (Nr. {self._last_saved_id}).")
            return
        try:
            new_id = self.measurement_db.insert_measurement(result)
        except Exception as error:
            self.set_status(f"Berechnet, aber nicht gespeichert: {error}", meas.LEVEL_ERROR)
            return
        self._last_saved_key, self._last_saved_id = key, new_id
        self.set_status(f"Berechnet und in der Messhistorie gespeichert (Nr. {new_id}).")
        self.refresh_history()

    # ------------------------------------------------------------------ Export und Druck

    def print_results(self):
        """Druckt den Bericht über das Standarddrucksystem (nur Windows)."""
        if not self.last_report.strip():
            messagebox.showwarning("Warnung", "Keine Ergebnisse zum Drucken vorhanden!")
            return
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt", mode="w", encoding="utf-8") as tmp:
            tmp.write(self.last_report)
            tmp_path = tmp.name
        try:
            if platform.system() == "Windows":
                os.startfile(tmp_path, "print")
            else:
                messagebox.showwarning("Warnung", "Direktes Drucken wird auf diesem Betriebssystem nicht unterstützt.\n"
                                                  f"Die Ergebnisse wurden hier gespeichert:\n{tmp_path}")
        except OSError as error:
            messagebox.showerror("Fehler", f"Drucken fehlgeschlagen: {error}\nDatei: {tmp_path}")

    def export_results(self):
        if not self.last_results:
            messagebox.showwarning("Warnung", "Keine Ergebnisse zum Exportieren vorhanden!")
            return
        filename = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON Dateien", "*.json"), ("Text Dateien", "*.txt"), ("Alle Dateien", "*.*")],
            initialfile=f"Alex501_Ergebnis_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        if not filename:
            return
        try:
            with open(filename, "w", encoding="utf-8") as handle:
                if filename.endswith(".json"):
                    json.dump(self.last_results, handle, indent=2, ensure_ascii=False, default=str)
                else:
                    handle.write(self.last_report)
            messagebox.showinfo("Erfolg", f"Ergebnisse wurden gespeichert:\n{filename}")
        except Exception as error:
            messagebox.showerror("Fehler", f"Fehler beim Speichern: {error}")

    # ------------------------------------------------------------------ Tab Messhistorie

    def _build_history_tab(self, tab):
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(1, weight=3)
        tab.rowconfigure(2, weight=2)

        toolbar = ttk.Frame(tab)
        toolbar.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 8))
        ttk.Label(toolbar, text="Suchen:").pack(side="left")
        self.history_filter = tk.StringVar()
        search = ttk.Entry(toolbar, textvariable=self.history_filter, width=26, font=self.f_base)
        search.pack(side="left", padx=(8, 12))
        self.history_filter.trace_add("write", lambda *_args: self.refresh_history())
        ttk.Button(toolbar, text="Laborwerte zur Auswahl …", style="Secondary.TButton",
                   command=self.edit_lab_reference).pack(side="left")
        ttk.Button(toolbar, text="Als CSV exportieren …", style="Secondary.TButton",
                   command=self.export_history_csv).pack(side="left", padx=(8, 0))
        self.history_count = ttk.Label(toolbar, text="", foreground=C["muted"])
        self.history_count.pack(side="right")

        table_frame = tk.Frame(tab, bg=C["card"], highlightbackground=C["border"], highlightthickness=1)
        table_frame.grid(row=1, column=0, sticky="nsew", padx=16)
        columns = [key for key, _title, _width in meas.HISTORY_COLUMNS]
        self.history_tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")
        for key, title, width in meas.HISTORY_COLUMNS:
            self.history_tree.heading(key, text=title)
            numeric = key in ("actual_alcohol", "actual_density", "actual_extract", "spindle", "spindle_dev", "lab",
                              "lab_dev")
            self.history_tree.column(key, width=width, anchor="e" if numeric else "w", stretch=key == "sample_name")
        scroll = ttk.Scrollbar(table_frame, command=self.history_tree.yview)
        self.history_tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.history_tree.pack(side="left", fill="both", expand=True)
        self.history_tree.tag_configure("stripe", background=C["stripe"])
        self.history_tree.bind("<<TreeviewSelect>>", self._on_history_select)

        card, body = self._card(tab, "Details zur ausgewählten Messung")
        card.grid(row=2, column=0, sticky="nsew", padx=16, pady=(10, 14))
        self.history_detail = body
        self._set_detail_text([("head", "Bitte eine Messung in der Tabelle auswählen.")])

    def refresh_history(self):
        if not hasattr(self, "history_tree"):
            return
        selected = self.history_tree.selection()
        needle = self.history_filter.get().strip().lower()
        rows = self.measurement_db.fetch_all()
        self._history_rows = {str(row["id"]): row for row in rows}
        self.history_tree.delete(*self.history_tree.get_children())
        shown = 0
        for row in rows:
            haystack = f"{row.get('sample_name') or ''} {row.get('batch') or ''}".lower()
            if needle and needle not in haystack:
                continue
            tags = ("stripe",) if shown % 2 else ()
            self.history_tree.insert("", "end", iid=str(row["id"]), values=meas.history_table_values(row), tags=tags)
            shown += 1
        self.history_count.config(text=f"{shown} von {len(rows)} Messungen")
        if selected and self.history_tree.exists(selected[0]):
            self.history_tree.selection_set(selected[0])

    def _set_detail_text(self, lines):
        """Zeigt die Detailzeilen einer Messung abschnittsweise nebeneinander an."""
        for child in self.history_detail.winfo_children():
            child.destroy()
        sections = []
        for line in lines:
            if line[0] == "head":
                sections.append((line[1], []))
            else:
                sections[-1][1].append((line[1], line[2]))
        for column, (title, items) in enumerate(sections):
            self.history_detail.columnconfigure(column, weight=1)
            block = tk.Frame(self.history_detail, bg=C["card"])
            block.grid(row=0, column=column, sticky="nw", padx=(0, 14))
            tk.Label(block, text=title, bg=C["card"], fg=C["primary"], font=self.f_head).grid(
                row=0, column=0, columnspan=2, sticky="w", pady=(0, 3))
            for index, (label, value) in enumerate(items, start=1):
                tk.Label(block, text=label, bg=C["card"], fg=C["muted"], font=self.f_small, anchor="w").grid(
                    row=index, column=0, sticky="w", padx=(0, 8))
                tk.Label(block, text=value, bg=C["card"], fg=C["text"], font=self.f_base, anchor="w").grid(
                    row=index, column=1, sticky="w")

    def _on_history_select(self, _event=None):
        selection = self.history_tree.selection()
        if selection and selection[0] in self._history_rows:
            self._set_detail_text(meas.history_detail_lines(self._history_rows[selection[0]]))

    def edit_lab_reference(self):
        selection = self.history_tree.selection()
        if not selection:
            messagebox.showinfo("Laborwerte", "Bitte zuerst eine Messung in der Tabelle auswählen.")
            return
        row = self._history_rows[selection[0]]
        win = tk.Toplevel(self.root)
        win.title(f"Laborwerte zu Messung Nr. {row['id']}")
        win.configure(bg=C["bg"])
        win.transient(self.root)
        win.resizable(False, False)
        self._place_dialog(win)
        card, body = self._card(win, f"{row.get('sample_name') or 'Messung'} – {meas._fmt_time(row.get('timestamp'))}",
                                accent=C["extract"])
        card.pack(fill="x", padx=16, pady=16)
        body.columnconfigure(1, weight=1)
        variables = {}
        fields = (("lab_alcohol", "Alkohol", "%vol", 2), ("lab_density", "Dichte", "g/cm³", 5),
                  ("lab_extract", "Extrakt", "g/100ml", 2))
        for index, (key, label, unit, decimals) in enumerate(fields):
            variables[key] = tk.StringVar(value="" if row.get(key) is None else format_de(row[key], decimals))
            ttk.Label(body, text=label, style="Card.TLabel").grid(row=index, column=0, sticky="w", pady=3, padx=(0, 10))
            ttk.Entry(body, textvariable=variables[key], width=12, font=self.f_base).grid(row=index, column=1, sticky="ew")
            ttk.Label(body, text=unit, style="Muted.TLabel").grid(row=index, column=2, sticky="w", padx=(6, 0))
        note = tk.StringVar(value=row.get("lab_note") or "")
        ttk.Label(body, text="Bemerkung", style="Card.TLabel").grid(row=3, column=0, sticky="w", pady=3, padx=(0, 10))
        ttk.Entry(body, textvariable=note, width=28, font=self.f_base).grid(row=3, column=1, columnspan=2, sticky="ew")

        def save():
            try:
                values = {key: meas.parse_decimal(var.get()) for key, var in variables.items()}
            except ValueError:
                messagebox.showerror("Fehler", "Bitte gültige Zahlen eingeben!", parent=win)
                return
            self.measurement_db.update_lab_reference(row["id"], values["lab_alcohol"], values["lab_density"],
                                                     values["lab_extract"], note.get().strip())
            win.destroy()
            self.refresh_history()
            self._on_history_select()
            self.set_status(f"Laborwerte zu Messung Nr. {row['id']} gespeichert.")

        buttons = tk.Frame(win, bg=C["bg"])
        buttons.pack(pady=(0, 16))
        ttk.Button(buttons, text="Speichern", style="Primary.TButton", command=save).pack(side="left")
        ttk.Button(buttons, text="Abbrechen", style="Secondary.TButton", command=win.destroy).pack(
            side="left", padx=(8, 0))

    def export_history_csv(self):
        table = meas.history_csv_table(self.measurement_db.fetch_all())
        if not table:
            messagebox.showinfo("Export", "Die Messhistorie ist noch leer.")
            return
        filename = filedialog.asksaveasfilename(
            defaultextension=".csv", filetypes=[("CSV Dateien", "*.csv"), ("Alle Dateien", "*.*")],
            initialfile=f"Alex501_Messhistorie_{datetime.now().strftime('%Y%m%d')}")
        if not filename:
            return
        try:
            # Semikolon und UTF-8 mit BOM, damit Excel (deutsche Einstellung) Umlaute und Zahlen richtig liest
            with open(filename, "w", encoding="utf-8-sig", newline="") as handle:
                csv.writer(handle, delimiter=";").writerows(table)
            self.set_status(f"Messhistorie exportiert: {filename}")
        except OSError as error:
            messagebox.showerror("Fehler", f"Export fehlgeschlagen: {error}")

    # ------------------------------------------------------------------ Tab Kalibrierkurve

    def _build_calib_tab(self, tab):
        card, body = self._card(tab, "Messwerte für die Kalibrierkurve", accent=C["density"])
        card.pack(fill="x", padx=16, pady=(14, 8))
        self.calib_ref = tk.StringVar()
        self.calib_meas = tk.StringVar()
        ttk.Label(body, text="Referenzwert [%vol]", style="Card.TLabel").grid(row=0, column=0, sticky="w", padx=(0, 8))
        ref_entry = ttk.Entry(body, textvariable=self.calib_ref, width=10, font=self.f_base)
        ref_entry.grid(row=0, column=1, padx=(0, 18))
        ttk.Label(body, text="Messwert [%vol]", style="Card.TLabel").grid(row=0, column=2, sticky="w", padx=(0, 8))
        meas_entry = ttk.Entry(body, textvariable=self.calib_meas, width=10, font=self.f_base)
        meas_entry.grid(row=0, column=3, padx=(0, 18))
        for entry in (ref_entry, meas_entry):
            entry.bind("<Return>", lambda _event: self.add_calib_point())
        ttk.Button(body, text="Punkt hinzufügen", style="Primary.TButton", command=self.add_calib_point).grid(
            row=0, column=4)

        content = ttk.Frame(tab)
        content.pack(fill="both", expand=True, padx=16, pady=(0, 14))
        content.columnconfigure(1, weight=1)
        content.rowconfigure(0, weight=1)

        left = ttk.Frame(content)
        left.grid(row=0, column=0, sticky="ns", padx=(0, 12))
        self.calib_tree = ttk.Treeview(left, columns=("ref", "meas"), show="headings", height=10)
        self.calib_tree.heading("ref", text="Referenzwert")
        self.calib_tree.heading("meas", text="Messwert")
        self.calib_tree.column("ref", width=135, anchor="e")
        self.calib_tree.column("meas", width=110, anchor="e")
        self.calib_tree.pack(fill="y", expand=True)
        ttk.Button(left, text="Ausgewählten Punkt löschen", style="Secondary.TButton",
                   command=self.delete_selected_calib_point).pack(fill="x", pady=(10, 0))
        ttk.Button(left, text="Kalibrierkurve speichern …", style="Secondary.TButton",
                   command=self.save_calib_curve).pack(fill="x", pady=(8, 0))

        plot_card = tk.Frame(content, bg=C["card"], highlightbackground=C["border"], highlightthickness=1)
        plot_card.grid(row=0, column=1, sticky="nsew")
        self.calib_fig = Figure(figsize=(5, 3), dpi=100, facecolor=C["card"])
        self.calib_ax = self.calib_fig.add_subplot(111)
        self.calib_canvas = FigureCanvasTkAgg(self.calib_fig, master=plot_card)
        self.calib_canvas.get_tk_widget().pack(fill="both", expand=True, padx=6, pady=6)
        self.update_calib_plot()

    def add_calib_point(self):
        try:
            ref = float(self.calib_ref.get().replace(",", "."))
            measured = float(self.calib_meas.get().replace(",", "."))
        except ValueError:
            messagebox.showerror("Fehler", "Bitte gültige Zahlen eingeben!")
            return
        self.calib_data.append((ref, measured))
        self.calib_tree.insert("", "end", values=(format_de(ref, 2), format_de(measured, 2)))
        self.update_calib_plot()
        self.autosave_calib_curve()
        self.calib_ref.set("")
        self.calib_meas.set("")

    def update_calib_plot(self):
        ax = self.calib_ax
        ax.clear()
        ax.set_facecolor("white")
        ax.set_xlim(0, 50)
        ax.set_ylim(0, 50)
        ax.set_xlabel("Referenzwert [%vol]", color=C["text"])
        ax.set_ylabel("Messwert [%vol]", color=C["text"])
        ax.set_title("Kalibrierkurve", color=C["primary_dark"], fontweight="bold")
        ax.grid(True, color="#e3e9e0", linewidth=0.8)
        ax.tick_params(colors=C["muted"])
        for spine in ax.spines.values():
            spine.set_color(C["border"])
        if self.calib_data:
            sorted_data = sorted(self.calib_data, key=lambda point: point[0])
            refs, measured = zip(*sorted_data)
            ax.plot(refs, measured, "o", color=C["primary"], markersize=7, label="Messpunkte")
            if len(self.calib_data) >= 2:
                coeffs = np.polyfit(refs, measured, 1)
                trend_x = np.linspace(0, 50, 100)
                ax.plot(trend_x, np.polyval(coeffs, trend_x), "--", color=C["extract"], linewidth=2,
                        label="Trendlinie")
            ax.legend(frameon=False)
        self.calib_fig.tight_layout()
        self.calib_canvas.draw()

    def save_calib_curve(self):
        """Speichert die aktuelle Kalibrierkurve als JSON-Datei."""
        if len(self.calib_data) < 2:
            messagebox.showwarning("Warnung", "Mindestens zwei Kalibrierpunkte erforderlich!")
            return
        filename = filedialog.asksaveasfilename(
            defaultextension=".json", filetypes=[("JSON Dateien", "*.json"), ("Alle Dateien", "*.*")],
            initialfile=f"Kalibrierkurve_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
        if filename:
            try:
                with open(filename, "w", encoding="utf-8") as handle:
                    json.dump(self.calib_data, handle, indent=2, ensure_ascii=False)
                messagebox.showinfo("Erfolg", f"Kalibrierkurve gespeichert: {filename}")
            except Exception as error:
                messagebox.showerror("Fehler", f"Fehler beim Speichern: {error}")

    def load_calib_curve(self, filename="kalibrierkurve.json"):
        """Lädt die Kalibrierkurve aus einer JSON-Datei, falls vorhanden."""
        if not os.path.exists(filename):
            return
        try:
            with open(filename, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            if isinstance(data, list) and all(isinstance(pair, (list, tuple)) for pair in data):
                self.calib_data = [tuple(pair) for pair in data]
                self.calib_tree.delete(*self.calib_tree.get_children())
                for ref, measured in self.calib_data:
                    self.calib_tree.insert("", "end", values=(format_de(ref, 2), format_de(measured, 2)))
                self.update_calib_plot()
        except Exception as error:
            messagebox.showerror("Fehler", f"Kalibrierkurve konnte nicht geladen werden: {error}")

    def autosave_calib_curve(self):
        """Speichert die aktuelle Kalibrierkurve automatisch als JSON-Datei."""
        if len(self.calib_data) >= 2:
            try:
                with open("kalibrierkurve.json", "w", encoding="utf-8") as handle:
                    json.dump(self.calib_data, handle, indent=2, ensure_ascii=False)
            except Exception:
                pass
        elif len(self.calib_data) == 0 and os.path.exists("kalibrierkurve.json"):
            # Wenn alle Punkte gelöscht wurden, Datei entfernen
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
            index = self.calib_tree.index(item)
            if 0 <= index < len(self.calib_data):
                # Reihenfolge der Tabelle entspricht der Reihenfolge in calib_data
                del self.calib_data[index]
            self.calib_tree.delete(item)
        self.update_calib_plot()
        self.autosave_calib_curve()

    # ------------------------------------------------------------------ Tab Information

    def _build_info_tab(self, tab):
        tab.columnconfigure(0, weight=1)
        tab.rowconfigure(0, weight=1)
        frame = tk.Frame(tab, bg=C["card"], highlightbackground=C["border"], highlightthickness=1)
        frame.grid(row=0, column=0, sticky="nsew", padx=16, pady=14)
        text = tk.Text(frame, wrap="word", font=self.f_base, relief="flat", bg=C["card"], fg=C["text"],
                       padx=24, pady=16, spacing3=6)
        scroll = ttk.Scrollbar(frame, command=text.yview)
        text.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        text.pack(side="left", fill="both", expand=True)
        text.tag_configure("title", font=self.f_title, foreground=C["primary_dark"], spacing3=10)
        text.tag_configure("head", font=self.f_head, foreground=C["primary"], spacing1=14, spacing3=4)
        text.insert(tk.END, "Alex 501 Mazerat-Interpolations-App\n", "title")
        for heading, paragraphs in INFO_SECTIONS:
            text.insert(tk.END, heading + "\n", "head")
            for paragraph in paragraphs:
                text.insert(tk.END, paragraph + "\n")
        text.config(state="disabled")


def main():
    root = tk.Tk()
    root.geometry("1340x880")
    Alex501App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
