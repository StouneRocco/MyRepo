"""API de consultation des badgeages, agrégés par niveau, jour, salle et heure."""
import csv
import datetime as dt
from collections import defaultdict
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from flask import jsonify

ROOT = Path(__file__).resolve().parent.parent
PARIS = ZoneInfo("Europe/Paris")
CSV_PATH = ROOT / "ressources" / "badgeages.csv"
CSV_URL = (
    "https://raw.githubusercontent.com/StouneRocco/MyRepo/"
    "feature/badgeages-mars/makette-matis/makette-matis/ressources/badgeages.csv"
)


def ensure_csv():
    """Récupère le CSV public de badgeages si le fichier n'est pas fourni dans le ZIP."""
    if CSV_PATH.is_file():
        return
    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    response = requests.get(CSV_URL, timeout=45)
    response.raise_for_status()
    # Écrit d'abord dans un fichier temporaire pour éviter un CSV partiel.
    temporary = CSV_PATH.with_suffix(".csv.download")
    temporary.write_bytes(response.content)
    temporary.replace(CSV_PATH)


def load_plans():
    import json
    import xml.etree.ElementTree as ET

    catalog = json.loads((ROOT / "shared" / "plan-n3.json").read_text(encoding="utf-8"))
    plans = {3: catalog["rooms"]}
    root = ET.parse(ROOT / "frontend" / "public" / "plans" / "N4.svg").getroot()
    rooms = []
    for element in root.iter():
        if element.tag.endswith("polygon") and element.get("data-selectable") == "true":
            points = element.get("points") or ""
            rooms.append({
                "id": element.get("data-space-id"),
                "code": element.get("data-room-code"),
                "name": element.get("data-room-name", "Salle"),
                "points": [list(map(float, point.split(","))) for point in points.split()],
            })
    plans[4] = rooms
    return plans


def parse_timestamp(value):
    value = (value or "").strip()
    if not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=PARIS)
    return parsed.astimezone(PARIS)


def register_badgeage_views(app, auth_required):
    plans = load_plans()
    code_to_floor = {
        room["code"]: floor
        for floor, rooms in plans.items()
        for room in rooms
    }

    @lru_cache(maxsize=1)
    def load_data():
        ensure_csv()
        by_day = defaultdict(lambda: {
            floor: {
                room["code"]: {"total": 0, "hours": [0] * 24}
                for room in rooms
            }
            for floor, rooms in plans.items()
        })
        with CSV_PATH.open("r", encoding="utf-8-sig", newline="") as source:
            reader = csv.DictReader(source)
            required = {"DateHeure", "Code salle"}
            if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
                raise ValueError("Le CSV doit contenir les colonnes DateHeure et Code salle.")
            for row in reader:
                timestamp = parse_timestamp(row.get("DateHeure"))
                code = (row.get("Code salle") or "").strip()
                floor = code_to_floor.get(code)
                if timestamp is None or timestamp.month != 3 or floor is None:
                    continue
                room = by_day[timestamp.date().isoformat()][floor][code]
                room["total"] += 1
                room["hours"][timestamp.hour] += 1
        return by_day

    @app.get("/api/badgeages/days/<int:floor>")
    @auth_required
    def badgeage_days(floor):
        if floor not in plans:
            return jsonify(error="Niveau inconnu."), 404
        try:
            data = load_data()
            return jsonify(sorted(
                day for day, levels in data.items()
                if sum(room["total"] for room in levels[floor].values()) > 0
            ))
        except (OSError, ValueError, csv.Error, requests.RequestException):
            app.logger.exception("Impossible de charger les badgeages")
            return jsonify(error="Impossible de lire les badgeages. Vérifie ta connexion Internet et le fichier ressources/badgeages.csv."), 503

    @app.get("/api/badgeages/day/<int:floor>/<day>")
    @auth_required
    def badgeage_day(floor, day):
        if floor not in plans:
            return jsonify(error="Niveau inconnu."), 404
        try:
            parsed_day = dt.date.fromisoformat(day)
            if parsed_day.isoformat() != day or parsed_day.month != 3:
                return jsonify(error="Les badgeages sont disponibles uniquement en mars."), 400
            data = load_data()
            if day not in data:
                return jsonify(error="Aucun badgeage disponible pour cette date de mars."), 404
            source_rooms = data[day][floor]
            room_names = {room["code"]: room["name"] for room in plans[floor]}
            rooms = {
                code: {"name": room_names.get(code, code), "total": values["total"], "hours": values["hours"]}
                for code, values in source_rooms.items()
            }
            hour_totals = [
                sum(values["hours"][hour] for values in source_rooms.values())
                for hour in range(24)
            ]
            return jsonify({
                "floor": floor, "day": day, "rooms": rooms,
                "hourTotals": hour_totals, "total": sum(hour_totals),
            })
        except (OSError, ValueError, csv.Error, requests.RequestException):
            app.logger.exception("Impossible de charger les badgeages")
            return jsonify(error="Impossible de lire les badgeages. Vérifie ta connexion Internet et le fichier ressources/badgeages.csv."), 503
