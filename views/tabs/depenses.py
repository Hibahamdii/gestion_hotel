# -*- coding: utf-8 -*-

import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import date

from db.repository import (
    get_depenses, add_depense, update_depense, delete_depense,
)
from models.enums import CATEGORIES_DEPENSE
from views.widgets import DateEntry, date_str_to_iso, iso_to_date_str
from pdf.listes import generer_liste_depenses_pdf


class DepensesTab(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.selected_depense_id = None

        self._build_ui()
        self.refresh()

    def _formater_montant(self, event=None):
        valeur = self.montant_var.get().replace(",", ".").strip()
        try:
            self.montant_var.set(f"{float(valeur):.3f}".replace(".", ","))
        except ValueError:
            pass

    def _build_ui(self):
        form_frame = ttk.LabelFrame(self, text="Nouvelle d\u00e9pense / Modification")
        form_frame.pack(side="left", fill="y", padx=8, pady=8)

        ttk.Label(form_frame, text="Date *").grid(row=0, column=0, sticky="w",
                                                    padx=4, pady=4)
        self.date_entry = DateEntry(form_frame, width=12)
        self.date_entry.grid(row=0, column=1, padx=4, pady=4, sticky="w")

        ttk.Label(form_frame, text="Cat\u00e9gorie *").grid(row=1, column=0, sticky="w",
                                                              padx=4, pady=4)
        self.categorie_var = tk.StringVar(value=CATEGORIES_DEPENSE[0])
        ttk.Combobox(form_frame, textvariable=self.categorie_var,
                     values=CATEGORIES_DEPENSE, width=22,
                     state="readonly").grid(row=1, column=1, padx=4, pady=4, sticky="w")

        ttk.Label(form_frame, text="Description").grid(row=2, column=0, sticky="w",
                                                          padx=4, pady=4)
        self.description_var = tk.StringVar()
        ttk.Entry(form_frame, textvariable=self.description_var,
                  width=25).grid(row=2, column=1, padx=4, pady=4, sticky="w")

        ttk.Label(form_frame, text="Montant (TND) *").grid(row=3, column=0, sticky="w",
                                                              padx=4, pady=4)
        self.montant_var = tk.StringVar()
        self.montant_entry = ttk.Entry(form_frame, textvariable=self.montant_var, width=25)
        self.montant_entry.grid(row=3, column=1, padx=4, pady=4, sticky="w")
        self.montant_entry.bind("<FocusOut>", self._formater_montant)
        ttk.Label(form_frame, text="Mode de paiement").grid(row=4, column=0, sticky="w",
                                                               padx=4, pady=4)
        self.mode_var = tk.StringVar(value="Esp\u00e8ces")
        ttk.Combobox(form_frame, textvariable=self.mode_var,
                     values=["Esp\u00e8ces", "Ch\u00e8que", "Carte bancaire", "Virement"],
                     width=22, state="readonly").grid(row=4, column=1, padx=4, pady=4, sticky="w")

        btn_frame = ttk.Frame(form_frame)
        btn_frame.grid(row=5, column=0, columnspan=2, pady=10)
        ttk.Button(btn_frame, text="Nouveau", command=self.nouveau).pack(
            side="left", padx=3)
        ttk.Button(btn_frame, text="Enregistrer", command=self.enregistrer).pack(
            side="left", padx=3)
        ttk.Button(btn_frame, text="\u270f\ufe0f Modifier", command=self.modifier).pack(
            side="left", padx=3)
        ttk.Button(btn_frame, text="Supprimer", command=self.supprimer).pack(
            side="left", padx=3)

        right_frame = ttk.Frame(self)
        right_frame.pack(side="left", fill="both", expand=True, padx=8, pady=8)

        filtre_frame = ttk.Frame(right_frame)
        filtre_frame.pack(fill="x", pady=(0, 6))

        ttk.Label(filtre_frame, text="Du :").pack(side="left")
        self.filtre_debut = DateEntry(filtre_frame, width=12)
        self.filtre_debut.pack(side="left", padx=4)
        self.filtre_debut.set("01/01/2000")

        ttk.Label(filtre_frame, text="Au :").pack(side="left", padx=(8, 0))
        self.filtre_fin = DateEntry(filtre_frame, width=12)
        self.filtre_fin.pack(side="left", padx=4)

        ttk.Button(filtre_frame, text="Filtrer", command=self.refresh).pack(
            side="left", padx=8)
        ttk.Button(filtre_frame, text="Tout afficher",
                   command=self.reset_filtre).pack(side="left", padx=4)
        ttk.Button(filtre_frame, text="\U0001F5A8\ufe0f Imprimer la liste",
                   command=self.imprimer_liste).pack(side="left", padx=8)

        columns = ("id", "date", "categorie", "description", "montant", "mode")
        headers = {
            "id": "ID", "date": "Date", "categorie": "Cat\u00e9gorie",
            "description": "Description", "montant": "Montant (TND)",
            "mode": "Mode de paiement",
        }
        self.tree = ttk.Treeview(right_frame, columns=columns, show="headings",
                                  height=22)
        for c in columns:
            self.tree.heading(c, text=headers[c])
            width = 60 if c == "id" else 120
            self.tree.column(c, width=width, anchor="center")
        self.tree.column("description", width=220, anchor="w")
        self.tree.column("categorie", width=150, anchor="w")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.on_select)

        self.total_var = tk.StringVar()
        ttk.Label(right_frame, textvariable=self.total_var,
                  font=("Segoe UI", 10, "bold")).pack(anchor="e", pady=(6, 0))

    def reset_filtre(self):
        self.filtre_debut.set("01/01/2000")
        self.filtre_fin.set_date(date.today())
        self.refresh()

    def refresh(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        debut = date_str_to_iso(self.filtre_debut.get()) or "0000-01-01"
        fin = date_str_to_iso(self.filtre_fin.get()) or "9999-12-31"

        depenses = get_depenses(debut, fin)
        total = 0.0
        for d in depenses:
            total += d["montant"]
            self.tree.insert("", "end", iid=str(d["id"]), values=(
                d["id"], iso_to_date_str(d["date"]) or d["date"],
                d["categorie"], d["description"],
                f"{d['montant']:.3f}", d["mode_paiement"],
            ))
        self.total_var.set(f"Total des d\u00e9penses affich\u00e9es : {total:.3f} TND")

    def imprimer_liste(self):
        items = self.tree.get_children()
        if not items:
            messagebox.showwarning("Attention", "Aucune d\u00e9pense \u00e0 imprimer.")
            return

        depenses_data = []
        for iid in items:
            valeurs = self.tree.item(iid)["values"]
            date_d, categorie, description, montant_str, mode = valeurs[1:]
            try:
                montant = float(str(montant_str).replace(",", "."))
            except ValueError:
                montant = 0.0
            depenses_data.append((date_d, categorie, description, montant, mode))

        nom_fichier_defaut = f"Liste_depenses_{date.today().strftime('%Y%m%d')}.pdf"
        chemin = filedialog.asksaveasfilename(
            title="Enregistrer la liste des d\u00e9penses",
            defaultextension=".pdf",
            initialfile=nom_fichier_defaut,
            filetypes=[("Fichier PDF", "*.pdf")],
        )
        if not chemin:
            return

        try:
            generer_liste_depenses_pdf(depenses_data, chemin)
        except Exception as exc:
            messagebox.showerror("Erreur", f"Impossible de g\u00e9n\u00e9rer le PDF : {exc}")
            return

        messagebox.showinfo("Succ\u00e8s", f"Liste export\u00e9e : {chemin}")
        try:
            if os.name == "nt":
                os.startfile(chemin)
        except Exception:
            pass

    def on_select(self, event=None):
        selection = self.tree.selection()
        if not selection:
            return
        depense_id = int(selection[0])
        self.selected_depense_id = depense_id

        conn_rows = get_depenses()
        for d in conn_rows:
            if d["id"] == depense_id:
                self.date_entry.set(iso_to_date_str(d["date"]) or d["date"])
                self.categorie_var.set(d["categorie"])
                self.description_var.set(d["description"])
                self.montant_var.set(f"{d['montant']:.3f}")
                self.mode_var.set(d["mode_paiement"])
                break

    def nouveau(self):
        self.selected_depense_id = None
        self.date_entry.set_date(date.today())
        self.categorie_var.set(CATEGORIES_DEPENSE[0])
        self.description_var.set("")
        self.montant_var.set("")
        self.mode_var.set("Esp\u00e8ces")
        self.tree.selection_remove(self.tree.selection())
        self.refresh()

    def enregistrer(self):
        date_iso = date_str_to_iso(self.date_entry.get())
        if not date_iso:
            messagebox.showerror("Erreur", "La date est invalide (format JJ/MM/AAAA).")
            return
        try:
            montant = float(self.montant_var.get().replace(",", "."))
            if montant <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("Erreur", "Le montant doit \u00eatre un nombre positif.")
            return

        categorie = self.categorie_var.get()
        description = self.description_var.get().strip()
        mode = self.mode_var.get()

        if self.selected_depense_id:
            update_depense(self.selected_depense_id, date_iso, categorie,
                             description, montant, mode)
            messagebox.showinfo("Succ\u00e8s", "D\u00e9pense mise \u00e0 jour.")
        else:
            add_depense(date_iso, categorie, description, montant, mode)
            messagebox.showinfo("Succ\u00e8s", "D\u00e9pense ajout\u00e9e.")

        self.refresh()
        self.app.refresh_stats_tab()

    def modifier(self):
        if not self.selected_depense_id:
            messagebox.showwarning("Attention", "Veuillez s\u00e9lectionner une d\u00e9pense dans la liste.")
            return

        win = tk.Toplevel(self)
        win.title("Modifier la d\u00e9pense")
        win.resizable(False, False)
        win.transient(self)
        win.grab_set()

        ttk.Label(win, text="Date *").grid(row=0, column=0, sticky="w", padx=8, pady=4)
        date_entry = DateEntry(win, width=12)
        date_entry.grid(row=0, column=1, padx=8, pady=4, sticky="w")
        date_entry.set(self.date_entry.get())

        ttk.Label(win, text="Cat\u00e9gorie *").grid(row=1, column=0, sticky="w", padx=8, pady=4)
        categorie_var = tk.StringVar(value=self.categorie_var.get())
        ttk.Combobox(win, textvariable=categorie_var,
                     values=CATEGORIES_DEPENSE, width=22,
                     state="readonly").grid(row=1, column=1, padx=8, pady=4, sticky="w")

        ttk.Label(win, text="Description").grid(row=2, column=0, sticky="w", padx=8, pady=4)
        description_var = tk.StringVar(value=self.description_var.get())
        ttk.Entry(win, textvariable=description_var, width=25).grid(
            row=2, column=1, padx=8, pady=4, sticky="w")

        ttk.Label(win, text="Montant (TND) *").grid(row=3, column=0, sticky="w", padx=8, pady=4)
        montant_var = tk.StringVar(value=self.montant_var.get())
        ttk.Entry(win, textvariable=montant_var, width=25).grid(
            row=3, column=1, padx=8, pady=4, sticky="w")

        ttk.Label(win, text="Mode de paiement").grid(row=4, column=0, sticky="w", padx=8, pady=4)
        mode_var = tk.StringVar(value=self.mode_var.get())
        ttk.Combobox(win, textvariable=mode_var,
                     values=["Esp\u00e8ces", "Ch\u00e8que", "Carte bancaire", "Virement"],
                     width=22, state="readonly").grid(
            row=4, column=1, padx=8, pady=4, sticky="w")

        def confirmer():
            date_iso = date_str_to_iso(date_entry.get())
            if not date_iso:
                messagebox.showerror("Erreur", "Date invalide (format JJ/MM/AAAA).")
                return
            try:
                montant = float(montant_var.get().replace(",", "."))
                if montant <= 0:
                    raise ValueError
            except ValueError:
                messagebox.showerror("Erreur", "Le montant doit \u00eatre un nombre positif.")
                return

            update_depense(
                self.selected_depense_id,
                date_iso,
                categorie_var.get(),
                description_var.get().strip(),
                montant,
                mode_var.get(),
            )
            win.destroy()
            self.refresh()
            self.app.refresh_stats_tab()
            messagebox.showinfo("Succ\u00e8s", "D\u00e9pense modifi\u00e9e avec succ\u00e8s.")

        btn = ttk.Frame(win)
        btn.grid(row=5, column=0, columnspan=2, pady=10)
        ttk.Button(btn, text="Confirmer", command=confirmer).pack(side="left", padx=4)
        ttk.Button(btn, text="Annuler", command=win.destroy).pack(side="left", padx=4)

    def supprimer(self):
        if not self.selected_depense_id:
            messagebox.showwarning("Attention", "Veuillez s\u00e9lectionner une d\u00e9pense.")
            return
        if not messagebox.askyesno("Confirmation", "Supprimer cette d\u00e9pense ?"):
            return
        delete_depense(self.selected_depense_id)
        self.nouveau()
        self.refresh()
        self.app.refresh_stats_tab()
