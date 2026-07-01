# -*- coding: utf-8 -*-

import tkinter as tk
from tkinter import ttk

from db.connection import init_db
from views.tabs.chambres import RoomsTab
from views.tabs.clients import ClientsTab
from views.tabs.facturation import FacturationTab
from views.tabs.depenses import DepensesTab
from views.tabs.statistiques import StatsTab
from views.tabs.parametres import ParametresTab
from views.tabs.reservations import ReservationsTab


class HotelApp(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("Gestion d'H\u00f4tel - Logiciel de gestion (TND)")
        self.geometry("1280x800")
        self.minsize(1024, 650)

        self._configurer_style()

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True)
        self.notebook = notebook

        self.tab_chambres = RoomsTab(notebook, self)
        self.tab_clients = ClientsTab(notebook, self)
        self.tab_facturation = FacturationTab(notebook, self)
        self.tab_depenses = DepensesTab(notebook, self)
        self.tab_stats = StatsTab(notebook, self)
        self.tab_parametres = ParametresTab(notebook, self)
        self.tab_reservations = ReservationsTab(notebook, self)

        notebook.add(self.tab_chambres, text="  Chambres  ")
        notebook.add(self.tab_clients, text="  Clients  ")
        notebook.add(self.tab_reservations, text="  R\u00e9servations  ")
        notebook.add(self.tab_facturation, text="  Facturation  ")
        notebook.add(self.tab_depenses, text="  D\u00e9penses  ")
        notebook.add(self.tab_stats, text="  Statistiques  ")
        notebook.add(self.tab_parametres, text="  Param\u00e8tres  ")

        notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)

    def _configurer_style(self):
        style = ttk.Style(self)
        try:
            style.theme_use("vista")
        except tk.TclError:
            try:
                style.theme_use("clam")
            except tk.TclError:
                pass
        style.configure("TNotebook.Tab", padding=(12, 6),
                        font=("Segoe UI", 10, "bold"))
        style.configure("Treeview", rowheight=24, font=("Segoe UI", 9))
        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))

    def refresh_rooms_tab(self):
        self.tab_chambres.refresh()

    def refresh_clients_tab(self):
        self.tab_clients.refresh()

    def refresh_stats_tab(self):
        self.tab_stats.refresh()

    def on_tab_changed(self, event):
        selected = event.widget.select()
        widget = event.widget.nametowidget(selected)
        if widget is self.tab_chambres:
            self.tab_chambres.refresh()
        elif widget is self.tab_clients:
            self.tab_clients.refresh()
        elif widget is self.tab_facturation:
            self.tab_facturation.refresh()
        elif widget is self.tab_depenses:
            self.tab_depenses.refresh()
        elif widget is self.tab_stats:
            self.tab_stats.refresh()
        elif widget is self.tab_reservations:
            self.tab_reservations.refresh()

    def refresh_reservations_tab(self):
        self.tab_reservations.refresh()
