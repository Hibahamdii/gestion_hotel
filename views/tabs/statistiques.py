# -*- coding: utf-8 -*-

import tkinter as tk
from tkinter import ttk
from datetime import date, datetime, timedelta

import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from db.repository import recap_recettes, recap_depenses, taux_occupation
from models.enums import PERIODES
from views.widgets import DateEntry, date_str_to_iso
from services.statistiques import formater_periode, calculer_kpis


class StatsTab(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        filtre_frame = ttk.Frame(self)
        filtre_frame.pack(fill="x", padx=8, pady=8)

        ttk.Label(filtre_frame, text="Du :").pack(side="left")
        self.date_debut = DateEntry(filtre_frame, width=12)
        self.date_debut.pack(side="left", padx=4)
        debut_defaut = date.today() - timedelta(days=365)
        self.date_debut.set_date(debut_defaut)

        ttk.Label(filtre_frame, text="Au :").pack(side="left", padx=(8, 0))
        self.date_fin = DateEntry(filtre_frame, width=12)
        self.date_fin.pack(side="left", padx=4)

        ttk.Label(filtre_frame, text="Regrouper par :").pack(side="left", padx=(12, 0))
        self.periode_var = tk.StringVar(value="Mois")
        ttk.Combobox(filtre_frame, textvariable=self.periode_var,
                     values=list(PERIODES.keys()), width=10,
                     state="readonly").pack(side="left", padx=4)

        ttk.Button(filtre_frame, text="Actualiser",
                   command=self.refresh).pack(side="left", padx=12)

        ttk.Button(filtre_frame, text="Aujourd'hui",
                   command=self.raccourci_jour).pack(side="left", padx=2)
        ttk.Button(filtre_frame, text="Ce mois",
                   command=self.raccourci_mois).pack(side="left", padx=2)
        ttk.Button(filtre_frame, text="Cette ann\u00e9e",
                   command=self.raccourci_annee).pack(side="left", padx=2)

        kpi_frame = ttk.Frame(self)
        kpi_frame.pack(fill="x", padx=8, pady=(0, 8))

        self.kpi_recettes = self._creer_kpi(kpi_frame, "Recettes", "#1F8A4C")
        self.kpi_depenses = self._creer_kpi(kpi_frame, "D\u00e9penses", "#C0392B")
        self.kpi_benefice = self._creer_kpi(kpi_frame, "B\u00e9n\u00e9fice", "#1F4E79")
        self.kpi_occupation = self._creer_kpi(kpi_frame, "Taux d'occupation", "#8E44AD")

        main_frame = ttk.Frame(self)
        main_frame.pack(fill="both", expand=True, padx=8, pady=8)

        table_frame = ttk.LabelFrame(main_frame, text="R\u00e9capitulatif par p\u00e9riode")
        table_frame.pack(side="left", fill="both", expand=False, padx=(0, 8))

        columns = ("periode", "recettes", "depenses", "benefice")
        headers = {"periode": "P\u00e9riode", "recettes": "Recettes (TND)",
                   "depenses": "D\u00e9penses (TND)", "benefice": "B\u00e9n\u00e9fice (TND)"}
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings",
                                  height=18)
        for c in columns:
            self.tree.heading(c, text=headers[c])
            self.tree.column(c, width=110, anchor="center")
        self.tree.pack(fill="both", expand=True, padx=4, pady=4)

        graph_frame = ttk.LabelFrame(main_frame, text="Graphiques")
        graph_frame.pack(side="left", fill="both", expand=True)

        self.figure = Figure(figsize=(7, 6), dpi=90)
        self.ax1 = self.figure.add_subplot(211)
        self.ax2 = self.figure.add_subplot(212)
        self.figure.tight_layout(pad=3.0)

        self.canvas = FigureCanvasTkAgg(self.figure, master=graph_frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

    def _creer_kpi(self, parent, titre, couleur):
        frame = tk.Frame(parent, bg=couleur, bd=0)
        frame.pack(side="left", fill="x", expand=True, padx=4, pady=4)
        tk.Label(frame, text=titre, bg=couleur, fg="white",
                 font=("Segoe UI", 10, "bold")).pack(pady=(8, 0))
        var = tk.StringVar(value="--")
        tk.Label(frame, textvariable=var, bg=couleur, fg="white",
                 font=("Segoe UI", 14, "bold")).pack(pady=(0, 8))
        return var

    def raccourci_jour(self):
        today = date.today()
        self.date_debut.set_date(today)
        self.date_fin.set_date(today)
        self.periode_var.set("Jour")
        self.refresh()

    def raccourci_mois(self):
        today = date.today()
        self.date_debut.set_date(date(today.year, today.month, 1))
        self.date_fin.set_date(today)
        self.periode_var.set("Jour")
        self.refresh()

    def raccourci_annee(self):
        today = date.today()
        self.date_debut.set_date(date(today.year, 1, 1))
        self.date_fin.set_date(today)
        self.periode_var.set("Mois")
        self.refresh()

    def refresh(self):
        debut = date_str_to_iso(self.date_debut.get())
        fin = date_str_to_iso(self.date_fin.get())
        if not debut or not fin:
            return

        group_by = PERIODES.get(self.periode_var.get(), "month")

        recettes = {r["periode"]: r["total"] or 0.0
                    for r in recap_recettes(debut, fin, group_by)}
        depenses = {r["periode"]: r["total"] or 0.0
                    for r in recap_depenses(debut, fin, group_by)}

        periodes = sorted(set(recettes.keys()) | set(depenses.keys()))

        for item in self.tree.get_children():
            self.tree.delete(item)

        total_recettes, total_depenses, total_benefice = calculer_kpis(
            periodes, recettes, depenses)

        for p in periodes:
            r = recettes.get(p, 0.0)
            d = depenses.get(p, 0.0)
            benefice = r - d
            self.tree.insert("", "end", values=(
                formater_periode(p, group_by),
                f"{r:.3f}", f"{d:.3f}", f"{benefice:.3f}",
            ))

        occ, total_chambres = taux_occupation()
        taux = (occ / total_chambres * 100) if total_chambres else 0

        self.kpi_recettes.set(f"{total_recettes:.3f} TND")
        self.kpi_depenses.set(f"{total_depenses:.3f} TND")
        self.kpi_benefice.set(f"{total_benefice:.3f} TND")
        self.kpi_occupation.set(f"{taux:.1f} %  ({occ}/{total_chambres})")

        self._dessiner_graphiques(periodes, recettes, depenses, group_by)

    def _dessiner_graphiques(self, periodes, recettes, depenses, group_by):
        labels = [formater_periode(p, group_by) for p in periodes]
        valeurs_recettes = [recettes.get(p, 0.0) for p in periodes]
        valeurs_depenses = [depenses.get(p, 0.0) for p in periodes]
        benefices = [r - d for r, d in zip(valeurs_recettes, valeurs_depenses)]

        self.ax1.clear()
        self.ax2.clear()

        if periodes:
            x = range(len(periodes))
            largeur = 0.4

            self.ax1.bar([i - largeur / 2 for i in x], valeurs_recettes,
                          width=largeur, label="Recettes", color="#1F8A4C")
            self.ax1.bar([i + largeur / 2 for i in x], valeurs_depenses,
                          width=largeur, label="D\u00e9penses", color="#C0392B")
            self.ax1.set_xticks(list(x))
            self.ax1.set_xticklabels(labels, rotation=45, ha="right", fontsize=7)
            self.ax1.set_title("Recettes vs D\u00e9penses", fontsize=10)
            self.ax1.set_ylabel("TND")
            self.ax1.legend(fontsize=8)

            self.ax2.plot(list(x), benefices, marker="o", color="#1F4E79",
                           label="B\u00e9n\u00e9fice")
            self.ax2.axhline(0, color="grey", linewidth=0.8)
            self.ax2.set_xticks(list(x))
            self.ax2.set_xticklabels(labels, rotation=45, ha="right", fontsize=7)
            self.ax2.set_title("\u00c9volution du b\u00e9n\u00e9fice", fontsize=10)
            self.ax2.set_ylabel("TND")
            self.ax2.legend(fontsize=8)
        else:
            self.ax1.text(0.5, 0.5, "Aucune donn\u00e9e pour cette p\u00e9riode",
                           ha="center", va="center")
            self.ax2.text(0.5, 0.5, "Aucune donn\u00e9e pour cette p\u00e9riode",
                           ha="center", va="center")

        self.figure.tight_layout(pad=3.0)
        self.canvas.draw()
