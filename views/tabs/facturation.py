# -*- coding: utf-8 -*-

import os
import tempfile
import subprocess
import platform
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import date, datetime

from db.repository import (
    get_clients, get_reservations, get_facture, get_connection,
    create_facture, set_facture_payee, get_factures, get_parametre,
)
from views.widgets import DateEntry, date_str_to_iso, iso_to_date_str, _formater_prix
from utils.num2words_fr import montant_en_lettres
from pdf.facture import generer_facture_pdf
from pdf.listes import generer_liste_factures_pdf
from services.facturation import calculer_total_et_remise
from views.dialogs.paiement import ouvrir_paiement_dialog
from views.dialogs.historique_factures import ouvrir_historique_dialog


class FacturationTab(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.lignes = []
        self.client_map = {}
        self.paiements = {}
        self.facture_id_map = {}
        self.soldes_factures = {}

        self._build_ui()
        self.refresh()

    def _build_ui(self):
        top_frame = ttk.LabelFrame(self, text="Client / S\u00e9jour")
        top_frame.pack(fill="x", padx=8, pady=8)

        ttk.Label(top_frame, text="Rechercher par CIN :").grid(
            row=0, column=0, sticky="w", padx=4, pady=4)
        self.cin_search_var = tk.StringVar()
        self.cin_search_var.trace_add("write", lambda *a: self.search_by_cin())
        cin_entry = ttk.Entry(top_frame, textvariable=self.cin_search_var, width=22)
        cin_entry.grid(row=0, column=1, padx=4, pady=4, sticky="w")

        self.client_var = tk.StringVar()
        self.combo_client = ttk.Combobox(top_frame, textvariable=self.client_var,
                                        width=70, state="readonly")
        self.combo_client.grid(row=0, column=2, padx=4, pady=4, sticky="w")
        self.combo_client.bind("<<ComboboxSelected>>", self.on_client_selected)

        ttk.Label(top_frame, text="Chambre :").grid(row=1, column=0, sticky="w",
                                                       padx=4, pady=4)
        self.chambre_label_var = tk.StringVar(value="-")
        ttk.Label(top_frame, textvariable=self.chambre_label_var).grid(
            row=1, column=1, sticky="w", padx=4, pady=4)

        ttk.Label(top_frame, text="Date d'entr\u00e9e :").grid(row=2, column=0, sticky="w",
                                                                 padx=4, pady=4)
        self.date_entree = DateEntry(top_frame, width=12)
        self.date_entree.grid(row=2, column=1, sticky="w", padx=4, pady=4)

        ttk.Label(top_frame, text="Date de sortie :").grid(row=3, column=0, sticky="w",
                                                              padx=4, pady=4)
        self.date_sortie = DateEntry(top_frame, width=12)
        self.date_sortie.grid(row=3, column=1, sticky="w", padx=4, pady=4)

        ttk.Button(top_frame, text="Recalculer h\u00e9bergement",
                   command=self.recalculer_hebergement).grid(
            row=2, column=2, rowspan=2, padx=8)

        mid_frame = ttk.LabelFrame(self, text="D\u00e9tail de la facture")
        mid_frame.pack(fill="both", expand=False, padx=8, pady=4)

        columns = ("description", "quantite", "prix", "montant", "statut")
        headers = {"description": "Description", "quantite": "Quantit\u00e9",
                "prix": "Prix unitaire (TND)", "montant": "Montant (TND)",
                "statut": "Statut paiement"}
        self.tree = ttk.Treeview(mid_frame, columns=columns, show="headings",
                                height=6)
        for c in columns:
            self.tree.heading(c, text=headers[c])
            self.tree.column(c, width=150, anchor="center")
        self.tree.column("description", width=260, anchor="w")
        self.tree.column("quantite", width=60, anchor="center")
        self.tree.column("statut", width=240, anchor="center")
        self.tree.tag_configure("paye", foreground="#1F8A4C")
        self.tree.tag_configure("non_paye", foreground="#C0392B")
        self.tree.tag_configure("partiel", foreground="#E67E22")
        self.tree.pack(fill="both", expand=True, padx=4, pady=4)

        add_frame = ttk.Frame(mid_frame)
        add_frame.pack(fill="x", padx=4, pady=4)

        ttk.Label(add_frame, text="Description").pack(side="left")
        self.desc_var = tk.StringVar()
        ttk.Entry(add_frame, textvariable=self.desc_var, width=30).pack(
            side="left", padx=4)

        ttk.Label(add_frame, text="Qt\u00e9").pack(side="left")
        self.qte_var = tk.StringVar(value="1")
        ttk.Entry(add_frame, textvariable=self.qte_var, width=6).pack(
            side="left", padx=4)

        ttk.Label(add_frame, text="Prix unit. (TND)").pack(side="left")
        self.prix_var = tk.StringVar(value="0,000")
        self.prix_entry = ttk.Entry(add_frame, textvariable=self.prix_var, width=10)
        self.prix_entry.pack(side="left", padx=4)
        self.prix_entry.bind("<FocusOut>", lambda e: _formater_prix(self.prix_var))

        ttk.Button(add_frame, text="Ajouter ligne",
                   command=self.ajouter_ligne).pack(side="left", padx=8)
        ttk.Button(add_frame, text="Supprimer ligne s\u00e9lectionn\u00e9e",
                   command=self.supprimer_ligne).pack(side="left", padx=4)

        bottom_frame = ttk.LabelFrame(self, text="Totaux et validation")
        bottom_frame.pack(fill="x", padx=8, pady=8)

        ttk.Label(bottom_frame, text="Remise (TND) :").grid(
            row=0, column=0, sticky="w", padx=4, pady=4)
        self.remise_var = tk.StringVar(value="0,000")
        self.remise_var.trace_add("write", lambda *a: self.update_total())
        self.remise_entry = ttk.Entry(bottom_frame, textvariable=self.remise_var, width=10)
        self.remise_entry.grid(row=0, column=1, sticky="w", padx=4, pady=4)
        self.remise_entry.bind("<FocusOut>", lambda e: _formater_prix(self.remise_var))

        ttk.Label(bottom_frame, text="Mode de paiement :").grid(
            row=0, column=2, sticky="w", padx=4, pady=4)
        self.mode_var = tk.StringVar(value="Esp\u00e8ces")
        ttk.Combobox(bottom_frame, textvariable=self.mode_var,
                     values=["Esp\u00e8ces", "Ch\u00e8que", "Carte bancaire", "Virement"],
                     width=15, state="readonly").grid(row=0, column=3, padx=4, pady=4)

        self.total_var = tk.StringVar(value="Total : 0.000 TND")
        ttk.Label(bottom_frame, textvariable=self.total_var,
                font=("Segoe UI", 12, "bold")).grid(
            row=0, column=4, padx=20, pady=4)
        ttk.Button(bottom_frame, text="\U0001F4B0 Payer",
                command=self.ouvrir_paiement).grid(
            row=0, column=5, padx=8, pady=4)

        self.lettres_var = tk.StringVar(value="")
        ttk.Label(bottom_frame, textvariable=self.lettres_var,
                  wraplength=700, font=("Segoe UI", 9, "italic")).grid(
            row=1, column=0, columnspan=5, sticky="w", padx=4, pady=2)

        self.paye_var = tk.BooleanVar(value=False)
        self.check_paye = ttk.Checkbutton(
            bottom_frame, text="\u2705 Facture pay\u00e9e",
            variable=self.paye_var,
            command=self.on_toggle_paye
        )
        self.check_paye.grid(row=2, column=0, columnspan=2, sticky="w", padx=4, pady=4)

        action_frame = ttk.Frame(bottom_frame)
        action_frame.grid(row=3, column=0, columnspan=5, pady=8)
        ttk.Button(action_frame, text="G\u00e9n\u00e9rer la facture",
                   command=self.generer_facture).pack(side="left", padx=4)
        ttk.Button(action_frame, text="R\u00e9initialiser",
                   command=self.reinitialiser).pack(side="left", padx=4)
        ttk.Button(action_frame, text="\U0001F4CB Historique des factures",
                   command=self.ouvrir_historique).pack(side="left", padx=4)
        ttk.Button(action_frame, text="\U0001F441\ufe0f Voir la facture",
                   command=self.voir_facture_client).pack(side="left", padx=4)

    def refresh(self):
        self.client_map = {}
        valeurs = []

        for c in get_clients("En cours"):
            if not c["chambre_id"]:
                continue
            texte = (f"[CLIENT] {c['nom']} {c['prenom']} - Chambre "
                     f"{c['chambre_numero']} ({c['numero_identifiant']})")
            self.client_map[texte] = {
                "id": c["id"],
                "nom": c["nom"],
                "prenom": c["prenom"],
                "numero_identifiant": c["numero_identifiant"],
                "type_identifiant": c["type_identifiant"],
                "adresse": c["adresse"],
                "chambre_id": c["chambre_id"],
                "chambre_numero": c["chambre_numero"],
                "chambre_prix": c["chambre_prix"],
                "date_entree": c["date_entree"],
                "date_sortie": c["date_sortie"],
                "is_reservation": False,
            }
            valeurs.append(texte)

        for r in get_reservations("RESERVE"):
            if not r["chambre_id"]:
                continue
            texte = (f"[R\u00c9SERV.] {r['nom']} {r['prenom']} - Chambre "
                     f"{r['chambre_numero']} ({r['numero_identifiant'] or 'sans ID'})")
            self.client_map[texte] = {
                "id": r["id"],
                "nom": r["nom"],
                "prenom": r["prenom"],
                "numero_identifiant": r["numero_identifiant"],
                "type_identifiant": r["type_identifiant"],
                "adresse": "",
                "chambre_id": r["chambre_id"],
                "chambre_numero": r["chambre_numero"],
                "chambre_prix": r["chambre_prix"],
                "date_entree": r["date_arrivee"],
                "date_sortie": r["date_depart"],
                "is_reservation": True,
            }
            valeurs.append(texte)

        if self.client_var.get() not in valeurs:
            self.client_var.set("")
            self.chambre_label_var.set("-")
        self.combo_client["values"] = valeurs

        self.refresh_historique()

        self.paiements = {}
        self.facture_id_map = {}
        self.soldes_factures = {}
        conn = get_connection()

        factures_payees = conn.execute(
            "SELECT id, client_id, nom_client FROM factures WHERE payee=1"
        ).fetchall()

        factures_partielles = conn.execute(
            "SELECT id, client_id, nom_client, montant_total, montant_paye "
            "FROM factures WHERE payee=0 AND montant_paye>0"
        ).fetchall()

        conn.close()

        for f in factures_payees:
            for texte, c in self.client_map.items():
                nom_c = f"{c.get('prenom', '')} {c.get('nom', '')}".strip()
                if (not c.get("is_reservation") and c.get("id") and c["id"] == f["client_id"]) \
                or (f["nom_client"] and f["nom_client"].strip() == nom_c):
                    self.paiements[texte] = True
                    self.facture_id_map[texte] = f["id"]
                    break

        for f in factures_partielles:
            for texte, c in self.client_map.items():
                nom_c = f"{c.get('prenom', '')} {c.get('nom', '')}".strip()
                if (not c.get("is_reservation") and c.get("id") and c["id"] == f["client_id"]) \
                or (f["nom_client"] and f["nom_client"].strip() == nom_c):
                    self.paiements[texte] = "partiel"
                    self.facture_id_map[texte] = f["id"]
                    self.soldes_factures[texte] = round(
                        f["montant_total"] - f["montant_paye"], 3)
                    break

    def search_by_cin(self):
        cin = self.cin_search_var.get().strip()
        if not cin:
            self.combo_client["values"] = []
            self.client_var.set("")
            self.chambre_label_var.set("-")
            return

        resultats = [texte for texte, c in self.client_map.items()
                    if cin.lower() in str(c.get("numero_identifiant", "")).lower()]

        self.combo_client["values"] = resultats

        if len(resultats) == 1:
            self.client_var.set(resultats[0])
            self.on_client_selected()
        else:
            self.client_var.set("")

    def _filtrer_clients(self):
        recherche = self.search_client_var.get().strip().lower()
        if not recherche:
            self.combo_client["values"] = list(self.client_map.keys())
            return

        filtres = [
            texte for texte, c in self.client_map.items()
            if recherche in str(c.get("numero_identifiant", "")).lower()
        ]
        self.combo_client["values"] = filtres

        if len(filtres) == 1:
            self.client_var.set(filtres[0])
            self.on_client_selected()
        elif len(filtres) == 0:
            self.client_var.set("")
            self.chambre_label_var.set("-")

    def refresh_historique(self):
        pass

    def on_client_selected(self, event=None):
        texte = self.client_var.get()
        statut = self.paiements.get(texte, False)
        self.paye_var.set(statut is True)
        client = self.client_map.get(texte)
        if not client:
            return

        prefix = "\U0001F4CB R\u00e9servation" if client.get("is_reservation") else "\U0001F464 Client"
        self.chambre_label_var.set(
            f"{prefix} \u2014 Chambre {client['chambre_numero']} "
            f"({client['chambre_prix']:.3f} TND / nuit)")

        if client["date_entree"]:
            self.date_entree.set(iso_to_date_str(client["date_entree"]))
        else:
            self.date_entree.set_date(date.today())

        if client["date_sortie"]:
            self.date_sortie.set(iso_to_date_str(client["date_sortie"]))
        else:
            self.date_sortie.set_date(date.today())

        texte_client = self.client_var.get()
        facture_id = self.facture_id_map.get(texte_client)
        if facture_id:
            _, lignes_db = get_facture(facture_id)
            self.lignes = [{
                "description": l["description"],
                "quantite": l["quantite"],
                "prix_unitaire": l["prix_unitaire"],
                "auto": True,
            } for l in lignes_db]
            self.refresh_lignes()
        else:
            self.recalculer_hebergement()

    def recalculer_hebergement(self):
        if self.paiements.get(self.client_var.get(), False):
            return
        texte = self.client_var.get()
        client = self.client_map.get(texte)
        if not client:
            messagebox.showwarning("Attention", "Veuillez d'abord s\u00e9lectionner un client.")
            return

        d_entree = self.date_entree.get_date()
        d_sortie = self.date_sortie.get_date()
        if not d_entree or not d_sortie:
            messagebox.showerror("Erreur", "Dates invalides (format JJ/MM/AAAA).")
            return

        nb_nuits = (d_sortie - d_entree).days
        if nb_nuits < 1:
            nb_nuits = 1

        prix_chambre = client["chambre_prix"]

        self.lignes = [l for l in self.lignes if not l.get("auto")]

        description = (f"H\u00e9bergement - Chambre {client['chambre_numero']} "
                        f"({nb_nuits} nuit{'s' if nb_nuits > 1 else ''})")
        self.lignes.insert(0, {
            "description": description,
            "quantite": nb_nuits,
            "prix_unitaire": prix_chambre,
            "auto": True,
        })
        self.refresh_lignes()

    def refresh_lignes(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        statut_paiement = self.paiements.get(self.client_var.get(), False)

        if statut_paiement == True:
            statut_texte = "\u2705 Pay\u00e9e"
            tag = "paye"
        elif statut_paiement == "partiel":
            solde = self.soldes_factures.get(self.client_var.get(), 0.0)
            statut_texte = f"\u26a0\ufe0f Partiellement pay\u00e9e - Reste {solde:.3f} TND".replace(".", ",")
            tag = "partiel"
        else:
            statut_texte = "\u23f3 En attente"
            tag = "non_paye"

        for index, ligne in enumerate(self.lignes):
            montant = ligne["quantite"] * ligne["prix_unitaire"]
            self.tree.insert("", "end", iid=str(index), values=(
                ligne["description"], f"{ligne['quantite']:g}",
                f"{ligne['prix_unitaire']:.3f}".replace(".", ","),
                f"{montant:.3f}".replace(".", ","),
                statut_texte,
            ), tags=(tag,))
        self.update_total()

    def _verifier_paye(self):
        if self.paiements.get(self.client_var.get(), False):
            messagebox.showwarning(
                "Action impossible",
                "Cette facture est d\u00e9j\u00e0 marqu\u00e9e comme pay\u00e9e.\n"
                "Aucune modification n'est autoris\u00e9e.")
            return True
        return False

    def ajouter_ligne(self):
        if self._verifier_paye():
            return
        description = self.desc_var.get().strip()
        if not description:
            messagebox.showerror("Erreur", "La description est obligatoire.")
            return
        try:
            quantite = float(self.qte_var.get().replace(",", "."))
            prix = float(self.prix_var.get().replace(",", "."))
        except ValueError:
            messagebox.showerror("Erreur", "Quantit\u00e9 et prix doivent \u00eatre num\u00e9riques.")
            return

        self.lignes.append({
            "description": description,
            "quantite": quantite,
            "prix_unitaire": prix,
            "auto": False,
        })
        self.desc_var.set("")
        self.qte_var.set("1")
        self.prix_var.set("0,000")
        self.refresh_lignes()

    def supprimer_ligne(self):
        if self._verifier_paye():
            return
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("Attention", "Veuillez s\u00e9lectionner une ligne.")
            return
        index = int(selection[0])
        del self.lignes[index]
        self.refresh_lignes()

    def update_total(self):
        total, _, _ = calculer_total_et_remise(self.lignes, self.remise_var.get())
        self.total_var.set(f"Total : {total:.3f} TND")
        if total > 0:
            self.lettres_var.set(
                "Arr\u00eat\u00e9e la pr\u00e9sente facture \u00e0 la somme de : "
                + montant_en_lettres(total))
        else:
            self.lettres_var.set("")

    def reinitialiser(self):
        self.client_var.set("")
        self.chambre_label_var.set("-")
        self.lignes = []
        self.remise_var.set("0,000")
        self.mode_var.set("Esp\u00e8ces")
        self.paye_var.set(False)
        self.refresh_lignes()

    def on_toggle_paye(self):
        if self.paye_var.get():
            confirme = messagebox.askyesno(
                "Confirmer le paiement",
                "Confirmez-vous que cette facture a \u00e9t\u00e9 pay\u00e9e ?\n"
                "Cette action ne pourra pas \u00eatre annul\u00e9e.")
            if not confirme:
                self.paye_var.set(False)
            else:
                self.paiements[self.client_var.get()] = True
                facture_id = self.facture_id_map.get(self.client_var.get())
                if facture_id:
                    set_facture_payee(facture_id)
                self.refresh_lignes()
        else:
            messagebox.showwarning(
                "Action impossible",
                "Une facture marqu\u00e9e comme pay\u00e9e ne peut plus \u00eatre modifi\u00e9e.")
            self.paye_var.set(True)

    def generer_facture(self):
        texte = self.client_var.get()
        client = self.client_map.get(texte)
        if not client:
            messagebox.showerror("Erreur", "Veuillez s\u00e9lectionner un client.")
            return
        if not self.lignes:
            messagebox.showerror("Erreur", "Aucune ligne de facturation.")
            return

        d_entree = self.date_entree.get_date()
        d_sortie = self.date_sortie.get_date()
        if not d_entree or not d_sortie:
            messagebox.showerror("Erreur", "Dates invalides (format JJ/MM/AAAA).")
            return
        nb_nuits = max((d_sortie - d_entree).days, 1)

        try:
            remise = float(self.remise_var.get().replace(",", "."))
        except ValueError:
            remise = 0.0

        lignes_db = [(l["description"], l["quantite"], l["prix_unitaire"])
                     for l in self.lignes]

        client_id = None if client.get("is_reservation") else client["id"]
        nom_client = f"{client['prenom']} {client['nom']}".strip()

        facture_id, numero, total = create_facture(
            client_id=client_id,
            date_facture=date.today().strftime("%Y-%m-%d"),
            date_entree=date_str_to_iso(self.date_entree.get()),
            date_sortie=date_str_to_iso(self.date_sortie.get()),
            nb_nuits=nb_nuits,
            lignes=lignes_db,
            remise=remise,
            mode_paiement=self.mode_var.get(),
            nom_client=nom_client,
        )

        self.derniere_facture_id = facture_id
        self.derniere_facture_numero = numero
        self.derniere_facture_total = total
        self.facture_id_map[self.client_var.get()] = facture_id
        if self.paye_var.get():
            set_facture_payee(facture_id)
            self.paiements[self.client_var.get()] = True

        statut_paiement = "\u2705 Pay\u00e9e" if self.paye_var.get() else "\u23f3 En attente de paiement"
        messagebox.showinfo(
            "Facture cr\u00e9\u00e9e",
            f"Facture {numero} cr\u00e9\u00e9e avec succ\u00e8s.\n"
            f"Total : {total:.3f} TND\n"
            f"Statut : {statut_paiement}")

        self.refresh_historique()
        self.app.refresh_stats_tab()

        if messagebox.askyesno("Export PDF",
                                "Voulez-vous g\u00e9n\u00e9rer le PDF de cette facture ?"):
            self._exporter_pdf(facture_id, numero)

    def _exporter_pdf(self, facture_id, numero):
        nom_fichier_defaut = f"Facture_{numero}.pdf"
        chemin = filedialog.asksaveasfilename(
            title="Enregistrer la facture",
            defaultextension=".pdf",
            initialfile=nom_fichier_defaut,
            filetypes=[("Fichier PDF", "*.pdf")],
        )
        if not chemin:
            return
        try:
            generer_facture_pdf(facture_id, chemin)
        except Exception as exc:
            messagebox.showerror("Erreur", f"Impossible de g\u00e9n\u00e9rer le PDF : {exc}")
            return

        messagebox.showinfo("Succ\u00e8s", f"Facture export\u00e9e : {chemin}")

        try:
            if os.name == "nt":
                os.startfile(chemin)
        except Exception:
            pass

    def ouvrir_historique(self):
        ouvrir_historique_dialog(self)

    def _voir_depuis_historique(self, hist_tree):
        selection = hist_tree.selection()
        if not selection:
            messagebox.showwarning("Attention",
                                "Veuillez s\u00e9lectionner une facture.")
            return
        facture_id = int(selection[0])
        facture, lignes = get_facture(facture_id)
        if facture is None:
            messagebox.showerror("Erreur", "Facture introuvable en base.")
            return

        est_paye = bool(facture["payee"]) if "payee" in facture.keys() else False
        self._afficher_fenetre_facture(facture, lignes, facture_id)

    def _exporter_depuis_historique(self, hist_tree):
        selection = hist_tree.selection()
        if not selection:
            messagebox.showwarning("Attention",
                                "Veuillez s\u00e9lectionner une facture.")
            return
        facture_id = int(selection[0])
        facture, _ = get_facture(facture_id)
        if facture is None:
            return
        if not messagebox.askyesno(
                "Confirmation",
                "Confirmez-vous que cette facture a bien \u00e9t\u00e9 pay\u00e9e ?"):
            messagebox.showwarning(
                "PDF non disponible",
                "Le PDF ne peut \u00eatre g\u00e9n\u00e9r\u00e9 que pour une facture pay\u00e9e.")
            return
        self._exporter_pdf(facture_id, facture["numero"])

    def _imprimer_liste_factures(self, hist_tree):
        items = hist_tree.get_children()
        if not items:
            messagebox.showwarning("Attention", "Aucune facture \u00e0 imprimer.")
            return

        factures_data = []
        for iid in items:
            valeurs = hist_tree.item(iid)["values"]
            numero, date_f, client, identifiant, total_str, statut = valeurs[1:]
            try:
                montant = float(str(total_str).replace(",", "."))
            except ValueError:
                montant = 0.0
            factures_data.append((numero, date_f, client, identifiant, montant, statut))

        nom_fichier_defaut = f"Liste_factures_{date.today().strftime('%Y%m%d')}.pdf"
        chemin = filedialog.asksaveasfilename(
            title="Enregistrer la liste des factures",
            defaultextension=".pdf",
            initialfile=nom_fichier_defaut,
            filetypes=[("Fichier PDF", "*.pdf")],
        )
        if not chemin:
            return

        try:
            generer_liste_factures_pdf(factures_data, chemin)
        except Exception as exc:
            messagebox.showerror("Erreur", f"Impossible de g\u00e9n\u00e9rer le PDF : {exc}")
            return

        messagebox.showinfo("Succ\u00e8s", f"Liste export\u00e9e : {chemin}")
        try:
            if os.name == "nt":
                os.startfile(chemin)
        except Exception:
            pass

    def ouvrir_paiement(self):
        ouvrir_paiement_dialog(self)

    def voir_facture_client(self):
        texte = self.client_var.get()
        if not texte:
            messagebox.showwarning("Attention", "Veuillez s\u00e9lectionner un client.")
            return

        facture_id = self.facture_id_map.get(texte)
        if not facture_id:
            messagebox.showwarning(
                "Aucune facture",
                "Aucune facture trouv\u00e9e pour ce client.\n"
                "G\u00e9n\u00e9rez d'abord la facture.")
            return

        facture, lignes = get_facture(facture_id)
        if facture is None:
            messagebox.showerror("Erreur", "Facture introuvable en base.")
            return

        self._afficher_fenetre_facture(facture, lignes, facture_id)

    def _afficher_fenetre_facture(self, facture, lignes, facture_id):
        nom_fichier = f"Facture_{facture['numero']}.pdf"
        chemin = os.path.join(tempfile.gettempdir(), nom_fichier)

        try:
            generer_facture_pdf(facture_id, chemin)
        except Exception as exc:
            messagebox.showerror("Erreur", f"Impossible de g\u00e9n\u00e9rer l'aper\u00e7u : {exc}")
            return

        try:
            if platform.system() == "Windows":
                os.startfile(chemin)
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", chemin])
            else:
                subprocess.Popen(["xdg-open", chemin])
        except Exception as exc:
            messagebox.showerror(
                "Erreur",
                f"Impossible d'ouvrir le PDF automatiquement.\n"
                f"Fichier disponible ici :\n{chemin}")
