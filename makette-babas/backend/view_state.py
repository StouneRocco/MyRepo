"""Une vue partagée et un seul pilote de projection pour tous les appareils."""
import datetime as dt
import threading
import time
from functools import lru_cache
from zoneinfo import ZoneInfo

from flask import jsonify, request
from temperature_day import load_plans, daily_frame, day_bounds


class SharedView:
    def __init__(self, collection, measurements, receiver, http):
        self.collection, self.measurements = collection, measurements
        self.receiver, self.http = receiver, http
        self.plans = load_plans()
        self.lock = threading.RLock()
        self.active = False
        self.error = None
        self.available = False
        self.last_tick = time.monotonic()
        self.rendered = -1
        self.state = dict(floor=3, day='2026-01-01', minute=0, playing=False,
                          heatmap=True, interpolate=True, roomId=None, revision=0)
        stored = collection.find_one({'_id':'shared'})
        if isinstance(stored, dict):
            try:
                self.state.update(self.validate({k:v for k,v in stored.items() if k in self.state and k!='revision'}))
            except (ValueError, TypeError):
                pass
            if type(stored.get('revision')) is int:
                self.state['revision'] = max(0, stored['revision'])+1
        self.frame = lru_cache(maxsize=16)(lambda floor, day: daily_frame(measurements, self.plans[floor], day))

    def validate(self, patch):
        if not isinstance(patch,dict) or not patch or set(patch)-set(self.state) or 'revision' in patch:
            raise ValueError('Réglages de consultation invalides.')
        state = {**self.state, **patch}
        if type(state['floor']) is not int or state['floor'] not in self.plans:
            raise ValueError('Étage inconnu.')
        day_bounds(state['day'])
        if type(state['minute']) is not int or not 0 <= state['minute'] <= 1435 or state['minute']%5:
            raise ValueError('Horaire invalide.')
        if any(type(state[key]) is not bool for key in ('playing','heatmap','interpolate')):
            raise ValueError('Option invalide.')
        if state['roomId'] is not None and state['roomId'] not in {r['id'] for r in self.plans[state['floor']]['rooms']}:
            raise ValueError('Salle inconnue pour cet étage.')
        return patch

    def snapshot(self):
        with self.lock:
            return {**self.state, 'available':self.available, 'projectionError':self.error}

    def update(self, patch):
        with self.lock:
            patch = self.validate(patch)
            self.state.update(patch)
            self.state['revision'] += 1
            self.active = True
            self.last_tick = time.monotonic()
            self.collection.replace_one({'_id':'shared'}, {'_id':'shared', **self.state}, upsert=True)
            return self.snapshot()

    def tick(self, now):
        with self.lock:
            if self.active and self.state['playing'] and now-self.last_tick >= .5:
                steps = int((now-self.last_tick)/.5)
                for _ in range(steps):
                    self.state['minute'] = 0 if self.state['minute']+15 >= 1440 else self.state['minute']+15
                self.state['revision'] += 1
                self.last_tick += steps*.5
                self.collection.replace_one({'_id':'shared'}, {'_id':'shared', **self.state}, upsert=True)

    def project(self, state):
        # N4 reste consultable ; la maquette physique représente N3.
        plan = self.plans[3]
        frame = self.frame(3,state['day'])
        series = frame['interpolated_series'] if state['interpolate'] else frame['series']
        bucket = state['minute']//5
        values = {r['code']:series[r['id']][bucket] for r in plan['rooms'] if series[r['id']][bucket] is not None}
        room = next((r for r in plan['rooms'] if r['id']==state['roomId']),None) if state['floor']==3 else None
        daily = [v for v in series[room['id']] if v is not None] if room else []
        context = dict(day=state['day'], minute=state['minute'], roomCode=room['code'] if room else None,
                       estimated=[r['code'] for r in plan['rooms'] if state['interpolate'] and frame['estimated'][r['id']][bucket]],
                       roomStats=dict(min=min(daily) if daily else None, max=max(daily) if daily else None,
                                      mean=sum(daily)/len(daily) if daily else None))
        response = self.http.post(self.receiver+'/project-temperatures',json={
            'temperatures':values if state['heatmap'] else {}, 'context':context,
            'roomId':room['id'] if room else None},timeout=3)
        response.raise_for_status()

    def run(self):
        while True:
            self.tick(time.monotonic())
            state = self.snapshot()
            if self.active and (state['revision']!=self.rendered or self.error):
                try:
                    self.project(state)
                    with self.lock:
                        self.available, self.error, self.rendered = True, None, state['revision']
                except Exception:
                    with self.lock:
                        self.available, self.error = False, 'Projection indisponible. Vérifie le récepteur.'
                    time.sleep(.5)
            time.sleep(.1)


def register_shared_view(app, view, auth):
    @app.route('/api/view-state', methods=['GET','POST'])
    @auth
    def view_state():
        try:
            if request.method=='POST':
                return jsonify(view.update(request.get_json(silent=True)))
            with view.lock:
                view.active = True
            return jsonify(view.snapshot())
        except (ValueError, TypeError):
            return jsonify(error='Réglages de consultation invalides.'),400
