# -*- coding: utf-8 -*-

import os

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable, Image,
)

import db.repository as repo
from config import BASE_DIR
from views.widgets import iso_to_date_str
from utils.num2words_fr import montant_en_lettres


def generer_facture_pdf(facture_id, chemin_pdf):
    facture, lignes = repo.get_facture(facture_id)
    if facture is None:
        raise ValueError("Facture introuvable")

    nom_hotel = repo.get_parametre("nom_hotel", "H\u00f4tel")
    adresse_hotel = repo.get_parametre("adresse_hotel", "")
    telephone_hotel = repo.get_parametre("telephone_hotel", "")
    matricule_fiscal = repo.get_parametre("matricule_fiscal", "")

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

    logo_path = os.path.join(BASE_DIR, "logo_hotel.jpg")
    if os.path.exists(logo_path):
        logo = Image(logo_path, width=25 * mm, height=25 * mm)
        entete_gauche = [logo,
                         Paragraph(f"<b>{nom_hotel}</b>", style_title),
                         Paragraph(adresse_hotel, style_small),
                         Paragraph(f"T\u00e9l : {telephone_hotel}", style_small),
                         Paragraph(f"M.F. : {matricule_fiscal}", style_small)]
    else:
        entete_gauche = [
            Paragraph(f"<b>{nom_hotel}</b>", style_title),
            Paragraph(adresse_hotel, style_small),
            Paragraph(f"T\u00e9l : {telephone_hotel}", style_small),
            Paragraph(f"M.F. : {matricule_fiscal}", style_small),
        ]

    entete_droite = [
        Paragraph(f"<b>FACTURE N\u00b0 {facture['numero']}</b>", style_right),
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

    nom_complet = f"{facture['prenom'] or ''} {facture['nom'] or ''}".strip()
    info_client = [
        ["Client :", nom_complet],
        ["Identifiant :", f"{facture['type_identifiant'] or ''} "
                           f"{facture['numero_identifiant'] or ''}"],
        ["Adresse :", facture["adresse"] or ""],
        ["Chambre :", facture["chambre_numero"] or ""],
        ["Date d'arriv\u00e9e :", iso_to_date_str(facture["date_entree"]) or facture["date_entree"]],
        ["Date de d\u00e9part :", iso_to_date_str(facture["date_sortie"]) or facture["date_sortie"]],
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

    data = [["Description", "Quantit\u00e9", "Prix unitaire (TND)", "Montant (TND)"]]
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

    montant_lettres = montant_en_lettres(facture["montant_total"])
    texte_arret = (
        f"Arr\u00eat\u00e9e la pr\u00e9sente facture \u00e0 la somme de : "
        f"<b>{montant_lettres}</b>."
    )
    elements.append(HRFlowable(width="100%", color=colors.grey, thickness=0.5))
    elements.append(Spacer(1, 3 * mm))
    elements.append(Paragraph(texte_arret, style_normal))
    elements.append(Spacer(1, 3 * mm))
    elements.append(Paragraph(
        f"Mode de paiement : {facture['mode_paiement']}", style_small))
    elements.append(Spacer(1, 12 * mm))

    pied_table = Table(
        [["Cachet et signature de l'h\u00f4tel", "Signature du client"]],
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
        f"{nom_hotel} - {adresse_hotel} - T\u00e9l : {telephone_hotel} - "
        f"M.F. : {matricule_fiscal}",
        ParagraphStyle("Footer", parent=styles["Normal"], fontSize=8,
                       alignment=TA_CENTER, textColor=colors.grey),
    ))

    doc.build(elements)
    return chemin_pdf
