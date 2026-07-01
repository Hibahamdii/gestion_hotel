# -*- coding: utf-8 -*-

import tkinter as tk
from tkinter import ttk, messagebox

from db.repository import get_parametre, set_parametre


class ParametresTab(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app

        frame = ttk.LabelFrame(self, text="Informations de l'h\u00f4tel (en-t\u00eate de facture)")
        frame.pack(padx=16, pady=16, anchor="nw")

        self.vars = {}
        champs = [
            ("nom_hotel", "Nom de l'h\u00f4tel"),
            ("adresse_hotel", "Adresse"),
            ("telephone_hotel", "T\u00e9l\u00e9phone"),
            ("matricule_fiscal", "Matricule fiscal"),
        ]
        for i, (cle, label) in enumerate(champs):
            ttk.Label(frame, text=label).grid(row=i, column=0, sticky="w",
                                                padx=8, pady=6)
            var = tk.StringVar(value=get_parametre(cle, ""))
            self.vars[cle] = var
            ttk.Entry(frame, textvariable=var, width=50).grid(
                row=i, column=1, sticky="w", padx=8, pady=6)

        ttk.Label(frame, text="Prochain num\u00e9ro de facture").grid(
            row=len(champs), column=0, sticky="w", padx=8, pady=6)
        self.vars["prochain_numero_facture"] = tk.StringVar(
            value=get_parametre("prochain_numero_facture", "1"))
        ttk.Entry(frame, textvariable=self.vars["prochain_numero_facture"],
                  width=15).grid(row=len(champs), column=1, sticky="w",
                                  padx=8, pady=6)

        ttk.Button(frame, text="Enregistrer",
                   command=self.enregistrer).grid(
            row=len(champs) + 1, column=0, columnspan=2, pady=12)

        info_frame = ttk.LabelFrame(self, text="\u00c0 propos")
        info_frame.pack(padx=16, pady=16, anchor="nw", fill="x")
        ttk.Label(info_frame, text=(
            "Logiciel de gestion d'h\u00f4tel\n"
            "Base de donn\u00e9es SQLite : hotel.db (dans le dossier de l'application)\n"
            "Devise utilis\u00e9e : Dinar Tunisien (TND), 1 TND = 1000 millimes"
        ), justify="left").pack(padx=8, pady=8, anchor="w")

    def enregistrer(self):
        try:
            int(self.vars["prochain_numero_facture"].get())
        except ValueError:
            messagebox.showerror("Erreur", "Le prochain num\u00e9ro de facture doit \u00eatre un entier.")
            return

        for cle, var in self.vars.items():
            set_parametre(cle, var.get())

        messagebox.showinfo("Succ\u00e8s", "Param\u00e8tres enregistr\u00e9s.")
