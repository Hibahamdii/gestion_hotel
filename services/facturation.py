# -*- coding: utf-8 -*-

from datetime import date

from db.repository import (
    get_facture, create_facture, set_facture_payee,
    set_facture_paiement_partiel, set_client_solde,
)
from views.widgets import date_str_to_iso


def calculer_total_et_remise(lignes, remise_str):
    sous_total = sum(l["quantite"] * l["prix_unitaire"] for l in lignes)
    try:
        remise = float(remise_str.replace(",", "."))
    except (ValueError, AttributeError):
        remise = 0.0
    total = round(sous_total - remise, 3)
    return max(total, 0.0), remise, sous_total


def creer_et_sauvegarder_facture(client_map_key, client_map, lignes,
                                  date_entree_widget, date_sortie_widget,
                                  remise_str, mode_paiement, payee):
    client = client_map.get(client_map_key)
    if not client:
        raise ValueError("Client introuvable")

    d_entree = date_entree_widget.get_date()
    d_sortie = date_sortie_widget.get_date()
    if not d_entree or not d_sortie:
        raise ValueError("Dates invalides (format JJ/MM/AAAA)")

    nb_nuits = max((d_sortie - d_entree).days, 1)
    total, remise, _ = calculer_total_et_remise(lignes, remise_str)

    lignes_db = [(l["description"], l["quantite"], l["prix_unitaire"])
                 for l in lignes]

    client_id = None if client.get("is_reservation") else client["id"]
    nom_client = f"{client['prenom']} {client['nom']}".strip()

    facture_id, numero, montant_total = create_facture(
        client_id=client_id,
        date_facture=date.today().strftime("%Y-%m-%d"),
        date_entree=date_str_to_iso(date_entree_widget.get()),
        date_sortie=date_str_to_iso(date_sortie_widget.get()),
        nb_nuits=nb_nuits,
        lignes=lignes_db,
        remise=remise,
        mode_paiement=mode_paiement,
        nom_client=nom_client,
    )

    if payee:
        set_facture_payee(facture_id)

    return facture_id, numero, montant_total


def traiter_paiement_complet(facture_id, client, mode_paiement, total, recu):
    set_facture_payee(facture_id)
    if client and not client.get("is_reservation") and client.get("id"):
        set_client_solde(client["id"], 0.0)
    monnaie = round(recu - total, 3)
    return monnaie


def traiter_paiement_partiel(facture_id, client, recu, total):
    solde_restant = round(total - recu, 3)
    set_facture_paiement_partiel(facture_id, recu)
    if client and not client.get("is_reservation") and client.get("id"):
        set_client_solde(client["id"], solde_restant)
    return solde_restant
