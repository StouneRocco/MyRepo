import argparse
import csv
from pathlib import Path
from pymongo import MongoClient

# --- CONFIGURATION MONGODB ---
MONGO_URI = "mongodb://localhost:27017/"
NOM_BASE = "pfe"  # À remplacer par le vrai nom de la base
NOM_COLLECTION_SOURCE = "badgeage_effectif"
NOM_COLLECTION_CIBLE = "badgeage_effectif2"
CSV_PAR_DEFAUT = Path(__file__).resolve().parent / "Correspondance.csv"

# Colonnes du CSV utilisées pour la correspondance et les champs de sortie.
COL_CSV_EMPLACEMENT = "Emplacement (PDF)"
COL_CSV_CODE = "Code espace final"
COL_CSV_DESIGNATION = "Désignation salle"
CHAMP_CODE_SORTIE = "Code espace final"
CHAMP_DESIGNATION_SORTIE = "Désignation salle"


def normaliser(valeur):
    """Normalise une valeur textuelle pour faire une comparaison insensible à la casse."""
    if not isinstance(valeur, str):
        return ""
    return " ".join(valeur.strip().lower().split())


def detecter_separateur(extrait):
    """Détecte le séparateur CSV, avec une solution de repli sur la virgule."""
    try:
        return csv.Sniffer().sniff(extrait, delimiters=",;\t|").delimiter
    except csv.Error:
        return ","


def lire_correspondances(chemin_csv):
    """Construit emplacement PDF normalisé -> (code espace final, désignation)."""
    correspondances = {}
    doublons = 0
    lignes_sans_code = 0

    print(f"Chargement des correspondances depuis : {chemin_csv}")
    with chemin_csv.open("r", encoding="utf-8-sig", newline="") as fichier:
        extrait = fichier.read(8192)
        fichier.seek(0)
        separateur = detecter_separateur(extrait)
        lecteur = csv.DictReader(fichier, delimiter=separateur)

        if not lecteur.fieldnames:
            raise ValueError("Le CSV est vide ou ne contient pas d'en-tête.")

        lecteur.fieldnames = [nom.strip().lstrip("\ufeff") if nom else "" for nom in lecteur.fieldnames]
        colonnes = lecteur.fieldnames
        obligatoires = [COL_CSV_EMPLACEMENT, COL_CSV_CODE, COL_CSV_DESIGNATION]
        manquantes = [nom for nom in obligatoires if nom not in colonnes]
        if manquantes:
            raise ValueError(
                f"Colonnes manquantes dans {chemin_csv}: {manquantes}. "
                f"Séparateur détecté : {separateur!r}. Colonnes trouvées : {colonnes}"
            )

        print(f"Séparateur détecté : {separateur!r}")
        print(f"Colonnes utilisées : {obligatoires}")
        for numero, ligne in enumerate(lecteur, start=2):
            emplacement_brut = ligne.get(COL_CSV_EMPLACEMENT) or ""
            cle = normaliser(emplacement_brut)
            code = (ligne.get(COL_CSV_CODE) or "").strip()
            designation = (ligne.get(COL_CSV_DESIGNATION) or "").strip()

            # Une ligne sans code final ne permet pas d'enrichir un document.
            if not cle or not code:
                lignes_sans_code += 1
                continue

            nouvelle = (code, designation)
            if cle in correspondances:
                doublons += 1
                if correspondances[cle] != nouvelle:
                    print(
                        f"AVERTISSEMENT ligne {numero}: doublon ambigu pour "
                        f"{emplacement_brut!r}; valeur conservée : {correspondances[cle]!r}, "
                        f"valeur ignorée : {nouvelle!r}"
                    )
                continue
            correspondances[cle] = nouvelle

    print(f"{len(correspondances)} correspondances utilisables chargées.")
    print(f"{lignes_sans_code} ligne(s) CSV sans emplacement ou code final ignorée(s).")
    if doublons:
        print(f"{doublons} clé(s) en double détectée(s).")
    return correspondances


