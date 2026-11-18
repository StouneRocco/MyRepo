"""Consultation des badgeages de babas dans les plans et l'authentification Axel."""
import csv
import datetime as dt
import os
from collections import defaultdict
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

from flask import jsonify
from temperature_day import load_plans, day_bounds

PARIS = ZoneInfo('Europe/Paris')
CSV_PATH = Path(__file__).resolve().parent.parent/'ressources'/'badgeages.csv'


def parse_timestamp(value):
    try:
        timestamp=dt.datetime.fromisoformat((value or '').strip().replace('Z','+00:00'))
        if timestamp.tzinfo is None:
            local=timestamp.replace(tzinfo=PARIS)
            if local.astimezone(dt.timezone.utc).astimezone(PARIS).replace(tzinfo=None)!=timestamp:
                return None
            timestamp=local
        return timestamp.astimezone(PARIS)
    except (ValueError, TypeError, OverflowError):
        return None


class BadgeageData:
    def __init__(self, path, plans):
        self.path=Path(path)
        self.plans=plans
        self.code_to_floor={room['code']:floor for floor,plan in plans.items() for room in plan['rooms']}
        self._cached=lru_cache(maxsize=1)(self._load)

    def load(self):
        stat=self.path.stat()
        return self._cached(stat.st_mtime_ns,stat.st_size)

    def _load(self, modified, size):
        by_day=defaultdict(lambda:defaultdict(dict))
        with self.path.open(encoding='utf-8-sig',newline='') as stream:
            sample=stream.read(4096);stream.seek(0)
            reader=csv.DictReader(stream,dialect=csv.Sniffer().sniff(sample,delimiters=',;\t'))
            if not {'DateHeure','Code salle'}.issubset(reader.fieldnames or []):
                raise ValueError('Colonnes DateHeure et Code salle requises.')
            for row in reader:
                timestamp=parse_timestamp(row.get('DateHeure'))
                code=(row.get('Code salle') or '').strip()
                floor=self.code_to_floor.get(code)
                if timestamp is None or floor is None:
                    continue
                room=by_day[timestamp.date().isoformat()][floor].setdefault(code,{'total':0,'hours':[0]*24})
                room['total']+=1
                room['hours'][timestamp.hour]+=1
        return by_day

    def days(self,floor):
        return sorted(day for day,levels in self.load().items() if floor in levels)

    def day(self,floor,day):
        data=self.load()
        if day not in data or floor not in data[day]:
            return None
        measured=data[day][floor]
        rooms={room['code']:{'name':room['name'],**measured.get(room['code'],{'total':0,'hours':[0]*24})}
               for room in self.plans[floor]['rooms']}
        totals=[sum(room['hours'][hour] for room in rooms.values()) for hour in range(24)]
        return {'floor':floor,'day':day,'rooms':rooms,'hourTotals':totals,'total':sum(totals)}


def register_badgeage_views(app, auth_required, path=None):
    plans=load_plans()
    source=BadgeageData(path or os.getenv('BADGEAGES_FILE') or CSV_PATH,plans)

    def unavailable(error):
        app.logger.warning('Badgeages indisponibles : %s',type(error).__name__)
        return jsonify(error='Badgeages indisponibles. Vérifie le fichier ressources/badgeages.csv ou BADGEAGES_FILE.'),503

    @app.get('/api/badgeages/days/<int:floor>')
    @auth_required
    def badgeage_days(floor):
        if floor not in plans:
            return jsonify(error='Étage inconnu.'),404
        try:
            return jsonify(source.days(floor))
        except (OSError,ValueError,csv.Error,UnicodeError) as error:
            return unavailable(error)

    @app.get('/api/badgeages/day/<int:floor>/<day>')
    @auth_required
    def badgeage_day(floor,day):
        if floor not in plans:
            return jsonify(error='Étage inconnu.'),404
        try:
            day_bounds(day)
        except (ValueError,TypeError,OverflowError):
            return jsonify(error='Date attendue au format AAAA-MM-JJ.'),400
        try:
            frame=source.day(floor,day)
            if frame is None:
                return jsonify(error='Aucun badgeage disponible pour cet étage et cette journée.'),404
            return jsonify(frame)
        except (OSError,ValueError,csv.Error,UnicodeError) as error:
            return unavailable(error)
