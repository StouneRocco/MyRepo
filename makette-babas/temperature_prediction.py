"""Prévision rapide d'une journée choisie, à partir du fichier historique et d'Open-Meteo."""
import datetime as dt
import math
import os
import json
from collections import defaultdict
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from flask import jsonify, request

ROOT = Path(__file__).resolve().parent.parent
PARIS = ZoneInfo("Europe/Paris")
LAT = float(os.getenv("WEATHER_LATITUDE", "47.4784"))
LON = float(os.getenv("WEATHER_LONGITUDE", "-0.5632"))
WEATHER_TIMEOUT = 10
MODEL_DIR = ROOT / "trained_models"
WEATHER_CACHE_DIR = MODEL_DIR / "weather_cache"

@lru_cache(maxsize=1)
def model_manifest():
    """Charge le manifeste des modèles préentraînés, sans lancer d'entraînement."""
    path = MODEL_DIR / "manifest.json"
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

@lru_cache(maxsize=128)
def load_room_model(room):
    """Charge paresseusement le modèle sauvegardé pour une salle."""
    entry = model_manifest().get("rooms", {}).get(room)
    if not entry:
        return None
    path = MODEL_DIR / entry.get("file", "")
    if not path.is_file():
        return None
    try:
        import joblib
        return joblib.load(path)
    except Exception:
        return None

def preload_room_models():
    """Charge tous les modèles déclarés au démarrage du backend."""
    for room in model_manifest().get("rooms", {}):
        load_room_model(room)


@lru_cache(maxsize=1)
def saved_hourly_profiles():
    path = MODEL_DIR / "hourly_profiles.json"
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return {room: {int(hour): float(value) for hour, value in profile.items()}
                for room, profile in raw.items()}
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return {}

@lru_cache(maxsize=1)
def historical_daily():
    """Charge et agrège le fichier local une seule fois par lancement du backend."""
    from import_temperatures import read_rows, measurement
    candidates = [Path(os.getenv("TEMPERATURE_CSV"))] if os.getenv("TEMPERATURE_CSV") else []
    resource_dir = ROOT / "ressources"
    candidates += sorted(p for p in resource_dir.glob("*.csv") if "temperature" in p.name.lower())
    candidates += [resource_dir / "temperature_clean.csv", resource_dir / "temperature_clean.xlsx"]
    source = next((p for p in candidates if p and p.exists()), None)
    if source is None:
        raise RuntimeError("Fichier de températures introuvable. Place temperature_clean.csv ou temperature_clean.xlsx dans ressources/.")
    sums, counts = defaultdict(float), defaultdict(int)
    for row in read_rows(source):
        doc = measurement(row)
        if not doc:
            continue
        day = doc["timestamp"].astimezone(PARIS).date().isoformat()
        key = (doc["room"], day)
        sums[key] += doc["temperature"]
        counts[key] += 1
    result = defaultdict(dict)
    for (room, day), total in sums.items():
        result[room][day] = round(total / counts[(room, day)], 3)
    if not result:
        raise RuntimeError(f"Aucune mesure valide dans {source.name}.")
    return dict(result)

def weather_daily(start, end, forecast=False):
    """Récupère une plage météo et la conserve durablement sur disque."""
    endpoint = "forecast" if forecast else "archive"
    cache_key = f"{endpoint}_{LAT}_{LON}_{start}_{end}".replace("/", "_")
    cache_path = WEATHER_CACHE_DIR / f"{cache_key}.json"
    if cache_path.is_file():
        try:
            return json.loads(cache_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    base = "https://api.open-meteo.com/v1/forecast" if forecast else "https://archive-api.open-meteo.com/v1/archive"
    params = {"latitude": LAT, "longitude": LON, "start_date": start, "end_date": end,
              "daily": "temperature_2m_mean,temperature_2m_max,temperature_2m_min", "timezone": "Europe/Paris"}
    response = requests.get(base, params=params, timeout=WEATHER_TIMEOUT)
    response.raise_for_status()
    daily = response.json().get("daily") or {}
    dates = daily.get("time") or []
    cols = [daily.get("temperature_2m_mean", []), daily.get("temperature_2m_max", []), daily.get("temperature_2m_min", [])]
    result = {day: [col[i] if i < len(col) else None for col in cols] for i, day in enumerate(dates)}
    WEATHER_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = cache_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(result), encoding="utf-8")
    os.replace(tmp, cache_path)
    return result

def features(day, weather):
    date = dt.date.fromisoformat(day)
    w = weather.get(day, [None, None, None])
    mean = w[0] if w[0] is not None else 12.0
    high = w[1] if w[1] is not None else mean + 4
    low = w[2] if w[2] is not None else mean - 4
    return [mean, high, low, date.month, date.weekday(),
            math.sin(2 * math.pi * date.timetuple().tm_yday / 365.25),
            math.cos(2 * math.pi * date.timetuple().tm_yday / 365.25)]

def predict_one(series, weather, target, room=None):
    """Prédit avec le modèle préentraîné ; moyenne récente si aucun modèle n'existe."""
    model = load_room_model(room) if room else None
    if model is not None:
        try:
            import numpy as np
            return round(float(model.predict(np.asarray([features(target, weather)], dtype=float))[0]), 2)
        except Exception:
            # Un modèle incompatible/corrompu ne doit pas empêcher la consultation.
            pass
    values = [value for _, value in sorted(series.items())]
    if not values:
        return None
    window = min(21, len(values))
    return round(sum(values[-window:]) / window, 2)

