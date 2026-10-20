import datetime
import functools
import os
import json
import math
import secrets
import sys
from pathlib import Path

import jwt
import requests
from flask import Flask, g, jsonify, request, send_from_directory, Response
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError
from werkzeug.security import check_password_hash, generate_password_hash
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'shared'))
from projection_context import validate_context

MONGO_URI = os.getenv("MONGO_URI", "mongodb://127.0.0.1:27017")
JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET:
    # Clé persistante pour pouvoir démarrer sans export manuel.
    secret_path = Path(__file__).resolve().parent / ".jwt_secret"
    try:
        descriptor = os.open(secret_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        JWT_SECRET = secret_path.read_text(encoding="utf-8").strip()
    else:
        JWT_SECRET = secrets.token_hex(32)
        with os.fdopen(descriptor, "w") as secret_file:
            secret_file.write(JWT_SECRET)
    if not JWT_SECRET:
        raise RuntimeError("Le fichier backend/.jwt_secret est vide.")
CAMERA_URL = os.getenv("CAMERA_URL", "http://127.0.0.1:5001")  # color_receiver.py
DIST = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")

app = Flask(__name__)
PLAN_ROOMS = json.loads(
    (Path(__file__).resolve().parent.parent / "shared/plan-n3.json").read_text(encoding="utf-8")
)["rooms"]
ROOM_IDS = {room["id"] for room in PLAN_ROOMS}
ROOM_CODES = {room["code"] for room in PLAN_ROOMS}
users = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)[os.getenv("MONGO_DB", "calibration_app")]["users"]
users.create_index("username", unique=True)
temperatures = users.database["temperature_measurements"]
temperatures.create_index([("room", 1), ("timestamp", 1)], unique=True)
temperatures.create_index("timestamp")


def make_token(username):
    exp = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=12)
    return jwt.encode({"sub": username, "exp": exp}, JWT_SECRET, algorithm="HS256")


