"""Vues journalières en lecture seule sur les mesures MongoDB existantes."""
import datetime as dt
import json
import math
import time
from functools import lru_cache
from pathlib import Path
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

from flask import jsonify
from pymongo.errors import PyMongoError

ROOT = Path(__file__).resolve().parent.parent
PARIS = ZoneInfo('Europe/Paris')
MAX_GAP_MINUTES = 180


def expiring_cache(maxsize=16, seconds=30):
    """Caches bornés : un import est visible sans redémarrage, sous 30 secondes."""
    def decorate(fn):
        cached = lru_cache(maxsize=maxsize)(lambda epoch, *args: fn(*args))
        def read(*args):
            return cached(int(time.monotonic()//seconds), *args)
        read.cache_clear = cached.cache_clear
        return read
    return decorate


def valid_local_buckets(day):
    date = dt.date.fromisoformat(day)
    result=[]
    for minute in range(0,1440,5):
        local=dt.datetime.combine(date,dt.time(minute//60,minute%60),PARIS)
        result.append(local.astimezone(dt.timezone.utc).astimezone(PARIS).replace(tzinfo=None)==local.replace(tzinfo=None))
    return result


def load_plans():
    catalog = json.loads((ROOT / 'shared/plan-n3.json').read_text(encoding="utf-8"))
    x0, y0, x1, y1 = catalog['svgBounds']
    plans = {3: {'floor': 3, 'bounds': [x0 - 2, y0 - 2, x1 - x0 + 4, y1 - y0 + 4], 'rooms': catalog['rooms']}}
    root = ET.parse(ROOT / 'frontend/public/plans/N4.svg').getroot()
    rooms = []
    for element in root.iter():
        if element.tag.endswith('polygon') and element.get('data-selectable') == 'true':
            rooms.append({'id': element.get('data-space-id'), 'code': element.get('data-room-code'),
                          'name': element.get('data-room-name', 'Salle'),
                          'points': [list(map(float, point.split(','))) for point in element.get('points').split()]})
    xs, ys = zip(*(point for room in rooms for point in room['points']))
    plans[4] = {'floor': 4, 'bounds': [min(xs)-2, min(ys)-2, max(xs)-min(xs)+4, max(ys)-min(ys)+4], 'rooms': rooms}
    return plans


def day_bounds(day):
    date = dt.date.fromisoformat(day)
    if date.isoformat() != day:
        raise ValueError('Date attendue au format AAAA-MM-JJ')
    begin = dt.datetime.combine(date, dt.time(), PARIS)
    end = dt.datetime.combine(date + dt.timedelta(days=1), dt.time(), PARIS)
    return begin.astimezone(dt.timezone.utc), end.astimezone(dt.timezone.utc)


def interpolate_gaps(values, valid=None):
    filled, estimated = list(values), [False] * len(values)
    left = None
    for right, value in enumerate(values):
        if valid is not None and not valid[right]:
            filled[right] = None
            left = None
            continue
        if value is None:
            continue
        if left is not None and right > left + 1 and (right-left)*5 <= MAX_GAP_MINUTES:
            for index in range(left+1, right):
                filled[index] = round(values[left] + (value-values[left])*(index-left)/(right-left), 3)
                estimated[index] = True
        left = right
    return filled, estimated


def daily_frame(collection, plan, day):
    begin, end = day_bounds(day)
    codes = {room['code']: room['id'] for room in plan['rooms']}
    series = {room_id: [None]*288 for room_id in codes.values()}
    counts = {room_id: 0 for room_id in codes.values()}
    rows = collection.find({'room': {'$in': list(codes)}, 'timestamp': {'$gte': begin, '$lt': end}},
                           {'_id': 0, 'room': 1, 'timestamp': 1, 'temperature': 1}).sort([('room', 1), ('timestamp', 1)])
    for row in rows:
        value = row.get('temperature')
        room_id = codes.get(row['room'])
        if room_id is None or not isinstance(value, (int, float)) or not math.isfinite(value):
            continue
        timestamp = row['timestamp']
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=dt.timezone.utc)
        local = timestamp.astimezone(PARIS)
        bucket = (local.hour*60 + local.minute)//5
        series[room_id][bucket] = value
        counts[room_id] += 1
    interpolated, estimated = {}, {}
    valid = valid_local_buckets(day)
    for room_id, values in series.items():
        interpolated[room_id], estimated[room_id] = interpolate_gaps(values, valid)
    return {'floor': plan['floor'], 'day': day, 'step_minutes': 5, 'series': series, 'counts': counts,
            'interpolated_series': interpolated, 'estimated': estimated, 'max_gap_minutes': MAX_GAP_MINUTES,
            'invalid_minutes':[i*5 for i,exists in enumerate(valid) if not exists],
            'aggregation':'Dernière mesure du créneau de cinq minutes'}


def register_temperature_views(app, collection, auth_required):
    plans = load_plans()

    @expiring_cache(maxsize=16)
    def cached_day(floor, day):
        return daily_frame(collection, plans[floor], day)

    @expiring_cache(maxsize=4)
    def cached_days(floor):
        codes = [room['code'] for room in plans[floor]['rooms']]
        return [row['_id'] for row in collection.aggregate([
            {'$match': {'room': {'$in': codes}}},
            {'$group': {'_id': {'$dateToString': {'date': '$timestamp', 'format': '%Y-%m-%d', 'timezone': 'Europe/Paris'}}}},
            {'$sort': {'_id': 1}},
        ])]

    @app.get('/api/plans')
    @auth_required
    def temperature_plans():
        return jsonify(list(plans.values()))

    @app.get('/api/days/<int:floor>')
    @auth_required
    def temperature_days(floor):
        if floor not in plans:
            return jsonify(error='Étage inconnu.'), 404
        try:
            return jsonify(cached_days(floor))
        except PyMongoError:
            return jsonify(error='MongoDB local indisponible.'), 503

    @app.get('/api/day/<int:floor>/<day>')
    @auth_required
    def temperature_day(floor, day):
        if floor not in plans:
            return jsonify(error='Étage inconnu.'), 404
        try:
            day_bounds(day)
            return jsonify(cached_day(floor, day))
        except (ValueError, OverflowError):
            return jsonify(error='Date invalide.'), 400
        except PyMongoError:
            return jsonify(error='MongoDB local indisponible.'), 503