def weather_for_target(target_date, today):
    target = dt.date.fromisoformat(target_date)
    if target <= today:
        return weather_daily(target_date, target_date, False), "archive météo observée"
    if target <= today + dt.timedelta(days=15):
        return weather_daily(target_date, target_date, True), "prévision météo Open-Meteo"
    climate = model_manifest().get("monthly_weather", {}).get(str(target.month))
    if climate:
        return {target_date: climate}, "climatologie mensuelle sauvegardée (pas une prévision exacte)"
    return {target_date: [12.0, 16.0, 8.0]}, "estimation météo saisonnière de repli"


@lru_cache(maxsize=1)
def historical_hourly_offsets():
    """Profil horaire moyen par salle, exprimé en écart à la moyenne du jour.

    Ce profil est une estimation issue des mesures historiques, pas une prévision
    horaire apprise directement par le modèle journalier.
    """
    from import_temperatures import read_rows, measurement
    candidates = [Path(os.getenv("TEMPERATURE_CSV"))] if os.getenv("TEMPERATURE_CSV") else []
    resource_dir = ROOT / "ressources"
    candidates += sorted(p for p in resource_dir.glob("*.csv") if "temperature" in p.name.lower())
    candidates += [resource_dir / "temperature_clean.csv", resource_dir / "temperature_clean.xlsx"]
    source = next((p for p in candidates if p and p.exists()), None)
    if source is None:
        return {}
    days = defaultdict(list)
    for row in read_rows(source):
        doc = measurement(row)
        if not doc:
            continue
        local = doc["timestamp"].astimezone(PARIS)
        days[(doc["room"], local.date().isoformat())].append((local.hour, doc["temperature"]))
    totals, counts = defaultdict(float), defaultdict(int)
    for (room, _day), points in days.items():
        daily_mean = sum(value for _, value in points) / len(points)
        hour_values = defaultdict(list)
        for hour, value in points:
            hour_values[hour].append(value)
        for hour, values in hour_values.items():
            key = (room, hour)
            totals[key] += sum(values) / len(values) - daily_mean
            counts[key] += 1
    offsets = defaultdict(dict)
    for (room, hour), total in totals.items():
        offsets[room][hour] = total / counts[(room, hour)]
    return {room: dict(values) for room, values in offsets.items()}

def hourly_estimate(room, daily_temperature):
    """Construit 24 estimations horaires à partir du profil observé de la salle."""
    if daily_temperature is None:
        return []
    profile = saved_hourly_profiles().get(room, {})
    # Profil neutre si les historiques n'ont pas de mesures intra-journalières.
    offsets = [profile.get(hour, 0.0) for hour in range(24)]
    # Centrer le profil afin que sa moyenne ne déplace pas la prédiction journalière.
    center = sum(offsets) / len(offsets)
    return [{"hour": hour, "temperature": round(float(daily_temperature) + offsets[hour] - center, 2),
             "type": "estimation_horaire_historique" if hour in profile else "estimation_profil_incomplet"}
            for hour in range(24)]

def register_prediction_views(app, auth_required):
    @app.get("/api/predictions/temperatures")
    @auth_required
    def predict_temperatures():
        room = request.args.get("room", "").strip()
        target = request.args.get("date", "").strip()
        if not target:
            target = dt.datetime.now(PARIS).date().isoformat()
        try:
            dt.date.fromisoformat(target)
            manifest = model_manifest()
            rooms = manifest.get("rooms", {})
            if room and room not in rooms:
                return jsonify(error="Salle inconnue ou sans modèle entraîné (étages 03/04)."), 404
            if not rooms:
                return jsonify(error="Aucun modèle entraîné. Lance training/train_models.py avant les prédictions."), 503
            today = dt.datetime.now(PARIS).date()
            weather_target, weather_mode = weather_for_target(target, today)
            selected = {room: rooms[room]} if room else rooms
            output = []
            for room_name in selected:
                temp = predict_one({}, weather_target, target, room_name)
                w = weather_target.get(target, [None, None, None])
                output.append({"room": room_name, "date": target, "temperature": temp, "type": "prediction",
                               "hourly": hourly_estimate(room_name, temp),
                               "weather": {"mean": w[0], "max": w[1], "min": w[2]}})
            return jsonify({"source": "modèles préentraînés + météo Open-Meteo",
                            "model": "Random Forest préentraîné par salle",
                            "training": {"available": True, "trained_at": manifest.get("trained_at"),
                                         "model_version": manifest.get("version")},
                            "hourly_method": "Profil horaire historique sauvegardé et recentré sur la moyenne journalière prédite. Valeurs estimées, non mesurées.",
                            "weather_mode": weather_mode,
                            "history_start": manifest.get("history_start"),
                            "history_end": manifest.get("history_end"),
                            "predictions": output})
        except (ValueError, requests.RequestException, RuntimeError) as exc:
            return jsonify(error=f"Prévision indisponible : {exc}"), 502

    @app.get("/api/predictions/missing-days")
    @auth_required
    def missing_temperature_days():
        # Endpoint conservé pour compatibilité, mais la page de prévision ne le charge plus automatiquement.
        room = request.args.get("room", "").strip()
        try:
            history = historical_daily()
            if room and room not in history:
                return jsonify(error="Salle inconnue ou absente du fichier source."), 404
            selected = {room: history[room]} if room else history
            results = []
            for name, values in selected.items():
                dates = sorted(dt.date.fromisoformat(day) for day in values)
                for left, right in zip(dates, dates[1:]):
                    gap = (right-left).days
                    for offset in range(1, min(gap, 31)):
                        day = (left+dt.timedelta(days=offset)).isoformat()
                        fraction = offset/gap
                        value = values[left.isoformat()] + (values[right.isoformat()]-values[left.isoformat()])*fraction
                        results.append({"room": name, "date": day, "temperature": round(value, 2), "type": "estimation_interpolation"})
            return jsonify({"source": "fichier historique fourni", "missing_days": results})
        except (RuntimeError, ValueError) as exc:
            return jsonify(error=str(exc)), 500
