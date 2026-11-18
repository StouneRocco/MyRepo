from pathlib import Path
import datetime
import os
import sqlite3
from contextlib import closing
from flask import jsonify, request
from temperature_day import load_plans, day_bounds, expiring_cache

ROOT = Path(__file__).resolve().parent.parent


def database_path():
    configured = os.getenv('BOS_DB_PATH')
    local_config = ROOT / '.runtime' / 'bos-db-path.txt'
    if not configured and local_config.is_file():
        configured = local_config.read_text(encoding='utf-8-sig').strip()
    return Path(configured) if configured else ROOT / 'ressources' / 'bos.db'


@expiring_cache(maxsize=16, seconds=30)
def electrical_frame(floor, day):
    day_bounds(day)
    plans = load_plans()
    if floor not in plans:
        raise ValueError('Étage inconnu.')
    path = database_path()
    if not path.is_file():
        raise FileNotFoundError('Base BOS introuvable.')
    end = (datetime.date.fromisoformat(day) + datetime.timedelta(days=1)).isoformat()
    codes = {room['code'] for room in plans[floor]['rooms']}
    rooms = {code: {'hours': [None]*24, 'dedicated': [None]*24, 'shared': [None]*24,
                    'observed': [0]*24, 'meters': 0, 'sharedMeters': 0} for code in codes}
    with closing(sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)) as conn:
        links = conn.execute('''SELECT m.sensor_id, cr.room FROM electrical_meters m
            JOIN circuit_rooms cr ON cr.circuit_id=m.circuit_id WHERE m.included=1
            ORDER BY m.sensor_id, cr.room''').fetchall()
        mapping = {}
        for sensor, room in links:
            mapping.setdefault(sensor, []).append(room)
        for linked in mapping.values():
            for room in codes.intersection(linked):
                rooms[room]['meters'] += 1
                if len(linked) > 1:
                    rooms[room]['sharedMeters'] += 1
        seen = {}
        for sensor, hour, energy in conn.execute('''SELECT sensor_id, hour, energy_kwh FROM electrical_hourly
                WHERE hour>=? AND hour<?''', (day, end)):
            linked = mapping.get(sensor)
            if not linked:
                continue
            index = int(hour[11:13])
            for code in codes.intersection(linked):
                key = (code, index)
                count, dedicated, shared = seen.get(key, (0, 0.0, 0.0))
                if len(linked) == 1:
                    dedicated += energy
                else:
                    shared += energy / len(linked)
                seen[key] = count+1, dedicated, shared
        for (code, hour), (count, dedicated, shared) in seen.items():
            rooms[code]['observed'][hour] = count
            if count == rooms[code]['meters']:
                rooms[code]['dedicated'][hour] = dedicated
                rooms[code]['shared'][hour] = shared
                rooms[code]['hours'][hour] = dedicated + shared
    return {'floor': floor, 'day': day, 'rooms': rooms}


def register_electrical_views(app, auth_required):
    @app.get('/api/electricity/day/<int:floor>/<day>')
    @auth_required
    def electricity_day(floor, day):
        try:
            return jsonify(electrical_frame(floor, day))
        except (ValueError, OverflowError):
            return jsonify(error='Étage ou date invalide.'), 400
        except (sqlite3.Error, OSError):
            return jsonify(error='Base électrique BOS indisponible ou invalide.'), 503

    @app.get('/api/electricity')
    @auth_required
    def electricity():
        path = database_path()
        if not path.is_file():
            return jsonify(error='Base BOS introuvable. Configurez BOS_DB_PATH ou .runtime/bos-db-path.txt.'), 503
        try:
            with closing(sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)) as conn:
                conn.row_factory = sqlite3.Row
                bounds = conn.execute('SELECT MIN(hour), MAX(hour) FROM electrical_hourly').fetchone()
                if not bounds[0]:
                    return jsonify(error='Aucune mesure électrique dans la base BOS.'), 503
                first, last = bounds[0][:10], bounds[1][:10]
                day = request.args.get('day', first)
                try:
                    if datetime.date.fromisoformat(day).isoformat() != day:
                        raise ValueError()
                    end = (datetime.date.fromisoformat(day) + datetime.timedelta(days=1)).isoformat()
                except (ValueError, OverflowError):
                    return jsonify(error='Date invalide.'), 400
                rows = conn.execute('''SELECT m.sensor_id, m.circuit_id, m.label, m.usage, m.included,
                    SUM(e.energy_kwh) AS energy_kwh, COUNT(e.hour) AS observed_hours
                    FROM electrical_meters m LEFT JOIN electrical_hourly e
                    ON e.sensor_id=m.sensor_id AND e.hour>=? AND e.hour<?
                    GROUP BY m.sensor_id ORDER BY energy_kwh DESC, m.circuit_id''', (day, end)).fetchall()
                links = {}
                for link in conn.execute('SELECT circuit_id, room FROM circuit_rooms ORDER BY room'):
                    links.setdefault(link['circuit_id'], []).append(link['room'])
                circuits = []
                for row in rows:
                    circuit = dict(row)
                    circuit['included'] = bool(circuit['included'])
                    circuit['rooms'] = links.get(circuit['circuit_id'], [])
                    circuits.append(circuit)
                measured = [c for c in circuits if c['included'] and c['energy_kwh'] is not None]
                return jsonify(day=day, first=first, last=last, circuits=circuits,
                    total=sum(c['energy_kwh'] for c in measured) if measured else None)
        except (sqlite3.Error, OSError):
            app.logger.exception('Lecture de la base électrique BOS impossible')
            return jsonify(error='Impossible de lire les données électriques BOS. Vérifiez la base configurée.'), 503