def main():
    analyseur = argparse.ArgumentParser(
        description=(
            "Copie badgeage_effectif vers badgeage_effectif2, recherche chaque ancien "
            "Emplacement dans Correspondance.csv, puis remplace Emplacement par les "
            "champs Code espace final et Désignation salle."
        )
    )
    analyseur.add_argument("--csv", type=Path, default=CSV_PAR_DEFAUT,
                           help="Chemin de Correspondance.csv (par défaut à côté du script).")
    analyseur.add_argument("--dry-run", action="store_true",
                           help="Simule le traitement sans modifier/créer badgeage_effectif2.")
    args = analyseur.parse_args()

    if not args.csv.is_file():
        raise FileNotFoundError(f"Fichier CSV introuvable : {args.csv}")
    if NOM_BASE == "votre_nom_de_base":
        raise ValueError(
            "Configure NOM_BASE en haut de correspondance.py avec le vrai nom de la base MongoDB."
        )

    correspondances = lire_correspondances(args.csv)
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    try:
        client.admin.command("ping")
        db = client[NOM_BASE]
        source = db[NOM_COLLECTION_SOURCE]
        cible = db[NOM_COLLECTION_CIBLE]
        total = source.count_documents({})

        print(f"\nBase de données     : {NOM_BASE}")
        print(f"Collection source   : {NOM_COLLECTION_SOURCE}")
        print(f"Collection cible    : {NOM_COLLECTION_CIBLE}")
        print(f"Documents source    : {total}")

        if args.dry_run:
            travail = source
            print("\nMODE SIMULATION : aucune écriture MongoDB ne sera effectuée.")
        else:
            print(f"\nCopie de {NOM_COLLECTION_SOURCE} vers {NOM_COLLECTION_CIBLE}...")
            print("ATTENTION : le contenu existant de la collection cible sera remplacé.")
            source.aggregate([{"$out": NOM_COLLECTION_CIBLE}])
            travail = cible
            print("Copie terminée. Application des correspondances...")

        correspondants = 0
        sans_correspondance = 0
        modifies = 0
        deja_a_jour = 0
        inconnus = {}

        # Le document lu dans la cible conserve le même _id que celui de la source.
        projection = {"Emplacement": 1, CHAMP_CODE_SORTIE: 1, CHAMP_DESIGNATION_SORTIE: 1}
        for document in travail.find({}, projection):
            emplacement = document.get("Emplacement")
            cle = normaliser(emplacement)
            if not cle or cle not in correspondances:
                sans_correspondance += 1
                valeur = str(emplacement) if emplacement is not None else "<vide>"
                inconnus[valeur] = inconnus.get(valeur, 0) + 1
                # On conserve Emplacement pour ces documents : sans code dans le CSV,
                # le supprimer ferait perdre la seule valeur de rapprochement dans la cible.
                continue

            code, designation = correspondances[cle]
            correspondants += 1
            champs = {
                CHAMP_CODE_SORTIE: code,
                CHAMP_DESIGNATION_SORTIE: designation,
            }
            emplacement_deja_absent = "Emplacement" not in document
            if all(document.get(champ) == valeur for champ, valeur in champs.items()) and emplacement_deja_absent:
                deja_a_jour += 1
                continue

            if not args.dry_run:
                resultat = travail.update_one(
                    {"_id": document["_id"]},
                    {"$set": champs, "$unset": {"Emplacement": ""}},
                )
                modifies += resultat.modified_count

        print("\n--- Bilan ---")
        print(f"Documents avec correspondance : {correspondants}")
        print(f"Documents modifiés dans {NOM_COLLECTION_CIBLE if not args.dry_run else 'la simulation'} : {modifies}")
        print(f"Documents déjà à jour : {deja_a_jour}")
        print(f"Documents sans correspondance : {sans_correspondance}")
        if args.dry_run:
            print("Aucune modification enregistrée. Relance sans --dry-run pour appliquer les changements.")
        if inconnus:
            print("\nValeurs sans correspondance (20 premières) :")
            for valeur, nombre in sorted(inconnus.items(), key=lambda item: (-item[1], item[0]))[:20]:
                print(f"  {valeur!r} : {nombre} document(s)")
            print(
                "Ces documents gardent leur champ Emplacement dans la cible pour éviter une perte "
                "d'information. Ajoute un Code espace final correspondant dans le CSV, puis relance le script."
            )
    finally:
        client.close()


if __name__ == "__main__":
    main()
