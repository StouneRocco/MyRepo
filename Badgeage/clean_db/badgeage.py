from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27017/")

db = client["pfe"]
collection = db["badgeage"]

DATE = "Date de l'évé…"


# ==========================================
# PAR JOUR
# ==========================================

pipeline_jour = [
    {
        "$match": {
            DATE: {"$exists": True, "$ne": None, "$ne": ""}
        }
    },
    {
        "$group": {
            "_id": f"${DATE}",
            "nombre_badgeages": {"$sum": 1}
        }
    },
    {
        "$sort": {"_id": 1}
    }
]

print("\n========== BADGEAGES PAR JOUR ==========")

for r in collection.aggregate(pipeline_jour):
    print(r["_id"], ":", r["nombre_badgeages"])


# ==========================================
# PAR SEMAINE
# ==========================================

pipeline_semaine = [
    {
        "$addFields": {
            "date_convertie": {
                "$dateFromString": {
                    "dateString": f"${DATE}",
                    "format": "%d/%m/%Y",
                    "onError": None,
                    "onNull": None
                }
            }
        }
    },
    {
        "$match": {
            "date_convertie": {"$ne": None}
        }
    },
    {
        "$group": {
            "_id": {
                "annee": {"$isoWeekYear": "$date_convertie"},
                "semaine": {"$isoWeek": "$date_convertie"}
            },
            "nombre_badgeages": {"$sum": 1}
        }
    },
    {
        "$sort": {
            "_id.annee": 1,
            "_id.semaine": 1
        }
    }
]

print("\n========== BADGEAGES PAR SEMAINE ==========")

for r in collection.aggregate(pipeline_semaine):
    print(
        f"{r['_id']['annee']} - Semaine {r['_id']['semaine']:02d} : "
        f"{r['nombre_badgeages']}"
    )


# ==========================================
# PAR MOIS
# ==========================================

pipeline_mois = [
    {
        "$addFields": {
            "date_convertie": {
                "$dateFromString": {
                    "dateString": f"${DATE}",
                    "format": "%d/%m/%Y",
                    "onError": None,
                    "onNull": None
                }
            }
        }
    },
    {
        "$match": {
            "date_convertie": {"$ne": None}
        }
    },
    {
        "$group": {
            "_id": {
                "annee": {"$year": "$date_convertie"},
                "mois": {"$month": "$date_convertie"}
            },
            "nombre_badgeages": {"$sum": 1}
        }
    },
    {
        "$sort": {
            "_id.annee": 1,
            "_id.mois": 1
        }
    }
]

print("\n========== BADGEAGES PAR MOIS ==========")

for r in collection.aggregate(pipeline_mois):
    print(
        f"{r['_id']['annee']}-{r['_id']['mois']:02d} : "
        f"{r['nombre_badgeages']}"
    )


client.close()