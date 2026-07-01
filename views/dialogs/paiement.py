# -*- coding: utf-8 -*-

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date

from db.repository import (
    create_facture, set_facture_payee,
    set_facture_paiement_partiel, set_client_solde,
)
from views.widgets import date_str_to_iso
from services.facturation import calculer_total_et_remise


def ouvrir_paiement_dialog(tab):
    if not tab.client_var.get():
        messagebox.showwarning("Attention", "Veuillez s\u00e9lectionner un client.")
        return
    if not tab.lignes:
        messagebox.showwarning("Attention", "Aucune ligne de facturation.")
        return
    if tab.paiements.get(tab.client_var.get(), False):
        messagebox.showinfo("Information", "Cette facture est d\u00e9j\u00e0 pay\u00e9e.")
        return

    if not tab.facture_id_map.get(tab.client_var.get()):
        texte = tab.client_var.get()
        client = tab.client_map.get(texte)
        d_entree = tab.date_entree.get_date()
        d_sortie = tab.date_sortie.get_date()
        if not d_entree or not d_sortie:
            messagebox.showerror("Erreur", "Dates invalides.")
            return
        nb_nuits = max((d_sortie - d_entree).days, 1)
        try:
            remise = float(tab.remise_var.get().replace(",", "."))
        except ValueError:
            remise = 0.0
        lignes_db = [(l["description"], l["quantite"], l["prix_unitaire"]) for l in tab.lignes]
        client_id = None if client.get("is_reservation") else client["id"]
        nom_client = f"{client['prenom']} {client['nom']}".strip()
        facture_id, numero, total = create_facture(
            client_id=client_id,
            date_facture=date.today().strftime("%Y-%m-%d"),
            date_entree=date_str_to_iso(tab.date_entree.get()),
            date_sortie=date_str_to_iso(tab.date_sortie.get()),
            nb_nuits=nb_nuits,
            lignes=lignes_db,
            remise=remise,
            mode_paiement=tab.mode_var.get(),
            nom_client=nom_client,
        )
        tab.facture_id_map[tab.client_var.get()] = facture_id

    total, remise, _ = calculer_total_et_remise(tab.lignes, tab.remise_var.get())

    win = tk.Toplevel(tab)
    win.title("\U0001F4B0 Paiement de la facture")
    win.resizable(False, False)
    win.transient(tab)
    win.grab_set()

    BLEU = "#1F4E79"
    header = tk.Frame(win, bg=BLEU)
    header.pack(fill="x")
    tk.Label(header, text="Paiement de la facture", bg=BLEU, fg="white",
            font=("Segoe UI", 13, "bold")).pack(pady=12, padx=16)

    frame = ttk.Frame(win)
    frame.pack(padx=20, pady=12)

    ttk.Label(frame, text="Montant total \u00e0 payer :",
            font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky="w", pady=6)
    ttk.Label(frame, text=f"{total:.3f} TND",
            font=("Segoe UI", 12, "bold"),
            foreground="#1F4E79").grid(row=0, column=1, sticky="w", padx=12, pady=6)

    ttk.Label(frame, text="Mode de paiement :").grid(row=1, column=0, sticky="w", pady=6)
    mode_var = tk.StringVar(value=tab.mode_var.get())
    ttk.Combobox(frame, textvariable=mode_var,
                values=["Esp\u00e8ces", "Ch\u00e8que", "Carte bancaire", "Virement"],
                width=20, state="readonly").grid(row=1, column=1, sticky="w", padx=12, pady=6)

    ttk.Label(frame, text="Montant re\u00e7u (TND) :").grid(row=2, column=0, sticky="w", pady=6)
    recu_var = tk.StringVar(value=f"{total:.3f}".replace(".", ","))
    ttk.Entry(frame, textvariable=recu_var, width=15).grid(
        row=2, column=1, sticky="w", padx=12, pady=6)

    monnaie_var = tk.StringVar(value="Monnaie \u00e0 rendre : 0.000 TND")
    ttk.Label(frame, textvariable=monnaie_var,
            font=("Segoe UI", 10, "italic"),
            foreground="#1F8A4C").grid(row=3, column=0, columnspan=2, pady=6)

    def calculer_monnaie(*args):
        try:
            recu = float(recu_var.get().replace(",", "."))
            if recu >= total:
                monnaie = round(recu - total, 3)
                monnaie_var.set(f"Monnaie \u00e0 rendre : {monnaie:.3f} TND")
            else:
                solde = round(total - recu, 3)
                monnaie_var.set(f"\u26a0\ufe0f Paiement partiel \u2014 Solde restant : {solde:.3f} TND")
        except ValueError:
            monnaie_var.set("Montant re\u00e7u invalide")

    recu_var.trace_add("write", calculer_monnaie)

    def confirmer_paiement():
        try:
            recu = float(recu_var.get().replace(",", "."))
            if recu <= 0:
                messagebox.showerror("Erreur",
                    "Le montant re\u00e7u doit \u00eatre positif.", parent=win)
                return
        except ValueError:
            messagebox.showerror("Erreur", "Montant re\u00e7u invalide.", parent=win)
            return

        facture_id = tab.facture_id_map.get(tab.client_var.get())
        texte = tab.client_var.get()
        client = tab.client_map.get(texte)

        if recu >= total:
            tab.mode_var.set(mode_var.get())
            tab.paye_var.set(True)
            tab.paiements[texte] = True

            if facture_id:
                set_facture_payee(facture_id)

            if client and not client.get("is_reservation") and client.get("id"):
                set_client_solde(client["id"], 0.0)

            tab.refresh_lignes()
            tab.app.refresh_clients_tab()
            win.destroy()
            messagebox.showinfo(
                "Paiement confirm\u00e9",
                f"Paiement complet de {total:.3f} TND confirm\u00e9.\n"
                f"Mode : {mode_var.get()}\n"
                f"Monnaie rendue : {round(recu - total, 3):.3f} TND")

        else:
            solde_restant = round(total - recu, 3)

            if facture_id:
                set_facture_paiement_partiel(facture_id, recu)

            if client and not client.get("is_reservation") and client.get("id"):
                set_client_solde(client["id"], solde_restant)

            tab.paiements[texte] = "partiel"

            tab.refresh_lignes()
            tab.app.refresh_clients_tab()
            win.destroy()
            messagebox.showinfo(
                "Paiement partiel enregistr\u00e9",
                f"Montant re\u00e7u : {recu:.3f} TND\n"
                f"Solde restant : {solde_restant:.3f} TND\n"
                f"Le solde a \u00e9t\u00e9 ajout\u00e9 \u00e0 la fiche client.")

    btn_frame = ttk.Frame(win)
    btn_frame.pack(pady=12)
    ttk.Button(btn_frame, text="\u2705 Confirmer le paiement",
            command=confirmer_paiement).pack(side="left", padx=6)
    ttk.Button(btn_frame, text="Annuler",
            command=win.destroy).pack(side="left", padx=6)