def auth_required(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        header = request.headers.get("Authorization", "")
        try:
            payload = jwt.decode(header.removeprefix("Bearer "), JWT_SECRET, algorithms=["HS256"])
        except jwt.PyJWTError:
            return jsonify({"error": "Session expirée, reconnecte-toi."}), 401
        g.username = payload["sub"]
        return fn(*args, **kwargs)
    return wrapper


def credentials():
    data = request.get_json(silent=True) or {}
    return str(data.get("username", "")).strip().lower(), str(data.get("password", ""))


@app.post("/api/register")
def register():
    username, password = credentials()
    if not 3 <= len(username) <= 32 or len(password) < 8:
        return jsonify({"error": "Identifiant de 3 à 32 caractères, mot de passe de 8 caractères minimum."}), 400
    try:
        users.insert_one({"username": username, "password": generate_password_hash(password),
                          "created_at": datetime.datetime.now(datetime.timezone.utc)})
    except DuplicateKeyError:
        return jsonify({"error": "Cet identifiant existe déjà."}), 409
    return jsonify({"token": make_token(username), "username": username}), 201


@app.post("/api/login")
def login():
    username, password = credentials()
    user = users.find_one({"username": username})
    if not user or not check_password_hash(user["password"], password):
        return jsonify({"error": "Identifiant ou mot de passe incorrect."}), 401
    return jsonify({"token": make_token(username), "username": username})


@app.post("/api/calibrate")
@auth_required
def calibrate():
    try:
        r = requests.post(f"{CAMERA_URL}/calibrate", timeout=5)
        r.raise_for_status()
    except requests.RequestException:
        return jsonify({"error": "color_receiver.py ne répond pas sur le port 5001. Vérifie qu'il est lancé."}), 502
    return jsonify({"status": "ok"})


@app.post("/api/project-room")
@auth_required
def project_room():
    if shared_view.active:
        return jsonify(status='shared-view', roomId=shared_view.snapshot()['roomId'])
    data = request.get_json(silent=True)
    if not isinstance(data, dict) or "roomId" not in data:
        return jsonify({"error": "Salle manquante."}), 400
    room_id = data["roomId"]
    if room_id is not None and (not isinstance(room_id, str) or room_id not in ROOM_IDS):
        return jsonify({"error": "Salle inconnue."}), 400
    try:
        response = requests.post(f"{CAMERA_URL}/project-room", json={"roomId": room_id}, timeout=5)
        response.raise_for_status()
    except requests.RequestException:
        return jsonify({"error": "Projection indisponible. Vérifie que color_receiver.py est lancé."}), 502
    return jsonify({"status": "ok", "roomId": room_id})


@app.route('/api/calibration-settings', methods=['GET', 'POST'])
@auth_required
def calibration_settings():
    if request.method == 'POST' and not isinstance(request.get_json(silent=True), dict):
        return jsonify({'error': 'Réglages de calibration requis.'}), 400
    try:
        if request.method == 'POST':
            response = requests.post(f'{CAMERA_URL}/calibration-settings', json=request.get_json(), timeout=5)
        else:
            response = requests.get(f'{CAMERA_URL}/calibration-settings', timeout=5)
        data = response.json()
        return jsonify(data), response.status_code
    except (requests.RequestException, ValueError):
        return jsonify({'error': 'Réglages indisponibles. Vérifie que le récepteur de projection est lancé et à jour.'}), 502


@app.get('/api/projection-preview')
@auth_required
def projection_preview():
    try:
        response = requests.get(f'{CAMERA_URL}/projection-preview', timeout=2)
        response.raise_for_status()
        return Response(response.content, mimetype='image/jpeg', headers={'Cache-Control': 'no-store', 'X-Calibration-Settings': response.headers.get('X-Calibration-Settings', '{}')})
    except requests.RequestException:
        return jsonify({'error': 'Aperçu du projecteur indisponible.'}), 502


@app.post("/api/project-temperatures")
@auth_required
def project_temperatures():
    if shared_view.active:
        return jsonify(status='shared-view')
    values = request.get_json(silent=True)
    context = None
    if isinstance(values, dict) and 'temperatures' in values:
        try:
            context = validate_context(values.get('context', {}), ROOM_CODES)
        except (ValueError, TypeError):
            return jsonify(error='Contexte de projection invalide.'), 400
        values = values['temperatures']
    if not isinstance(values, dict) or any(
        code not in ROOM_CODES or isinstance(value, bool)
        or not isinstance(value, (int, float)) or not math.isfinite(value)
        for code, value in values.items()
    ):
        return jsonify({"error": "Code de salle ou température invalide."}), 400
    try:
        payload = values if context is None else {'temperatures': values, 'context': context}
        response = requests.post(f"{CAMERA_URL}/project-temperatures", json=payload, timeout=5)
        response.raise_for_status()
    except requests.RequestException:
        return jsonify({"error": "Couleurs non transmises. Vérifiez que le récepteur Pi est lancé et à jour."}), 502
    return jsonify({"status": "ok"})


@app.get("/api/temperatures/range")
@auth_required
def temperature_range():
    first = temperatures.find_one({}, {"timestamp": 1}, sort=[("timestamp", 1)])
    last = temperatures.find_one({}, {"timestamp": 1}, sort=[("timestamp", -1)])
    def iso(doc):
        return doc["timestamp"].replace(tzinfo=datetime.timezone.utc).isoformat() if doc else None
    return jsonify({"minTimestamp": iso(first), "maxTimestamp": iso(last)})


@app.get("/api/temperatures")
@auth_required
def room_temperatures():
    try:
        target = datetime.datetime.fromisoformat(request.args.get("timestamp", "").replace("Z", "+00:00"))
        if target.tzinfo is None:
            raise ValueError()
        target = target.astimezone(datetime.timezone.utc)
        tolerance = datetime.timedelta(minutes=10)
        lower, upper = target - tolerance, target + tolerance
    except (ValueError, OverflowError):
        return jsonify({"error": "Timestamp ISO 8601 avec fuseau horaire requis."}), 400
    # L'index timestamp limite les documents avant le tri et le regroupement.
    pipeline = [
        {"$match": {"timestamp": {"$gte": lower, "$lte": upper}}},
        {"$addFields": {"distance": {"$abs": {"$subtract": ["$timestamp", target]}}}},
        {"$sort": {"distance": 1, "timestamp": 1, "_id": 1}},
        {"$group": {"_id": "$room", "temperature": {"$first": "$temperature"}}},
    ]
    return jsonify({doc["_id"]: doc["temperature"] for doc in temperatures.aggregate(pipeline)})


# Lecture journalière pour l'interface Axel ; les commandes Pi restent inchangées.
from temperature_day import register_temperature_views
register_temperature_views(app, temperatures, auth_required)
from view_state import SharedView, register_shared_view
shared_view = SharedView(users.database['viewer_state'], temperatures, CAMERA_URL, requests)
register_shared_view(app, shared_view, auth_required)


@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def spa(path):
    if path and os.path.isfile(os.path.join(DIST, path)):
        return send_from_directory(DIST, path)
    return send_from_directory(DIST, "index.html")


if __name__ == "__main__":
    import threading
    threading.Thread(target=shared_view.run, daemon=True).start()
    app.run(host="0.0.0.0", port=5000)
