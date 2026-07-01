# -*- coding: utf-8 -*-

import calendar
import tkinter as tk
from tkinter import ttk
from datetime import date, datetime


MOIS_FR = [
    "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
    "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre",
]

JOURS_FR = ["Lu", "Ma", "Me", "Je", "Ve", "Sa", "Di"]


def _formater_prix(var, event=None):
    valeur = var.get().replace(",", ".").strip()
    try:
        var.set(f"{float(valeur):.3f}".replace(".", ","))
    except ValueError:
        pass


class CalendarPopup(tk.Toplevel):

    def __init__(self, parent, on_select, initial_date=None):
        super().__init__(parent)
        self.title("Choisir une date")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.on_select = on_select

        if initial_date is None:
            initial_date = date.today()
        self.current_year = initial_date.year
        self.current_month = initial_date.month

        self.header = tk.Frame(self)
        self.header.pack(fill="x", padx=4, pady=4)

        ttk.Button(self.header, text="<", width=3,
                   command=self.mois_precedent).pack(side="left")
        self.label_mois = tk.Label(self.header, width=18, anchor="center",
                                    font=("Segoe UI", 10, "bold"))
        self.label_mois.pack(side="left", expand=True)
        ttk.Button(self.header, text=">", width=3,
                   command=self.mois_suivant).pack(side="right")

        self.grid_frame = tk.Frame(self)
        self.grid_frame.pack(padx=4, pady=4)

        self.dessiner_calendrier()

        self.update_idletasks()
        try:
            x = parent.winfo_rootx() + 20
            y = parent.winfo_rooty() + 20
            self.geometry(f"+{x}+{y}")
        except Exception:
            pass

    def mois_precedent(self):
        self.current_month -= 1
        if self.current_month < 1:
            self.current_month = 12
            self.current_year -= 1
        self.dessiner_calendrier()

    def mois_suivant(self):
        self.current_month += 1
        if self.current_month > 12:
            self.current_month = 1
            self.current_year += 1
        self.dessiner_calendrier()

    def dessiner_calendrier(self):
        for widget in self.grid_frame.winfo_children():
            widget.destroy()

        self.label_mois.config(
            text=f"{MOIS_FR[self.current_month - 1]} {self.current_year}"
        )

        for col, nom_jour in enumerate(JOURS_FR):
            tk.Label(self.grid_frame, text=nom_jour, width=4,
                     font=("Segoe UI", 9, "bold")).grid(row=0, column=col)

        cal = calendar.Calendar(firstweekday=0)
        semaine = 1
        for jour_semaine_data in cal.monthdayscalendar(
                self.current_year, self.current_month):
            for col, jour in enumerate(jour_semaine_data):
                if jour == 0:
                    tk.Label(self.grid_frame, text="", width=4).grid(
                        row=semaine, column=col)
                else:
                    btn = tk.Button(
                        self.grid_frame, text=str(jour), width=4,
                        relief="flat",
                        command=lambda j=jour: self.choisir(j),
                    )
                    if (jour == date.today().day
                            and self.current_month == date.today().month
                            and self.current_year == date.today().year):
                        btn.config(bg="#cce5ff")
                    btn.grid(row=semaine, column=col, padx=1, pady=1)
            semaine += 1

    def choisir(self, jour):
        d = date(self.current_year, self.current_month, jour)
        self.on_select(d)
        self.destroy()


class DateEntry(tk.Frame):

    def __init__(self, parent, width=10, **kwargs):
        super().__init__(parent)
        self.var = tk.StringVar()
        self.entry = ttk.Entry(self, textvariable=self.var, width=width,
                                **kwargs)
        self.entry.pack(side="left")
        self.bouton = ttk.Button(self, text="\U0001F4C5", width=3,
                                  command=self.ouvrir_calendrier)
        self.bouton.pack(side="left", padx=(2, 0))

        self.set_date(date.today())

    def ouvrir_calendrier(self):
        initial = self.get_date() or date.today()
        CalendarPopup(self, self.on_date_selected, initial)

    def on_date_selected(self, d):
        self.set_date(d)

    def get(self):
        return self.var.get()

    def set(self, value):
        self.var.set(value)

    def set_date(self, d):
        self.var.set(d.strftime("%d/%m/%Y"))

    def get_date(self):
        try:
            return datetime.strptime(self.var.get(), "%d/%m/%Y").date()
        except ValueError:
            return None


def date_str_to_iso(date_str):
    try:
        return datetime.strptime(date_str, "%d/%m/%Y").strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return ""


def iso_to_date_str(iso_str):
    try:
        return datetime.strptime(iso_str, "%Y-%m-%d").strftime("%d/%m/%Y")
    except (ValueError, TypeError):
        return ""


class ScrollableFrame(tk.Frame):

    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)

        self.canvas = tk.Canvas(self, borderwidth=0, highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical",
                                        command=self.canvas.yview)
        self.inner = tk.Frame(self.canvas)

        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        self.canvas_window = self.canvas.create_window(
            (0, 0), window=self.inner, anchor="nw")

        self.inner.bind("<Configure>", self._on_inner_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _on_inner_configure(self, event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self.canvas.itemconfig(self.canvas_window, width=event.width)

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
