#!/usr/bin/env python3
"""Entraîne les profils électriques globaux et par salle à partir de BOS."""
import sqlite3, json, os, sys
from pathlib import Path
from collections import defaultdict
import datetime as dt
ROOT=Path(__file__).resolve().parents[1]
def database_path():
    configured=os.getenv('BOS_DB_PATH')
    runtime=ROOT/'.runtime'/'bos-db-path.txt'
    if not configured and runtime.is_file(): configured=runtime.read_text(encoding='utf-8-sig').strip()
    return Path(configured) if configured else ROOT/'ressources'/'bos.db'

def mean(values): return sum(values)/len(values) if values else None

def main():
    db=database_path()
    if not db.exists(): raise SystemExit(f"Base BOS absente: {db}")
    totals=defaultdict(list); wd=defaultdict(list); wdm=defaultdict(list)
    room_hour=defaultdict(list); room_wd=defaultdict(list); room_wdm=defaultdict(list)
    with sqlite3.connect(db) as c:
        rows=c.execute("""SELECT e.sensor_id,e.hour,e.energy_kwh FROM electrical_hourly e JOIN electrical_meters m
          ON m.sensor_id=e.sensor_id WHERE m.included=1""").fetchall()
        links=c.execute("""SELECT m.sensor_id,cr.room FROM electrical_meters m JOIN circuit_rooms cr
          ON cr.circuit_id=m.circuit_id WHERE m.included=1 ORDER BY m.sensor_id,cr.room""").fetchall()
    mapping=defaultdict(list)
    for sensor,room in links: mapping[sensor].append(room)
    if not rows: raise SystemExit("Aucune mesure retenue.")
    for sensor,stamp,val in rows:
        date,hour=stamp[:10],int(stamp[11:13]); d=dt.date.fromisoformat(date)
        totals[hour].append(val);wd[(d.weekday(),hour)].append(val);wdm[(d.month,d.weekday(),hour)].append(val)
        linked=mapping.get(sensor,[])
        if linked:
            share=val/len(linked)
            for room in linked:
                room_hour[(room,hour)].append(share)
                room_wd[(room,d.weekday(),hour)].append(share)
                room_wdm[(room,d.month,d.weekday(),hour)].append(share)
    profile={"hour":{str(k):mean(v) for k,v in totals.items()},
      "hour_weekday":{f"{k[0]}:{k[1]}":mean(v) for k,v in wd.items()},
      "hour_weekday_month":{f"{k[0]}:{k[1]}:{k[2]}":mean(v) for k,v in wdm.items()}}
    room_profiles={}
    for room in sorted({k[0] for k in room_hour}):
        room_profiles[room]={"hour":{str(k[1]):mean(v) for k,v in room_hour.items() if k[0]==room},
          "hour_weekday":{f"{k[1]}:{k[2]}":mean(v) for k,v in room_wd.items() if k[0]==room},
          "hour_weekday_month":{f"{k[1]}:{k[2]}:{k[3]}":mean(v) for k,v in room_wdm.items() if k[0]==room}}
    model={"profile":profile,"room_profiles":room_profiles,"training":{"samples":len(rows),"source":"electrical_hourly (included meters), shared meters distributed equally across linked rooms","min_hour":min(r[1] for r in rows),"max_hour":max(r[1] for r in rows),"algorithm":"historical averages per room, weekday, month and hour"}}
    out=ROOT/"trained_models"/"electricity.json";out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(model,ensure_ascii=False,indent=2),encoding="utf-8")
    print(f"Modèle électrique entraîné ({len(rows)} mesures): {out}")
if __name__=="__main__":main()
