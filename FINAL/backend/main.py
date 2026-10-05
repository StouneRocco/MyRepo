from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastapi.responses import Response
from pathlib import Path

from ifc_service import (
    get_building_info,
    get_floors,
    get_floor_geometry,
)


# ============================================================
# APPLICATION
# ============================================================

app = FastAPI(
    title="Campus Dijon API",
    version="0.3.0"
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Expose les SVG exportés par export_svg.py
# Structure: projet/exports/N0.svg, N1.svg, ...
EXPORTS_DIR = Path(__file__).resolve().parent.parent / "exports"
app.mount("/exports", StaticFiles(directory=str(EXPORTS_DIR)), name="exports")


# ============================================================
# SVG MODIFIE PAR L'UTILISATEUR
# ============================================================
# L'IFC et les SVG originaux restent inchangés.
# Les modifications du mode "Modifier" sont enregistrées dans
# exports/edited/<etage>.svg et rechargées automatiquement.
EDITED_EXPORTS_DIR = EXPORTS_DIR / "edited"
EDITED_EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

def safe_svg_floor(value: str) -> str:
    value = str(value or "").strip()
    if not value or "/" in value or "\\" in value or ".." in value:
        raise HTTPException(status_code=400, detail="Nom d'étage invalide")
    return value

@app.get("/api/svg/{floor}")
def get_edited_svg(floor: str):
    floor = safe_svg_floor(floor)
    path = EDITED_EXPORTS_DIR / f"{floor}.svg"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Aucun SVG modifié pour cet étage")
    return Response(content=path.read_bytes(), media_type="image/svg+xml")

@app.put("/api/svg/{floor}")
async def save_edited_svg(floor: str, request: Request):
    floor = safe_svg_floor(floor)
    content = await request.body()
    if not content or b"<svg" not in content[:2000]:
        raise HTTPException(status_code=400, detail="SVG invalide")
    path = EDITED_EXPORTS_DIR / f"{floor}.svg"
    path.write_bytes(content)
    return {"ok": True, "floor": floor, "path": str(path)}

@app.delete("/api/svg/{floor}")
def delete_edited_svg(floor: str):
    floor = safe_svg_floor(floor)
    path = EDITED_EXPORTS_DIR / f"{floor}.svg"
    if path.exists():
        path.unlink()
    return {"ok": True, "floor": floor}


# ============================================================
# CALIBRATION
# ============================================================

class Calibration(BaseModel):
    floor: str
    scale: float = 1.0
    offset_x: float = 0.0
    offset_y: float = 0.0


calibrations = {}


# ============================================================
# HEALTH
# ============================================================

@app.get("/api/health")
def health():
    """
    Vérifie que l'API fonctionne.
    """

    return {
        "status": "ok",
        "service": "campus-dijon-api"
    }


# ============================================================
# IFC - INFORMATIONS GENERALES
# ============================================================

@app.get("/api/ifc/info")
def ifc_info():
    """
    Retourne les informations générales
    directement depuis le fichier IFC.
    """

    return get_building_info()


# ============================================================
# IFC - LISTE DES NIVEAUX
# ============================================================

@app.get("/api/floors")
def floors():
    """
    Retourne les niveaux directement
    depuis le fichier IFC.
    """

    return {
        "floors": get_floors()
    }


# ============================================================
# IFC - LISTE DES NIVEAUX
# ALIAS
# ============================================================

@app.get("/api/ifc/floors")
def ifc_floors():
    """
    Alias de /api/floors.
    """

    return {
        "floors": get_floors()
    }


# ============================================================
# IFC - GEOMETRIE REELLE D'UN NIVEAU
# ============================================================

@app.get("/api/floors/{floor}")
def floor(floor: str):
    """
    Retourne la géométrie réelle d'un niveau
    extraite du fichier IFC.

    Exemple :

        /api/floors/N1

    retourne les murs, portes, fenêtres,
    espaces et les limites du niveau.
    """

    # --------------------------------------------------------
    # Vérification que le niveau existe
    # --------------------------------------------------------

    floors_data = get_floors()

    floor_names = [
        f["name"]
        for f in floors_data
    ]

    if floor not in floor_names:
        return {
            "error": "Unknown floor",
            "floors": floor_names
        }

    # --------------------------------------------------------
    # Extraction de la vraie géométrie IFC
    # --------------------------------------------------------

    try:

        geometry = get_floor_geometry(floor)

        return geometry

    except Exception as error:

        print(
            f"Erreur lors de l'extraction "
            f"de la géométrie de {floor} : {error}"
        )

        return {
            "error": str(error),
            "floor": floor
        }


# ============================================================
# CAPTEURS
# ============================================================

@app.get("/api/sensors")
def sensors(floor: str | None = None):
    """
    Données de capteurs provisoires.

    Pour le moment elles sont simulées.

    Elles seront remplacées ensuite par les
    vraies données provenant de la base de données.
    """

    data = [
        {
            "id": "CAP-01",
            "floor": "N1",
            "x": 0.25,
            "y": 0.35,
            "temperature": 21.4,
            "co2": 680,
            "humidity": 45
        },
        {
            "id": "CAP-02",
            "floor": "N1",
            "x": 0.62,
            "y": 0.42,
            "temperature": 23.1,
            "co2": 920,
            "humidity": 51
        },
        {
            "id": "CAP-03",
            "floor": "N2",
            "x": 0.45,
            "y": 0.60,
            "temperature": 19.8,
            "co2": 540,
            "humidity": 42
        }
    ]

    # --------------------------------------------------------
    # Filtre par niveau
    # --------------------------------------------------------

    if floor is not None:

        data = [
            sensor
            for sensor in data
            if sensor["floor"] == floor
        ]

    return {
        "sensors": data
    }


# ============================================================
# CALIBRATION - ENREGISTREMENT
# ============================================================

@app.post("/api/calibration")
def save_calibration(item: Calibration):
    """
    Enregistre les paramètres de calibration
    d'un niveau.
    """

    calibrations[item.floor] = item.model_dump()

    return {
        "ok": True,
        "calibration": calibrations[item.floor]
    }


# ============================================================
# CALIBRATION - LECTURE
# ============================================================

@app.get("/api/calibration/{floor}")
def get_calibration(floor: str):
    """
    Retourne la calibration d'un niveau.

    Si aucune calibration n'existe encore,
    retourne les valeurs par défaut.
    """

    return calibrations.get(
        floor,
        {
            "floor": floor,
            "scale": 1.0,
            "offset_x": 0.0,
            "offset_y": 0.0
        }
    )