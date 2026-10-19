import argparse
import csv
from pathlib import Path
from pymongo import MongoClient

# --- CONFIGURATION MONGODB ---
MONGO_URI = "mongodb://localhost:27017/"
NOM_BASE = "pfe"
NOM_COLLECTION_SOURCE = "badgeage_effectif"   # lue, jamais modifiée
NOM_COLLECTION_OUI = "correspondance_oui"     # salles AVEC correspondance (remplacée à chaque lancement)
NOM_COLLECTION_NON = "correspondance_non"     # salles SANS correspondance (remplacée à chaque lancement)
CSV_PAR_DEFAUT = Path(__file__).resolve().parent / "Correspondance.csv"
TAILLE_LOT = 5000

# Colonnes du CSV de correspondance
COL_CSV_EMPLACEMENT = "Emplacement (PDF)"
COL_CSV_CODE = "Code espace final"
COL_CSV_DESIGNATION = "Désignation salle"

# Champs écrits dans la collection cible
CHAMP_CODE_SORTIE = "Code salle"
CHAMP_DESIGNATION_SORTIE = "Designation salle"



def normaliser(valeur):
    """Minuscules, espaces nettoyés : comparaison insensible à la casse."""
    if not isinstance(valeur, str):
        return ""
    return " ".join(valeur.strip().lower().split())


def detecter_separateur(extrait):
    try:
        return csv.Sniffer().sniff(extrait, delimiters=",;\t|").delimiter
    except csv.Error:
        return ","


def lire_correspondances(chemin_csv):
    """Construit : emplacement normalisé -> (code espace final, désignation)."""
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

        lecteur.fieldnames = [
            nom.strip().lstrip("\ufeff") if nom else "" for nom in lecteur.fieldnames
        ]
        obligatoires = [COL_CSV_EMPLACEMENT, COL_CSV_CODE, COL_CSV_DESIGNATION]
        manquantes = [nom for nom in obligatoires if nom not in lecteur.fieldnames]
        if manquantes:
            raise ValueError(
                f"Colonnes manquantes : {manquantes}. "
                f"Séparateur détecté : {separateur!r}. "
                f"Colonnes trouvées : {lecteur.fieldnames}"
            )

        print(f"Séparateur détecté : {separateur!r}")
        for numero, ligne in enumerate(lecteur, start=2):
            emplacement_brut = ligne.get(COL_CSV_EMPLACEMENT) or ""
            cle = normaliser(emplacement_brut)
            code = (ligne.get(COL_CSV_CODE) or "").strip()
            designation = (ligne.get(COL_CSV_DESIGNATION) or "").strip()

            if not cle or not code:
                lignes_sans_code += 1
                continue

            nouvelle = (code, designation)
            if cle in correspondances:
                doublons += 1
                if correspondances[cle] != nouvelle:
                    print(
                        f"AVERTISSEMENT ligne {numero}: doublon ambigu pour "
                        f"{emplacement_brut!r}; conservé : {correspondances[cle]!r}, "
                        f"ignoré : {nouvelle!r}"
                    )
                continue
            correspondances[cle] = nouvelle

    print(f"{len(correspondances)} correspondances utilisables chargées.")
    print(f"{lignes_sans_code} ligne(s) CSV sans emplacement ou code ignorée(s).")
    if doublons:
        print(f"{doublons} clé(s) en double détectée(s).")
    return correspondances


def main():
    analyseur = argparse.ArgumentParser(
        description=(
            "Sépare badgeage_effectif en 'correspondance_oui' (emplacement trouvé dans "
            "Correspondance.csv, remplacé par Code salle + Designation salle) et "
            "'correspondance_non' (emplacement absent du CSV, conservé tel quel)."
        )
    )
    analyseur.add_argument("--csv", type=Path, default=CSV_PAR_DEFAUT,
                           help="Chemin de Correspondance.csv (par défaut à côté du script).")
    analyseur.add_argument("--dry-run", action="store_true",
                           help="Simule sans créer ni modifier les collections cibles.")
    args = analyseur.parse_args()

    if not args.csv.is_file():
        raise FileNotFoundError(f"Fichier CSV introuvable : {args.csv}")

    correspondances = lire_correspondances(args.csv)
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    try:
        client.admin.command("ping")
        db = client[NOM_BASE]
        source = db[NOM_COLLECTION_SOURCE]
        oui = db[NOM_COLLECTION_OUI]
        non = db[NOM_COLLECTION_NON]
        total = source.count_documents({})

        print(f"\nBase de données   : {NOM_BASE}")
        print(f"Collection source : {NOM_COLLECTION_SOURCE} ({total} documents)")
        print(f"Collections cibles: {NOM_COLLECTION_OUI}, {NOM_COLLECTION_NON}")

        if args.dry_run:
            print("\nMODE SIMULATION : aucune écriture MongoDB.")
        else:
            print("\nATTENTION : le contenu existant des collections cibles est remplacé.")
            oui.drop()
            non.drop()

        nb_oui = 0
        nb_non = 0
        inconnus = {}
        lot_oui, lot_non = [], []

        for document in source.find():
            emplacement = document.get("Emplacement")
            cle = normaliser(emplacement)

            if cle and cle in correspondances:
                code, designation = correspondances[cle]
                nouveau = {k: v for k, v in document.items() if k != "Emplacement"}
                nouveau[CHAMP_CODE_SORTIE] = code
                nouveau[CHAMP_DESIGNATION_SORTIE] = designation
                nb_oui += 1
                if not args.dry_run:
                    lot_oui.append(nouveau)
            else:
                nb_non += 1
                valeur = str(emplacement) if emplacement is not None else "<vide>"
                inconnus[valeur] = inconnus.get(valeur, 0) + 1
                if not args.dry_run:
                    lot_non.append(document)

            if len(lot_oui) >= TAILLE_LOT:
                oui.insert_many(lot_oui, ordered=False)
                lot_oui = []
            if len(lot_non) >= TAILLE_LOT:
                non.insert_many(lot_non, ordered=False)
                lot_non = []

        if lot_oui:
            oui.insert_many(lot_oui, ordered=False)
        if lot_non:
            non.insert_many(lot_non, ordered=False)

        print("\n--- Bilan ---")
        print(f"{NOM_COLLECTION_OUI} (avec correspondance) : {nb_oui} documents")
        print(f"{NOM_COLLECTION_NON} (sans correspondance) : {nb_non} documents")
        print(f"Total                                 : {nb_oui + nb_non} / {total}")
        if args.dry_run:
            print("Aucune modification enregistrée. Relance sans --dry-run pour appliquer.")

        if inconnus:
            print("\nEmplacements sans correspondance (20 premiers) :")
            for valeur, nombre in sorted(inconnus.items(), key=lambda i: (-i[1], i[0]))[:20]:
                print(f"  {valeur!r} : {nombre} document(s)")
    finally:
        client.close()


if __name__ == "__main__":
    main()