#!/usr/bin/env python3
"""Entraîne hors ligne les modèles de température par salle.

Depuis la racine du dépôt :
    python training/train_models.py
Les modèles validés sont écrits dans trained_models/.
"""
from __future__ import annotations
import datetime as dt
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from temperature_prediction import (  # noqa: E402
    features, historical_daily, historical_hourly_offsets, weather_daily,
)


def room_filename(room: str, run_stamp: str) -> str:
    slug = "".join(c.lower() if c.isalnum() else "_" for c in room).strip("_")[:48] or "salle"
    digest = hashlib.sha1(room.encode("utf-8")).hexdigest()[:8]
    return f"{slug}_{digest}_{run_stamp}.joblib"


def main() -> int:
    try:
        import numpy as np
        import joblib
        from sklearn.ensemble import RandomForestRegressor
        import sklearn
    except ImportError as exc:
        print(f"Dépendance manquante : {exc}. Installe backend/requirements.txt")
        return 2

    out = ROOT / "trained_models"
    rooms_dir = out / "rooms"
    rooms_dir.mkdir(parents=True, exist_ok=True)
    print("Lecture des températures historiques…")
    # Limiter strictement l'entraînement aux salles dont le code commence
    # par 03 ou 04 (3e et 4e étages).
    all_histories = historical_daily()
    histories = {
        room: series
        for room, series in all_histories.items()
        if str(room).strip().startswith(("03", "04"))
    }
    excluded_count = len(all_histories) - len(histories)
    print(f"Salles retenues (préfixes 03 et 04) : {len(histories)}")
    print(f"Salles des autres étages ignorées : {excluded_count}")
    if not histories:
        print("Aucune salle commençant par 03 ou 04 trouvée dans les données.")
        return 1

    all_days = [day for values in histories.values() for day in values]
    first, last = min(all_days), max(all_days)
    print(f"Récupération de l'archive météo Open-Meteo ({first} → {last})…")
    weather = weather_daily(first, last, False)

    trained_at = dt.datetime.now(dt.timezone.utc)
    run_stamp = trained_at.strftime("%Y%m%dT%H%M%SZ")
    manifest = {
        "version": 1,
        "trained_at": trained_at.isoformat(),
        "source": "ressources/temperature_clean.xlsx ou TEMPERATURE_CSV",
        "weather_source": "Open-Meteo Archive API",
        "history_start": first,
        "history_end": last,
        "algorithm": "RandomForestRegressor",
        "sklearn_version": sklearn.__version__,
        "features": ["temperature_2m_mean", "temperature_2m_max", "temperature_2m_min", "month", "weekday", "day_of_year_sin", "day_of_year_cos"],
        "rooms": {},
        "skipped_rooms": {},
        "monthly_weather": {
            str(month): [
                round(sum(row[i] for day, row in weather.items()
                          if dt.date.fromisoformat(day).month == month
                          and all(value is not None for value in row)) /
                      max(1, sum(1 for day, row in weather.items()
                                 if dt.date.fromisoformat(day).month == month
                                 and all(value is not None for value in row))), 2)
                for i in range(3)
            ]
            for month in range(1, 13)
        },
    }

    for room, series in sorted(histories.items()):
        rows = [(day, value) for day, value in series.items()
                if day in weather and all(v is not None for v in weather[day])]
        if len(rows) < 10:
            manifest["skipped_rooms"][room] = f"Seulement {len(rows)} jours avec météo complète (10 minimum)."
            print(f"- {room}: ignorée ({len(rows)} jours exploitables)")
            continue
        rows.sort(key=lambda item: item[0])
        X = np.asarray([features(day, weather) for day, _ in rows], dtype=float)
        y = np.asarray([value for _, value in rows], dtype=float)
        # Validation chronologique : les jours les plus récents restent hors apprentissage.
        split = max(1, int(len(rows) * 0.8))
        metrics = {}
        if len(rows) - split >= 2:
            evaluation_model = RandomForestRegressor(n_estimators=120, max_depth=8,
                min_samples_leaf=2, random_state=42, n_jobs=-1)
            evaluation_model.fit(X[:split], y[:split])
            pred = evaluation_model.predict(X[split:])
            errors = np.abs(pred - y[split:])
            metrics = {"mae_c": round(float(errors.mean()), 3),
                       "test_days": int(len(errors)), "train_days": int(split)}
        model = RandomForestRegressor(n_estimators=120, max_depth=8,
            min_samples_leaf=2, random_state=42, n_jobs=-1)
        model.fit(X, y)
        filename = room_filename(room, run_stamp)
        target = rooms_dir / filename
        fd, tmp = tempfile.mkstemp(prefix=filename, suffix=".tmp", dir=rooms_dir)
        os.close(fd)
        try:
            joblib.dump(model, tmp)
            os.replace(tmp, target)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
        manifest["rooms"][room] = {"file": f"rooms/{filename}",
            "training_days": len(rows), "metrics": metrics}
        mae = f", MAE validation {metrics['mae_c']} °C" if metrics else ""
        print(f"- {room}: entraînée ({len(rows)} jours{mae})")

    # Ne sauvegarder les profils horaires que pour les mêmes étages.
    profiles = historical_hourly_offsets()
    serial_profiles = {room: {str(hour): round(float(value), 5)
                              for hour, value in profile.items()}
                       for room, profile in profiles.items()
                       if str(room).strip().startswith(("03", "04"))}
    out.mkdir(parents=True, exist_ok=True)
    (out / "hourly_profiles.json").write_text(
        json.dumps(serial_profiles, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest_path = out / "manifest.json"
    tmp_manifest = out / "manifest.json.tmp"
    tmp_manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp_manifest, manifest_path)
    print(f"\nTerminé : {len(manifest['rooms'])} modèles sauvegardés dans {out}")
    print("Les fichiers des entraînements précédents sont conservés ; le manifeste actif a été remplacé atomiquement.")
    if manifest["skipped_rooms"]:
        print(f"{len(manifest['skipped_rooms'])} salle(s) sans assez de données pour un modèle.")
    print("Relance le backend pour recharger le manifeste si celui-ci tournait déjà.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
