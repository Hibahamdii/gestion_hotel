# -*- coding: utf-8 -*-

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date

from db.repository import (
    get_reservations, get_reservation, get_chambres,
    add_reservation, update_reservation, delete_reservation,
    add_client, get_connection,
)
from models.enums import TYPES_IDENTIFIANT, STATUTS_RESERVATION, COULEURS_STATUT_REZ
from views.widgets import DateEntry, date_str_to_iso, iso_to_date_str


class ReservationsTab(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.selected_reservation_id = None
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        top_frame = ttk.Frame(self)
        top_frame.pack(fill="x", padx=8, pady=(8, 0))

        ttk.Label(top_frame, text="Filtre statut :").pack(side="left")
        self.filtre_statut = tk.StringVar(value="Tous")
        ttk.Combobox(
            top_frame, textvariable=self.filtre_statut,
            values=["Tous"] + STATUTS_RESERVATION,
            width=12, state="readonly"
        ).pack(side="left", padx=4)
        self.filtre_statut.trace_add("write", lambda *a: self.refresh())

        ttk.Label(top_frame, text="Recherche :").pack(side="left", padx=(12, 0))
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *a: self.refresh())
        ttk.Entry(top_frame, textvariable=self.search_var, width=25).pack(
            side="left", padx=4)

        ttk.Button(
            top_frame, text="+ Nouvelle r\u00e9servation",
            command=self.nouvelle_reservation
        ).pack(side="right", padx=4)
        ttk.Button(
            top_frame, text="\u270f\ufe0f Modifier",
            command=self.modifier_reservation
        ).pack(side="right", padx=4)
        ttk.Button(
            top_frame, text="\U0001F5D1\ufe0f Supprimer",
            command=self.supprimer_reservation
        ).pack(side="right", padx=4)
        ttk.Button(
            top_frame, text="\u2705 Check-in",
            command=self.checkin_reservation
        ).pack(side="right", padx=4)

        list_frame = ttk.Frame(self)
        list_frame.pack(fill="both", expand=True, padx=8, pady=8)

        columns = ("id", "nom", "prenom", "telephone", "chambre",
                   "arrivee", "depart", "nb_personnes", "statut")
        headers = {
            "id": "ID", "nom": "Nom", "prenom": "Pr\u00e9nom",
            "telephone": "T\u00e9l\u00e9phone", "chambre": "Chambre",
            "arrivee": "Arriv\u00e9e", "depart": "D\u00e9part",
            "nb_personnes": "Pers.", "statut": "Statut",
        }
        self.tree = ttk.Treeview(
            list_frame, columns=columns, show="headings", height=20)
        for c in columns:
            self.tree.heading(c, text=headers[c])
            self.tree.column(c, width=80, anchor="center")
        self.tree.column("nom", width=120, anchor="w")
        self.tree.column("prenom", width=120, anchor="w")
        self.tree.column("telephone", width=110, anchor="w")

        for statut, couleur in COULEURS_STATUT_REZ.items():
            self.tree.tag_configure(statut, background=couleur,
                                    foreground="white")

        scrollbar = ttk.Scrollbar(list_frame, orient="vertical",
                                   command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        self.compteur_var = tk.StringVar()
        ttk.Label(self, textvariable=self.compteur_var,
                  font=("Segoe UI", 9, "italic")).pack(anchor="e", padx=8)

    def refresh(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        statut = self.filtre_statut.get()
        reservations = get_reservations(
            None if statut == "Tous" else statut)

        recherche = self.search_var.get().strip().lower()
        total = 0
        for r in reservations:
            ligne = (r["nom"], r["prenom"], r["telephone"],
                     r["chambre_numero"] or "")
            if recherche and not any(
                    recherche in str(v).lower() for v in ligne):
                continue
            tag = r["statut"] if r["statut"] in COULEURS_STATUT_REZ else ""
            self.tree.insert("", "end", iid=str(r["id"]), tags=(tag,), values=(
                r["id"],
                r["nom"], r["prenom"], r["telephone"],
                r["chambre_numero"] or "\u2014",
                iso_to_date_str(r["date_arrivee"]) or r["date_arrivee"],
                iso_to_date_str(r["date_depart"]) or r["date_depart"],
                r["nb_personnes"],
                r["statut"],
            ))
            total += 1

        self.compteur_var.set(f"{total} r\u00e9servation(s) affich\u00e9e(s)")

    def _on_select(self, event=None):
        selection = self.tree.selection()
        if selection:
            self.selected_reservation_id = int(selection[0])

    def _ouvrir_formulaire(self, reservation=None):
        win = tk.Toplevel(self)
        win.title("Nouvelle r\u00e9servation" if reservation is None
                  else f"Modifier r\u00e9servation #{reservation['id']}")
        win.resizable(False, False)
        win.transient(self)
        win.grab_set()

        frame = ttk.Frame(win)
        frame.pack(padx=16, pady=12)

        def row(r, label, widget_fn):
            ttk.Label(frame, text=label).grid(
                row=r, column=0, sticky="w", padx=6, pady=4)
            w = widget_fn(frame)
            w.grid(row=r, column=1, sticky="w", padx=6, pady=4)
            return w

        def entry(parent, var, width=24):
            return ttk.Entry(parent, textvariable=var, width=width)

        nom_var = tk.StringVar(value=reservation["nom"] if reservation else "")
        prenom_var = tk.StringVar(
            value=reservation["prenom"] if reservation else "")
        tel_var = tk.StringVar(
            value=reservation["telephone"] if reservation else "")
        type_id_var = tk.StringVar(
            value=reservation["type_identifiant"] if reservation
            else TYPES_IDENTIFIANT[0])
        num_id_var = tk.StringVar(
            value=reservation["numero_identifiant"] if reservation else "")
        nb_var = tk.StringVar(
            value=str(reservation["nb_personnes"]) if reservation else "1")
        notes_var = tk.StringVar(
            value=reservation["notes"] if reservation else "")
        statut_var = tk.StringVar(
            value=reservation["statut"] if reservation else "RESERVE")

        row(0, "Nom *", lambda p: entry(p, nom_var))
        row(1, "Pr\u00e9nom *", lambda p: entry(p, prenom_var))
        row(2, "T\u00e9l\u00e9phone", lambda p: entry(p, tel_var))

        ttk.Label(frame, text="Type d'identifiant").grid(
            row=3, column=0, sticky="w", padx=6, pady=4)
        ttk.Combobox(frame, textvariable=type_id_var,
                     values=TYPES_IDENTIFIANT, width=22,
                     state="readonly").grid(row=3, column=1, sticky="w",
                                            padx=6, pady=4)

        row(4, "N\u00b0 identifiant", lambda p: entry(p, num_id_var))

        ttk.Label(frame, text="Chambre").grid(
            row=5, column=0, sticky="w", padx=6, pady=4)
        chambres = get_chambres()
        chambre_map = {"\u2014 Aucune \u2014": None}
        chambre_vals = ["\u2014 Aucune \u2014"]
        for ch in chambres:
            if (ch["etat"] in ("Libre", "R\u00e9serv\u00e9e") or
                    (reservation and ch["id"] == reservation["chambre_id"])):
                texte = f"{ch['numero']} - {ch['type']} ({ch['prix']} TND)"
                chambre_map[texte] = ch["id"]
                chambre_vals.append(texte)

        chambre_var = tk.StringVar(value="\u2014 Aucune \u2014")
        if reservation and reservation["chambre_id"]:
            for t, cid in chambre_map.items():
                if cid == reservation["chambre_id"]:
                    chambre_var.set(t)
                    break

        ttk.Combobox(frame, textvariable=chambre_var, values=chambre_vals,
                     width=28, state="readonly").grid(
            row=5, column=1, sticky="w", padx=6, pady=4)

        ttk.Label(frame, text="Date d'arriv\u00e9e *").grid(
            row=6, column=0, sticky="w", padx=6, pady=4)
        date_arrivee = DateEntry(frame, width=12)
        date_arrivee.grid(row=6, column=1, sticky="w", padx=6, pady=4)
        if reservation and reservation["date_arrivee"]:
            date_arrivee.set(
                iso_to_date_str(reservation["date_arrivee"]))

        ttk.Label(frame, text="Date de d\u00e9part *").grid(
            row=7, column=0, sticky="w", padx=6, pady=4)
        date_depart = DateEntry(frame, width=12)
        date_depart.grid(row=7, column=1, sticky="w", padx=6, pady=4)
        if reservation and reservation["date_depart"]:
            date_depart.set(
                iso_to_date_str(reservation["date_depart"]))

        row(8, "Nb. personnes", lambda p: entry(p, nb_var, width=6))
        row(9, "Notes", lambda p: entry(p, notes_var, width=30))

        ttk.Label(frame, text="Statut").grid(
            row=10, column=0, sticky="w", padx=6, pady=4)
        ttk.Combobox(frame, textvariable=statut_var,
                     values=STATUTS_RESERVATION, width=22,
                     state="readonly").grid(row=10, column=1, sticky="w",
                                            padx=6, pady=4)

        def enregistrer():
            nom = nom_var.get().strip()
            prenom = prenom_var.get().strip()
            if not nom or not prenom:
                messagebox.showerror(
                    "Erreur", "Nom et Pr\u00e9nom sont obligatoires.", parent=win)
                return

            d_arr = date_str_to_iso(date_arrivee.get())
            d_dep = date_str_to_iso(date_depart.get())
            if not d_arr or not d_dep:
                messagebox.showerror(
                    "Erreur", "Dates invalides (format JJ/MM/AAAA).",
                    parent=win)
                return
            if d_dep < d_arr:
                messagebox.showerror(
                    "Erreur",
                    "La date de d\u00e9part doit \u00eatre apr\u00e8s ou \u00e9gale \u00e0 la date d'arriv\u00e9e.",
                    parent=win)
                return

            try:
                nb = int(nb_var.get())
                if nb < 1:
                    raise ValueError
            except ValueError:
                messagebox.showerror(
                    "Erreur", "Le nombre de personnes doit \u00eatre \u2265 1.",
                    parent=win)
                return

            data = {
                "nom": nom,
                "prenom": prenom,
                "telephone": tel_var.get().strip(),
                "type_identifiant": type_id_var.get(),
                "numero_identifiant": num_id_var.get().strip(),
                "chambre_id": chambre_map.get(chambre_var.get()),
                "date_arrivee": d_arr,
                "date_depart": d_dep,
                "nb_personnes": nb,
                "notes": notes_var.get().strip(),
                "statut": statut_var.get(),
            }

            if reservation is None:
                add_reservation(data)
                messagebox.showinfo("Succ\u00e8s", "R\u00e9servation ajout\u00e9e.", parent=win)
            else:
                update_reservation(reservation["id"], data)
                messagebox.showinfo("Succ\u00e8s", "R\u00e9servation modifi\u00e9e.", parent=win)

            win.destroy()
            self.refresh()
            self.app.refresh_rooms_tab()

        btn_f = ttk.Frame(win)
        btn_f.pack(pady=10)
        ttk.Button(btn_f, text="Enregistrer",
                   command=enregistrer).pack(side="left", padx=6)
        ttk.Button(btn_f, text="Annuler",
                   command=win.destroy).pack(side="left", padx=6)

    def nouvelle_reservation(self):
        self._ouvrir_formulaire(None)

    def modifier_reservation(self):
        if not self.selected_reservation_id:
            messagebox.showwarning("Attention",
                                   "Veuillez s\u00e9lectionner une r\u00e9servation.")
            return
        r = get_reservation(self.selected_reservation_id)
        if r:
            self._ouvrir_formulaire(dict(r))

    def supprimer_reservation(self):
        if not self.selected_reservation_id:
            messagebox.showwarning("Attention",
                                   "Veuillez s\u00e9lectionner une r\u00e9servation.")
            return
        r = get_reservation(self.selected_reservation_id)
        if not r:
            return
        if not messagebox.askyesno(
                "Confirmation",
                f"Supprimer la r\u00e9servation de {r['prenom']} {r['nom']} ?"):
            return
        delete_reservation(self.selected_reservation_id)
        self.selected_reservation_id = None
        self.refresh()
        self.app.refresh_rooms_tab()

    def annuler_reservation(self):
        if not self.selected_reservation_id:
            messagebox.showwarning("Attention",
                                   "Veuillez s\u00e9lectionner une r\u00e9servation.")
            return
        r = get_reservation(self.selected_reservation_id)
        if not r:
            return
        if r["statut"] == "ANNULE":
            messagebox.showinfo("Info", "Cette r\u00e9servation est d\u00e9j\u00e0 annul\u00e9e.")
            return
        if not messagebox.askyesno(
                "Confirmation",
                f"Annuler la r\u00e9servation de {r['prenom']} {r['nom']} ?"):
            return
        data = dict(r)
        data["statut"] = "ANNULE"
        update_reservation(self.selected_reservation_id, data)
        self.refresh()
        self.app.refresh_rooms_tab()

    def checkin_reservation(self):
        if not self.selected_reservation_id:
            messagebox.showwarning("Attention",
                                   "Veuillez s\u00e9lectionner une r\u00e9servation.")
            return
        r = get_reservation(self.selected_reservation_id)
        if not r:
            return
        if r["statut"] == "ANNULE":
            messagebox.showerror("Erreur",
                                 "Impossible de faire le check-in d'une r\u00e9servation annul\u00e9e.")
            return
        if not r["chambre_id"]:
            messagebox.showerror("Erreur",
                                 "Aucune chambre associ\u00e9e \u00e0 cette r\u00e9servation.")
            return
        if not messagebox.askyesno(
                "Confirmer le Check-in",
                f"Confirmer l'arriv\u00e9e de {r['prenom']} {r['nom']} "
                f"en chambre {r['chambre_numero']} ?"):
            return

        data_client = {
            "nom": r["nom"],
            "prenom": r["prenom"],
            "type_identifiant": r["type_identifiant"],
            "numero_identifiant": r["numero_identifiant"],
            "date_naissance": "",
            "lieu_naissance": "",
            "adresse": "",
            "telephone": r["telephone"],
            "venant_de": "",
            "allant_a": "",
            "chambre_id": r["chambre_id"],
            "date_entree": date.today().strftime("%Y-%m-%d"),
            "date_sortie": r["date_depart"],
            "statut": "En cours",
        }
        add_client(data_client)

        conn = get_connection()
        conn.execute("DELETE FROM reservations WHERE id=?",
                     (self.selected_reservation_id,))
        conn.commit()
        conn.close()

        self.selected_reservation_id = None
        self.refresh()
        self.app.refresh_rooms_tab()
        self.app.refresh_clients_tab()
        messagebox.showinfo(
            "Check-in effectu\u00e9",
            f"{r['prenom']} {r['nom']} est maintenant enregistr\u00e9(e) "
            f"comme client en chambre {r['chambre_numero']}.")
