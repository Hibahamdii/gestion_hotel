# -*- coding: utf-8 -*-

import os
import subprocess
import platform
from datetime import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable, Image,
)

import db.repository as repo
from config import BASE_DIR
from views.widgets import iso_to_date_str


def generer_fiche_police(client):
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
            Paragraph(str(valeur) if valeur else "\u2014", styles["Normal"]),
        ]

    story = []

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
        f"G\u00e9n\u00e9r\u00e9e le {datetime.now().strftime('%d/%m/%Y \u00e0 %H:%M')}",
        sous_titre_style
    ))
    story.append(HRFlowable(width="100%", thickness=2, color=BLEU, spaceAfter=12))

    story.append(Paragraph("  IDENTIT\u00c9 DU CLIENT", section_style))
    story.append(Spacer(1, 4))
    t1 = Table([
        ligne("Nom", client.get("nom")),
        ligne("Pr\u00e9nom", client.get("prenom")),
        ligne("Date de naissance", iso_to_date_str(client.get("date_naissance", "")) or "\u2014"),
        ligne("Lieu de naissance", client.get("lieu_naissance")),
        ligne("Adresse", client.get("adresse")),
        ligne("T\u00e9l\u00e9phone", client.get("telephone")),
    ], colWidths=[55*mm, 120*mm])
    t1.setStyle(TableStyle([
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [GRIS, colors.white]),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(t1)

    story.append(Paragraph("  PI\u00c8CE D'IDENTIT\u00c9", section_style))
    story.append(Spacer(1, 4))
    t2 = Table([
        ligne("Type d'identifiant", client.get("type_identifiant")),
        ligne("Num\u00e9ro d'identifiant", client.get("numero_identifiant")),
    ], colWidths=[55*mm, 120*mm])
    t2.setStyle(TableStyle([
        ("ROWBACKGROUNDS", (0, 0), (-1, -1), [GRIS, colors.white]),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.lightgrey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(t2)

    story.append(Paragraph("  INFORMATIONS DU S\u00c9JOUR", section_style))
    story.append(Spacer(1, 4))
    t3 = Table([
        ligne("Chambre N\u00b0", client.get("chambre_numero")),
        ligne("Prix / nuit", f"{client.get('chambre_prix', '\u2014')} TND"),
        ligne("Date d'entr\u00e9e", iso_to_date_str(client.get("date_entree", "")) or "\u2014"),
        ligne("Date de sortie", iso_to_date_str(client.get("date_sortie", "")) or "\u2014"),
        ligne("Venant de", client.get("venant_de")),
        ligne("Allant \u00e0", client.get("allant_a")),
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
    story.append(Paragraph("Document officiel \u2014 Usage interne uniquement", footer_style))

    nom_hotel = repo.get_parametre("nom_hotel", "H\u00f4tel")
    doc = SimpleDocTemplate(
        chemin, pagesize=A4,
        leftMargin=20*mm, rightMargin=20*mm,
        topMargin=20*mm, bottomMargin=20*mm,
    )
    doc.build(story)

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
