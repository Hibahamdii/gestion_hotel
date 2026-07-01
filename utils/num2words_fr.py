# -*- coding: utf-8 -*-

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
    if n < 10:
        return UNITES[n]
    if n in DIX_A_SEIZE:
        return DIX_A_SEIZE[n]
    if n < 20:
        return "dix-" + UNITES[n - 10]

    dizaine = n // 10
    unite = n % 10

    if dizaine in (7, 9):
        base = DIZAINES[dizaine - 1]
        if unite == 0:
            return base + "-dix"
        if unite == 1:
            return base + "-et-onze" if dizaine == 7 else base + "-onze"
        return base + "-" + _moins_de_cent(10 + unite)

    base = DIZAINES[dizaine]

    if unite == 0:
        if dizaine == 8:
            return base + "s"
        return base
    if unite == 1 and dizaine != 8:
        return base + "-et-un"
    return base + "-" + UNITES[unite]


def _moins_de_mille(n):
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

    noms = ["", "mille", "million", "milliard"]
    parties = []

    for i in range(len(groupes) - 1, -1, -1):
        valeur = groupes[i]
        if valeur == 0:
            continue
        if i == 1:
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
    montant = round(float(montant), 3)
    entier = int(montant)
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
    for valeur in [0, 1, 5, 10, 11, 16, 17, 19, 20, 21, 30, 71, 75, 80, 81,
                    91, 99, 100, 101, 199, 200, 1000, 1001, 1999, 2000, 2021,
                    1000000, 1234567, 125.350, 1.001, 1.0, 0.500]:
        if isinstance(valeur, int):
            print(valeur, "->", nombre_en_lettres(valeur))
        else:
            print(valeur, "->", montant_en_lettres(valeur))
