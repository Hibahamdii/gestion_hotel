# -*- coding: utf-8 -*-

ETATS_CHAMBRE = ["Libre", "Occupée", "Réservée", "Maintenance"]

CATEGORIES_DEPENSE = [
    "Maintenance", "Ménage", "STEG (Électricité)", "SONEDE (Eau)",
    "Internet / Télécom", "Fournitures", "Salaires", "Impôts / Taxes", "Autre",
]

TYPES_IDENTIFIANT = ["CIN", "Passeport", "Carte de séjour"]

STATUTS_RESERVATION = ["RESERVE", "ANNULE"]

COULEURS_ETAT = {
    "Libre": "#4CAF50",
    "Occupée": "#E53935",
    "Réservée": "#FB8C00",
    "Maintenance": "#9E9E9E",
}

COULEURS_STATUT_REZ = {
    "RESERVE": "#FB8C00",
    "ANNULE": "#9E9E9E",
}

PERIODES = {
    "Jour": "day",
    "Mois": "month",
    "Année": "year",
}
