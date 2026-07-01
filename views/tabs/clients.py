# -*- coding: utf-8 -*-

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date

from db.repository import (
    get_chambres, get_clients, get_client,
    add_client, update_client, delete_client,
)
from models.enums import TYPES_IDENTIFIANT
from views.widgets import DateEntry, date_str_to_iso, iso_to_date_str
from pdf.fiche_police import generer_fiche_police


class ClientsTab(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.selected_client_id = None

        self._build_ui()
        self.refresh()

    def _build_ui(self):
        form_frame = ttk.LabelFrame(self, text="Fiche client")
        form_frame.pack(side="left", fill="y", padx=8, pady=8)

        self.vars = {}

        def add_row(row, label, key, width=24):
            ttk.Label(form_frame, text=label).grid(
                row=row, column=0, sticky="w", padx=4, pady=3)
            var = tk.StringVar()
            widget = ttk.Entry(form_frame, textvariable=var, width=width)
            self.vars[key] = var
            widget.grid(row=row, column=1, sticky="w", padx=4, pady=3)
            return widget

        r = 0
        add_row(r, "Nom *", "nom"); r += 1
        add_row(r, "Pr\u00e9nom *", "prenom"); r += 1

        ttk.Label(form_frame, text="Type d'identifiant *").grid(
            row=r, column=0, sticky="w", padx=4, pady=3)
        self.vars["type_identifiant"] = tk.StringVar(value=TYPES_IDENTIFIANT[0])
        ttk.Combobox(form_frame, textvariable=self.vars["type_identifiant"],
                     values=TYPES_IDENTIFIANT, width=21,
                     state="readonly").grid(row=r, column=1, sticky="w", padx=4, pady=3)
        r += 1

        add_row(r, "N\u00b0 identifiant *", "numero_identifiant"); r += 1

        ttk.Label(form_frame, text="Date de naissance").grid(
            row=r, column=0, sticky="w", padx=4, pady=3)
        self.date_naissance = DateEntry(form_frame, width=12)
        self.date_naissance.grid(row=r, column=1, sticky="w", padx=4, pady=3)
        r += 1

        add_row(r, "Lieu de naissance", "lieu_naissance"); r += 1
        add_row(r, "Adresse", "adresse", width=30); r += 1
        add_row(r, "T\u00e9l\u00e9phone", "telephone"); r += 1
        add_row(r, "Venant de", "venant_de"); r += 1
        add_row(r, "Allant \u00e0", "allant_a"); r += 1

        ttk.Label(form_frame, text="Chambre r\u00e9serv\u00e9e").grid(
            row=r, column=0, sticky="w", padx=4, pady=3)
        self.chambre_var = tk.StringVar()
        self.combo_chambres = ttk.Combobox(
            form_frame, textvariable=self.chambre_var, width=21,
            state="readonly")
        self.combo_chambres.grid(row=r, column=1, sticky="w", padx=4, pady=3)
        r += 1

        ttk.Label(form_frame, text="Date d'entr\u00e9e").grid(
            row=r, column=0, sticky="w", padx=4, pady=3)
        self.date_entree = DateEntry(form_frame, width=12)
        self.date_entree.grid(row=r, column=1, sticky="w", padx=4, pady=3)
        r += 1

        ttk.Label(form_frame, text="Date de sortie").grid(
            row=r, column=0, sticky="w", padx=4, pady=3)
        self.date_sortie = DateEntry(form_frame, width=12)
        self.date_sortie.grid(row=r, column=1, sticky="w", padx=4, pady=3)
        r += 1

        ttk.Label(form_frame, text="Statut").grid(
            row=r, column=0, sticky="w", padx=4, pady=3)
        self.statut_var = tk.StringVar(value="En cours")
        ttk.Combobox(form_frame, textvariable=self.statut_var,
                     values=["En cours", "Sorti"], width=21,
                     state="readonly").grid(row=r, column=1, sticky="w", padx=4, pady=3)
        r += 1

        btn_frame = ttk.Frame(form_frame)
        btn_frame.grid(row=r, column=0, columnspan=2, pady=10)

        ttk.Button(btn_frame, text="Nouveau", command=self.nouveau).pack(
            side="left", padx=3)
        ttk.Button(btn_frame, text="Enregistrer", command=self.enregistrer).pack(
            side="left", padx=3)
        ttk.Button(btn_frame, text="Supprimer", command=self.supprimer).pack(
            side="left", padx=3)
        ttk.Button(btn_frame, text="Check-out / Sortie",
                   command=self.checkout).pack(side="left", padx=3)
        ttk.Button(btn_frame, text="\U0001F4C4 Fiche Police",
                   command=self.imprimer_fiche_police).pack(side="left", padx=3)

        right_frame = ttk.Frame(self)
        right_frame.pack(side="left", fill="both", expand=True, padx=8, pady=8)

        search_frame = ttk.Frame(right_frame)
        search_frame.pack(fill="x", pady=(0, 6))
        ttk.Label(search_frame, text="Recherche :").pack(side="left")
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *a: self.refresh())
        ttk.Entry(search_frame, textvariable=self.search_var, width=30).pack(
            side="left", padx=4)

        ttk.Label(search_frame, text="Filtre :").pack(side="left", padx=(12, 0))
        self.filtre_statut = tk.StringVar(value="Tous")
        ttk.Combobox(search_frame, textvariable=self.filtre_statut,
                     values=["Tous", "En cours", "Sorti"], width=12,
                     state="readonly").pack(side="left", padx=4)
        self.filtre_statut.trace_add("write", lambda *a: self.refresh())
        columns = ("id", "nom", "prenom", "identifiant", "chambre",
                   "entree", "sortie", "statut", "solde")
        headers = {
            "id": "ID", "nom": "Nom", "prenom": "Pr\u00e9nom",
            "identifiant": "Identifiant", "chambre": "Chambre",
            "entree": "Entr\u00e9e", "sortie": "Sortie", "statut": "Statut",
            "solde": "Solde (TND)",
        }
        self.tree = ttk.Treeview(right_frame, columns=columns, show="headings",
                                  height=22)
        for c in columns:
            self.tree.heading(c, text=headers[c])
            width = 60 if c in ("id", "chambre", "statut") else 100
            self.tree.column(c, width=width, anchor="center")
        self.tree.column("nom", width=110, anchor="w")
        self.tree.column("prenom", width=110, anchor="w")
        self.tree.column("identifiant", width=100, anchor="w")
        self.tree.column("entree", width=85, anchor="center")
        self.tree.column("sortie", width=85, anchor="center")
        self.tree.column("solde", width=130, anchor="center")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.on_select)

    def refresh(self):
        chambres = get_chambres()
        self.chambres_map = {"": None}
        valeurs = [""]
        current_chambre_id = self._get_current_chambre_id()
        for ch in chambres:
            if ch["etat"] == "Libre" or ch["id"] == current_chambre_id:
                texte = f"{ch['numero']} - {ch['type']} ({ch['prix']} TND)"
                self.chambres_map[texte] = ch["id"]
                valeurs.append(texte)
        self.combo_chambres["values"] = valeurs
        if self.chambre_var.get() not in valeurs:
            self.chambre_var.set("")

        for item in self.tree.get_children():
            self.tree.delete(item)

        statut_filtre = self.filtre_statut.get()
        if statut_filtre == "Tous":
            clients = get_clients()
        else:
            clients = get_clients(statut_filtre)

        recherche = self.search_var.get().strip().lower()

        for c in clients:
            ligne = (c["nom"], c["prenom"], c["numero_identifiant"],
                     c["chambre_numero"] or "")
            if recherche and not any(recherche in str(v).lower() for v in ligne):
                continue
            self.tree.insert("", "end", iid=str(c["id"]), values=(
                c["id"], c["nom"], c["prenom"], c["numero_identifiant"],
                c["chambre_numero"] or "-",
                iso_to_date_str(c["date_entree"]) or c["date_entree"],
                iso_to_date_str(c["date_sortie"]) or c["date_sortie"],
                c["statut"],
                f"{c['solde']:.3f}" if c['solde'] else "0.000",
            ))

    def _get_current_chambre_id(self):
        if not self.selected_client_id:
            return None
        client = get_client(self.selected_client_id)
        return client["chambre_id"] if client else None

    def on_select(self, event=None):
        selection = self.tree.selection()
        if not selection:
            return
        client_id = int(selection[0])
        self.selected_client_id = client_id
        client = get_client(client_id)
        if not client:
            return

        self.vars["nom"].set(client["nom"])
        self.vars["prenom"].set(client["prenom"])
        self.vars["type_identifiant"].set(client["type_identifiant"])
        self.vars["numero_identifiant"].set(client["numero_identifiant"])
        self.vars["lieu_naissance"].set(client["lieu_naissance"])
        self.vars["adresse"].set(client["adresse"])
        self.vars["telephone"].set(client["telephone"])
        self.vars["venant_de"].set(client["venant_de"])
        self.vars["allant_a"].set(client["allant_a"])
        self.statut_var.set(client["statut"])

        if client["date_naissance"]:
            self.date_naissance.set(iso_to_date_str(client["date_naissance"]))
        else:
            self.date_naissance.set("")
        if client["date_entree"]:
            self.date_entree.set(iso_to_date_str(client["date_entree"]))
        if client["date_sortie"]:
            self.date_sortie.set(iso_to_date_str(client["date_sortie"]))

        self.refresh_chambre_combo(client)

    def refresh_chambre_combo(self, client):
        chambres = get_chambres()
        valeurs = [""]
        self.chambres_map = {"": None}
        for ch in chambres:
            if ch["etat"] == "Libre" or ch["id"] == client["chambre_id"]:
                texte = f"{ch['numero']} - {ch['type']} ({ch['prix']} TND)"
                self.chambres_map[texte] = ch["id"]
                valeurs.append(texte)
        self.combo_chambres["values"] = valeurs
        if client["chambre_id"]:
            for texte, cid in self.chambres_map.items():
                if cid == client["chambre_id"]:
                    self.chambre_var.set(texte)
                    return
        self.chambre_var.set("")

    def nouveau(self):
        self.selected_client_id = None
        for var in self.vars.values():
            var.set("")
        self.vars["type_identifiant"].set(TYPES_IDENTIFIANT[0])
        self.date_naissance.set("")
        self.date_entree.set_date(date.today())
        self.date_sortie.set_date(date.today())
        self.statut_var.set("En cours")
        self.chambre_var.set("")
        self.refresh()
        self.tree.selection_remove(self.tree.selection())

    def _collect_form_data(self):
        nom = self.vars["nom"].get().strip()
        prenom = self.vars["prenom"].get().strip()
        numero_id = self.vars["numero_identifiant"].get().strip()

        if not nom or not prenom or not numero_id:
            messagebox.showerror(
                "Champs manquants",
                "Les champs Nom, Pr\u00e9nom et N\u00b0 d'identifiant sont obligatoires.")
            return None

        date_naissance_iso = date_str_to_iso(self.date_naissance.get())
        date_entree_iso = date_str_to_iso(self.date_entree.get())
        date_sortie_iso = date_str_to_iso(self.date_sortie.get())

        chambre_texte = self.chambre_var.get()
        chambre_id = self.chambres_map.get(chambre_texte)

        data = {
            "nom": nom,
            "prenom": prenom,
            "type_identifiant": self.vars["type_identifiant"].get(),
            "numero_identifiant": numero_id,
            "date_naissance": date_naissance_iso,
            "lieu_naissance": self.vars["lieu_naissance"].get().strip(),
            "adresse": self.vars["adresse"].get().strip(),
            "telephone": self.vars["telephone"].get().strip(),
            "venant_de": self.vars["venant_de"].get().strip(),
            "allant_a": self.vars["allant_a"].get().strip(),
            "chambre_id": chambre_id,
            "date_entree": date_entree_iso,
            "date_sortie": date_sortie_iso,
            "statut": self.statut_var.get(),
        }
        return data

    def enregistrer(self):
        data = self._collect_form_data()
        if data is None:
            return

        if self.selected_client_id:
            update_client(self.selected_client_id, data)
            messagebox.showinfo("Succ\u00e8s", "Client mis \u00e0 jour avec succ\u00e8s.")
        else:
            new_id = add_client(data)
            self.selected_client_id = new_id
            messagebox.showinfo("Succ\u00e8s", "Client ajout\u00e9 avec succ\u00e8s.")

        self.refresh()
        self.app.refresh_rooms_tab()

    def supprimer(self):
        if not self.selected_client_id:
            messagebox.showwarning("Attention", "Veuillez s\u00e9lectionner un client.")
            return
        if not messagebox.askyesno(
                "Confirmation",
                "Voulez-vous vraiment supprimer ce client ? "
                "Sa chambre sera lib\u00e9r\u00e9e."):
            return
        delete_client(self.selected_client_id)
        self.nouveau()
        self.refresh()
        self.app.refresh_rooms_tab()

    def checkout(self):
        if not self.selected_client_id:
            messagebox.showwarning("Attention", "Veuillez s\u00e9lectionner un client.")
            return
        client = get_client(self.selected_client_id)
        if not client:
            return
        if client["statut"] == "Sorti":
            messagebox.showinfo("Information", "Ce client est d\u00e9j\u00e0 sorti.")
            return

        if not messagebox.askyesno(
                "Confirmation",
                f"Confirmer la sortie de {client['prenom']} {client['nom']} "
                f"et lib\u00e9rer la chambre {client['chambre_numero'] or ''} ?"):
            return

        data = dict(client)
        data["statut"] = "Sorti"
        data["date_sortie"] = date.today().strftime("%Y-%m-%d")
        update_client(self.selected_client_id, data)
        self.refresh()
        self.app.refresh_rooms_tab()
        messagebox.showinfo("Succ\u00e8s", "Le client est marqu\u00e9 comme sorti et la chambre est lib\u00e9r\u00e9e.")

    def imprimer_fiche_police(self):
        if not self.selected_client_id:
            messagebox.showwarning("Attention", "Veuillez s\u00e9lectionner un client.")
            return
        client = get_client(self.selected_client_id)
        if not client:
            messagebox.showerror("Erreur", "Client introuvable.")
            return
        try:
            chemin = generer_fiche_police(dict(client))
            messagebox.showinfo("Succ\u00e8s", f"Fiche Police g\u00e9n\u00e9r\u00e9e :\n{chemin}")
        except Exception as e:
            messagebox.showerror("Erreur PDF", f"Impossible de g\u00e9n\u00e9rer la fiche :\n{e}")
