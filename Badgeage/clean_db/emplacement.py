from pymongo import MongoClient
from collections import Counter

# Connexion à MongoDB
client = MongoClient("mongodb://localhost:27017/")

db = client["pfe"]
collection = db["badgeage_effectif"]


# Récupérer tous les documents
documents = collection.find({}, {"Emplacement": 1})


# Compter les occurrences de chaque emplacement
compteur = Counter()

for document in documents:

    emplacement = document.get("Emplacement")

    if emplacement is not None:

        emplacement = str(emplacement).strip()

        if emplacement != "":
            compteur[emplacement] += 1


# Supprimer les doublons et trier par ordre alphabétique
emplacements_propres = sorted(compteur.keys())


# Affichage
print("========== EMPLACEMENTS ==========")

print(
    "Nombre d'emplacements différents :",
    len(emplacements_propres)
)

print()

for i, emplacement in enumerate(emplacements_propres, start=1):

    nombre = compteur[emplacement]

    print(
        f"{i}. {emplacement} → {nombre} fois"
    )


# Fermeture de la connexion
client.close()