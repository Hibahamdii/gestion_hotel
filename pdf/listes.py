# -*- coding: utf-8 -*-

from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
)

import db.repository as repo
from views.widgets import iso_to_date_str


def generer_liste_factures_pdf(factures_data, chemin_pdf, titre="Historique des factures"):
    nom_hotel = repo.get_parametre("nom_hotel", "H\u00f4tel")
    adresse_hotel = repo.get_parametre("adresse_hotel", "")

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
        f"G\u00e9n\u00e9r\u00e9 le {datetime.now().strftime('%d/%m/%Y \u00e0 %H:%M')}",
        style_small))
    elements.append(Spacer(1, 4 * mm))

    data = [["N\u00b0 Facture", "Date", "Client", "Identifiant", "Montant (TND)", "Statut"]]
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


def generer_liste_depenses_pdf(depenses_data, chemin_pdf, titre="Liste des d\u00e9penses"):
    nom_hotel = repo.get_parametre("nom_hotel", "H\u00f4tel")
    adresse_hotel = repo.get_parametre("adresse_hotel", "")

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
        f"G\u00e9n\u00e9r\u00e9 le {datetime.now().strftime('%d/%m/%Y \u00e0 %H:%M')}",
        style_small))
    elements.append(Spacer(1, 4 * mm))

    data = [["Date", "Cat\u00e9gorie", "Description", "Montant (TND)", "Mode de paiement"]]
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
        f"Nombre de d\u00e9penses : {len(depenses_data)}",
        ParagraphStyle("Footer", parent=styles["Normal"], fontSize=9)))

    doc.build(elements)
    return chemin_pdf
