"""Prévision rapide d'une journée choisie, à partir du fichier historique et d'Open-Meteo."""
import datetime as dt
import math
import os
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

@lru_cache(maxsize=32)
def weather_daily(start, end, forecast=False):
    base = "https://api.open-meteo.com/v1/forecast" if forecast else "https://archive-api.open-meteo.com/v1/archive"
    params = {"latitude": LAT, "longitude": LON, "start_date": start, "end_date": end,
              "daily": "temperature_2m_mean,temperature_2m_max,temperature_2m_min", "timezone": "Europe/Paris"}
    response = requests.get(base, params=params, timeout=WEATHER_TIMEOUT)
    response.raise_for_status()
    daily = response.json().get("daily") or {}
    dates = daily.get("time") or []
    cols = [daily.get("temperature_2m_mean", []), daily.get("temperature_2m_max", []), daily.get("temperature_2m_min", [])]
    return {day: [col[i] if i < len(col) else None for col in cols] for i, day in enumerate(dates)}

def features(day, weather):
    date = dt.date.fromisoformat(day)
    w = weather.get(day, [None, None, None])
    mean = w[0] if w[0] is not None else 12.0
    high = w[1] if w[1] is not None else mean + 4
    low = w[2] if w[2] is not None else mean - 4
    return [mean, high, low, date.month, date.weekday(),
            math.sin(2 * math.pi * date.timetuple().tm_yday / 365.25),
            math.cos(2 * math.pi * date.timetuple().tm_yday / 365.25)]

def predict_one(series, weather, target):
    history = [(day, value) for day, value in series.items() if day in weather and all(v is not None for v in weather[day])]
    if len(history) < 10:
        values = [value for _, value in sorted(series.items())]
        return round(sum(values[-min(21, len(values)):]) / min(21, len(values)), 2) if values else None
    try:
        import numpy as np
        from sklearn.ensemble import RandomForestRegressor
        X = np.asarray([features(day, weather) for day, _ in history], dtype=float)
        y = np.asarray([value for _, value in history], dtype=float)
        model = RandomForestRegressor(n_estimators=35, max_depth=6, min_samples_leaf=3,
                                      random_state=42, n_jobs=-1)
        model.fit(X, y)
        return round(float(model.predict(np.asarray([features(target, weather)], dtype=float))[0]), 2)
    except ImportError:
        vals = [value for _, value in sorted(series.items())]
        return round(sum(vals[-min(21, len(vals)):]) / min(21, len(vals)), 2) if vals else None

def weather_for_target(target_date, today):
    target = dt.date.fromisoformat(target_date)
    if target <= today:
        return weather_daily(target_date, target_date, False), "archive météo observée"
    if target <= today + dt.timedelta(days=15):
        return weather_daily(target_date, target_date, True), "prévision météo Open-Meteo"
    # Open-Meteo ne prédit pas la météo à plusieurs mois : climatologie du même mois, sur 5 ans.
    end = today - dt.timedelta(days=6)
    start = end - dt.timedelta(days=5 * 365)
    archive = weather_daily(start.isoformat(), end.isoformat(), False)
    month_rows = [row for day, row in archive.items() if dt.date.fromisoformat(day).month == target.month
                  and all(value is not None for value in row)]
    if not month_rows:
        return {target_date: [12.0, 16.0, 8.0]}, "estimation météo saisonnière de repli"
    mean = [round(sum(row[i] for row in month_rows) / len(month_rows), 2) for i in range(3)]
    return {target_date: mean}, "climatologie mensuelle Open-Meteo (pas une prévision météo exacte)"

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
    profile = historical_hourly_offsets().get(room, {})
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
            target_date = dt.date.fromisoformat(target)
            history = historical_daily()
            if room and room not in history:
                return jsonify(error="Salle inconnue ou absente du fichier source."), 404
            today = dt.datetime.now(PARIS).date()
            # Uniquement la plage historique présente dans le fichier (généralement janvier-juin).
            all_days = [day for values in history.values() for day in values]
            first, last = min(all_days), max(all_days)
            weather_hist = weather_daily(first, last, False)
            weather_target, weather_mode = weather_for_target(target, today)
            weather_all = {**weather_hist, **weather_target}
            selected = {room: history[room]} if room else history
            output = []
            for room_name, values in selected.items():
                temp = predict_one(values, weather_all, target)
                w = weather_target.get(target, [None, None, None])
                output.append({"room": room_name, "date": target, "temperature": temp, "type": "prediction",
                               "hourly": hourly_estimate(room_name, temp),
                               "weather": {"mean": w[0], "max": w[1], "min": w[2]}})
            return jsonify({"source": "fichier historique fourni + API météo Open-Meteo",
                            "model": "Random Forest par salle (entraînement limité à l'historique local)",
                            "hourly_method": "Profil horaire historique par salle, recentré sur la moyenne journalière prédite. Valeurs horaires estimées, non mesurées.",
                            "weather_mode": weather_mode, "history_start": first, "history_end": last,
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
