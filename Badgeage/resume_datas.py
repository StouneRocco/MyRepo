from pymongo import MongoClient
from collections import defaultdict, Counter
from datetime import datetime


# ============================================================
# CONNEXION
# ============================================================

client = MongoClient("mongodb://localhost:27017/")

db = client["pfe"]

collection = db["badgeage_effectif"]


# ============================================================
# DETECTION AUTOMATIQUE DES CHAMPS
# ============================================================

document_test = collection.find_one()

if document_test is None:
    print("La collection badgeage_effectif est vide.")
    client.close()
    exit()


champs = list(document_test.keys())

champ_date = None
champ_heure = None


for champ in champs:

    nom = champ.lower()

    if "date" in nom and "v" in nom:
        champ_date = champ

    if "heure" in nom and "v" in nom:
        champ_heure = champ


# Si la détection automatique échoue
if champ_date is None:

    for champ in champs:

        if champ.startswith("Date"):
            champ_date = champ


if champ_heure is None:

    for champ in champs:

        if champ.startswith("Heure"):
            champ_heure = champ


print()
print("=" * 60)
print("CHAMPS UTILISES")
print("=" * 60)

print("Date  :", repr(champ_date))
print("Heure :", repr(champ_heure))

print()


# ============================================================
# VERIFICATION
# ============================================================

if champ_date is None or champ_heure is None:

    print("Impossible de trouver automatiquement les champs")
    print("Date et Heure.")

    print()
    print("Champs disponibles :")

    for champ in champs:
        print("-", repr(champ))

    client.close()
    exit()


# ============================================================
# STOCKAGE DES INFORMATIONS PAR JOUR
# ============================================================

resume_jours = defaultdict(list)


# ============================================================
# LECTURE DES BADGEAGES
# ============================================================

for document in collection.find():

    date = document.get(champ_date)
    heure = document.get(champ_heure)

    if date is None:
        continue

    if heure is None:
        continue

    date = str(date).strip()
    heure = str(heure).strip()

    if date == "" or heure == "":
        continue

    resume_jours[date].append({
        "heure": heure,
        "emplacement": document.get("Emplacement")
    })


# ============================================================
# RESUME PAR JOUR
# ============================================================

print()
print("=" * 80)
print("                    RESUME DES BADGEAGES PAR JOUR")
print("=" * 80)
print()


resultats = []


for date, badgeages in resume_jours.items():

    # --------------------------------------------------------
    # Trier les heures
    # --------------------------------------------------------

    badgeages_tries = sorted(
        badgeages,
        key=lambda x: x["heure"]
    )


    # --------------------------------------------------------
    # Premier et dernier badgeage
    # --------------------------------------------------------

    premiere_heure = badgeages_tries[0]["heure"]

    derniere_heure = badgeages_tries[-1]["heure"]


    # --------------------------------------------------------
    # Nombre de badgeages
    # --------------------------------------------------------

    nombre_badgeages = len(badgeages)


    # --------------------------------------------------------
    # Nombre d'emplacements différents
    # --------------------------------------------------------

    emplacements = set()

    for badgeage in badgeages:

        emplacement = badgeage["emplacement"]

        if emplacement is not None:

            emplacement = str(emplacement).strip()

            if emplacement != "":
                emplacements.add(emplacement)


    nombre_emplacements = len(emplacements)


    # --------------------------------------------------------
    # Création du résultat
    # --------------------------------------------------------

    resultat = {
        "date": date,
        "nombre_badgeages": nombre_badgeages,
        "nombre_emplacements": nombre_emplacements,
        "premier_badgeage": premiere_heure,
        "dernier_badgeage": derniere_heure
    }

    resultats.append(resultat)


# ============================================================
# TRI DES RESULTATS PAR DATE
# ============================================================

def convertir_date(resultat):

    try:

        return datetime.strptime(
            resultat["date"],
            "%d/%m/%Y"
        )

    except ValueError:

        return datetime.max


resultats.sort(key=convertir_date)


# ============================================================
# AFFICHAGE
# ============================================================

for resultat in resultats:

    print(
        f"{resultat['date']} | "
        f"{resultat['nombre_badgeages']} badgeages | "
        f"{resultat['nombre_emplacements']} emplacements | "
        f"premier : {resultat['premier_badgeage']} | "
        f"dernier : {resultat['dernier_badgeage']}"
    )


# ============================================================
# STATISTIQUES GENERALES
# ============================================================

print()
print("=" * 80)
print("                       STATISTIQUES")
print("=" * 80)
print()

print(
    "Nombre de jours analysés :",
    len(resultats)
)

print(
    "Nombre total de badgeages :",
    sum(
        resultat["nombre_badgeages"]
        for resultat in resultats
    )
)

if resultats:

    moyenne = (
        sum(
            resultat["nombre_badgeages"]
            for resultat in resultats
        )
        / len(resultats)
    )

    print(
        "Moyenne de badgeages par jour :",
        round(moyenne, 2)
    )


# ============================================================
# FERMETURE
# ============================================================

client.close()