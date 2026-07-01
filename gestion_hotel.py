# -*- coding: utf-8 -*-
"""
================================================================================
  GESTION D'HOTEL - Logiciel de gestion complet (fichier unique)
================================================================================

  Application de gestion d'hôtel développée en Python / Tkinter.
  Toutes les fonctionnalités sont regroupées dans ce fichier unique pour
  faciliter l'installation et le déploiement.

  Fonctionnalités :
    - Vue graphique des chambres (libre / occupée / réservée / maintenance)
    - Fiches clients complètes (identité, dates, chambre réservée...)
    - Facturation détaillée en Dinar Tunisien (TND) avec export PDF
    - Gestion des dépenses (maintenance, ménage, STEG, SONEDE...)
    - Statistiques et courbes (recettes, dépenses, bénéfices, occupation)

  Lancement :
      python gestion_hotel.py

  La base de données "hotel.db" est créée automatiquement au même endroit
  que ce fichier lors du premier lancement.

================================================================================
"""


import os
import sys
import sqlite3
import calendar
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import date, datetime, timedelta
# matplotlib est optionnel : l'app peut fonctionner sans les graphiques.
try:
    import matplotlib
    matplotlib.use("TkAgg")
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    _HAS_MATPLOTLIB = True
except ModuleNotFoundError:
    Figure = None
    FigureCanvasTkAgg = None
    _HAS_MATPLOTLIB = False
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable, Image,
)







# ---------------------------------------------------------------------------
# Clients
# ---------------------------------------------------------------------------
def get_clients(statut=None):
    conn = get_connection()
    if statut:
        rows = conn.execute(
            """
            SELECT c.*, ch.numero AS chambre_numero, ch.prix AS chambre_prix
            FROM clients c
            LEFT JOIN chambres ch ON ch.id = c.chambre_id
            WHERE c.statut = ?
            ORDER BY c.id DESC
            """,
            (statut,),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT c.*, ch.numero AS chambre_numero, ch.prix AS chambre_prix
            FROM clients c
            LEFT JOIN chambres ch ON ch.id = c.chambre_id
            ORDER BY c.id DESC
            """
        ).fetchall()
    conn.close()
    return rows


def get_client(client_id):
    conn = get_connection()
    row = conn.execute(
        """
        SELECT c.*, ch.numero AS chambre_numero, ch.prix AS chambre_prix
        FROM clients c
        LEFT JOIN chambres ch ON ch.id = c.chambre_id
        WHERE c.id = ?
        """,
        (client_id,),
    ).fetchone()
    conn.close()
    return row


def add_client(data):
    """data: dict avec les clés correspondant aux colonnes de la table."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO clients (
            nom, prenom, type_identifiant, numero_identifiant,
            date_naissance, lieu_naissance, adresse, telephone,
            venant_de, allant_a, chambre_id, date_entree, date_sortie, statut
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            data["nom"], data["prenom"], data["type_identifiant"],
            data["numero_identifiant"], data["date_naissance"],
            data["lieu_naissance"], data["adresse"], data["telephone"],
            data["venant_de"], data["allant_a"], data["chambre_id"],
            data["date_entree"], data["date_sortie"], data.get("statut", "En cours"),
        ),
    )
    client_id = cur.lastrowid
    # Si une chambre est associée, on la marque occupée
    if data.get("chambre_id"):
        cur.execute(
            "UPDATE chambres SET etat='Occupée' WHERE id=?",
            (data["chambre_id"],),
        )
    conn.commit()
    conn.close()
    return client_id


def update_client(client_id, data):
    conn = get_connection()
    cur = conn.cursor()

    # Récupérer l'ancienne chambre pour la libérer si elle change
    ancien = cur.execute(
        "SELECT chambre_id FROM clients WHERE id=?", (client_id,)
    ).fetchone()
    ancienne_chambre = ancien["chambre_id"] if ancien else None

    cur.execute(
        """
        UPDATE clients SET
            nom=?, prenom=?, type_identifiant=?, numero_identifiant=?,
            date_naissance=?, lieu_naissance=?, adresse=?, telephone=?,
            venant_de=?, allant_a=?, chambre_id=?, date_entree=?,
            date_sortie=?, statut=?
        WHERE id=?
        """,
        (
            data["nom"], data["prenom"], data["type_identifiant"],
            data["numero_identifiant"], data["date_naissance"],
            data["lieu_naissance"], data["adresse"], data["telephone"],
            data["venant_de"], data["allant_a"], data["chambre_id"],
            data["date_entree"], data["date_sortie"], data.get("statut", "En cours"),
            client_id,
        ),
    )

    nouvelle_chambre = data.get("chambre_id")

    # Libérer l'ancienne chambre si elle a changé
    if ancienne_chambre and ancienne_chambre != nouvelle_chambre:
        cur.execute(
            "UPDATE chambres SET etat='Libre' WHERE id=?", (ancienne_chambre,)
        )

    # Occuper la nouvelle chambre si le client est toujours en cours
    if nouvelle_chambre and data.get("statut", "En cours") == "En cours":
        cur.execute(
            "UPDATE chambres SET etat='Occupée' WHERE id=?", (nouvelle_chambre,)
        )

    # Si le client est marqué "Sorti", on libère sa chambre
    if data.get("statut") == "Sorti" and nouvelle_chambre:
        cur.execute(
            "UPDATE chambres SET etat='Libre' WHERE id=?", (nouvelle_chambre,)
        )

    conn.commit()
    conn.close()


def delete_client(client_id):
    conn = get_connection()
    cur = conn.cursor()
    row = cur.execute(
        "SELECT chambre_id FROM clients WHERE id=?", (client_id,)
    ).fetchone()
    cur.execute("DELETE FROM clients WHERE id=?", (client_id,))
    if row and row["chambre_id"]:
        cur.execute(
            "UPDATE chambres SET etat='Libre' WHERE id=?", (row["chambre_id"],)
        )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Factures
# ---------------------------------------------------------------------------
def get_next_numero_facture():
    n = get_parametre("prochain_numero_facture", "1")
    try:
        n = int(n)
    except ValueError:
        n = 1
    annee = datetime.now().year
    return f"F{annee}-{n:05d}"


def create_facture(client_id, date_facture, date_entree, date_sortie,
                    nb_nuits, lignes, remise=0.0, mode_paiement="Espèces",
                    nom_client=""):
    """
    lignes: liste de tuples (description, quantite, prix_unitaire)
    Retourne (facture_id, numero, montant_total)
    """
    montant_total = 0.0
    lignes_calc = []
    for description, quantite, prix_unitaire in lignes:
        montant = round(float(quantite) * float(prix_unitaire), 3)
        montant_total += montant
        lignes_calc.append((description, quantite, prix_unitaire, montant))
    montant_total = round(montant_total - float(remise or 0), 3)

    numero = get_next_numero_facture()

    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO factures (numero, client_id, nom_client, date_facture,
                               date_entree, date_sortie, nb_nuits, montant_total,
                               remise, mode_paiement)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (numero, client_id, nom_client, date_facture, date_entree, date_sortie,
         nb_nuits, montant_total, remise, mode_paiement),
    )
    facture_id = cur.lastrowid

    for description, quantite, prix_unitaire, montant in lignes_calc:
        cur.execute(
            """
            INSERT INTO facture_lignes
                (facture_id, description, quantite, prix_unitaire, montant)
            VALUES (?, ?, ?, ?, ?)
            """,
            (facture_id, description, quantite, prix_unitaire, montant),
        )

    # Incrémenter le compteur de factures
    try:
        prochain = int(get_parametre("prochain_numero_facture", "1")) + 1
    except ValueError:
        prochain = 2
    cur.execute(
        "UPDATE parametres SET valeur=? WHERE cle='prochain_numero_facture'",
        (str(prochain),),
    )

    conn.commit()
    conn.close()
    return facture_id, numero, montant_total


def get_facture(facture_id):
    conn = get_connection()
    facture = conn.execute(
        """
        SELECT f.*, c.nom, c.prenom, c.numero_identifiant, c.type_identifiant,
               c.adresse, ch.numero AS chambre_numero
        FROM factures f
        LEFT JOIN clients c ON c.id = f.client_id
        LEFT JOIN chambres ch ON ch.id = c.chambre_id
        WHERE f.id = ?
        """,
        (facture_id,),
    ).fetchone()
    lignes = conn.execute(
        "SELECT * FROM facture_lignes WHERE facture_id=? ORDER BY id",
        (facture_id,),
    ).fetchall()
    conn.close()
    return facture, lignes


def get_factures(date_debut=None, date_fin=None):
    conn = get_connection()
    if date_debut and date_fin:
        rows = conn.execute(
            """
            SELECT f.*, c.nom, c.prenom
            FROM factures f
            LEFT JOIN clients c ON c.id = f.client_id
            WHERE f.date_facture BETWEEN ? AND ?
            ORDER BY f.date_facture DESC, f.id DESC
            """,
            (date_debut, date_fin),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT f.*, c.nom, c.prenom
            FROM factures f
            LEFT JOIN clients c ON c.id = f.client_id
            ORDER BY f.date_facture DESC, f.id DESC
            """
        ).fetchall()
    conn.close()
    return rows
def set_facture_payee(facture_id):
    conn = get_connection()
    conn.execute("UPDATE factures SET payee=1 WHERE id=?", (facture_id,))
    conn.commit()
    conn.close()
def set_facture_paiement_partiel(facture_id, montant_paye):
    conn = get_connection()
    conn.execute(
        "UPDATE factures SET payee=0, montant_paye=? WHERE id=?",
        (montant_paye, facture_id)
    )
    conn.commit()
    conn.close()
def set_client_solde(client_id, solde):
    conn = get_connection()
    conn.execute("UPDATE clients SET solde=? WHERE id=?", (solde, client_id))
    conn.commit()
    conn.close()

def get_client_solde(client_id):
    conn = get_connection()
    row = conn.execute(
        "SELECT solde FROM clients WHERE id=?", (client_id,)
    ).fetchone()
    conn.close()
    return row["solde"] if row else 0.0


# ---------------------------------------------------------------------------
# Dépenses
# ---------------------------------------------------------------------------
def get_depenses(date_debut=None, date_fin=None):
    conn = get_connection()
    if date_debut and date_fin:
        rows = conn.execute(
            "SELECT * FROM depenses WHERE date BETWEEN ? AND ? "
            "ORDER BY date DESC, id DESC",
            (date_debut, date_fin),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM depenses ORDER BY date DESC, id DESC"
        ).fetchall()
    conn.close()
    return rows


def add_depense(date, categorie, description, montant, mode_paiement="Espèces"):
    conn = get_connection()
    conn.execute(
        "INSERT INTO depenses (date, categorie, description, montant, mode_paiement) "
        "VALUES (?, ?, ?, ?, ?)",
        (date, categorie, description, montant, mode_paiement),
    )
    conn.commit()
    conn.close()


def update_depense(depense_id, date, categorie, description, montant, mode_paiement):
    conn = get_connection()
    conn.execute(
        "UPDATE depenses SET date=?, categorie=?, description=?, montant=?, "
        "mode_paiement=? WHERE id=?",
        (date, categorie, description, montant, mode_paiement, depense_id),
    )
    conn.commit()
    conn.close()


def delete_depense(depense_id):
    conn = get_connection()
    conn.execute("DELETE FROM depenses WHERE id=?", (depense_id,))
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Statistiques / récapitulatifs
# ---------------------------------------------------------------------------
def recap_recettes(date_debut, date_fin, group_by="day"):
    """
    Retourne une liste de tuples (periode, total_recettes) entre deux dates.
    group_by: 'day' -> 'YYYY-MM-DD', 'month' -> 'YYYY-MM', 'year' -> 'YYYY'
    """
    fmt = {"day": "%Y-%m-%d", "month": "%Y-%m", "year": "%Y"}[group_by]
    conn = get_connection()
    rows = conn.execute(
        f"""
        SELECT strftime('{fmt}', date_facture) AS periode,
               SUM(montant_total) AS total
        FROM factures
        WHERE date_facture BETWEEN ? AND ?
        GROUP BY periode
        ORDER BY periode
        """,
        (date_debut, date_fin),
    ).fetchall()
    conn.close()
    return rows


def recap_depenses(date_debut, date_fin, group_by="day"):
    fmt = {"day": "%Y-%m-%d", "month": "%Y-%m", "year": "%Y"}[group_by]
    conn = get_connection()
    rows = conn.execute(
        f"""
        SELECT strftime('{fmt}', date) AS periode,
               SUM(montant) AS total
        FROM depenses
        WHERE date BETWEEN ? AND ?
        GROUP BY periode
        ORDER BY periode
        """,
        (date_debut, date_fin),
    ).fetchall()
    conn.close()
    return rows


def recap_depenses_par_categorie(date_debut, date_fin):
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT categorie, SUM(montant) AS total
        FROM depenses
        WHERE date BETWEEN ? AND ?
        GROUP BY categorie
        ORDER BY total DESC
        """,
        (date_debut, date_fin),
    ).fetchall()
    conn.close()
    return rows


def total_recettes(date_debut, date_fin):
    conn = get_connection()
    row = conn.execute(
        "SELECT COALESCE(SUM(montant_total),0) AS total FROM factures "
        "WHERE date_facture BETWEEN ? AND ?",
        (date_debut, date_fin),
    ).fetchone()
    conn.close()
    return row["total"] or 0.0


def total_depenses(date_debut, date_fin):
    conn = get_connection()
    row = conn.execute(
        "SELECT COALESCE(SUM(montant),0) AS total FROM depenses "
        "WHERE date BETWEEN ? AND ?",
        (date_debut, date_fin),
    ).fetchone()
    conn.close()
    return row["total"] or 0.0


