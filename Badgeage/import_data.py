"""
Importe historique_mars_2026.csv dans MongoDB (base: pfe, collection: badgeage).

Prérequis :  pip install pymongo
Usage     :  python import_badgeage.py
(le CSV doit être dans le même dossier que ce script)
"""
import csv
from datetime import datetime
from pymongo import MongoClient

CSV_FILE = "Badgeage_Mars_2026.csv"
MONGO_URI = "mongodb://localhost:27017"
DB_NAME = "pfe"
COLLECTION = "badgeage"
BATCH = 5000

client = MongoClient(MONGO_URI)
col = client[DB_NAME][COLLECTION]

batch, total = [], 0
with open(CSV_FILE, newline="", encoding="utf-8-sig") as f:
    for row in csv.DictReader(f):
        batch.append({
            "Date": row["Date"],            # ex: "02/03/2026"
            "Heure": row["Heure"],          # ex: "07:19:59"
            "Emplacement": row["Emplacement"],
            # champ pratique pour trier / filtrer par date et heure
            "DateHeure": datetime.strptime(
                f'{row["Date"]} {row["Heure"]}', "%d/%m/%Y %H:%M:%S"
            ),
        })
        if len(batch) >= BATCH:
            col.insert_many(batch)
            total += len(batch)
            batch = []
    if batch:
        col.insert_many(batch)
        total += len(batch)

print(f"{total} documents insérés dans {DB_NAME}.{COLLECTION}")
print(f"Total dans la collection : {col.count_documents({})}")
print(client.address)
print(client.list_database_names())