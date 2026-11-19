"""Prediction électrique par salle et profil horaire issu de BOS."""
import datetime as dt, json
from pathlib import Path
from flask import jsonify, request
from temperature_day import load_plans

ROOT=Path(__file__).resolve().parent.parent
MODEL=ROOT/"trained_models"/"electricity.json"

def profile_value(profile, date, hour):
    weekday,month=date.weekday(),date.month
    value=profile.get("hour_weekday_month",{}).get(f"{month}:{weekday}:{hour}")
    if value is None: value=profile.get("hour_weekday",{}).get(f"{weekday}:{hour}")
    if value is None: value=profile.get("hour",{}).get(str(hour))
    return value

def register_energy_prediction(app, auth_required):
    plans=load_plans()
    @app.get("/api/predictions/electricity")
    @auth_required
    def prediction():
        target=request.args.get("date","").strip()
        try: date=dt.date.fromisoformat(target)
        except ValueError: return jsonify(error="Date invalide."),400
        try: floor=int(request.args.get("floor",3))
        except ValueError: return jsonify(error="Étage invalide."),400
        if floor not in plans: return jsonify(error="Étage inconnu."),400
        if not MODEL.exists(): return jsonify(error="Modèle électrique non entraîné. Lance training/train_electricity.py."),503
        try: model=json.loads(MODEL.read_text(encoding="utf-8"))
        except (OSError,ValueError): return jsonify(error="Modèle électrique illisible."),503
        profiles=model.get("room_profiles",{}); room_results={}; totals=[]
        for room in plans[floor]["rooms"]:
            profile=profiles.get(room["code"],{})
            hours=[profile_value(profile,date,h) for h in range(24)]
            room_results[room["code"]]={"hours":hours}
        for h in range(24):
            vals=[data["hours"][h] for data in room_results.values() if data["hours"][h] is not None]
            totals.append({"hour":h,"energy_kwh":sum(vals) if vals else None})
        total=sum(p["energy_kwh"] for p in totals if p["energy_kwh"] is not None) if any(p["energy_kwh"] is not None for p in totals) else None
        return jsonify(date=target,floor=floor,hourly=totals,rooms=room_results,total_kwh=total,training=model.get("training"),
          method="Profils historiques par salle, heure, jour de semaine et mois; départs partagés répartis à parts égales entre salles liées.",plan=plans[floor])