def taux_occupation(date_ref=None):
    """Retourne (nb_occupees, nb_total) chambres à l'instant présent."""
    conn = get_connection()
    total = conn.execute("SELECT COUNT(*) AS n FROM chambres").fetchone()["n"]
    occ = conn.execute(
        "SELECT COUNT(*) AS n FROM chambres WHERE etat='Occupée'"
    ).fetchone()["n"]
    conn.close()
    return occ, total
# ---------------------------------------------------------------------------
# Réservations
# ---------------------------------------------------------------------------
def get_reservations(statut=None):
    conn = get_connection()
    if statut:
        rows = conn.execute(
            """
            SELECT r.*, ch.numero AS chambre_numero, ch.prix AS chambre_prix
            FROM reservations r
            LEFT JOIN chambres ch ON ch.id = r.chambre_id
            WHERE r.statut = ?
            ORDER BY r.date_arrivee ASC
            """, (statut,)
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT r.*, ch.numero AS chambre_numero, ch.prix AS chambre_prix
            FROM reservations r
            LEFT JOIN chambres ch ON ch.id = r.chambre_id
            ORDER BY r.date_arrivee ASC
            """
        ).fetchall()
    conn.close()
    return rows


def get_reservation(reservation_id):
    conn = get_connection()
    row = conn.execute(
        """
        SELECT r.*, ch.numero AS chambre_numero, ch.prix AS chambre_prix
        FROM reservations r
        LEFT JOIN chambres ch ON ch.id = r.chambre_id
        WHERE r.id = ?
        """, (reservation_id,)
    ).fetchone()
    conn.close()
    return row


def add_reservation(data):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO reservations (
            nom, prenom, telephone, type_identifiant, numero_identifiant,
            chambre_id, date_arrivee, date_depart, nb_personnes, notes, statut
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            data["nom"], data["prenom"], data["telephone"],
            data["type_identifiant"], data["numero_identifiant"],
            data["chambre_id"], data["date_arrivee"], data["date_depart"],
            data["nb_personnes"], data["notes"], data.get("statut", "RESERVE"),
        )
    )
    if data.get("chambre_id"):
        cur.execute(
            "UPDATE chambres SET etat='Réservée' WHERE id=?",
            (data["chambre_id"],)
        )
    conn.commit()
    conn.close()


def update_reservation(reservation_id, data):
    conn = get_connection()
    cur = conn.cursor()

    ancien = cur.execute(
        "SELECT chambre_id, statut FROM reservations WHERE id=?",
        (reservation_id,)
    ).fetchone()
    ancienne_chambre = ancien["chambre_id"] if ancien else None

    cur.execute(
        """
        UPDATE reservations SET
            nom=?, prenom=?, telephone=?, type_identifiant=?,
            numero_identifiant=?, chambre_id=?, date_arrivee=?,
            date_depart=?, nb_personnes=?, notes=?, statut=?
        WHERE id=?
        """,
        (
            data["nom"], data["prenom"], data["telephone"],
            data["type_identifiant"], data["numero_identifiant"],
            data["chambre_id"], data["date_arrivee"], data["date_depart"],
            data["nb_personnes"], data["notes"], data.get("statut", "RESERVE"),
            reservation_id,
        )
    )

    nouvelle_chambre = data.get("chambre_id")

    if ancienne_chambre and ancienne_chambre != nouvelle_chambre:
        cur.execute(
            "UPDATE chambres SET etat='Libre' WHERE id=?", (ancienne_chambre,)
        )

    if nouvelle_chambre:
        statut = data.get("statut", "RESERVE")
        if statut == "RESERVE":
            cur.execute(
                "UPDATE chambres SET etat='Réservée' WHERE id=?", (nouvelle_chambre,)
            )
        elif statut == "ANNULE":
            cur.execute(
                "UPDATE chambres SET etat='Libre' WHERE id=?", (nouvelle_chambre,)
            )

    conn.commit()
    conn.close()


def delete_reservation(reservation_id):
    conn = get_connection()
    cur = conn.cursor()
    row = cur.execute(
        "SELECT chambre_id FROM reservations WHERE id=?", (reservation_id,)
    ).fetchone()
    cur.execute("DELETE FROM reservations WHERE id=?", (reservation_id,))
    if row and row["chambre_id"]:
        cur.execute(
            "UPDATE chambres SET etat='Libre' WHERE id=?", (row["chambre_id"],)
        )
    conn.commit()
    conn.close()

# ---------------------------------------------------------------------------
# Alias "db" pointant vers ce module lui-même.
#
# Le reste du code (UI, génération PDF, etc.) appelle systématiquement les
# fonctions ci-dessus via "db.xxx(...)" comme si elles provenaient d'un
# module séparé "database.py". Comme tout est regroupé ici dans un seul
# fichier, on crée cet alias pour que ces appels "db.xxx" fonctionnent sans
# avoir à réécrire tout le code.
# ---------------------------------------------------------------------------
db = sys.modules[__name__]
def _formater_prix(var, event=None):
    """Formate un champ prix : virgule comme séparateur, 3 décimales."""
    valeur = var.get().replace(",", ".").strip()
    try:
        var.set(f"{float(valeur):.3f}".replace(".", ","))
    except ValueError:
        pass



# ==============================================================================
# Module : num2words_fr.py
# ==============================================================================

UNITES = [
    "", "un", "deux", "trois", "quatre", "cinq", "six", "sept", "huit", "neuf",
]

DIX_A_SEIZE = {
    10: "dix", 11: "onze", 12: "douze", 13: "treize", 14: "quatorze",
    15: "quinze", 16: "seize",
}

DIZAINES = {
    1: "dix", 2: "vingt", 3: "trente", 4: "quarante", 5: "cinquante",
    6: "soixante", 7: "soixante-dix", 8: "quatre-vingt", 9: "quatre-vingt-dix",
}


def _moins_de_cent(n):
    """Convertit un nombre de 0 à 99 en lettres."""
    if n < 10:
        return UNITES[n]
    if n in DIX_A_SEIZE:
        return DIX_A_SEIZE[n]
    if n < 20:
        return "dix-" + UNITES[n - 10]

    dizaine = n // 10
    unite = n % 10

    if dizaine in (7, 9):
        # soixante-dix..79 et quatre-vingt-dix..99 -> base 60 / 80 + 10..19
        base = DIZAINES[dizaine - 1]  # "soixante" ou "quatre-vingt"
        if unite == 0:
            return base + "-dix"
        if unite == 1:
            return base + "-et-onze" if dizaine == 7 else base + "-onze"
        return base + "-" + _moins_de_cent(10 + unite)

    base = DIZAINES[dizaine]

    if unite == 0:
        # quatre-vingts (avec s) quand rien après, mais vingt/trente... non
        if dizaine == 8:
            return base + "s"
        return base
    if unite == 1 and dizaine != 8:
        return base + "-et-un"
    return base + "-" + UNITES[unite]


def _moins_de_mille(n):
    """Convertit un nombre de 0 à 999 en lettres."""
    if n < 100:
        return _moins_de_cent(n)

    centaine = n // 100
    reste = n % 100

    if centaine == 1:
        prefixe = "cent"
    else:
        prefixe = UNITES[centaine] + " cent"
        if reste == 0:
            prefixe += "s"

    if reste == 0:
        return prefixe
    return prefixe + " " + _moins_de_cent(reste)


def nombre_en_lettres(n):
    """Convertit un entier (0 à 999 999 999) en toutes lettres françaises."""
    n = int(n)
    if n == 0:
        return "zéro"
    if n < 0:
        return "moins " + nombre_en_lettres(-n)

    groupes = []
    temp = n
    while temp > 0:
        groupes.append(temp % 1000)
        temp //= 1000
    # groupes[0] = unités, groupes[1] = milliers, groupes[2] = millions,
    # groupes[3] = milliards

    noms = ["", "mille", "million", "milliard"]
    parties = []

    for i in range(len(groupes) - 1, -1, -1):
        valeur = groupes[i]
        if valeur == 0:
            continue
        if i == 1:
            # Milliers : "mille" reste invariable et "un mille" -> "mille"
            if valeur == 1:
                parties.append("mille")
            else:
                parties.append(_moins_de_mille(valeur) + " mille")
        elif i == 0:
            parties.append(_moins_de_mille(valeur))
        else:
            mot = noms[i]
            if valeur == 1:
                parties.append("un " + mot)
            else:
                parties.append(_moins_de_mille(valeur) + " " + mot + "s")

    return " ".join(parties)


def montant_en_lettres(montant, devise="dinars", sous_unite="millimes"):
    """
    Convertit un montant décimal (ex: 125.350) en toutes lettres, en
    distinguant la partie entière (dinars) et la partie décimale (millimes,
    sur 3 chiffres pour le dinar tunisien).

    Exemple : 125.350 -> "cent vingt-cinq dinars et trois cent
    cinquante millimes"
    """
    montant = round(float(montant), 3)
    entier = int(montant)
    # Partie décimale en millimes (3 chiffres)
    decimal = int(round((montant - entier) * 1000))

    if decimal >= 1000:
        entier += 1
        decimal -= 1000

    texte_entier = nombre_en_lettres(entier)
    unite_devise = devise if entier != 1 else devise.rstrip("s")

    if decimal == 0:
        return f"{texte_entier} {unite_devise}"

    texte_decimal = nombre_en_lettres(decimal)
    unite_sous = sous_unite if decimal != 1 else sous_unite.rstrip("s")

    return f"{texte_entier} {unite_devise} et {texte_decimal} {unite_sous}"


if __name__ == "__main__":
    # Quelques tests rapides
    for valeur in [0, 1, 5, 10, 11, 16, 17, 19, 20, 21, 30, 71, 75, 80, 81,
                    91, 99, 100, 101, 199, 200, 1000, 1001, 1999, 2000, 2021,
                    1000000, 1234567, 125.350, 1.001, 1.0, 0.500]:
        if isinstance(valeur, int):
            print(valeur, "->", nombre_en_lettres(valeur))
        else:
            print(valeur, "->", montant_en_lettres(valeur))



# ==============================================================================
# Module : widgets.py
# ==============================================================================

MOIS_FR = [
    "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
    "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre",
]

JOURS_FR = ["Lu", "Ma", "Me", "Je", "Ve", "Sa", "Di"]


class CalendarPopup(tk.Toplevel):
    """Petite fenêtre affichant un calendrier mensuel cliquable."""

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

        # Centrer la popup par rapport au parent
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

        cal = calendar.Calendar(firstweekday=0)  # Lundi = 0
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
    """
    Champ de saisie de date au format JJ/MM/AAAA avec un bouton qui ouvre
    un mini calendrier. Utilisable comme un simple Entry via les méthodes
    get() / set_date() / get_date().
    """

    def __init__(self, parent, width=10, **kwargs):
        super().__init__(parent)
        self.var = tk.StringVar()
        self.entry = ttk.Entry(self, textvariable=self.var, width=width,
                                **kwargs)
        self.entry.pack(side="left")
        self.bouton = ttk.Button(self, text="📅", width=3,
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
        """Retourne un objet date, ou None si le format est invalide."""
        try:
            return datetime.strptime(self.var.get(), "%d/%m/%Y").date()
        except ValueError:
            return None


def date_str_to_iso(date_str):
    """Convertit 'JJ/MM/AAAA' en 'AAAA-MM-JJ' (pour tri / SQL). Renvoie '' si invalide."""
    try:
        return datetime.strptime(date_str, "%d/%m/%Y").strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return ""


def iso_to_date_str(iso_str):
    """Convertit 'AAAA-MM-JJ' en 'JJ/MM/AAAA'. Renvoie '' si invalide."""
    try:
        return datetime.strptime(iso_str, "%Y-%m-%d").strftime("%d/%m/%Y")
    except (ValueError, TypeError):
        return ""


class ScrollableFrame(tk.Frame):
    """Frame avec barre de défilement verticale, utile pour les formulaires
    longs ou les petits écrans."""

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



# ==============================================================================
# Module : pdf_facture.py
# ==============================================================================

def generer_facture_pdf(facture_id, chemin_pdf):
    """Génère le fichier PDF de la facture `facture_id` à l'emplacement
    `chemin_pdf`."""

    facture, lignes = db.get_facture(facture_id)
    if facture is None:
        raise ValueError("Facture introuvable")

    nom_hotel = db.get_parametre("nom_hotel", "Hôtel")
    adresse_hotel = db.get_parametre("adresse_hotel", "")
    telephone_hotel = db.get_parametre("telephone_hotel", "")
    matricule_fiscal = db.get_parametre("matricule_fiscal", "")

    styles = getSampleStyleSheet()
    style_normal = styles["Normal"]
    style_title = ParagraphStyle(
        "TitreHotel", parent=styles["Title"], alignment=TA_LEFT,
        fontSize=16, spaceAfter=2,
    )
    style_small = ParagraphStyle(
        "Small", parent=styles["Normal"], fontSize=9, leading=12,
    )
    style_right = ParagraphStyle(
        "Right", parent=styles["Normal"], alignment=TA_RIGHT,
    )
    style_facture_titre = ParagraphStyle(
        "FactureTitre", parent=styles["Heading2"], alignment=TA_CENTER,
        textColor=colors.HexColor("#1F4E79"),
    )

    doc = SimpleDocTemplate(
        chemin_pdf, pagesize=A4,
        topMargin=18 * mm, bottomMargin=18 * mm,
        leftMargin=18 * mm, rightMargin=18 * mm,
    )

    elements = []

    # ----------------- En-tête -----------------
    # ----------------- En-tête -----------------
    logo_path = os.path.join(BASE_DIR, "logo_hotel.jpg")
    if os.path.exists(logo_path):
        logo = Image(logo_path, width=25 * mm, height=25 * mm)
        entete_gauche = [logo,
                         Paragraph(f"<b>{nom_hotel}</b>", style_title),
                         Paragraph(adresse_hotel, style_small),
                         Paragraph(f"Tél : {telephone_hotel}", style_small),
                         Paragraph(f"M.F. : {matricule_fiscal}", style_small)]
    else:
        entete_gauche = [
            Paragraph(f"<b>{nom_hotel}</b>", style_title),
            Paragraph(adresse_hotel, style_small),
            Paragraph(f"Tél : {telephone_hotel}", style_small),
            Paragraph(f"M.F. : {matricule_fiscal}", style_small),
        ]

    entete_droite = [
        Paragraph(f"<b>FACTURE N° {facture['numero']}</b>", style_right),
        Paragraph(f"Date : {iso_to_date_str(facture['date_facture']) or facture['date_facture']}",
                  style_right),
    ]

    entete_table = Table(
        [[entete_gauche, entete_droite]],
        colWidths=[100 * mm, 70 * mm],
    )
    entete_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    elements.append(entete_table)
    elements.append(Spacer(1, 6 * mm))
    elements.append(HRFlowable(width="100%", color=colors.HexColor("#1F4E79"),
                                thickness=1.2))
    elements.append(Spacer(1, 4 * mm))

    elements.append(Paragraph("FACTURE", style_facture_titre))
    elements.append(Spacer(1, 4 * mm))

    # ----------------- Informations client -----------------
    nom_complet = f"{facture['prenom'] or ''} {facture['nom'] or ''}".strip()
    info_client = [
        ["Client :", nom_complet],
        ["Identifiant :", f"{facture['type_identifiant'] or ''} "
                           f"{facture['numero_identifiant'] or ''}"],
        ["Adresse :", facture["adresse"] or ""],
        ["Chambre :", facture["chambre_numero"] or ""],
        ["Date d'arrivée :", iso_to_date_str(facture["date_entree"]) or facture["date_entree"]],
        ["Date de départ :", iso_to_date_str(facture["date_sortie"]) or facture["date_sortie"]],
        ["Nombre de nuits :", str(facture["nb_nuits"])],
    ]
    client_table = Table(info_client, colWidths=[40 * mm, 130 * mm])
    client_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
    ]))
    elements.append(client_table)
    elements.append(Spacer(1, 6 * mm))

    # ----------------- Tableau des lignes -----------------
    data = [["Description", "Quantité", "Prix unitaire (TND)", "Montant (TND)"]]
    for ligne in lignes:
        data.append([
            ligne["description"],
            f"{ligne['quantite']:g}",
            f"{ligne['prix_unitaire']:.3f}",
            f"{ligne['montant']:.3f}",
        ])

    if facture["remise"]:
        data.append(["Remise", "", "", f"-{facture['remise']:.3f}"])

    data.append(["", "", "TOTAL", f"{facture['montant_total']:.3f} TND"])

    lignes_table = Table(
        data, colWidths=[80 * mm, 25 * mm, 35 * mm, 35 * mm],
        repeatRows=1,
    )
    lignes_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E79")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("ALIGN", (1, 0), (-1, -1), "CENTER"),
        ("ALIGN", (0, 0), (0, -1), "LEFT"),
        ("GRID", (0, 0), (-1, -2), 0.5, colors.grey),
        ("LINEABOVE", (0, -1), (-1, -1), 1, colors.black),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
    ]))
    elements.append(lignes_table)
    elements.append(Spacer(1, 8 * mm))

    # ----------------- Montant en lettres -----------------
    montant_lettres = montant_en_lettres(facture["montant_total"])
    texte_arret = (
        f"Arrêtée la présente facture à la somme de : "
        f"<b>{montant_lettres}</b>."
    )
    elements.append(HRFlowable(width="100%", color=colors.grey, thickness=0.5))
    elements.append(Spacer(1, 3 * mm))
    elements.append(Paragraph(texte_arret, style_normal))
    elements.append(Spacer(1, 3 * mm))
    elements.append(Paragraph(
        f"Mode de paiement : {facture['mode_paiement']}", style_small))
    elements.append(Spacer(1, 12 * mm))

    # ----------------- Pied de page / signature -----------------
    pied_table = Table(
        [["Cachet et signature de l'hôtel", "Signature du client"]],
        colWidths=[85 * mm, 85 * mm],
    )
    pied_table.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 25),
        ("LINEABOVE", (0, 0), (0, 0), 0.5, colors.grey),
        ("LINEABOVE", (1, 0), (1, 0), 0.5, colors.grey),
    ]))
    elements.append(pied_table)

    elements.append(Spacer(1, 6 * mm))
    elements.append(Paragraph(
        f"{nom_hotel} - {adresse_hotel} - Tél : {telephone_hotel} - "
        f"M.F. : {matricule_fiscal}",
        ParagraphStyle("Footer", parent=styles["Normal"], fontSize=8,
                       alignment=TA_CENTER, textColor=colors.grey),
    ))

    doc.build(elements)
    return chemin_pdf
def generer_fiche_police(client):
    """Génère une Fiche Police PDF pour un client. Retourne le chemin du fichier."""
    import subprocess, platform

    output_dir = os.path.join(BASE_DIR, "fiches_police")
    os.makedirs(output_dir, exist_ok=True)

    nom_fichier = f"fiche_police_{client['id']}_{client['nom']}_{client['prenom']}.pdf"
    chemin = os.path.join(output_dir, nom_fichier)

    BLEU = colors.HexColor("#2C3E6B")
    GRIS = colors.HexColor("#F5F5F5")
    styles = getSampleStyleSheet()

    titre_style = ParagraphStyle(
        "Titre", parent=styles["Title"],
        fontSize=18, textColor=BLEU, spaceAfter=4
    )
    sous_titre_style = ParagraphStyle(
        "SousTitre", parent=styles["Normal"],
        fontSize=10, textColor=colors.grey, spaceAfter=12
    )
    section_style = ParagraphStyle(
        "Section", parent=styles["Normal"],
        fontSize=11, textColor=colors.white,
        backColor=BLEU, leftIndent=6, spaceBefore=10, spaceAfter=4, leading=18
    )
    footer_style = ParagraphStyle(
        "Footer", parent=styles["Normal"],
        fontSize=8, textColor=colors.grey, alignment=TA_CENTER
    )

    def ligne(label, valeur):
        return [
            Paragraph(f"<b>{label}</b>", styles["Normal"]),
            Paragraph(str(valeur) if valeur else "—", styles["Normal"]),
        ]

    story = []

    # En-tête
    # En-tête
    logo_path = os.path.join(BASE_DIR, "logo_hotel.jpg")
    if os.path.exists(logo_path):
        logo = Image(logo_path, width=22 * mm, height=22 * mm)
        entete_fiche = Table(
            [[logo, Paragraph("FICHE POLICE", titre_style)]],
            colWidths=[28 * mm, 140 * mm],
        )
        entete_fiche.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        story.append(entete_fiche)
    else:
        story.append(Paragraph("FICHE POLICE", titre_style))

    story.append(Paragraph(
        f"Générée le {datetime.now().strftime('%d/%m/%Y à %H:%M')}",
        sous_titre_style
    ))
    story.append(HRFlowable(width="100%", thickness=2, color=BLEU, spaceAfter=12))

    # Section Identité
    story.append(Paragraph("  IDENTITÉ DU CLIENT", section_style))
    story.append(Spacer(1, 4))
    t1 = Table([
        ligne("Nom", client.get("nom")),
        ligne("Prénom", client.get("prenom")),
        ligne("Date de naissance", iso_to_date_str(client.get("date_naissance", "")) or "—"),
        ligne("Lieu de naissance", client.get("lieu_naissance")),
        ligne("Adresse", client.get("adresse")),
        ligne("Téléphone", client.get("telephone")),
    ], colWidths=[55*mm, 120*mm])
    t1.setStyle(TableStyle([
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [GRIS, colors.white]),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(t1)

    # Section Pièce d'identité
    story.append(Paragraph("  PIÈCE D'IDENTITÉ", section_style))
    story.append(Spacer(1, 4))
    t2 = Table([
        ligne("Type d'identifiant", client.get("type_identifiant")),
        ligne("Numéro d'identifiant", client.get("numero_identifiant")),
    ], colWidths=[55*mm, 120*mm])
    t2.setStyle(TableStyle([
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [GRIS, colors.white]),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(t2)

    # Section Séjour
    story.append(Paragraph("  INFORMATIONS DU SÉJOUR", section_style))
    story.append(Spacer(1, 4))
    t3 = Table([
        ligne("Chambre N°", client.get("chambre_numero")),
        ligne("Prix / nuit", f"{client.get('chambre_prix', '—')} TND"),
        ligne("Date d'entrée", iso_to_date_str(client.get("date_entree", "")) or "—"),
        ligne("Date de sortie", iso_to_date_str(client.get("date_sortie", "")) or "—"),
        ligne("Venant de", client.get("venant_de")),
        ligne("Allant à", client.get("allant_a")),
        ligne("Statut", client.get("statut")),
    ], colWidths=[55*mm, 120*mm])
    t3.setStyle(TableStyle([
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [GRIS, colors.white]),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(t3)

    story.append(Spacer(1, 20))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.lightgrey))
    story.append(Spacer(1, 6))
    story.append(Paragraph("Document officiel — Usage interne uniquement", footer_style))

    nom_hotel = db.get_parametre("nom_hotel", "Hôtel")
    doc = SimpleDocTemplate(
        chemin, pagesize=A4,
        leftMargin=20*mm, rightMargin=20*mm,
        topMargin=20*mm, bottomMargin=20*mm,
    )
    doc.build(story)

    # Ouvrir automatiquement
    try:
        if platform.system() == "Windows":
            os.startfile(chemin)
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", chemin])
        else:
            subprocess.Popen(["xdg-open", chemin])
    except Exception:
        pass

    return chemin
def generer_liste_factures_pdf(factures_data, chemin_pdf, titre="Historique des factures"):
    """
    Génère un PDF listant des factures.
    factures_data : liste de tuples (numero, date, client, identifiant, montant, statut)
    """
    nom_hotel = db.get_parametre("nom_hotel", "Hôtel")
    adresse_hotel = db.get_parametre("adresse_hotel", "")

    styles = getSampleStyleSheet()
    style_title = ParagraphStyle(
        "TitreListe", parent=styles["Title"], alignment=TA_CENTER,
        fontSize=16, textColor=colors.HexColor("#1F4E79"), spaceAfter=4,
    )
    style_small = ParagraphStyle(
        "SmallCenter", parent=styles["Normal"], fontSize=9,
        alignment=TA_CENTER, textColor=colors.grey, spaceAfter=10,
    )

    doc = SimpleDocTemplate(
        chemin_pdf, pagesize=A4,
        topMargin=15 * mm, bottomMargin=15 * mm,
        leftMargin=12 * mm, rightMargin=12 * mm,
    )
    elements = []

    elements.append(Paragraph(nom_hotel, style_title))
    elements.append(Paragraph(adresse_hotel, style_small))
    elements.append(Paragraph(titre, ParagraphStyle(
        "SousTitre", parent=styles["Heading2"], alignment=TA_CENTER,
        textColor=colors.HexColor("#1F4E79"),
    )))
    elements.append(Paragraph(
        f"Généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')}",
        style_small))
    elements.append(Spacer(1, 4 * mm))

    data = [["N° Facture", "Date", "Client", "Identifiant", "Montant (TND)", "Statut"]]
    total = 0.0
    for numero, date_f, client, identifiant, montant, statut in factures_data:
        data.append([numero, date_f, client, identifiant,
                     f"{montant:.3f}".replace(".", ","), statut])
        total += montant

    data.append(["", "", "", "", f"TOTAL : {total:.3f} TND".replace(".", ","), ""])

    table = Table(
        data, colWidths=[28 * mm, 22 * mm, 38 * mm, 30 * mm, 35 * mm, 28 * mm],
        repeatRows=1,
    )
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E79")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -2), 0.5, colors.grey),
        ("LINEABOVE", (0, -1), (-1, -1), 1, colors.black),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 6 * mm))
    elements.append(Paragraph(
        f"Nombre de factures : {len(factures_data)}",
        ParagraphStyle("Footer", parent=styles["Normal"], fontSize=9)))

    doc.build(elements)
    return chemin_pdf


def generer_liste_depenses_pdf(depenses_data, chemin_pdf, titre="Liste des dépenses"):
    """
    Génère un PDF listant des dépenses.
    depenses_data : liste de tuples (date, categorie, description, montant, mode)
    """
    nom_hotel = db.get_parametre("nom_hotel", "Hôtel")
    adresse_hotel = db.get_parametre("adresse_hotel", "")

    styles = getSampleStyleSheet()
    style_title = ParagraphStyle(
        "TitreListe", parent=styles["Title"], alignment=TA_CENTER,
        fontSize=16, textColor=colors.HexColor("#C0392B"), spaceAfter=4,
    )
    style_small = ParagraphStyle(
        "SmallCenter", parent=styles["Normal"], fontSize=9,
        alignment=TA_CENTER, textColor=colors.grey, spaceAfter=10,
    )

    doc = SimpleDocTemplate(
        chemin_pdf, pagesize=A4,
        topMargin=15 * mm, bottomMargin=15 * mm,
        leftMargin=12 * mm, rightMargin=12 * mm,
    )
    elements = []

    elements.append(Paragraph(nom_hotel, style_title))
    elements.append(Paragraph(adresse_hotel, style_small))
    elements.append(Paragraph(titre, ParagraphStyle(
        "SousTitre", parent=styles["Heading2"], alignment=TA_CENTER,
        textColor=colors.HexColor("#C0392B"),
    )))
    elements.append(Paragraph(
        f"Généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')}",
        style_small))
    elements.append(Spacer(1, 4 * mm))

    data = [["Date", "Catégorie", "Description", "Montant (TND)", "Mode de paiement"]]
    total = 0.0
    for date_d, categorie, description, montant, mode in depenses_data:
        data.append([date_d, categorie, description,
                     f"{montant:.3f}".replace(".", ","), mode])
        total += montant

    data.append(["", "", "", f"TOTAL : {total:.3f} TND".replace(".", ","), ""])

    table = Table(
        data, colWidths=[24 * mm, 35 * mm, 55 * mm, 32 * mm, 35 * mm],
        repeatRows=1,
    )
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#C0392B")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("ALIGN", (1, 0), (-1, -1), "LEFT"),
        ("ALIGN", (3, 0), (3, -1), "CENTER"),
        ("GRID", (0, 0), (-1, -2), 0.5, colors.grey),
        ("LINEABOVE", (0, -1), (-1, -1), 1, colors.black),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 6 * mm))
    elements.append(Paragraph(
        f"Nombre de dépenses : {len(depenses_data)}",
        ParagraphStyle("Footer", parent=styles["Normal"], fontSize=9)))

    doc.build(elements)
    return chemin_pdf


# ==============================================================================
# Module : tab_chambres.py
# ==============================================================================

COULEURS_ETAT = {
    "Libre": "#4CAF50",       # vert
    "Occupée": "#E53935",     # rouge
    "Réservée": "#FB8C00",    # orange
    "Maintenance": "#9E9E9E",  # gris
}

COULEUR_TEXTE = "#FFFFFF"


class RoomsTab(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.selected_chambre_id = None

        self._build_ui()
        self.refresh()

    # ------------------------------------------------------------------
    def _build_ui(self):
        # ----- Légende -----
        legend_frame = ttk.Frame(self)
        legend_frame.pack(fill="x", padx=8, pady=(8, 0))

        ttk.Label(legend_frame, text="Légende :",
                  font=("Segoe UI", 10, "bold")).pack(side="left", padx=(0, 10))
        for etat, couleur in COULEURS_ETAT.items():
            carre = tk.Label(legend_frame, text="  ", bg=couleur)
            carre.pack(side="left", padx=(0, 4))
            ttk.Label(legend_frame, text=etat).pack(side="left", padx=(0, 12))

        # Bouton ajout
        ttk.Button(legend_frame, text="+ Ajouter une chambre",
                   command=self.ajouter_chambre).pack(side="right")

        # ----- Grille des chambres -----
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

        # ----- Récap occupation -----
        self.recap_var = tk.StringVar()
        ttk.Label(self, textvariable=self.recap_var,
                  font=("Segoe UI", 10, "bold")).pack(pady=(0, 8))

    def _on_frame_configure(self, event):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self.canvas.itemconfig(self.grid_window, width=event.width)

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    # ------------------------------------------------------------------
    def refresh(self):
        for widget in self.grid_frame.winfo_children():
            widget.destroy()

        chambres = db.get_chambres()

        nb_colonnes = 4
        row_index = 0
        col = 0
        etage_courant = None

        for ch in chambres:
            etage = ch["numero"].split("-")[0] if "-" in ch["numero"] else "?"

            if etage != etage_courant:
                etage_courant = etage
                if row_index > 0:
                    row_index += 1  # petit espace entre les étages
                lbl_etage = tk.Label(
                    self.grid_frame, text=f"Étage {etage_courant}",
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

        occ, total = db.taux_occupation()
        libre = total - occ
        self.recap_var.set(
            f"Total chambres : {total}   |   Occupées : {occ}   |   "
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

       # Rendre toute la tuile cliquable
        for widget in (tile, lbl_numero, lbl_type, lbl_prix, lbl_etat):
            widget.bind("<Button-1>",
                        lambda e, c=chambre: self.ouvrir_details(c))
            if chambre["etat"] in ("Occupée", "Réservée"):
                widget.bind("<Button-3>",
                            lambda e, c=chambre: self.afficher_occupant(c))
    def afficher_occupant(self, chambre):
        """Clic droit sur une chambre occupée ou réservée : affiche qui l'occupe."""
        win = tk.Toplevel(self)
        win.title(f"Chambre {chambre['numero']} — Détails occupation")
        win.resizable(False, False)
        win.transient(self)
        win.grab_set()

        BLEU = "#2C3E6B"
        header = tk.Frame(win, bg=BLEU)
        header.pack(fill="x")
        tk.Label(
            header,
            text=f"Chambre {chambre['numero']} — {chambre['etat']}",
            bg=BLEU, fg="white",
            font=("Segoe UI", 13, "bold")
        ).pack(pady=12, padx=16)

        frame = ttk.Frame(win)
        frame.pack(padx=16, pady=12)

        def ligne(label, valeur, row):
            ttk.Label(frame, text=label,
                      font=("Segoe UI", 9, "bold")).grid(
                row=row, column=0, sticky="w", padx=6, pady=3)
            ttk.Label(frame, text=valeur or "—").grid(
                row=row, column=1, sticky="w", padx=6, pady=3)

        if chambre["etat"] == "Occupée":
            # Chercher dans la table clients
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
                ligne("Téléphone", client["telephone"], 2)
                ligne("Venant de", client["venant_de"], 3)
                ligne("Allant à", client["allant_a"], 4)
                ligne("Date d'entrée",
                      iso_to_date_str(client["date_entree"]) or client["date_entree"], 5)
                ligne("Date de sortie prévue",
                      iso_to_date_str(client["date_sortie"]) or client["date_sortie"], 6)

                # Calcul nuits restantes
                try:
                    sortie = datetime.strptime(client["date_sortie"], "%Y-%m-%d").date()
                    restant = (sortie - date.today()).days
                    texte = f"{restant} nuit(s)" if restant > 0 else "Départ prévu aujourd'hui"
                    ligne("Nuits restantes", texte, 7)
                except Exception:
                    pass
            else:
                ttk.Label(frame, text="Aucun client trouvé.").grid(
                    row=0, column=0, columnspan=2, pady=8)

        elif chambre["etat"] == "Réservée":
            # Chercher dans la table reservations
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
                ligne("Téléphone", rez["telephone"], 1)
                ligne("Identifiant",
                      f"{rez['type_identifiant']} : {rez['numero_identifiant']}", 2)
                ligne("Nb. personnes", str(rez["nb_personnes"]), 3)
                ligne("Date d'arrivée",
                      iso_to_date_str(rez["date_arrivee"]) or rez["date_arrivee"], 4)
                ligne("Date de départ",
                      iso_to_date_str(rez["date_depart"]) or rez["date_depart"], 5)
                ligne("Notes", rez["notes"], 6)

                # Calcul jours avant arrivée
                try:
                    arrivee = datetime.strptime(rez["date_arrivee"], "%Y-%m-%d").date()
                    jours = (arrivee - date.today()).days
                    if jours > 0:
                        texte = f"Dans {jours} jour(s)"
                    elif jours == 0:
                        texte = "Aujourd'hui"
                    else:
                        texte = f"En retard de {abs(jours)} jour(s)"
                    ligne("Arrivée prévue", texte, 7)
                except Exception:
                    pass
            else:
                ttk.Label(frame, text="Aucune réservation trouvée.").grid(
                    row=0, column=0, columnspan=2, pady=8)

        ttk.Button(win, text="Fermer", command=win.destroy).pack(pady=10)

    # ------------------------------------------------------------------
    def ajouter_chambre(self):
        self._formulaire_chambre(None)

    def ouvrir_details(self, chambre):
        self._formulaire_chambre(chambre)

    def _formulaire_chambre(self, chambre):
        """Ouvre une fenêtre modale pour ajouter / modifier une chambre."""
        win = tk.Toplevel(self)
        win.title("Chambre" if chambre is None else f"Chambre {chambre['numero']}")
        win.resizable(False, False)
        win.transient(self)
        win.grab_set()

        ttk.Label(win, text="N° de chambre *").grid(row=0, column=0, sticky="w",
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

        ttk.Label(win, text="État").grid(row=3, column=0, sticky="w", padx=8, pady=4)
        etat_var = tk.StringVar(value=chambre["etat"] if chambre else "Libre")
        ttk.Combobox(win, textvariable=etat_var, values=db.ETATS_CHAMBRE,
                     width=18, state="readonly").grid(row=3, column=1, padx=8, pady=4)

        ttk.Label(win, text="Description").grid(row=4, column=0, sticky="w",
                                                  padx=8, pady=4)
        desc_var = tk.StringVar(value=chambre["description"] if chambre else "")
        ttk.Entry(win, textvariable=desc_var, width=20).grid(
            row=4, column=1, padx=8, pady=4)

        def enregistrer():
            numero = numero_var.get().strip()
            if not numero:
                messagebox.showerror("Erreur", "Le numéro de chambre est obligatoire.")
                return
            try:
                prix = float(prix_var.get().replace(",", "."))
            except ValueError:
                messagebox.showerror("Erreur", "Le prix doit être un nombre valide.")
                return

            try:
                if chambre is None:
                    db.add_chambre(numero, type_var.get(), prix, etat_var.get(),
                                   desc_var.get())
                else:
                    db.update_chambre(chambre["id"], numero, type_var.get(),
                                       prix, etat_var.get(), desc_var.get())
            except Exception as exc:  # ex: numéro déjà existant (UNIQUE)
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
                db.delete_chambre(chambre["id"])
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



# ==============================================================================
# Module : tab_clients.py
# ==============================================================================

class ClientsTab(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.selected_client_id = None

        self._build_ui()
        self.refresh()

    # ------------------------------------------------------------------
    # Construction de l'interface
    # ------------------------------------------------------------------
    def _build_ui(self):
        # ----- Partie gauche : formulaire -----
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
        add_row(r, "Prénom *", "prenom"); r += 1

        ttk.Label(form_frame, text="Type d'identifiant *").grid(
            row=r, column=0, sticky="w", padx=4, pady=3)
        self.vars["type_identifiant"] = tk.StringVar(value=db.TYPES_IDENTIFIANT[0])
        ttk.Combobox(form_frame, textvariable=self.vars["type_identifiant"],
                     values=db.TYPES_IDENTIFIANT, width=21,
                     state="readonly").grid(row=r, column=1, sticky="w", padx=4, pady=3)
        r += 1

        add_row(r, "N° identifiant *", "numero_identifiant"); r += 1

        ttk.Label(form_frame, text="Date de naissance").grid(
            row=r, column=0, sticky="w", padx=4, pady=3)
        self.date_naissance = DateEntry(form_frame, width=12)
        self.date_naissance.grid(row=r, column=1, sticky="w", padx=4, pady=3)
        r += 1

        add_row(r, "Lieu de naissance", "lieu_naissance"); r += 1
        add_row(r, "Adresse", "adresse", width=30); r += 1
        add_row(r, "Téléphone", "telephone"); r += 1
        add_row(r, "Venant de", "venant_de"); r += 1
        add_row(r, "Allant à", "allant_a"); r += 1

        ttk.Label(form_frame, text="Chambre réservée").grid(
            row=r, column=0, sticky="w", padx=4, pady=3)
        self.chambre_var = tk.StringVar()
        self.combo_chambres = ttk.Combobox(
            form_frame, textvariable=self.chambre_var, width=21,
            state="readonly")
        self.combo_chambres.grid(row=r, column=1, sticky="w", padx=4, pady=3)
        r += 1

        ttk.Label(form_frame, text="Date d'entrée").grid(
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

        # Boutons
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
        ttk.Button(btn_frame, text="📄 Fiche Police",
                   command=self.imprimer_fiche_police).pack(side="left", padx=3)

        # ----- Partie droite : liste des clients + recherche -----
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
            "id": "ID", "nom": "Nom", "prenom": "Prénom",
            "identifiant": "Identifiant", "chambre": "Chambre",
            "entree": "Entrée", "sortie": "Sortie", "statut": "Statut",
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

    # ------------------------------------------------------------------
    # Logique
    # ------------------------------------------------------------------
    def refresh(self):
        """Recharge la liste des chambres disponibles et la liste des clients."""
        chambres = db.get_chambres()
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

        # Liste des clients
        for item in self.tree.get_children():
            self.tree.delete(item)

        statut_filtre = self.filtre_statut.get()
        if statut_filtre == "Tous":
            clients = db.get_clients()
        else:
            clients = db.get_clients(statut_filtre)

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
        client = db.get_client(self.selected_client_id)
        return client["chambre_id"] if client else None

    def on_select(self, event=None):
        selection = self.tree.selection()
        if not selection:
            return
        client_id = int(selection[0])
        self.selected_client_id = client_id
        client = db.get_client(client_id)
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

        # Mettre à jour la combo des chambres pour inclure la chambre actuelle
        self.refresh_chambre_combo(client)

    def refresh_chambre_combo(self, client):
        chambres = db.get_chambres()
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
        self.vars["type_identifiant"].set(db.TYPES_IDENTIFIANT[0])
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
                "Les champs Nom, Prénom et N° d'identifiant sont obligatoires.")
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
            db.update_client(self.selected_client_id, data)
            messagebox.showinfo("Succès", "Client mis à jour avec succès.")
        else:
            new_id = db.add_client(data)
            self.selected_client_id = new_id
            messagebox.showinfo("Succès", "Client ajouté avec succès.")

        self.refresh()
        self.app.refresh_rooms_tab()

    def supprimer(self):
        if not self.selected_client_id:
            messagebox.showwarning("Attention", "Veuillez sélectionner un client.")
            return
        if not messagebox.askyesno(
                "Confirmation",
                "Voulez-vous vraiment supprimer ce client ? "
                "Sa chambre sera libérée."):
            return
        db.delete_client(self.selected_client_id)
        self.nouveau()
        self.refresh()
        self.app.refresh_rooms_tab()

    def checkout(self):
        """Marque le client comme 'Sorti' et libère sa chambre."""
        if not self.selected_client_id:
            messagebox.showwarning("Attention", "Veuillez sélectionner un client.")
            return
        client = db.get_client(self.selected_client_id)
        if not client:
            return
        if client["statut"] == "Sorti":
            messagebox.showinfo("Information", "Ce client est déjà sorti.")
            return

        if not messagebox.askyesno(
                "Confirmation",
                f"Confirmer la sortie de {client['prenom']} {client['nom']} "
                f"et libérer la chambre {client['chambre_numero'] or ''} ?"):
            return

        data = dict(client)
        data["statut"] = "Sorti"
        data["date_sortie"] = date.today().strftime("%Y-%m-%d")
        db.update_client(self.selected_client_id, data)
        self.refresh()
        self.app.refresh_rooms_tab()
        messagebox.showinfo("Succès", "Le client est marqué comme sorti et la chambre est libérée.")
    def imprimer_fiche_police(self):
        if not self.selected_client_id:
            messagebox.showwarning("Attention", "Veuillez sélectionner un client.")
            return
        client = db.get_client(self.selected_client_id)
        if not client:
            messagebox.showerror("Erreur", "Client introuvable.")
            return
        try:
            chemin = generer_fiche_police(dict(client))
            messagebox.showinfo("Succès", f"Fiche Police générée :\n{chemin}")
        except Exception as e:
            messagebox.showerror("Erreur PDF", f"Impossible de générer la fiche :\n{e}")



# ==============================================================================
# Module : tab_depenses.py
# ==============================================================================

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

    # ------------------------------------------------------------------
    def _build_ui(self):
        form_frame = ttk.LabelFrame(self, text="Nouvelle dépense / Modification")
        form_frame.pack(side="left", fill="y", padx=8, pady=8)

        ttk.Label(form_frame, text="Date *").grid(row=0, column=0, sticky="w",
                                                    padx=4, pady=4)
        self.date_entry = DateEntry(form_frame, width=12)
        self.date_entry.grid(row=0, column=1, padx=4, pady=4, sticky="w")

        ttk.Label(form_frame, text="Catégorie *").grid(row=1, column=0, sticky="w",
                                                         padx=4, pady=4)
        self.categorie_var = tk.StringVar(value=db.CATEGORIES_DEPENSE[0])
        ttk.Combobox(form_frame, textvariable=self.categorie_var,
                     values=db.CATEGORIES_DEPENSE, width=22,
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
        self.mode_var = tk.StringVar(value="Espèces")
        ttk.Combobox(form_frame, textvariable=self.mode_var,
                     values=["Espèces", "Chèque", "Carte bancaire", "Virement"],
                     width=22, state="readonly").grid(row=4, column=1, padx=4, pady=4, sticky="w")

        btn_frame = ttk.Frame(form_frame)
        btn_frame.grid(row=5, column=0, columnspan=2, pady=10)
        ttk.Button(btn_frame, text="Nouveau", command=self.nouveau).pack(
            side="left", padx=3)
        ttk.Button(btn_frame, text="Enregistrer", command=self.enregistrer).pack(
            side="left", padx=3)
        ttk.Button(btn_frame, text="✏️ Modifier", command=self.modifier).pack(
            side="left", padx=3)
        ttk.Button(btn_frame, text="Supprimer", command=self.supprimer).pack(
            side="left", padx=3)

        # ----- Liste des dépenses -----
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
        ttk.Button(filtre_frame, text="🖨️ Imprimer la liste",
                   command=self.imprimer_liste).pack(side="left", padx=8)

        columns = ("id", "date", "categorie", "description", "montant", "mode")
        headers = {
            "id": "ID", "date": "Date", "categorie": "Catégorie",
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

    # ------------------------------------------------------------------
    def reset_filtre(self):
        self.filtre_debut.set("01/01/2000")
        self.filtre_fin.set_date(date.today())
        self.refresh()

    def refresh(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        debut = date_str_to_iso(self.filtre_debut.get()) or "0000-01-01"
        fin = date_str_to_iso(self.filtre_fin.get()) or "9999-12-31"

        depenses = db.get_depenses(debut, fin)
        total = 0.0
        for d in depenses:
            total += d["montant"]
            self.tree.insert("", "end", iid=str(d["id"]), values=(
                d["id"], iso_to_date_str(d["date"]) or d["date"],
                d["categorie"], d["description"],
                f"{d['montant']:.3f}", d["mode_paiement"],
            ))
        self.total_var.set(f"Total des dépenses affichées : {total:.3f} TND")
    def imprimer_liste(self):
        items = self.tree.get_children()
        if not items:
            messagebox.showwarning("Attention", "Aucune dépense à imprimer.")
            return

        depenses_data = []
        for iid in items:
            valeurs = self.tree.item(iid)["values"]
            # valeurs = (id, date, categorie, description, montant, mode)
            date_d, categorie, description, montant_str, mode = valeurs[1:]
            try:
                montant = float(str(montant_str).replace(",", "."))
            except ValueError:
                montant = 0.0
            depenses_data.append((date_d, categorie, description, montant, mode))

        nom_fichier_defaut = f"Liste_depenses_{date.today().strftime('%Y%m%d')}.pdf"
        chemin = filedialog.asksaveasfilename(
            title="Enregistrer la liste des dépenses",
            defaultextension=".pdf",
            initialfile=nom_fichier_defaut,
            filetypes=[("Fichier PDF", "*.pdf")],
        )
        if not chemin:
            return

        try:
            generer_liste_depenses_pdf(depenses_data, chemin)
        except Exception as exc:
            messagebox.showerror("Erreur", f"Impossible de générer le PDF : {exc}")
            return

        messagebox.showinfo("Succès", f"Liste exportée : {chemin}")
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

        conn_rows = db.get_depenses()
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
        self.categorie_var.set(db.CATEGORIES_DEPENSE[0])
        self.description_var.set("")
        self.montant_var.set("")
        self.mode_var.set("Espèces")
        self.tree.selection_remove(self.tree.selection())
        self.refresh()  # ← ajouter cette ligne

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
            messagebox.showerror("Erreur", "Le montant doit être un nombre positif.")
            return

        categorie = self.categorie_var.get()
        description = self.description_var.get().strip()
        mode = self.mode_var.get()

        if self.selected_depense_id:
            db.update_depense(self.selected_depense_id, date_iso, categorie,
                               description, montant, mode)
            messagebox.showinfo("Succès", "Dépense mise à jour.")
        else:
            db.add_depense(date_iso, categorie, description, montant, mode)
            messagebox.showinfo("Succès", "Dépense ajoutée.")

        self.refresh()
        self.app.refresh_stats_tab()
    def modifier(self):
        if not self.selected_depense_id:
            messagebox.showwarning("Attention", "Veuillez sélectionner une dépense dans la liste.")
            return

        # Ouvre une fenêtre de confirmation avant modification
        win = tk.Toplevel(self)
        win.title("Modifier la dépense")
        win.resizable(False, False)
        win.transient(self)
        win.grab_set()

        ttk.Label(win, text="Date *").grid(row=0, column=0, sticky="w", padx=8, pady=4)
        date_entry = DateEntry(win, width=12)
        date_entry.grid(row=0, column=1, padx=8, pady=4, sticky="w")
        date_entry.set(self.date_entry.get())

        ttk.Label(win, text="Catégorie *").grid(row=1, column=0, sticky="w", padx=8, pady=4)
        categorie_var = tk.StringVar(value=self.categorie_var.get())
        ttk.Combobox(win, textvariable=categorie_var,
                     values=db.CATEGORIES_DEPENSE, width=22,
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
                     values=["Espèces", "Chèque", "Carte bancaire", "Virement"],
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
                messagebox.showerror("Erreur", "Le montant doit être un nombre positif.")
                return

            db.update_depense(
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
            messagebox.showinfo("Succès", "Dépense modifiée avec succès.")

        btn = ttk.Frame(win)
        btn.grid(row=5, column=0, columnspan=2, pady=10)
        ttk.Button(btn, text="Confirmer", command=confirmer).pack(side="left", padx=4)
        ttk.Button(btn, text="Annuler", command=win.destroy).pack(side="left", padx=4)

    def supprimer(self):
        if not self.selected_depense_id:
            messagebox.showwarning("Attention", "Veuillez sélectionner une dépense.")
            return
        if not messagebox.askyesno("Confirmation", "Supprimer cette dépense ?"):
            return
        db.delete_depense(self.selected_depense_id)
        self.nouveau()
        self.refresh()
        self.app.refresh_stats_tab()



# ==============================================================================
# Module : tab_facturation.py
# ==============================================================================

class FacturationTab(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.lignes = []  # liste de dicts: description, quantite, prix_unitaire
        self.client_map = {}
        self.paiements = {}
        self.facture_id_map = {}
        self.soldes_factures = {}

        self._build_ui()
        self.refresh()

    # ------------------------------------------------------------------
    def _build_ui(self):
        # ----- Partie haute : sélection client -----
        top_frame = ttk.LabelFrame(self, text="Client / Séjour")
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

        ttk.Label(top_frame, text="Date d'entrée :").grid(row=2, column=0, sticky="w",
                                                            padx=4, pady=4)
        self.date_entree = DateEntry(top_frame, width=12)
        self.date_entree.grid(row=2, column=1, sticky="w", padx=4, pady=4)

        ttk.Label(top_frame, text="Date de sortie :").grid(row=3, column=0, sticky="w",
                                                             padx=4, pady=4)
        self.date_sortie = DateEntry(top_frame, width=12)
        self.date_sortie.grid(row=3, column=1, sticky="w", padx=4, pady=4)

        ttk.Button(top_frame, text="Recalculer hébergement",
                   command=self.recalculer_hebergement).grid(
            row=2, column=2, rowspan=2, padx=8)

        # ----- Partie centrale : lignes de facturation -----
        mid_frame = ttk.LabelFrame(self, text="Détail de la facture")
        mid_frame.pack(fill="both", expand=False, padx=8, pady=4)

        columns = ("description", "quantite", "prix", "montant", "statut")
        headers = {"description": "Description", "quantite": "Quantité",
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

        # Ajout d'une ligne (service supplémentaire)
        add_frame = ttk.Frame(mid_frame)
        add_frame.pack(fill="x", padx=4, pady=4)

        ttk.Label(add_frame, text="Description").pack(side="left")
        self.desc_var = tk.StringVar()
        ttk.Entry(add_frame, textvariable=self.desc_var, width=30).pack(
            side="left", padx=4)

        ttk.Label(add_frame, text="Qté").pack(side="left")
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
        ttk.Button(add_frame, text="Supprimer ligne sélectionnée",
                   command=self.supprimer_ligne).pack(side="left", padx=4)

        # ----- Partie basse : totaux + actions -----
        # ----- Partie basse : totaux + actions -----
        bottom_frame = ttk.LabelFrame(self, text="Totaux et validation")
        bottom_frame.pack(fill="x", padx=8, pady=8)

        # Ligne 0 : Remise + Mode paiement + Total
        ttk.Label(bottom_frame, text="Remise (TND) :").grid(
            row=0, column=0, sticky="w", padx=4, pady=4)
        self.remise_var = tk.StringVar(value="0,000")
        self.remise_var.trace_add("write", lambda *a: self.update_total())
        self.remise_entry = ttk.Entry(bottom_frame, textvariable=self.remise_var, width=10)
        self.remise_entry.grid(row=0, column=1, sticky="w", padx=4, pady=4)
        self.remise_entry.bind("<FocusOut>", lambda e: _formater_prix(self.remise_var))

        ttk.Label(bottom_frame, text="Mode de paiement :").grid(
            row=0, column=2, sticky="w", padx=4, pady=4)
        self.mode_var = tk.StringVar(value="Espèces")
        ttk.Combobox(bottom_frame, textvariable=self.mode_var,
                     values=["Espèces", "Chèque", "Carte bancaire", "Virement"],
                     width=15, state="readonly").grid(row=0, column=3, padx=4, pady=4)

        self.total_var = tk.StringVar(value="Total : 0.000 TND")
        ttk.Label(bottom_frame, textvariable=self.total_var,
                font=("Segoe UI", 12, "bold")).grid(
            row=0, column=4, padx=20, pady=4)
        ttk.Button(bottom_frame, text="💰 Payer",
                command=self.ouvrir_paiement).grid(
            row=0, column=5, padx=8, pady=4)

        # Ligne 1 : Montant en lettres
        self.lettres_var = tk.StringVar(value="")
        ttk.Label(bottom_frame, textvariable=self.lettres_var,
                  wraplength=700, font=("Segoe UI", 9, "italic")).grid(
            row=1, column=0, columnspan=5, sticky="w", padx=4, pady=2)

        # Ligne 2 : Case à cocher "Facture payée"
        self.paye_var = tk.BooleanVar(value=False)
        self.check_paye = ttk.Checkbutton(
            bottom_frame, text="✅ Facture payée",
            variable=self.paye_var,
            command=self.on_toggle_paye
        )
        self.check_paye.grid(row=2, column=0, columnspan=2, sticky="w", padx=4, pady=4)

        # Ligne 3 : Boutons
        action_frame = ttk.Frame(bottom_frame)
        action_frame.grid(row=3, column=0, columnspan=5, pady=8)
        ttk.Button(action_frame, text="Générer la facture",
                   command=self.generer_facture).pack(side="left", padx=4)
        ttk.Button(action_frame, text="Réinitialiser",
                   command=self.reinitialiser).pack(side="left", padx=4)
        ttk.Button(action_frame, text="📋 Historique des factures",
                   command=self.ouvrir_historique).pack(side="left", padx=4)
        ttk.Button(action_frame, text="👁️ Voir la facture",          # ← AJOUTER
                   command=self.voir_facture_client).pack(side="left", padx=4)

        # ----- Historique des factures -----
        

    # ------------------------------------------------------------------
    def refresh(self):
        self.client_map = {}
        valeurs = []

        # Clients en cours
        for c in db.get_clients("En cours"):
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

        # Réservations actives
        for r in db.get_reservations("RESERVE"):
            if not r["chambre_id"]:
                continue
            texte = (f"[RÉSERV.] {r['nom']} {r['prenom']} - Chambre "
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
        self.combo_client["values"] = valeurs  # ← AJOUTER CETTE LIGNE

        self.refresh_historique()
        

        # Recharger les paiements depuis la base
        # Recharger les paiements depuis la base
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
            # Afficher tous les clients/réservations
            self.combo_client["values"] = list(self.client_map.keys())
            return

        filtres = [
            texte for texte, c in self.client_map.items()
            if recherche in str(c.get("numero_identifiant", "")).lower()
        ]
        self.combo_client["values"] = filtres

        # Sélectionner automatiquement si un seul résultat
        if len(filtres) == 1:
            self.client_var.set(filtres[0])
            self.on_client_selected()
        elif len(filtres) == 0:
            self.client_var.set("")
            self.chambre_label_var.set("-")

    def refresh_historique(self):
        pass  # plus utilisé, l'historique est dans une fenêtre séparée

    # ------------------------------------------------------------------
    def on_client_selected(self, event=None):
        texte = self.client_var.get()
        statut = self.paiements.get(texte, False)
        self.paye_var.set(statut is True)
        client = self.client_map.get(texte)
        if not client:
            return

        prefix = "📋 Réservation" if client.get("is_reservation") else "👤 Client"
        self.chambre_label_var.set(
            f"{prefix} — Chambre {client['chambre_numero']} "
            f"({client['chambre_prix']:.3f} TND / nuit)")

        if client["date_entree"]:
            self.date_entree.set(iso_to_date_str(client["date_entree"]))
        else:
            self.date_entree.set_date(date.today())

        if client["date_sortie"]:
            self.date_sortie.set(iso_to_date_str(client["date_sortie"]))
        else:
            self.date_sortie.set_date(date.today())

        # Charger les lignes depuis la base si facture existante
        texte_client = self.client_var.get()
        facture_id = self.facture_id_map.get(texte_client)
        if facture_id:
            _, lignes_db = db.get_facture(facture_id)
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
            messagebox.showwarning("Attention", "Veuillez d'abord sélectionner un client.")
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

        # Supprimer toute ligne d'hébergement existante (générée auto)
        self.lignes = [l for l in self.lignes if not l.get("auto")]

        description = (f"Hébergement - Chambre {client['chambre_numero']} "
                        f"({nb_nuits} nuit{'s' if nb_nuits > 1 else ''})")
        self.lignes.insert(0, {
            "description": description,
            "quantite": nb_nuits,
            "prix_unitaire": prix_chambre,
            "auto": True,
        })
        self.refresh_lignes()

    # ------------------------------------------------------------------
    def refresh_lignes(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        statut_paiement = self.paiements.get(self.client_var.get(), False)

        if statut_paiement == True:
            statut_texte = "✅ Payée"
            tag = "paye"
        elif statut_paiement == "partiel":
            solde = self.soldes_factures.get(self.client_var.get(), 0.0)
            statut_texte = f"⚠️ Partiellement payée - Reste {solde:.3f} TND".replace(".", ",")
            tag = "partiel"
        else:
            statut_texte = "⏳ En attente"
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
        """Retourne True si la facture est payée (action bloquée)."""
        if self.paiements.get(self.client_var.get(), False):
            messagebox.showwarning(
                "Action impossible",
                "Cette facture est déjà marquée comme payée.\n"
                "Aucune modification n'est autorisée.")
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
            messagebox.showerror("Erreur", "Quantité et prix doivent être numériques.")
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
            messagebox.showwarning("Attention", "Veuillez sélectionner une ligne.")
            return
        index = int(selection[0])
        del self.lignes[index]
        self.refresh_lignes()

    def update_total(self):
        sous_total = sum(l["quantite"] * l["prix_unitaire"] for l in self.lignes)
        try:
            remise = float(self.remise_var.get().replace(",", "."))
        except ValueError:
            remise = 0.0
        total = round(sous_total - remise, 3)
        if total < 0:
            total = 0.0
        self.total_var.set(f"Total : {total:.3f} TND")
        if total > 0:
            self.lettres_var.set(
                "Arrêtée la présente facture à la somme de : "
                + montant_en_lettres(total))
        else:
            self.lettres_var.set("")

    # ------------------------------------------------------------------
    def reinitialiser(self):
        self.client_var.set("")
        self.chambre_label_var.set("-")
        self.lignes = []
        self.remise_var.set("0,000")
        self.mode_var.set("Espèces")
        self.paye_var.set(False)   # ← ajouter cette ligne
        self.refresh_lignes()
    def on_toggle_paye(self):
        if self.paye_var.get():
            confirme = messagebox.askyesno(
                "Confirmer le paiement",
                "Confirmez-vous que cette facture a été payée ?\n"
                "Cette action ne pourra pas être annulée.")
            if not confirme:
                self.paye_var.set(False)
            else:
                self.paiements[self.client_var.get()] = True
                # Sauvegarder en base
                facture_id = self.facture_id_map.get(self.client_var.get())
                if facture_id:
                    db.set_facture_payee(facture_id)
                self.refresh_lignes()
        else:
            messagebox.showwarning(
                "Action impossible",
                "Une facture marquée comme payée ne peut plus être modifiée.")
            self.paye_var.set(True)

    def generer_facture(self):
        texte = self.client_var.get()
        client = self.client_map.get(texte)
        if not client:
            messagebox.showerror("Erreur", "Veuillez sélectionner un client.")
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

        # Si c'est une réservation, on passe client_id=None
        # (pas encore de client créé dans la table clients)
        client_id = None if client.get("is_reservation") else client["id"]
        nom_client = f"{client['prenom']} {client['nom']}".strip()

        facture_id, numero, total = db.create_facture(
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
            db.set_facture_payee(facture_id)
            self.paiements[self.client_var.get()] = True

        statut_paiement = "✅ Payée" if self.paye_var.get() else "⏳ En attente de paiement"
        messagebox.showinfo(
            "Facture créée",
            f"Facture {numero} créée avec succès.\n"
            f"Total : {total:.3f} TND\n"
            f"Statut : {statut_paiement}")

        self.refresh_historique()
        self.app.refresh_stats_tab()

        if messagebox.askyesno("Export PDF",
                                "Voulez-vous générer le PDF de cette facture ?"):
            self._exporter_pdf(facture_id, numero)

    # ------------------------------------------------------------------
   
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
            messagebox.showerror("Erreur", f"Impossible de générer le PDF : {exc}")
            return

        messagebox.showinfo("Succès", f"Facture exportée : {chemin}")

        # Ouvrir automatiquement le PDF si possible (Windows)
        try:
            if os.name == "nt":
                os.startfile(chemin)
        except Exception:
            pass
    def ouvrir_historique(self):
        win = tk.Toplevel(self)
        win.title("Historique des factures")
        win.geometry("1100x700")
        win.transient(self)

        # ----- Barre de filtres -----
        filtre_frame = ttk.LabelFrame(win, text="Filtres")
        filtre_frame.pack(fill="x", padx=8, pady=8)

        ttk.Label(filtre_frame, text="Critère :").grid(row=0, column=0, padx=6, pady=6, sticky="w")
        critere_var = tk.StringVar(value="Toutes les factures")
        combo_critere = ttk.Combobox(
            filtre_frame, textvariable=critere_var,
            values=["Toutes les factures", "Par date", "Par N° identifiant client"],
            width=25, state="readonly"
        )
        combo_critere.grid(row=0, column=1, padx=6, pady=6, sticky="w")

        lbl_debut = ttk.Label(filtre_frame, text="Du :")
        date_debut = DateEntry(filtre_frame, width=12)
        lbl_fin = ttk.Label(filtre_frame, text="Au :")
        date_fin = DateEntry(filtre_frame, width=12)
        date_debut.set_date(date.today().replace(day=1))

        lbl_cin = ttk.Label(filtre_frame, text="N° identifiant :")
        cin_var = tk.StringVar()
        entry_cin = ttk.Entry(filtre_frame, textvariable=cin_var, width=22)

        ttk.Button(
            filtre_frame, text="🔍 Filtrer",
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
            elif c == "Par N° identifiant client":
                lbl_cin.grid(row=0, column=2, padx=4, pady=6, sticky="w")
                entry_cin.grid(row=0, column=3, padx=4, pady=6, sticky="w")

        critere_var.trace_add("write", on_critere_change)

        # ----- Tableau des factures -----
        hist_columns = ("id", "numero", "date", "client", "identifiant", "total", "statut")
        headers_h = {
            "id": "ID", "numero": "N° Facture", "date": "Date",
            "client": "Client", "identifiant": "N° Identifiant",
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
                factures = db.get_factures()
            elif c == "Par date":
                debut = date_str_to_iso(date_debut.get()) or "0000-01-01"
                fin = date_str_to_iso(date_fin.get()) or "9999-12-31"
                factures = db.get_factures(debut, fin)
            elif c == "Par N° identifiant client":
                cin = cin_var.get().strip().lower()
                if not cin:
                    messagebox.showwarning(
                        "Attention", "Veuillez saisir un numéro d'identifiant.", parent=win)
                    return
                toutes = db.get_factures()
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
                factures = db.get_factures()

            for f in factures:
                client_nom = f"{f['prenom'] or ''} {f['nom'] or ''}".strip()
                if not client_nom:
                    client_nom = f["nom_client"] or "—"

                identifiant = "—"
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
                statut_txt = "✅ Payée" if est_paye else "⏳ En attente"
                tag = "paye" if est_paye else "non_paye"

                hist_tree.insert("", "end", iid=str(f["id"]), tags=(tag,), values=(
                    f["id"], f["numero"],
                    iso_to_date_str(f["date_facture"]) or f["date_facture"],
                    client_nom, identifiant,
                    f"{f['montant_total']:.3f}",
                    statut_txt,
                ))

            nb = len(hist_tree.get_children())
            compteur_var.set(f"{nb} facture(s) trouvée(s)")

        appliquer_filtre()

        # ----- Boutons bas -----
        btn_frame = ttk.Frame(win)
        btn_frame.pack(pady=6)
        ttk.Button(
            btn_frame, text="👁️ Voir la facture",
            command=lambda: self._voir_depuis_historique(hist_tree)
        ).pack(side="left", padx=4)
        ttk.Button(
            btn_frame, text="📄 Exporter en PDF",
            command=lambda: self._exporter_depuis_historique(hist_tree)
        ).pack(side="left", padx=4)
        ttk.Button(
            btn_frame, text="🖨️ Imprimer la liste",
            command=lambda: self._imprimer_liste_factures(hist_tree)
        ).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="Fermer",
                command=win.destroy).pack(side="left", padx=4)
    def _voir_depuis_historique(self, hist_tree):
        selection = hist_tree.selection()
        if not selection:
            messagebox.showwarning("Attention",
                                "Veuillez sélectionner une facture.")
            return
        facture_id = int(selection[0])
        facture, lignes = db.get_facture(facture_id)
        if facture is None:
            messagebox.showerror("Erreur", "Facture introuvable en base.")
            return

        # Vérifier si la facture est payée
        est_paye = bool(facture["payee"]) if "payee" in facture.keys() else False
        self._afficher_fenetre_facture(facture, lignes, facture_id)


    def _exporter_depuis_historique(self, hist_tree):
        selection = hist_tree.selection()
        if not selection:
            messagebox.showwarning("Attention",
                                "Veuillez sélectionner une facture.")
            return
        facture_id = int(selection[0])
        facture, _ = db.get_facture(facture_id)
        if facture is None:
            return
        if not messagebox.askyesno(
                "Confirmation",
                "Confirmez-vous que cette facture a bien été payée ?"):
            messagebox.showwarning(
                "PDF non disponible",
                "Le PDF ne peut être généré que pour une facture payée.")
            return
        self._exporter_pdf(facture_id, facture["numero"])
    def _imprimer_liste_factures(self, hist_tree):
        items = hist_tree.get_children()
        if not items:
            messagebox.showwarning("Attention", "Aucune facture à imprimer.")
            return

        factures_data = []
        for iid in items:
            valeurs = hist_tree.item(iid)["values"]
            # valeurs = (id, numero, date, client, identifiant, total, statut)
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
            messagebox.showerror("Erreur", f"Impossible de générer le PDF : {exc}")
            return

        messagebox.showinfo("Succès", f"Liste exportée : {chemin}")
        try:
            if os.name == "nt":
                os.startfile(chemin)
        except Exception:
            pass
    def ouvrir_paiement(self):
        if not self.client_var.get():
            messagebox.showwarning("Attention", "Veuillez sélectionner un client.")
            return
        if not self.lignes:
            messagebox.showwarning("Attention", "Aucune ligne de facturation.")
            return
        if self.paiements.get(self.client_var.get(), False):
            messagebox.showinfo("Information", "Cette facture est déjà payée.")
            return

        # Générer la facture automatiquement si pas encore fait
        if not self.facture_id_map.get(self.client_var.get()):
            texte = self.client_var.get()
            client = self.client_map.get(texte)
            d_entree = self.date_entree.get_date()
            d_sortie = self.date_sortie.get_date()
            if not d_entree or not d_sortie:
                messagebox.showerror("Erreur", "Dates invalides.")
                return
            nb_nuits = max((d_sortie - d_entree).days, 1)
            try:
                remise = float(self.remise_var.get().replace(",", "."))
            except ValueError:
                remise = 0.0
            lignes_db = [(l["description"], l["quantite"], l["prix_unitaire"]) for l in self.lignes]
            client_id = None if client.get("is_reservation") else client["id"]
            nom_client = f"{client['prenom']} {client['nom']}".strip()
            facture_id, numero, total = db.create_facture(
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
            self.facture_id_map[self.client_var.get()] = facture_id

        win = tk.Toplevel(self)
        win.title("💰 Paiement de la facture")
        win.resizable(False, False)
        win.transient(self)
        win.grab_set()

        BLEU = "#1F4E79"
        header = tk.Frame(win, bg=BLEU)
        header.pack(fill="x")
        tk.Label(header, text="Paiement de la facture", bg=BLEU, fg="white",
                font=("Segoe UI", 13, "bold")).pack(pady=12, padx=16)

        frame = ttk.Frame(win)
        frame.pack(padx=20, pady=12)

        sous_total = sum(l["quantite"] * l["prix_unitaire"] for l in self.lignes)
        try:
            remise = float(self.remise_var.get().replace(",", "."))
        except ValueError:
            remise = 0.0
        total = round(sous_total - remise, 3)

        ttk.Label(frame, text="Montant total à payer :",
                font=("Segoe UI", 10, "bold")).grid(row=0, column=0, sticky="w", pady=6)
        ttk.Label(frame, text=f"{total:.3f} TND",
                font=("Segoe UI", 12, "bold"),
                foreground="#1F4E79").grid(row=0, column=1, sticky="w", padx=12, pady=6)

        ttk.Label(frame, text="Mode de paiement :").grid(row=1, column=0, sticky="w", pady=6)
        mode_var = tk.StringVar(value=self.mode_var.get())
        ttk.Combobox(frame, textvariable=mode_var,
                    values=["Espèces", "Chèque", "Carte bancaire", "Virement"],
                    width=20, state="readonly").grid(row=1, column=1, sticky="w", padx=12, pady=6)

        ttk.Label(frame, text="Montant reçu (TND) :").grid(row=2, column=0, sticky="w", pady=6)
        recu_var = tk.StringVar(value=f"{total:.3f}".replace(".", ","))
        ttk.Entry(frame, textvariable=recu_var, width=15).grid(
            row=2, column=1, sticky="w", padx=12, pady=6)

        monnaie_var = tk.StringVar(value="Monnaie à rendre : 0.000 TND")
        ttk.Label(frame, textvariable=monnaie_var,
                font=("Segoe UI", 10, "italic"),
                foreground="#1F8A4C").grid(row=3, column=0, columnspan=2, pady=6)

        def calculer_monnaie(*args):
            try:
                recu = float(recu_var.get().replace(",", "."))
                if recu >= total:
                    monnaie = round(recu - total, 3)
                    monnaie_var.set(f"Monnaie à rendre : {monnaie:.3f} TND")
                else:
                    solde = round(total - recu, 3)
                    monnaie_var.set(f"⚠️ Paiement partiel — Solde restant : {solde:.3f} TND")
            except ValueError:
                monnaie_var.set("Montant reçu invalide")

        recu_var.trace_add("write", calculer_monnaie)

        def confirmer_paiement():
            try:
                recu = float(recu_var.get().replace(",", "."))
                if recu <= 0:
                    messagebox.showerror("Erreur",
                        "Le montant reçu doit être positif.", parent=win)
                    return
            except ValueError:
                messagebox.showerror("Erreur", "Montant reçu invalide.", parent=win)
                return

            facture_id = self.facture_id_map.get(self.client_var.get())
            texte = self.client_var.get()
            client = self.client_map.get(texte)

            if recu >= total:
                # ----- Paiement complet -----
                self.mode_var.set(mode_var.get())
                self.paye_var.set(True)
                self.paiements[texte] = True

                if facture_id:
                    db.set_facture_payee(facture_id)

                if client and not client.get("is_reservation") and client.get("id"):
                    db.set_client_solde(client["id"], 0.0)

                self.refresh_lignes()
                self.app.refresh_clients_tab()
                win.destroy()
                messagebox.showinfo(
                    "Paiement confirmé",
                    f"Paiement complet de {total:.3f} TND confirmé.\n"
                    f"Mode : {mode_var.get()}\n"
                    f"Monnaie rendue : {round(recu - total, 3):.3f} TND")

            else:
                # ----- Paiement partiel -----
                solde_restant = round(total - recu, 3)

                if facture_id:
                    db.set_facture_paiement_partiel(facture_id, recu)

                if client and not client.get("is_reservation") and client.get("id"):
                    db.set_client_solde(client["id"], solde_restant)

                self.paiements[texte] = "partiel"

                self.refresh_lignes()
                self.app.refresh_clients_tab()
                win.destroy()
                messagebox.showinfo(
                    "Paiement partiel enregistré",
                    f"Montant reçu : {recu:.3f} TND\n"
                    f"Solde restant : {solde_restant:.3f} TND\n"
                    f"Le solde a été ajouté à la fiche client.")

        btn_frame = ttk.Frame(win)
        btn_frame.pack(pady=12)
        ttk.Button(btn_frame, text="✅ Confirmer le paiement",
                command=confirmer_paiement).pack(side="left", padx=6)
        ttk.Button(btn_frame, text="Annuler",
                command=win.destroy).pack(side="left", padx=6)
    def voir_facture_client(self):
        texte = self.client_var.get()
        if not texte:
            messagebox.showwarning("Attention", "Veuillez sélectionner un client.")
            return

        facture_id = self.facture_id_map.get(texte)
        if not facture_id:
            messagebox.showwarning(
                "Aucune facture",
                "Aucune facture trouvée pour ce client.\n"
                "Générez d'abord la facture.")
            return

        

        facture, lignes = db.get_facture(facture_id)
        if facture is None:
            messagebox.showerror("Erreur", "Facture introuvable en base.")
            return

        self._afficher_fenetre_facture(facture, lignes, facture_id)


    def _afficher_fenetre_facture(self, facture, lignes, facture_id):
        import tempfile
        import subprocess
        import platform

        # Générer le PDF dans un dossier temporaire
        nom_fichier = f"Facture_{facture['numero']}.pdf"
        chemin = os.path.join(tempfile.gettempdir(), nom_fichier)

        try:
            generer_facture_pdf(facture_id, chemin)
        except Exception as exc:
            messagebox.showerror("Erreur", f"Impossible de générer l'aperçu : {exc}")
            return

        # Ouvrir le PDF avec le lecteur par défaut du système
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



# ==============================================================================
# Module : tab_statistiques.py
# ==============================================================================

PERIODES = {
    "Jour": "day",
    "Mois": "month",
    "Année": "year",
}


class StatsTab(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self._build_ui()
        self.refresh()

    # ------------------------------------------------------------------
    def _build_ui(self):
        # ----- Barre de filtres -----
        filtre_frame = ttk.Frame(self)
        filtre_frame.pack(fill="x", padx=8, pady=8)

        ttk.Label(filtre_frame, text="Du :").pack(side="left")
        self.date_debut = DateEntry(filtre_frame, width=12)
        self.date_debut.pack(side="left", padx=4)
        debut_defaut = date.today() - timedelta(days=365)
        self.date_debut.set_date(debut_defaut)

        ttk.Label(filtre_frame, text="Au :").pack(side="left", padx=(8, 0))
        self.date_fin = DateEntry(filtre_frame, width=12)
        self.date_fin.pack(side="left", padx=4)

        ttk.Label(filtre_frame, text="Regrouper par :").pack(side="left", padx=(12, 0))
        self.periode_var = tk.StringVar(value="Mois")
        ttk.Combobox(filtre_frame, textvariable=self.periode_var,
                     values=list(PERIODES.keys()), width=10,
                     state="readonly").pack(side="left", padx=4)

        ttk.Button(filtre_frame, text="Actualiser",
                   command=self.refresh).pack(side="left", padx=12)

        # Boutons de raccourcis de période
        ttk.Button(filtre_frame, text="Aujourd'hui",
                   command=self.raccourci_jour).pack(side="left", padx=2)
        ttk.Button(filtre_frame, text="Ce mois",
                   command=self.raccourci_mois).pack(side="left", padx=2)
        ttk.Button(filtre_frame, text="Cette année",
                   command=self.raccourci_annee).pack(side="left", padx=2)

        # ----- Indicateurs clés -----
        kpi_frame = ttk.Frame(self)
        kpi_frame.pack(fill="x", padx=8, pady=(0, 8))

        self.kpi_recettes = self._creer_kpi(kpi_frame, "Recettes", "#1F8A4C")
        self.kpi_depenses = self._creer_kpi(kpi_frame, "Dépenses", "#C0392B")
        self.kpi_benefice = self._creer_kpi(kpi_frame, "Bénéfice", "#1F4E79")
        self.kpi_occupation = self._creer_kpi(kpi_frame, "Taux d'occupation", "#8E44AD")

        # ----- Zone principale : tableau + graphiques -----
        main_frame = ttk.Frame(self)
        main_frame.pack(fill="both", expand=True, padx=8, pady=8)

        # Tableau récapitulatif
        table_frame = ttk.LabelFrame(main_frame, text="Récapitulatif par période")
        table_frame.pack(side="left", fill="both", expand=False, padx=(0, 8))

        columns = ("periode", "recettes", "depenses", "benefice")
        headers = {"periode": "Période", "recettes": "Recettes (TND)",
                   "depenses": "Dépenses (TND)", "benefice": "Bénéfice (TND)"}
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings",
                                  height=18)
        for c in columns:
            self.tree.heading(c, text=headers[c])
            self.tree.column(c, width=110, anchor="center")
        self.tree.pack(fill="both", expand=True, padx=4, pady=4)

        # Graphiques
        graph_frame = ttk.LabelFrame(main_frame, text="Graphiques")
        graph_frame.pack(side="left", fill="both", expand=True)

        self.figure = Figure(figsize=(7, 6), dpi=90)
        self.ax1 = self.figure.add_subplot(211)
        self.ax2 = self.figure.add_subplot(212)
        self.figure.tight_layout(pad=3.0)

        self.canvas = FigureCanvasTkAgg(self.figure, master=graph_frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

    def _creer_kpi(self, parent, titre, couleur):
        frame = tk.Frame(parent, bg=couleur, bd=0)
        frame.pack(side="left", fill="x", expand=True, padx=4, pady=4)
        tk.Label(frame, text=titre, bg=couleur, fg="white",
                 font=("Segoe UI", 10, "bold")).pack(pady=(8, 0))
        var = tk.StringVar(value="--")
        tk.Label(frame, textvariable=var, bg=couleur, fg="white",
                 font=("Segoe UI", 14, "bold")).pack(pady=(0, 8))
        return var

    # ------------------------------------------------------------------
    def raccourci_jour(self):
        today = date.today()
        self.date_debut.set_date(today)
        self.date_fin.set_date(today)
        self.periode_var.set("Jour")
        self.refresh()

    def raccourci_mois(self):
        today = date.today()
        self.date_debut.set_date(date(today.year, today.month, 1))
        self.date_fin.set_date(today)
        self.periode_var.set("Jour")
        self.refresh()

    def raccourci_annee(self):
        today = date.today()
        self.date_debut.set_date(date(today.year, 1, 1))
        self.date_fin.set_date(today)
        self.periode_var.set("Mois")
        self.refresh()

    # ------------------------------------------------------------------
    def refresh(self):
        debut = date_str_to_iso(self.date_debut.get())
        fin = date_str_to_iso(self.date_fin.get())
        if not debut or not fin:
            return

        group_by = PERIODES.get(self.periode_var.get(), "month")

        recettes = {r["periode"]: r["total"] or 0.0
                    for r in db.recap_recettes(debut, fin, group_by)}
        depenses = {r["periode"]: r["total"] or 0.0
                    for r in db.recap_depenses(debut, fin, group_by)}

        periodes = sorted(set(recettes.keys()) | set(depenses.keys()))

        for item in self.tree.get_children():
            self.tree.delete(item)

        total_recettes = 0.0
        total_depenses = 0.0
        for p in periodes:
            r = recettes.get(p, 0.0)
            d = depenses.get(p, 0.0)
            benefice = r - d
            total_recettes += r
            total_depenses += d
            self.tree.insert("", "end", values=(
                self._formatter_periode(p, group_by),
                f"{r:.3f}", f"{d:.3f}", f"{benefice:.3f}",
            ))

        total_benefice = total_recettes - total_depenses
        occ, total_chambres = db.taux_occupation()
        taux = (occ / total_chambres * 100) if total_chambres else 0

        self.kpi_recettes.set(f"{total_recettes:.3f} TND")
        self.kpi_depenses.set(f"{total_depenses:.3f} TND")
        self.kpi_benefice.set(f"{total_benefice:.3f} TND")
        self.kpi_occupation.set(f"{taux:.1f} %  ({occ}/{total_chambres})")

        self._dessiner_graphiques(periodes, recettes, depenses, group_by)

    def _formatter_periode(self, periode, group_by):
        try:
            if group_by == "day":
                return datetime.strptime(periode, "%Y-%m-%d").strftime("%d/%m/%Y")
            if group_by == "month":
                return datetime.strptime(periode, "%Y-%m").strftime("%m/%Y")
            return periode  # année
        except ValueError:
            return periode

    def _dessiner_graphiques(self, periodes, recettes, depenses, group_by):
        labels = [self._formatter_periode(p, group_by) for p in periodes]
        valeurs_recettes = [recettes.get(p, 0.0) for p in periodes]
        valeurs_depenses = [depenses.get(p, 0.0) for p in periodes]
        benefices = [r - d for r, d in zip(valeurs_recettes, valeurs_depenses)]

        self.ax1.clear()
        self.ax2.clear()

        if periodes:
            x = range(len(periodes))
            largeur = 0.4

            self.ax1.bar([i - largeur / 2 for i in x], valeurs_recettes,
                          width=largeur, label="Recettes", color="#1F8A4C")
            self.ax1.bar([i + largeur / 2 for i in x], valeurs_depenses,
                          width=largeur, label="Dépenses", color="#C0392B")
            self.ax1.set_xticks(list(x))
            self.ax1.set_xticklabels(labels, rotation=45, ha="right", fontsize=7)
            self.ax1.set_title("Recettes vs Dépenses", fontsize=10)
            self.ax1.set_ylabel("TND")
            self.ax1.legend(fontsize=8)

            self.ax2.plot(list(x), benefices, marker="o", color="#1F4E79",
                           label="Bénéfice")
            self.ax2.axhline(0, color="grey", linewidth=0.8)
            self.ax2.set_xticks(list(x))
            self.ax2.set_xticklabels(labels, rotation=45, ha="right", fontsize=7)
            self.ax2.set_title("Évolution du bénéfice", fontsize=10)
            self.ax2.set_ylabel("TND")
            self.ax2.legend(fontsize=8)
        else:
            self.ax1.text(0.5, 0.5, "Aucune donnée pour cette période",
                           ha="center", va="center")
            self.ax2.text(0.5, 0.5, "Aucune donnée pour cette période",
                           ha="center", va="center")

        self.figure.tight_layout(pad=3.0)
        self.canvas.draw()



# ==============================================================================
# Module : tab_parametres.py
# ==============================================================================

class ParametresTab(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app

        frame = ttk.LabelFrame(self, text="Informations de l'hôtel (en-tête de facture)")
        frame.pack(padx=16, pady=16, anchor="nw")

        self.vars = {}
        champs = [
            ("nom_hotel", "Nom de l'hôtel"),
            ("adresse_hotel", "Adresse"),
            ("telephone_hotel", "Téléphone"),
            ("matricule_fiscal", "Matricule fiscal"),
        ]
        for i, (cle, label) in enumerate(champs):
            ttk.Label(frame, text=label).grid(row=i, column=0, sticky="w",
                                                padx=8, pady=6)
            var = tk.StringVar(value=db.get_parametre(cle, ""))
            self.vars[cle] = var
            ttk.Entry(frame, textvariable=var, width=50).grid(
                row=i, column=1, sticky="w", padx=8, pady=6)

        ttk.Label(frame, text="Prochain numéro de facture").grid(
            row=len(champs), column=0, sticky="w", padx=8, pady=6)
        self.vars["prochain_numero_facture"] = tk.StringVar(
            value=db.get_parametre("prochain_numero_facture", "1"))
        ttk.Entry(frame, textvariable=self.vars["prochain_numero_facture"],
                  width=15).grid(row=len(champs), column=1, sticky="w",
                                  padx=8, pady=6)

        ttk.Button(frame, text="Enregistrer",
                   command=self.enregistrer).grid(
            row=len(champs) + 1, column=0, columnspan=2, pady=12)

        # Informations sur la base de données
        info_frame = ttk.LabelFrame(self, text="À propos")
        info_frame.pack(padx=16, pady=16, anchor="nw", fill="x")
        ttk.Label(info_frame, text=(
            "Logiciel de gestion d'hôtel\n"
            "Base de données SQLite : hotel.db (dans le dossier de l'application)\n"
            "Devise utilisée : Dinar Tunisien (TND), 1 TND = 1000 millimes"
        ), justify="left").pack(padx=8, pady=8, anchor="w")

    def enregistrer(self):
        try:
            int(self.vars["prochain_numero_facture"].get())
        except ValueError:
            messagebox.showerror("Erreur", "Le prochain numéro de facture doit être un entier.")
            return

        for cle, var in self.vars.items():
            db.set_parametre(cle, var.get())

        messagebox.showinfo("Succès", "Paramètres enregistrés.")


# ==============================================================================
# Module : tab_reservations.py
# ==============================================================================

STATUTS_RESERVATION = ["RESERVE", "ANNULE"]
COULEURS_STATUT_REZ = {
    "RESERVE": "#FB8C00",
    "ANNULE":  "#9E9E9E",
}


class ReservationsTab(tk.Frame):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.selected_reservation_id = None
        self._build_ui()
        self.refresh()

    # ------------------------------------------------------------------
    def _build_ui(self):
        # ----- Barre supérieure : filtres + bouton nouveau -----
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
            top_frame, text="+ Nouvelle réservation",
            command=self.nouvelle_reservation
        ).pack(side="right", padx=4)
        ttk.Button(
            top_frame, text="✏️ Modifier",
            command=self.modifier_reservation
        ).pack(side="right", padx=4)
        ttk.Button(
            top_frame, text="🗑️ Supprimer",
            command=self.supprimer_reservation
        ).pack(side="right", padx=4)
        ttk.Button(
            top_frame, text="✅ Check-in",
            command=self.checkin_reservation
        ).pack(side="right", padx=4)

        # ----- Liste des réservations -----
        list_frame = ttk.Frame(self)
        list_frame.pack(fill="both", expand=True, padx=8, pady=8)

        columns = ("id", "nom", "prenom", "telephone", "chambre",
                   "arrivee", "depart", "nb_personnes", "statut")
        headers = {
            "id": "ID", "nom": "Nom", "prenom": "Prénom",
            "telephone": "Téléphone", "chambre": "Chambre",
            "arrivee": "Arrivée", "depart": "Départ",
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

        # Couleurs par statut
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

    # ------------------------------------------------------------------
    def refresh(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        statut = self.filtre_statut.get()
        reservations = db.get_reservations(
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
                r["chambre_numero"] or "—",
                iso_to_date_str(r["date_arrivee"]) or r["date_arrivee"],
                iso_to_date_str(r["date_depart"]) or r["date_depart"],
                r["nb_personnes"],
                r["statut"],
            ))
            total += 1

        self.compteur_var.set(f"{total} réservation(s) affichée(s)")

    def _on_select(self, event=None):
        selection = self.tree.selection()
        if selection:
            self.selected_reservation_id = int(selection[0])

    # ------------------------------------------------------------------
    def _ouvrir_formulaire(self, reservation=None):
        """Fenêtre modale pour ajouter ou modifier une réservation."""
        win = tk.Toplevel(self)
        win.title("Nouvelle réservation" if reservation is None
                  else f"Modifier réservation #{reservation['id']}")
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

        # Champs texte
        def entry(parent, var, width=24):
            return ttk.Entry(parent, textvariable=var, width=width)

        nom_var = tk.StringVar(value=reservation["nom"] if reservation else "")
        prenom_var = tk.StringVar(
            value=reservation["prenom"] if reservation else "")
        tel_var = tk.StringVar(
            value=reservation["telephone"] if reservation else "")
        type_id_var = tk.StringVar(
            value=reservation["type_identifiant"] if reservation
            else db.TYPES_IDENTIFIANT[0])
        num_id_var = tk.StringVar(
            value=reservation["numero_identifiant"] if reservation else "")
        nb_var = tk.StringVar(
            value=str(reservation["nb_personnes"]) if reservation else "1")
        notes_var = tk.StringVar(
            value=reservation["notes"] if reservation else "")
        statut_var = tk.StringVar(
            value=reservation["statut"] if reservation else "RESERVE")

        row(0, "Nom *", lambda p: entry(p, nom_var))
        row(1, "Prénom *", lambda p: entry(p, prenom_var))
        row(2, "Téléphone", lambda p: entry(p, tel_var))

        ttk.Label(frame, text="Type d'identifiant").grid(
            row=3, column=0, sticky="w", padx=6, pady=4)
        ttk.Combobox(frame, textvariable=type_id_var,
                     values=db.TYPES_IDENTIFIANT, width=22,
                     state="readonly").grid(row=3, column=1, sticky="w",
                                            padx=6, pady=4)

        row(4, "N° identifiant", lambda p: entry(p, num_id_var))

        # Chambre
        ttk.Label(frame, text="Chambre").grid(
            row=5, column=0, sticky="w", padx=6, pady=4)
        chambres = db.get_chambres()
        chambre_map = {"— Aucune —": None}
        chambre_vals = ["— Aucune —"]
        for ch in chambres:
            if (ch["etat"] in ("Libre", "Réservée") or
                    (reservation and ch["id"] == reservation["chambre_id"])):
                texte = f"{ch['numero']} - {ch['type']} ({ch['prix']} TND)"
                chambre_map[texte] = ch["id"]
                chambre_vals.append(texte)

        chambre_var = tk.StringVar(value="— Aucune —")
        if reservation and reservation["chambre_id"]:
            for t, cid in chambre_map.items():
                if cid == reservation["chambre_id"]:
                    chambre_var.set(t)
                    break

        ttk.Combobox(frame, textvariable=chambre_var, values=chambre_vals,
                     width=28, state="readonly").grid(
            row=5, column=1, sticky="w", padx=6, pady=4)

        # Dates
        ttk.Label(frame, text="Date d'arrivée *").grid(
            row=6, column=0, sticky="w", padx=6, pady=4)
        date_arrivee = DateEntry(frame, width=12)
        date_arrivee.grid(row=6, column=1, sticky="w", padx=6, pady=4)
        if reservation and reservation["date_arrivee"]:
            date_arrivee.set(
                iso_to_date_str(reservation["date_arrivee"]))

        ttk.Label(frame, text="Date de départ *").grid(
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

        # Boutons
        def enregistrer():
            nom = nom_var.get().strip()
            prenom = prenom_var.get().strip()
            if not nom or not prenom:
                messagebox.showerror(
                    "Erreur", "Nom et Prénom sont obligatoires.", parent=win)
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
                    "La date de départ doit être après ou égale à la date d'arrivée.",
                    parent=win)
                return

            try:
                nb = int(nb_var.get())
                if nb < 1:
                    raise ValueError
            except ValueError:
                messagebox.showerror(
                    "Erreur", "Le nombre de personnes doit être ≥ 1.",
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
                db.add_reservation(data)
                messagebox.showinfo("Succès", "Réservation ajoutée.", parent=win)
            else:
                db.update_reservation(reservation["id"], data)
                messagebox.showinfo("Succès", "Réservation modifiée.", parent=win)

            win.destroy()
            self.refresh()
            self.app.refresh_rooms_tab()

        btn_f = ttk.Frame(win)
        btn_f.pack(pady=10)
        ttk.Button(btn_f, text="Enregistrer",
                   command=enregistrer).pack(side="left", padx=6)
        ttk.Button(btn_f, text="Annuler",
                   command=win.destroy).pack(side="left", padx=6)

    # ------------------------------------------------------------------
    def nouvelle_reservation(self):
        self._ouvrir_formulaire(None)

    def modifier_reservation(self):
        if not self.selected_reservation_id:
            messagebox.showwarning("Attention",
                                   "Veuillez sélectionner une réservation.")
            return
        r = db.get_reservation(self.selected_reservation_id)
        if r:
            self._ouvrir_formulaire(dict(r))

    def supprimer_reservation(self):
        if not self.selected_reservation_id:
            messagebox.showwarning("Attention",
                                   "Veuillez sélectionner une réservation.")
            return
        r = db.get_reservation(self.selected_reservation_id)
        if not r:
            return
        if not messagebox.askyesno(
                "Confirmation",
                f"Supprimer la réservation de {r['prenom']} {r['nom']} ?"):
            return
        db.delete_reservation(self.selected_reservation_id)
        self.selected_reservation_id = None
        self.refresh()
        self.app.refresh_rooms_tab()

    def annuler_reservation(self):
        if not self.selected_reservation_id:
            messagebox.showwarning("Attention",
                                   "Veuillez sélectionner une réservation.")
            return
        r = db.get_reservation(self.selected_reservation_id)
        if not r:
            return
        if r["statut"] == "ANNULE":
            messagebox.showinfo("Info", "Cette réservation est déjà annulée.")
            return
        if not messagebox.askyesno(
                "Confirmation",
                f"Annuler la réservation de {r['prenom']} {r['nom']} ?"):
            return
        data = dict(r)
        data["statut"] = "ANNULE"
        db.update_reservation(self.selected_reservation_id, data)
        self.refresh()
        self.app.refresh_rooms_tab()
    def checkin_reservation(self):
        if not self.selected_reservation_id:
            messagebox.showwarning("Attention",
                                   "Veuillez sélectionner une réservation.")
            return
        r = db.get_reservation(self.selected_reservation_id)
        if not r:
            return
        if r["statut"] == "ANNULE":
            messagebox.showerror("Erreur",
                                 "Impossible de faire le check-in d'une réservation annulée.")
            return
        if not r["chambre_id"]:
            messagebox.showerror("Erreur",
                                 "Aucune chambre associée à cette réservation.")
            return
        if not messagebox.askyesno(
                "Confirmer le Check-in",
                f"Confirmer l'arrivée de {r['prenom']} {r['nom']} "
                f"en chambre {r['chambre_numero']} ?"):
            return

        # Créer le client à partir de la réservation
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
        db.add_client(data_client)

        # Supprimer la réservation
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
            "Check-in effectué",
            f"{r['prenom']} {r['nom']} est maintenant enregistré(e) "
            f"comme client en chambre {r['chambre_numero']}.")
# ==============================================================================
# Module : main.py
# ==============================================================================

class HotelApp(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("Gestion d'Hôtel - Logiciel de gestion (TND)")
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
        notebook.add(self.tab_reservations, text="  Réservations  ")
        notebook.add(self.tab_facturation, text="  Facturation  ")
        notebook.add(self.tab_depenses, text="  Dépenses  ")
        notebook.add(self.tab_stats, text="  Statistiques  ")
        notebook.add(self.tab_parametres, text="  Paramètres  ")

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

    # ------------------------------------------------------------------
    # Méthodes de rafraîchissement croisé entre onglets
    # ------------------------------------------------------------------
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


def main():
    try:
        init_db()
    except Exception as exc:
        # Affiche une fenêtre d'erreur même si le reste de l'UI ne se charge pas
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "Erreur de démarrage",
            f"Impossible d'initialiser la base de données :\n{exc}")
        root.destroy()
        sys.exit(1)

    app = HotelApp()
    app.mainloop()


if __name__ == "__main__":
    main()