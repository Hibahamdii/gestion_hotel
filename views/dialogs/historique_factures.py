# -*- coding: utf-8 -*-

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date

from db.repository import get_factures, get_connection
from views.widgets import DateEntry, date_str_to_iso, iso_to_date_str


def ouvrir_historique_dialog(tab):
    win = tk.Toplevel(tab)
    win.title("Historique des factures")
    win.geometry("1100x700")
    win.transient(tab)

    filtre_frame = ttk.LabelFrame(win, text="Filtres")
    filtre_frame.pack(fill="x", padx=8, pady=8)

    ttk.Label(filtre_frame, text="Crit\u00e8re :").grid(row=0, column=0, padx=6, pady=6, sticky="w")
    critere_var = tk.StringVar(value="Toutes les factures")
    combo_critere = ttk.Combobox(
        filtre_frame, textvariable=critere_var,
        values=["Toutes les factures", "Par date", "Par N\u00b0 identifiant client"],
        width=25, state="readonly"
    )
    combo_critere.grid(row=0, column=1, padx=6, pady=6, sticky="w")

    lbl_debut = ttk.Label(filtre_frame, text="Du :")
    date_debut = DateEntry(filtre_frame, width=12)
    lbl_fin = ttk.Label(filtre_frame, text="Au :")
    date_fin = DateEntry(filtre_frame, width=12)
    date_debut.set_date(date.today().replace(day=1))

    lbl_cin = ttk.Label(filtre_frame, text="N\u00b0 identifiant :")
    cin_var = tk.StringVar()
    entry_cin = ttk.Entry(filtre_frame, textvariable=cin_var, width=22)

    ttk.Button(
        filtre_frame, text="\U0001F50D Filtrer",
        command=lambda: appliquer_filtre()
    ).grid(row=0, column=6, padx=12, pady=6)

    def on_critere_change(*args):
        for w in (lbl_debut, date_debut, lbl_fin, date_fin, lbl_cin, entry_cin):
            w.grid_remove()

        c = critere_var.get()
        if c == "Par date":
            lbl_debut.grid(row=0, column=2, padx=4, pady=6, sticky="w")
            date_debut.grid(row=0, column=3, padx=4, pady=6, sticky="w")
            lbl_fin.grid(row=0, column=4, padx=4, pady=6, sticky="w")
            date_fin.grid(row=0, column=5, padx=4, pady=6, sticky="w")
        elif c == "Par N\u00b0 identifiant client":
            lbl_cin.grid(row=0, column=2, padx=4, pady=6, sticky="w")
            entry_cin.grid(row=0, column=3, padx=4, pady=6, sticky="w")

    critere_var.trace_add("write", on_critere_change)

    hist_columns = ("id", "numero", "date", "client", "identifiant", "total", "statut")
    headers_h = {
        "id": "ID", "numero": "N\u00b0 Facture", "date": "Date",
        "client": "Client", "identifiant": "N\u00b0 Identifiant",
        "total": "Montant (TND)", "statut": "Statut"
    }

    frame = ttk.Frame(win)
    frame.pack(fill="both", expand=True, padx=8, pady=4)

    hist_tree = ttk.Treeview(frame, columns=hist_columns, show="headings", height=18)
    for c in hist_columns:
        hist_tree.heading(c, text=headers_h[c])
        hist_tree.column(c, width=100, anchor="center")
    hist_tree.column("client", width=180, anchor="w")
    hist_tree.column("identifiant", width=130, anchor="w")
    hist_tree.column("numero", width=120, anchor="center")
    hist_tree.tag_configure("paye", foreground="#1F8A4C")
    hist_tree.tag_configure("non_paye", foreground="#C0392B")

    scrollbar = ttk.Scrollbar(frame, orient="vertical", command=hist_tree.yview)
    hist_tree.configure(yscrollcommand=scrollbar.set)
    hist_tree.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    compteur_var = tk.StringVar()
    ttk.Label(win, textvariable=compteur_var,
            font=("Segoe UI", 9, "italic")).pack(anchor="e", padx=8)

    def appliquer_filtre():
        for item in hist_tree.get_children():
            hist_tree.delete(item)

        c = critere_var.get()

        if c == "Toutes les factures":
            factures = get_factures()
        elif c == "Par date":
            debut = date_str_to_iso(date_debut.get()) or "0000-01-01"
            fin = date_str_to_iso(date_fin.get()) or "9999-12-31"
            factures = get_factures(debut, fin)
        elif c == "Par N\u00b0 identifiant client":
            cin = cin_var.get().strip().lower()
            if not cin:
                messagebox.showwarning(
                    "Attention", "Veuillez saisir un num\u00e9ro d'identifiant.", parent=win)
                return
            toutes = get_factures()
            conn = get_connection()
            factures = []
            for f in toutes:
                if f["client_id"]:
                    client_row = conn.execute(
                        "SELECT numero_identifiant FROM clients WHERE id=?",
                        (f["client_id"],)
                    ).fetchone()
                    if client_row and cin in str(client_row["numero_identifiant"]).lower():
                        factures.append(f)
                else:
                    if cin in str(f["nom_client"] or "").lower():
                        factures.append(f)
            conn.close()
        else:
            factures = get_factures()

        for f in factures:
            client_nom = f"{f['prenom'] or ''} {f['nom'] or ''}".strip()
            if not client_nom:
                client_nom = f["nom_client"] or "\u2014"

            identifiant = "\u2014"
            if f["client_id"]:
                conn = get_connection()
                row = conn.execute(
                    "SELECT numero_identifiant FROM clients WHERE id=?",
                    (f["client_id"],)
                ).fetchone()
                conn.close()
                if row:
                    identifiant = row["numero_identifiant"]

            est_paye = bool(f["payee"]) if "payee" in f.keys() else False
            statut_txt = "\u2705 Pay\u00e9e" if est_paye else "\u23f3 En attente"
            tag = "paye" if est_paye else "non_paye"

            hist_tree.insert("", "end", iid=str(f["id"]), tags=(tag,), values=(
                f["id"], f["numero"],
                iso_to_date_str(f["date_facture"]) or f["date_facture"],
                client_nom, identifiant,
                f"{f['montant_total']:.3f}",
                statut_txt,
            ))

        nb = len(hist_tree.get_children())
        compteur_var.set(f"{nb} facture(s) trouv\u00e9e(s)")

    appliquer_filtre()

    btn_frame = ttk.Frame(win)
    btn_frame.pack(pady=6)
    ttk.Button(
        btn_frame, text="\U0001F441\ufe0f Voir la facture",
        command=lambda: tab._voir_depuis_historique(hist_tree)
    ).pack(side="left", padx=4)
    ttk.Button(
        btn_frame, text="\U0001F4C4 Exporter en PDF",
        command=lambda: tab._exporter_depuis_historique(hist_tree)
    ).pack(side="left", padx=4)
    ttk.Button(
        btn_frame, text="\U0001F5A8\ufe0f Imprimer la liste",
        command=lambda: tab._imprimer_liste_factures(hist_tree)
    ).pack(side="left", padx=4)
    ttk.Button(btn_frame, text="Fermer",
            command=win.destroy).pack(side="left", padx=4)
