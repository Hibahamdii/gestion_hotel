# -*- coding: utf-8 -*-

from datetime import datetime


def formater_periode(periode, group_by):
    try:
        if group_by == "day":
            return datetime.strptime(periode, "%Y-%m-%d").strftime("%d/%m/%Y")
        if group_by == "month":
            return datetime.strptime(periode, "%Y-%m").strftime("%m/%Y")
        return periode
    except ValueError:
        return periode


def calculer_kpis(periodes, recettes, depenses):
    total_recettes = sum(recettes.get(p, 0.0) for p in periodes)
    total_depenses = sum(depenses.get(p, 0.0) for p in periodes)
    total_benefice = round(total_recettes - total_depenses, 3)
    return total_recettes, total_depenses, total_benefice
