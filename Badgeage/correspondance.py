import argparse
import csv
from pathlib import Path
from pymongo import MongoClient

# --- CONFIGURATION MONGODB ---
# À adapter avec votre URI et le nom de votre base de données
MONGO_URI = "mongodb://localhost:27017/"
NOM_BASE = "votre_nom_de_base" # Remplacer par le nom de votre base de données
NOM_COLLECTION_SOURCE = "badgeage_effectif"
NOM_COLLECTION_CIBLE = "badgeage_effectif2"

CSV_PAR_DEFAUT = Path(__file__).resolve().parent / "Correspondance.csv"


def normaliser(chaine):
    """Met en minuscules et retire les espaces superflus pour comparer sans erreur."""
    if not isinstance(chaine, str):
        return ""
    return chaine.strip().lower()


def lire_correspondances(chemin_csv):
    """
    Lit le fichier CSV et construit un dictionnaire liant
    une clé normalisée (ex: "salle de réunion" ou "spc")
    à un tuple (code_ifc, designation_ifc).
    """
    correspondances = {}
    doublons = 0
    print(f"Chargement des correspondances depuis : {chemin_csv}")

    with chemin_csv.open("r", encoding="utf-8-sig") as fichier:
        # csv.DictReader lit la première ligne pour les noms de colonnes
        lecteur = csv.DictReader(fichier, delimiter=";")
        
        # S'assurer que les colonnes attendues existent
        colonnes_attendues = ["Emplacement", "Code salle", "Désignation salle"]
        if not lecteur.fieldnames or not all(c in lecteur.fieldnames for c in colonnes_attendues):
            raise ValueError(
                f"Le CSV doit contenir ces colonnes (séparées par ';') : {colonnes_attendues}. "
                f"Trouvé : {lecteur.fieldnames}"
            )

        for ligne in lecteur:
            # On cherche par Emplacement dans le CSV
            colonne_emplacement = "Emplacement"
            cle = normaliser(ligne.get(colonne_emplacement))
            
            code = ligne.get("Code salle", "").strip()
            designation = ligne.get("Désignation salle", "").strip()

            if not cle or not code:
                continue

            if cle in correspondances:
                doublons += 1
                ancienne = correspondances[cle]
                nouvelle = (code, designation)
                if ancienne != nouvelle:
                    print(
                        f"AVERTISSEMENT : correspondance ambiguë pour "
                        f"{ligne.get(colonne_emplacement)!r}. "
                        f"Valeur conservée : {ancienne}"
                    )
                continue

            correspondances[cle] = (code, designation)

    print(f"{len(correspondances)} correspondances utilisables chargées.")
    if doublons:
        print(f"{doublons} clé(s) en double détectée(s) dans le CSV.")
    return correspondances


def main():
    analyseur = argparse.ArgumentParser(
        description="Crée une nouvelle collection et y ajoute le code salle et la désignation."
    )
    analyseur.add_argument(
        "--csv",
        type=Path,
        default=CSV_PAR_DEFAUT,
        help="Chemin vers Correspondance.csv (par défaut : à côté du script).",
    )
    analyseur.add_argument(
        "--dry-run",
        action="store_true",
        help="Simule les changements sans créer la nouvelle collection ni écrire dans MongoDB.",
    )
    analyseur.add_argument(
        "--remplacer-emplacement",
        action="store_true",
        help=(
            "Remplace aussi la valeur Emplacement par le code IFC. "
            "Par défaut, Emplacement est conservé."
        ),
    )
    args = analyseur.parse_args()

    if not args.csv.is_file():
        raise FileNotFoundError(
            f"Fichier introuvable : {args.csv}\n"
            "Place Correspondance.csv à côté du script ou utilise --csv."
        )

    correspondances = lire_correspondances(args.csv)

    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    try:
        # Vérifie que MongoDB est accessible.
        client.admin.command("ping")
        db = client[NOM_BASE]
        collection_source = db[NOM_COLLECTION_SOURCE]
        collection_cible = db[NOM_COLLECTION_CIBLE]

        total = collection_source.count_documents({})

        print(f"\nBase de données    : {NOM_BASE}")
        print(f"Collection source  : {NOM_COLLECTION_SOURCE}")
        print(f"Collection cible   : {NOM_COLLECTION_CIBLE}")
        print(f"Documents à traiter: {total}")

        if args.dry_run:
            print("\n>>> MODE SIMULATION : aucune modification ne sera enregistrée, la collection cible ne sera pas créée. <<<")
            collection_travail = collection_source # On lit la source pour simuler l'analyse
        else:
            print(f"\nClonage de {NOM_COLLECTION_SOURCE} vers {NOM_COLLECTION_CIBLE}...")
            print("(Cette opération écrase la collection cible existante)")
            # Le $out permet à MongoDB de copier intégralement la collection côté serveur
            collection_source.aggregate([{"$out": NOM_COLLECTION_CIBLE}])
            print("Clonage terminé. Début de la mise à jour...")
            collection_travail = collection_cible # On travaille désormais exclusivement sur la copie

        trouves = 0
        non_correspondants = 0
        deja_a_jour = 0
        ecrits = 0
        emplacements_inconnus = {}

        # On parcourt la collection de travail (qui est une copie exacte de la source si pas en dry_run)
        for document in collection_travail.find({}, {"Emplacement": 1, "Code salle": 1, "Désignation salle": 1}):
            emplacement = document.get("Emplacement")
            cle = normaliser(emplacement)

            if not cle or cle not in correspondances:
                non_correspondants += 1
                valeur = str(emplacement) if emplacement is not None else "<vide>"
                emplacements_inconnus[valeur] = emplacements_inconnus.get(valeur, 0) + 1
                continue

            code, designation = correspondances[cle]
            trouves += 1

            changements = {
                "Code salle": code,
                "Désignation salle": designation,
            }
            if args.remplacer_emplacement:
                changements["Emplacement"] = code

            # Évite une écriture si les valeurs sont déjà identiques dans la base.
            if all(document.get(champ) == valeur for champ, valeur in changements.items()):
                deja_a_jour += 1
                continue

            if not args.dry_run:
                # Mise à jour sur la nouvelle collection (collection_cible via la variable collection_travail)
                resultat = collection_travail.update_one(
                    {"_id": document["_id"]},
                    {"$set": changements},
                )
                ecrits += resultat.modified_count

        print("\n--- Bilan ---")
        print(f"Documents avec correspondance : {trouves}")
        print(f"Documents déjà à jour : {deja_a_jour}")
        print(f"Documents mis à jour dans {NOM_COLLECTION_CIBLE if not args.dry_run else 'SIMULATION'} : {ecrits if not args.dry_run else 0}")
        if args.dry_run:
            print("RAPPEL : Les changements simulés n'ont pas été enregistrés.")
        print(f"Documents sans correspondance : {non_correspondants}")

        if emplacements_inconnus:
            print("\nValeurs de « Emplacement » sans correspondance (20 premières) :")
            for valeur, nombre in sorted(
                emplacements_inconnus.items(),
                key=lambda element: (-element[1], element[0])
            )[:20]:
                print(f"  {valeur!r} : {nombre} document(s)")
            print(
                "\nSi ces valeurs sont des codes (ex: « SPC ») alors que le CSV "
                "contient des noms (ex: « 001_FabLab »), il faut compléter "
                "Correspondance.csv avec une clé correspondant exactement à "
                "la valeur enregistrée dans la base MongoDB."
            )

    except Exception as e:
        print(f"Erreur lors de la connexion ou du traitement MongoDB : {e}")
    finally:
        client.close()

if __name__ == "__main__":
    main()