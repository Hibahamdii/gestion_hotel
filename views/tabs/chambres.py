# -*- coding: utf-8 -*-

import tkinter as tk
from tkinter import ttk, messagebox
from datetime import date, datetime

from db.repository import (
    get_chambres, get_connection, add_chambre,
    update_chambre, delete_chambre, taux_occupation,
)
from models.enums import ETATS_CHAMBRE, COULEURS_ETAT
from views.widgets import iso_to_date_str, _formater_prix

COULEUR_TEXTE = "#FFFFFF"


class RoomsTab(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.selected_chambre_id = None

        self._build_ui()
        self.refresh()

    def _build_ui(self):
        legend_frame = ttk.Frame(self)
        legend_frame.pack(fill="x", padx=8, pady=(8, 0))

        ttk.Label(legend_frame, text="L\u00e9gende :",
                  font=("Segoe UI", 10, "bold")).pack(side="left", padx=(0, 10))
        for etat, couleur in COULEURS_ETAT.items():
            carre = tk.Label(legend_frame, text="  ", bg=couleur)
            carre.pack(side="left", padx=(0, 4))
            ttk.Label(legend_frame, text=etat).pack(side="left", padx=(0, 12))

        ttk.Button(legend_frame, text="+ Ajouter une chambre",
                   command=self.ajouter_chambre).pack(side="right")

        canvas_frame = ttk.Frame(self)
        canvas_frame.pack(fill="both", expand=True, padx=8, pady=8)

        self.canvas = tk.Canvas(canvas_frame, bg="#F5F5F5",
                                 highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical",
                                        command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        self.grid_frame = tk.Frame(self.canvas, bg="#F5F5F5")
        self.grid_window = self.canvas.create_window(
            (0, 0), window=self.grid_frame, anchor="nw")

        self.grid_frame.bind("<Configure>", self._on_frame_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        self.recap_var = tk.StringVar()
        ttk.Label(self, textvariable=self.recap_var,
                  font=("Segoe UI", 10, "bold")).pack(pady=(0, 8))

    def _on_frame_configure(self, event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self.canvas.itemconfig(self.grid_window, width=event.width)

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def refresh(self):
        for widget in self.grid_frame.winfo_children():
            widget.destroy()

        chambres = get_chambres()

        nb_colonnes = 4
        row_index = 0
        col = 0
        etage_courant = None

        for ch in chambres:
            etage = ch["numero"].split("-")[0] if "-" in ch["numero"] else "?"

            if etage != etage_courant:
                etage_courant = etage
                if row_index > 0:
                    row_index += 1
                lbl_etage = tk.Label(
                    self.grid_frame, text=f"\u00c9tage {etage_courant}",
                    bg="#F5F5F5", fg="#1F4E79",
                    font=("Segoe UI", 12, "bold"), anchor="w")
                lbl_etage.grid(row=row_index, column=0, columnspan=nb_colonnes,
                                sticky="w", padx=4, pady=(10, 4))
                row_index += 1
                col = 0

            self._creer_tile(ch, row_index, col)
            col += 1
            if col >= nb_colonnes:
                col = 0
                row_index += 1

        for c in range(nb_colonnes):
            self.grid_frame.grid_columnconfigure(c, weight=1)

        occ, total = taux_occupation()
        libre = total - occ
        self.recap_var.set(
            f"Total chambres : {total}   |   Occup\u00e9es : {occ}   |   "
            f"Libres : {libre}   |   Taux d'occupation : "
            f"{(occ / total * 100) if total else 0:.1f} %"
        )

    def _creer_tile(self, chambre, row, col):
        couleur = COULEURS_ETAT.get(chambre["etat"], "#BDBDBD")

        tile = tk.Frame(self.grid_frame, bg=couleur, bd=2, relief="raised",
                        width=160, height=110)
        tile.grid(row=row, column=col, padx=8, pady=8, sticky="nsew")
        tile.grid_propagate(False)

        lbl_numero = tk.Label(tile, text=f"Chambre {chambre['numero']}",
                               bg=couleur, fg=COULEUR_TEXTE,
                               font=("Segoe UI", 12, "bold"))
        lbl_numero.pack(pady=(10, 2))

        lbl_type = tk.Label(tile, text=chambre["type"], bg=couleur,
                             fg=COULEUR_TEXTE, font=("Segoe UI", 10))
        lbl_type.pack()

        lbl_prix = tk.Label(tile, text=f"{chambre['prix']:.3f} TND / nuit",
                             bg=couleur, fg=COULEUR_TEXTE,
                             font=("Segoe UI", 9))
        lbl_prix.pack()

        lbl_etat = tk.Label(tile, text=chambre["etat"], bg=couleur,
                             fg=COULEUR_TEXTE, font=("Segoe UI", 9, "italic"))
        lbl_etat.pack(pady=(2, 6))

        for widget in (tile, lbl_numero, lbl_type, lbl_prix, lbl_etat):
            widget.bind("<Button-1>",
                        lambda e, c=chambre: self.ouvrir_details(c))
            if chambre["etat"] in ("Occup\u00e9e", "R\u00e9serv\u00e9e"):
                widget.bind("<Button-3>",
                            lambda e, c=chambre: self.afficher_occupant(c))

    def afficher_occupant(self, chambre):
        win = tk.Toplevel(self)
        win.title(f"Chambre {chambre['numero']} \u2014 D\u00e9tails occupation")
        win.resizable(False, False)
        win.transient(self)
        win.grab_set()

        BLEU = "#2C3E6B"
        header = tk.Frame(win, bg=BLEU)
        header.pack(fill="x")
        tk.Label(
            header,
            text=f"Chambre {chambre['numero']} \u2014 {chambre['etat']}",
            bg=BLEU, fg="white",
            font=("Segoe UI", 13, "bold")
        ).pack(pady=12, padx=16)

        frame = ttk.Frame(win)
        frame.pack(padx=16, pady=12)

        def ligne(label, valeur, row):
            ttk.Label(frame, text=label,
                      font=("Segoe UI", 9, "bold")).grid(
                row=row, column=0, sticky="w", padx=6, pady=3)
            ttk.Label(frame, text=valeur or "\u2014").grid(
                row=row, column=1, sticky="w", padx=6, pady=3)

        if chambre["etat"] == "Occup\u00e9e":
            conn = get_connection()
            client = conn.execute(
                """
                SELECT c.*, ch.numero AS chambre_numero
                FROM clients c
                JOIN chambres ch ON ch.id = c.chambre_id
                WHERE c.chambre_id = ? AND c.statut = 'En cours'
                ORDER BY c.id DESC LIMIT 1
                """, (chambre["id"],)
            ).fetchone()
            conn.close()

            if client:
                ligne("Nom", f"{client['prenom']} {client['nom']}", 0)
                ligne("Identifiant",
                      f"{client['type_identifiant']} : {client['numero_identifiant']}", 1)
                ligne("T\u00e9l\u00e9phone", client["telephone"], 2)
                ligne("Venant de", client["venant_de"], 3)
                ligne("Allant \u00e0", client["allant_a"], 4)
                ligne("Date d'entr\u00e9e",
                      iso_to_date_str(client["date_entree"]) or client["date_entree"], 5)
                ligne("Date de sortie pr\u00e9vue",
                      iso_to_date_str(client["date_sortie"]) or client["date_sortie"], 6)

                try:
                    sortie = datetime.strptime(client["date_sortie"], "%Y-%m-%d").date()
                    restant = (sortie - date.today()).days
                    texte = f"{restant} nuit(s)" if restant > 0 else "D\u00e9part pr\u00e9vu aujourd'hui"
                    ligne("Nuits restantes", texte, 7)
                except Exception:
                    pass
            else:
                ttk.Label(frame, text="Aucun client trouv\u00e9.").grid(
                    row=0, column=0, columnspan=2, pady=8)

        elif chambre["etat"] == "R\u00e9serv\u00e9e":
            conn = get_connection()
            rez = conn.execute(
                """
                SELECT * FROM reservations
                WHERE chambre_id = ? AND statut = 'RESERVE'
                ORDER BY date_arrivee ASC LIMIT 1
                """, (chambre["id"],)
            ).fetchone()
            conn.close()

            if rez:
                ligne("Nom", f"{rez['prenom']} {rez['nom']}", 0)
                ligne("T\u00e9l\u00e9phone", rez["telephone"], 1)
                ligne("Identifiant",
                      f"{rez['type_identifiant']} : {rez['numero_identifiant']}", 2)
                ligne("Nb. personnes", str(rez["nb_personnes"]), 3)
                ligne("Date d'arriv\u00e9e",
                      iso_to_date_str(rez["date_arrivee"]) or rez["date_arrivee"], 4)
                ligne("Date de d\u00e9part",
                      iso_to_date_str(rez["date_depart"]) or rez["date_depart"], 5)
                ligne("Notes", rez["notes"], 6)

                try:
                    arrivee = datetime.strptime(rez["date_arrivee"], "%Y-%m-%d").date()
                    jours = (arrivee - date.today()).days
                    if jours > 0:
                        texte = f"Dans {jours} jour(s)"
                    elif jours == 0:
                        texte = "Aujourd'hui"
                    else:
                        texte = f"En retard de {abs(jours)} jour(s)"
                    ligne("Arriv\u00e9e pr\u00e9vue", texte, 7)
                except Exception:
                    pass
            else:
                ttk.Label(frame, text="Aucune r\u00e9servation trouv\u00e9e.").grid(
                    row=0, column=0, columnspan=2, pady=8)

        ttk.Button(win, text="Fermer", command=win.destroy).pack(pady=10)

    def ajouter_chambre(self):
        self._formulaire_chambre(None)

    def ouvrir_details(self, chambre):
        self._formulaire_chambre(chambre)

    def _formulaire_chambre(self, chambre):
        win = tk.Toplevel(self)
        win.title("Chambre" if chambre is None else f"Chambre {chambre['numero']}")
        win.resizable(False, False)
        win.transient(self)
        win.grab_set()

        ttk.Label(win, text="N\u00b0 de chambre *").grid(row=0, column=0, sticky="w",
                                                          padx=8, pady=4)
        numero_var = tk.StringVar(value=chambre["numero"] if chambre else "")
        ttk.Entry(win, textvariable=numero_var, width=20).grid(
            row=0, column=1, padx=8, pady=4)

        ttk.Label(win, text="Type").grid(row=1, column=0, sticky="w", padx=8, pady=4)
        type_var = tk.StringVar(value=chambre["type"] if chambre else "Simple")
        ttk.Combobox(win, textvariable=type_var,
                     values=["Simple", "Double", "Suite", "Familiale"],
                     width=18, state="normal").grid(row=1, column=1, padx=8, pady=4)

        ttk.Label(win, text="Prix / nuit (TND) *").grid(row=2, column=0, sticky="w",
                                                          padx=8, pady=4)
        prix_var = tk.StringVar(value=f"{chambre['prix']:.3f}".replace(".", ",") if chambre else "0,000")
        prix_entry = ttk.Entry(win, textvariable=prix_var, width=20)
        prix_entry.grid(row=2, column=1, padx=8, pady=4)
        prix_entry.bind("<FocusOut>", lambda e: _formater_prix(prix_var))

        ttk.Label(win, text="\u00c9tat").grid(row=3, column=0, sticky="w", padx=8, pady=4)
        etat_var = tk.StringVar(value=chambre["etat"] if chambre else "Libre")
        ttk.Combobox(win, textvariable=etat_var, values=ETATS_CHAMBRE,
                     width=18, state="readonly").grid(row=3, column=1, padx=8, pady=4)

        ttk.Label(win, text="Description").grid(row=4, column=0, sticky="w",
                                                  padx=8, pady=4)
        desc_var = tk.StringVar(value=chambre["description"] if chambre else "")
        ttk.Entry(win, textvariable=desc_var, width=20).grid(
            row=4, column=1, padx=8, pady=4)

        def enregistrer():
            numero = numero_var.get().strip()
            if not numero:
                messagebox.showerror("Erreur", "Le num\u00e9ro de chambre est obligatoire.")
                return
            try:
                prix = float(prix_var.get().replace(",", "."))
            except ValueError:
                messagebox.showerror("Erreur", "Le prix doit \u00eatre un nombre valide.")
                return

            try:
                if chambre is None:
                    add_chambre(numero, type_var.get(), prix, etat_var.get(),
                                   desc_var.get())
                else:
                    update_chambre(chambre["id"], numero, type_var.get(),
                                       prix, etat_var.get(), desc_var.get())
            except Exception as exc:
                messagebox.showerror("Erreur", f"Impossible d'enregistrer : {exc}")
                return

            win.destroy()
            self.refresh()
            self.app.refresh_clients_tab()

        def supprimer():
            if chambre is None:
                return
            if not messagebox.askyesno(
                    "Confirmation",
                    f"Supprimer la chambre {chambre['numero']} ?"):
                return
            try:
                delete_chambre(chambre["id"])
            except Exception as exc:
                messagebox.showerror("Erreur", f"Impossible de supprimer : {exc}")
                return
            win.destroy()
            self.refresh()
            self.app.refresh_clients_tab()

        btn_frame = ttk.Frame(win)
        btn_frame.grid(row=5, column=0, columnspan=2, pady=10)
        ttk.Button(btn_frame, text="Enregistrer", command=enregistrer).pack(
            side="left", padx=4)
        if chambre is not None:
            ttk.Button(btn_frame, text="Supprimer", command=supprimer).pack(
                side="left", padx=4)
        ttk.Button(btn_frame, text="Annuler", command=win.destroy).pack(
            side="left", padx=4)
